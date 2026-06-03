"""ChatGPT OAuth Proxy Server.

Lightweight aiohttp web server that translates Chat Completions API
requests to ChatGPT Responses API format and back.
"""

import asyncio
import json
import logging

import aiohttp
from aiohttp import web

from . import api_translator
from .constants import CHATGPT_RESPONSES_URL
from .token_manager import TokenManager

logger = logging.getLogger(__name__)

_token_manager: TokenManager | None = None

# ChatGPT upstream timeout per attempt (seconds).
# Logs show successful responses complete within ~130s at most.
# 120s catches dropped requests early; up to PROXY_MAX_RETRIES retries follow.
_UPSTREAM_TIMEOUT = 120
_PROXY_MAX_RETRIES = 2
_RETRY_DELAY = 1.0  # seconds between retries

# Serialize upstream requests to ChatGPT.
# ChatGPT's unofficial Codex endpoint drops requests when multiple agents
# fire concurrently (e.g. telegram_summary_optimizer + evaluator).
# A semaphore of 1 queues them instead of racing → eliminates drop-induced timeouts.
_upstream_semaphore = asyncio.Semaphore(1)


def create_app(token_manager: TokenManager) -> web.Application:
    """Create the aiohttp proxy application."""
    global _token_manager
    _token_manager = token_manager

    app = web.Application()
    app.router.add_post("/v1/chat/completions", handle_chat_completions)
    app.router.add_post("/v1/responses", handle_responses)
    app.router.add_get("/health", handle_health)
    return app


async def handle_health(request: web.Request) -> web.Response:
    """Health check endpoint."""
    token_valid = False
    if _token_manager:
        try:
            await _token_manager.get_token()
            token_valid = True
        except Exception:
            pass

    return web.json_response({"status": "ok", "token_valid": token_valid})


async def handle_responses(request: web.Request) -> web.Response:
    """Proxy a Responses API request directly to the ChatGPT Responses API.

    Unlike handle_chat_completions, the request is already in Responses API
    format so no translation is needed — only model mapping and mandatory
    ChatGPT backend fields are applied. The response is returned as-is.
    """
    if not _token_manager:
        return web.json_response(
            {"error": {"message": "Token manager not initialized", "type": "server_error"}},
            status=500,
        )

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}},
            status=400,
        )

    original_model = body.get("model", "gpt-4o")

    try:
        normalized = api_translator.normalize_responses_request(body)
    except Exception as e:
        logger.error("Responses request normalization failed: %s", e)
        return web.json_response(
            {"error": {"message": f"Request normalization error: {e}", "type": "server_error"}},
            status=500,
        )

    try:
        token = await _token_manager.get_token()
        account_id = await _token_manager.get_account_id()
    except Exception as e:
        logger.error("Token retrieval failed: %s", e)
        return web.json_response(
            {"error": {"message": str(e), "type": "authentication_error"}},
            status=401,
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "responses=experimental",
        "accept": "text/event-stream",
    }
    if account_id:
        headers["chatgpt-account-id"] = account_id

    logger.debug("Responses proxy: model=%s -> %s", original_model, normalized.get("model"))

    api_response = None
    last_error: Exception | None = None

    async with _upstream_semaphore:
        for attempt in range(1, _PROXY_MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        CHATGPT_RESPONSES_URL,
                        json=normalized,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=_UPSTREAM_TIMEOUT),
                    ) as resp:
                        raw_body = await resp.text()

                        if resp.status != 200:
                            try:
                                error_body = json.loads(raw_body)
                            except json.JSONDecodeError:
                                error_body = {"error": {"message": raw_body}}

                            error_code = error_body.get("error", {}).get("code", "")
                            if resp.status == 401 and error_code == "token_invalidated" and attempt < _PROXY_MAX_RETRIES:
                                logger.warning("token_invalidated — forcing token refresh and retrying (attempt %d)...", attempt)
                                try:
                                    token = await _token_manager.force_refresh()
                                    headers["Authorization"] = f"Bearer {token}"
                                    continue
                                except Exception as refresh_err:
                                    logger.error("Token force-refresh failed: %s", refresh_err)

                            translated_error, status = api_translator.translate_error(error_body, resp.status)
                            logger.warning("ChatGPT API error (%d): %s", resp.status, raw_body[:200])
                            return web.json_response(translated_error, status=status)

                        content_type = resp.headers.get("Content-Type", "")
                        is_sse = "text/event-stream" in content_type or raw_body.lstrip().startswith("event:")
                        if is_sse:
                            try:
                                api_response = api_translator.collect_sse_to_response(raw_body)
                            except ValueError as e:
                                logger.error("SSE parsing failed: %s (body[:200]: %s)", e, raw_body[:200])
                                return web.json_response(
                                    {"error": {"message": f"SSE parsing error: {e}", "type": "server_error"}},
                                    status=502,
                                )
                        else:
                            try:
                                api_response = json.loads(raw_body)
                            except json.JSONDecodeError:
                                logger.error("Invalid JSON from ChatGPT (body[:200]: %s)", raw_body[:200])
                                return web.json_response(
                                    {"error": {"message": "Invalid response from upstream", "type": "server_error"}},
                                    status=502,
                                )
                break

            except (aiohttp.ClientError, TimeoutError) as e:
                last_error = e
                if attempt < _PROXY_MAX_RETRIES:
                    logger.warning(
                        "ChatGPT upstream timeout/error on attempt %d/%d (%s). Retrying in %.1fs...",
                        attempt, _PROXY_MAX_RETRIES, e, _RETRY_DELAY,
                    )
                    await asyncio.sleep(_RETRY_DELAY)
                else:
                    logger.error("ChatGPT upstream failed after %d attempts: %s", _PROXY_MAX_RETRIES, e)

    if api_response is None:
        return web.json_response(
            {"error": {"message": f"Upstream connection error: {last_error}", "type": "server_error"}},
            status=502,
        )

    return web.json_response(api_response)


