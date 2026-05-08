"""OpenAI <-> Anthropic API bidirectional translator.

Translates OpenAI Chat Completions requests to Anthropic Messages API format
and maps Anthropic responses back to OpenAI format.
"""

import json
import time
import uuid
from typing import Any


def translate_request(body: dict) -> dict:
    """Translate OpenAI Chat Completions request to Anthropic Messages API format.

    Key mappings:
    - messages -> messages (with role and content translation)
    - max_tokens -> max_tokens
    - stop -> stop_sequences
    - temperature, top_p -> passthrough
    """
    # Map OpenAI model names to Claude models
    model = body.get("model", "gpt-4")
    model_mapping = {
        "gpt-4": "claude-3-5-sonnet-20240620",
        "gpt-4-turbo": "claude-3-5-sonnet-20240620",
        "gpt-5": "claude-3-5-sonnet-20240620",
        "gpt-5.1": "claude-3-5-sonnet-20240620",
        "gpt-5.4-mini": "claude-3-5-sonnet-20240620",
        "gpt-3.5-turbo": "claude-3-haiku-20240307",
    }
    anthropic_model = model_mapping.get(model, "claude-3-5-sonnet-20240620")
    translated: dict[str, Any] = {
        "model": anthropic_model,
    }

    # Messages -> Messages (with role mapping)
    messages = body.get("messages") or []
    
    # Extract system messages
    system_parts = [m.get("content") or "" for m in messages if m.get("role") == "system"]
    if system_parts:
        translated["system"] = "\n\n".join(system_parts)
    
    # Non-system messages
    non_system = [m for m in messages if m.get("role") != "system"]
    translated["messages"] = _translate_messages_to_anthropic(non_system)

    # Parameters
    if "max_tokens" in body:
        translated["max_tokens"] = body["max_tokens"]
    else:
        translated["max_tokens"] = 4096  # Anthropic default-ish

    if "temperature" in body:
        translated["temperature"] = body["temperature"]
    
    if "top_p" in body:
        translated["top_p"] = body["top_p"]
        
    if "stop" in body:
        stop = body["stop"]
        translated["stop_sequences"] = [stop] if isinstance(stop, str) else stop

    # Tools
    if body.get("tools"):
        translated["tools"] = _translate_tools_to_anthropic(body["tools"])

    return translated


def _translate_messages_to_anthropic(messages: list[dict]) -> list[dict]:
    """Translate OpenAI messages to Anthropic messages format."""
    result = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        
        # Anthropic only supports 'user' and 'assistant' in the messages array
        anthropic_role = "user" if role in ("user", "tool") else "assistant"
        
        # Tool results (role='tool') become a 'user' message with a 'tool_result' block
        if role == "tool":
            result.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.get("tool_call_id", ""),
                        "content": content if isinstance(content, str) else json.dumps(content),
                    }
                ]
            })
            continue

        # Assistant messages with tool_calls
        if role == "assistant" and msg.get("tool_calls"):
            content_blocks = []
            if content:
                content_blocks.append({"type": "text", "text": content})
            
            for tc in msg.get("tool_calls", []):
                func = tc.get("function", {})
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.get("id", ""),
                    "name": func.get("name", ""),
                    "input": json.loads(func.get("arguments", "{}")) if isinstance(func.get("arguments"), str) else func.get("arguments", {}),
                })
            
            result.append({"role": "assistant", "content": content_blocks})
            continue

        # Standard message
        result.append({"role": anthropic_role, "content": content})

    # Anthropic requires messages to alternate user/assistant and start with user.
    # We might need to merge or insert placeholders if the source doesn't follow this.
    return _fix_alternation(result)


def _fix_alternation(messages: list[dict]) -> list[dict]:
    """Ensure messages alternate between user and assistant."""
    if not messages:
        return messages
        
    fixed = []
    for msg in messages:
        if not fixed:
            if msg["role"] != "user":
                # Prefix with empty user message if it starts with assistant
                fixed.append({"role": "user", "content": "..."})
            fixed.append(msg)
        else:
            if msg["role"] == fixed[-1]["role"]:
                # Merge consecutive messages of the same role
                last_content = fixed[-1]["content"]
                new_content = msg["content"]
                
                # Normalize content to list of blocks
                def normalize(c):
                    if isinstance(c, str): return [{"type": "text", "text": c}]
                    if isinstance(c, list): return c
                    return []

                merged = normalize(last_content) + normalize(new_content)
                fixed[-1]["content"] = merged
            else:
                fixed.append(msg)
    return fixed


def _translate_tools_to_anthropic(tools: list[dict]) -> list[dict]:
    """Translate OpenAI tools to Anthropic tools format."""
    result = []
    for tool in tools:
        if tool.get("type") == "function":
            func = tool.get("function", {})
            result.append({
                "name": func.get("name", ""),
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {}),
            })
    return result


def translate_response(anthropic_resp: dict, model: str) -> dict:
    """Translate Anthropic Messages response to OpenAI Chat Completions format."""
    resp_id = anthropic_resp.get("id", f"msg_{uuid.uuid4()}")
    
    text_content = ""
    tool_calls = []
    
    for block in anthropic_resp.get("content", []):
        if block.get("type") == "text":
            text_content += block.get("text", "")
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block.get("id", ""),
                "type": "function",
                "function": {
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {})),
                }
            })

    message: dict[str, Any] = {
        "role": "assistant",
        "content": text_content if text_content else None,
    }
    
    if tool_calls:
        message["tool_calls"] = tool_calls

    finish_reason = "stop"
    if anthropic_resp.get("stop_reason") == "tool_use":
        finish_reason = "tool_calls"
    elif anthropic_resp.get("stop_reason") == "max_tokens":
        finish_reason = "length"

    usage = anthropic_resp.get("usage", {})
    
    return {
        "id": f"chatcmpl-{resp_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        }
    }


def translate_error(error_body: dict, status_code: int) -> tuple[dict, int]:
    """Translate Anthropic error to OpenAI error format."""
    error = error_body.get("error", {})
    return {
        "error": {
            "message": error.get("message", "Unknown Anthropic error"),
            "type": error.get("type", "api_error"),
            "code": str(status_code),
        }
    }, status_code


def translate_cli_response(text: str, model: str) -> dict:
    """Translate Claude CLI text response to OpenAI Chat Completions format."""
    resp_id = f"msg_{uuid.uuid4()}"

    return {
        "id": f"chatcmpl-{resp_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            # CLI doesn't provide token counts, estimate based on text length
            "prompt_tokens": 0,  # Unknown, caller can estimate
            "completion_tokens": len(text.split()),  # Rough word count
            "total_tokens": len(text.split()),
        }
    }


def translate_responses_output(text: str, model: str) -> dict:
    """Translate Claude CLI text response to OpenAI Responses API format."""
    resp_id = f"resp_{uuid.uuid4()}"

    return {
        "id": resp_id,
        "object": "response",
        "created_at": int(time.time()),
        "model": model,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 0,  # Unknown
            "output_tokens": len(text.split()),  # Rough estimate
            "total_tokens": len(text.split()),
        }
    }
