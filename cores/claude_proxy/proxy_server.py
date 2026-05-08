"""Claude OAuth Proxy Server using Claude Code CLI.

Translates OpenAI Chat Completions requests and routes them through
Claude Code CLI subprocess with OAuth authentication.
"""

import json
import logging
import asyncio
import subprocess
import tempfile
import os
from pathlib import Path

from aiohttp import web

from . import api_translator
from .constants import DEFAULT_PROXY_PORT

logger = logging.getLogger(__name__)

_cli_path: str | None = None


def find_claude_cli() -> str:
    """Find Claude Code CLI executable."""
    global _cli_path
    if _cli_path:
        return _cli_path

    # Common locations
    candidates = [
        "claude",
        str(Path.home() / ".local/bin/claude"),
        "/usr/local/bin/claude",
        "/usr/bin/claude",
    ]

    for cmd in candidates:
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and "Claude Code" in result.stdout:
                _cli_path = cmd
                logger.info("Found Claude CLI: %s", cmd)
                return cmd
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue

    raise RuntimeError("Claude Code CLI not found. Please install: npm install -g @anthropic-ai/claude-code")


def create_app() -> web.Application:
    """Create the aiohttp proxy application."""
    app = web.Application()
    app.router.add_post("/v1/chat/completions", handle_chat_completions)
    app.router.add_post("/v1/responses", handle_responses)
    app.router.add_get("/health", handle_health)
    return app


async def handle_responses(request: web.Request) -> web.Response:
    """Handle OpenAI Responses API requests (translate to chat completions)."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}},
            status=400,
        )

    # Responses API uses 'input' instead of 'messages'
    input_data = body.get("input", [])
    model = body.get("model", "claude-3-5-sonnet-20241022")

    # Convert Responses API input format to chat messages
    messages = []
    for item in input_data or []:
        if isinstance(item, dict):
            role = item.get("role", "user")
            content = item.get("content", "")
            messages.append({"role": role, "content": content})

    if not messages:
        # Fallback: treat input as a single user message
        messages = [{"role": "user", "content": str(input_data)}]

    # Build prompt from messages
    prompt = build_prompt_from_messages(messages)

    logger.debug("Responses API request: model=%s, messages=%d, prompt_length=%d",
                 model, len(messages), len(prompt))

    try:
        # Call Claude CLI
        response_text = await call_claude_cli(
            prompt=prompt,
            model=map_model_name(model),
            max_tokens=body.get("max_output_tokens") or body.get("max_tokens"),
        )

        # Translate to OpenAI Responses API format
        result = api_translator.translate_responses_output(
            response_text,
            model,
        )

        return web.json_response(result)

    except subprocess.TimeoutExpired:
        logger.error("Claude CLI timed out")
        return web.json_response(
            {"error": {"message": "Request timeout", "type": "timeout"}},
            status=504,
        )
    except Exception as e:
        logger.error("Claude CLI call failed: %s", e)
        return web.json_response(
            {"error": {"message": f"Claude CLI error: {e}", "type": "server_error"}},
            status=502,
        )


async def handle_health(request: web.Request) -> web.Response:
    """Health check endpoint."""
    try:
        cli_path = find_claude_cli()
        return web.json_response({
            "status": "ok",
            "claude_cli": cli_path,
            "claude_cli_found": True
        })
    except RuntimeError as e:
        return web.json_response({
            "status": "error",
            "error": str(e),
            "claude_cli_found": False
        }, status=503)


async def handle_chat_completions(request: web.Request) -> web.Response:
    """Translate and proxy a Chat Completions request to Claude Code CLI."""
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}},
            status=400,
        )

    original_model = body.get("model", "claude-3-5-sonnet-20241022")
    messages = body.get("messages", [])
    temperature = body.get("temperature", 1.0)
    max_tokens = body.get("max_tokens")

    if not messages:
        return web.json_response(
            {"error": {"message": "No messages provided", "type": "invalid_request_error"}},
            status=400,
        )

    # Build prompt from messages
    prompt = build_prompt_from_messages(messages)

    logger.debug("Proxy request: model=%s, messages=%d, prompt_length=%d",
                 original_model, len(messages), len(prompt))

    try:
        # Call Claude CLI
        response_text = await call_claude_cli(
            prompt=prompt,
            model=map_model_name(original_model),
            max_tokens=max_tokens,
        )

        # Translate to OpenAI format
        result = api_translator.translate_cli_response(
            response_text,
            original_model,
        )

        return web.json_response(result)

    except subprocess.TimeoutExpired:
        logger.error("Claude CLI timed out")
        return web.json_response(
            {"error": {"message": "Request timeout", "type": "timeout"}},
            status=504,
        )
    except Exception as e:
        logger.error("Claude CLI call failed: %s", e)
        return web.json_response(
            {"error": {"message": f"Claude CLI error: {e}", "type": "server_error"}},
            status=502,
        )


def build_prompt_from_messages(messages: list) -> str:
    """Convert OpenAI message format to simple text prompt for CLI."""
    parts = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if isinstance(content, list):
            # Handle multimodal content (text only for now)
            text_parts = []
            for block in content:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            content = "\n".join(text_parts)

        if role == "system":
            parts.append(f"System: {content}")
        elif role == "user":
            parts.append(f"User: {content}")
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
        else:
            parts.append(f"{role}: {content}")

    return "\n\n".join(parts)


def map_model_name(model: str) -> str:
    """Map OpenAI-style or Anthropic model names to Claude CLI aliases."""
    model_lower = model.lower()
    
    # Map to CLI aliases: sonnet, opus, haiku
    if 'opus' in model_lower:
        return 'opus'
    elif 'haiku' in model_lower:
        return 'haiku'
    else:
        # Default to 'sonnet' for any sonnet variant or unknown models
        return 'sonnet'


async def call_claude_cli(
    prompt: str,
    model: str,
    max_tokens: int | None = None,
    timeout: int = 300,
) -> str:
    """Call Claude Code CLI with the given prompt."""
    cli_path = find_claude_cli()

    # Build command arguments
    cmd = [cli_path, "-p", prompt]

    # Add model if specified
    if model and model != "claude-3-5-sonnet-20241022":
        cmd.extend(["--model", model])

    logger.debug("Executing: %s", " ".join(cmd))

    # Run in subprocess
    # Remove plugin-related env vars that cause issues
    clean_env = {**os.environ}
    clean_env.pop("CLAUDE_PLUGIN_ROOT", None)
    clean_env.pop("CLAUDE_PLUGINS", None)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=clean_env,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise subprocess.TimeoutExpired(cmd, timeout)

    if proc.returncode != 0:
        stderr_text = stderr.decode("utf-8", errors="replace")
        logger.error("Claude CLI error (exit %d): %s", proc.returncode, stderr_text[:500])
        raise RuntimeError(f"Claude CLI failed: {stderr_text[:200]}")

    response = stdout.decode("utf-8", errors="replace")
    logger.debug("Claude CLI response length: %d", len(response))

    return response