async def handle_chat_completions(request: web.Request) -> web.Response:
    """Translate and proxy a Chat Completions request to ChatGPT Responses API."""
    if not _token_manager:
        return web.json_response(
            {"error": {"message": "Token manager not initialized", "type": "server_error"}},
            status=500,
        )

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}},
            status=400,
        )

    original_model = body.get("model", "gpt-4o")

    # Translate request
    try:
        translated_request = api_translator.translate_request(body)
    except Exception as e:
        msg_types = [(m.get("role"), type(m.get("content")).__name__, type(m.get("tool_calls")).__name__) for m in (body.get("messages") or [])]
        logger.error("Request translation failed: %s | messages: %s", e, msg_types)
        return web.json_response(
            {"error": {"message": f"Request translation error: {e}", "type": "server_error"}},
            status=500,
        )

    # Get OAuth token
    try:
        token = await _token_manager.get_token()
        account_id = await _token_manager.get_account_id()
    except Exception as e:
        logger.error("Token retrieval failed: %s", e)
        return web.json_response(
            {"error": {"message": str(e), "type": "authentication_error"}},
            status=401,
        )

    # Forward to ChatGPT
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "responses=experimental",
        "accept": "text/event-stream",
    }
    if account_id:
        headers["chatgpt-account-id"] = account_id

    logger.debug("Proxy request: model=%s -> %s, tools=%d, messages=%d",
                 original_model, translated_request.get("model"),
                 len(body.get("tools") or []), len(body.get("messages") or []))

    api_response = None
    last_error: Exception | None = None

    async with _upstream_semaphore:
        for attempt in range(1, _PROXY_MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        CHATGPT_RESPONSES_URL,
                        json=translated_request,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=_UPSTREAM_TIMEOUT),
                    ) as resp:
                        raw_body = await resp.text()

                        if resp.status != 200:
                            try:
                                error_body = json.loads(raw_body)
                            except json.JSONDecodeError:
                                error_body = {"error": {"message": raw_body}}

                            error_code = error_body.get("error", {}).get("code", "")
                            if resp.status == 401 and error_code == "token_invalidated" and attempt < _PROXY_MAX_RETRIES:
                                logger.warning("token_invalidated — forcing token refresh and retrying (attempt %d)...", attempt)
                                try:
                                    token = await _token_manager.force_refresh()
                                    headers["Authorization"] = f"Bearer {token}"
                                    continue
                                except Exception as refresh_err:
                                    logger.error("Token force-refresh failed: %s", refresh_err)

                            translated_error, status = api_translator.translate_error(error_body, resp.status)
                            logger.warning("ChatGPT API error (%d): %s", resp.status, raw_body[:200])
                            return web.json_response(translated_error, status=status)

                        # Parse response (may be SSE or JSON)
                        content_type = resp.headers.get("Content-Type", "")
                        is_sse = "text/event-stream" in content_type or raw_body.lstrip().startswith("event:")
                        if is_sse:
                            try:
                                api_response = api_translator.collect_sse_to_response(raw_body)
                                logger.debug("SSE parsed: output_items=%s status=%s",
                                             [i.get("type") for i in api_response.get("output", [])],
                                             api_response.get("status"))
                            except ValueError as e:
                                logger.error("SSE parsing failed: %s (Content-Type: %s, body[:200]: %s)", e, content_type, raw_body[:200])
                                return web.json_response(
                                    {"error": {"message": f"SSE parsing error: {e}", "type": "server_error"}},
                                    status=502,
                                )
                        else:
                            try:
                                api_response = json.loads(raw_body)
                            except json.JSONDecodeError:
                                logger.error("Invalid JSON response from ChatGPT (Content-Type: %s, body[:200]: %s)", content_type, raw_body[:200])
                                return web.json_response(
                                    {"error": {"message": "Invalid response from upstream", "type": "server_error"}},
                                    status=502,
                                )
                break  # success — exit retry loop

            except (aiohttp.ClientError, TimeoutError) as e:
                last_error = e
                if attempt < _PROXY_MAX_RETRIES:
                    logger.warning(
                        "ChatGPT upstream timeout/error on attempt %d/%d (%s). Retrying in %.1fs...",
                        attempt, _PROXY_MAX_RETRIES, e, _RETRY_DELAY,
                    )
                    await asyncio.sleep(_RETRY_DELAY)
                else:
                    logger.error("ChatGPT upstream failed after %d attempts: %s", _PROXY_MAX_RETRIES, e)

    if api_response is None:
        return web.json_response(
            {"error": {"message": f"Upstream connection error: {last_error}", "type": "server_error"}},
            status=502,
        )

    # Translate response back to Chat Completions format
    try:
        result = api_translator.translate_response(api_response, original_model)
    except Exception as e:
        logger.error("Response translation failed: %s", e)
        return web.json_response(
            {"error": {"message": f"Response translation error: {e}", "type": "server_error"}},
            status=500,
        )

    return web.json_response(result)
