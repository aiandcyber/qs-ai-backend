"""Configurable LLM client: OpenAI, Anthropic, or OpenAI-compatible local/frontier gateway."""
from __future__ import annotations

import logging
from typing import Any

from app import config

logger = logging.getLogger(__name__)


def provider_status() -> dict[str, Any]:
    return {
        "provider": config.MODEL_PROVIDER,
        "model_id": config.resolved_model_id(),
        "base_url": config.OPENAI_BASE_URL or None,
        "configured": config.llm_configured(),
        "max_tokens": config.MODEL_MAX_TOKENS,
    }


def chat(
    *,
    system: str,
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """
    Returns:
      {
        "content": str,
        "tool_calls": [{"id", "name", "arguments": dict}],
        "provider": str,
        "model_id": str,
        "used_llm": bool,
      }
    """
    provider = config.MODEL_PROVIDER
    if provider == "anthropic":
        return _chat_anthropic(system=system, messages=messages, tools=tools, temperature=temperature)
    if provider in {"openai", "openai_compatible"}:
        return _chat_openai(system=system, messages=messages, tools=tools, temperature=temperature)
    return {
        "content": "",
        "tool_calls": [],
        "provider": provider,
        "model_id": config.resolved_model_id(),
        "used_llm": False,
        "error": f"Unsupported MODEL_PROVIDER={provider}",
    }


def _chat_openai(
    *,
    system: str,
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None,
    temperature: float,
) -> dict[str, Any]:
    if not config.llm_configured():
        return _empty("openai")

    try:
        from openai import OpenAI

        kwargs: dict[str, Any] = {"api_key": config.OPENAI_API_KEY or "local"}
        if config.OPENAI_BASE_URL:
            kwargs["base_url"] = config.OPENAI_BASE_URL
        client = OpenAI(**kwargs)

        payload_messages = [{"role": "system", "content": system}, *messages]
        create_kwargs: dict[str, Any] = {
            "model": config.OPENAI_MODEL_ID,
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": config.OPENAI_MAX_TOKENS,
        }
        if tools:
            create_kwargs["tools"] = tools
            create_kwargs["tool_choice"] = "auto"

        completion = client.chat.completions.create(**create_kwargs)
        choice = completion.choices[0].message
        tool_calls = []
        for tc in choice.tool_calls or []:
            import json

            args: dict[str, Any] = {}
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:  # noqa: BLE001
                args = {"raw": tc.function.arguments}
            tool_calls.append(
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                }
            )
        return {
            "content": (choice.content or "").strip(),
            "tool_calls": tool_calls,
            "provider": config.MODEL_PROVIDER,
            "model_id": config.OPENAI_MODEL_ID,
            "used_llm": True,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI-compatible chat failed: %s", exc)
        return {**_empty("openai"), "error": str(exc)}


def _chat_anthropic(
    *,
    system: str,
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]] | None,
    temperature: float,
) -> dict[str, Any]:
    if not config.llm_configured():
        return _empty("anthropic")

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        anth_tools = None
        if tools:
            anth_tools = []
            for t in tools:
                fn = t.get("function") or {}
                anth_tools.append(
                    {
                        "name": fn.get("name"),
                        "description": fn.get("description", ""),
                        "input_schema": fn.get("parameters")
                        or {"type": "object", "properties": {}},
                    }
                )

        create_kwargs: dict[str, Any] = {
            "model": config.ANTHROPIC_MODEL_ID,
            "max_tokens": config.ANTHROPIC_MAX_TOKENS,
            "system": system,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "temperature": temperature,
        }
        if anth_tools:
            create_kwargs["tools"] = anth_tools

        message = client.messages.create(**create_kwargs)
        content_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for block in message.content:
            btype = getattr(block, "type", "")
            if btype == "text":
                content_parts.append(block.text)
            elif btype == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "arguments": dict(block.input or {}),
                    }
                )
        return {
            "content": "\n".join(content_parts).strip(),
            "tool_calls": tool_calls,
            "provider": "anthropic",
            "model_id": config.ANTHROPIC_MODEL_ID,
            "used_llm": True,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Anthropic chat failed: %s", exc)
        return {**_empty("anthropic"), "error": str(exc)}


def _empty(provider: str) -> dict[str, Any]:
    return {
        "content": "",
        "tool_calls": [],
        "provider": provider,
        "model_id": config.resolved_model_id(),
        "used_llm": False,
    }
