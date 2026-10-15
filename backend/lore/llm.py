"""LLM provider chain: Groq is primary, OpenAI is the fallback.

Both speak the OpenAI chat-completions protocol (Groq via its OpenAI-compatible endpoint), so one client
class and one message format cover both. A request is tried on each configured provider in order; any
error (rate limit, outage, bad model, malformed tool call) moves on to the next one. Messages stay in the
OpenAI format throughout, so a tool-use loop can even switch provider between turns.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache

from openai import OpenAI

from . import config

log = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


@dataclass
class Provider:
    name: str
    client: OpenAI
    agent_model: str
    extract_model: str


@lru_cache(maxsize=1)
def providers() -> list[Provider]:
    out: list[Provider] = []
    if config.GROQ_API_KEY:
        out.append(Provider("groq", OpenAI(api_key=config.GROQ_API_KEY, base_url=GROQ_BASE_URL, timeout=60, max_retries=1),
                            config.GROQ_AGENT_MODEL, config.GROQ_EXTRACT_MODEL))
    if config.OPENAI_API_KEY:
        out.append(Provider("openai", OpenAI(api_key=config.OPENAI_API_KEY, timeout=60, max_retries=1),
                            config.OPENAI_AGENT_MODEL, config.OPENAI_EXTRACT_MODEL))
    return out


def available() -> bool:
    return bool(providers())


def status() -> dict:
    ps = providers()
    return {"primary": ps[0].name if ps else None, "fallback": ps[1].name if len(ps) > 1 else None,
            "model": ps[0].agent_model if ps else None}


def chat(messages: list[dict], *, tools: list[dict] | None = None, json_mode: bool = False,
         kind: str = "agent", max_tokens: int = 4000) -> tuple[object, str]:
    """Returns (assistant message, provider name). Raises RuntimeError if every provider failed."""
    errors: list[str] = []
    for p in providers():
        kwargs: dict = {
            "model": p.agent_model if kind == "agent" else p.extract_model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = p.client.chat.completions.create(**kwargs)
            choice = resp.choices[0]
            if choice.finish_reason == "content_filter":
                raise RuntimeError("content filtered")
            return choice.message, p.name
        except Exception as e:  # fall through to the next provider
            log.warning("LLM provider %s failed: %s", p.name, e)
            errors.append(f"{p.name}: {type(e).__name__}: {e}")
    raise RuntimeError("no LLM provider succeeded: " + " | ".join(errors) if errors else "no LLM provider configured")


def assistant_message(msg) -> dict:
    """Portable assistant turn (drops provider-specific extras such as 'reasoning')."""
    out: dict = {"role": "assistant", "content": msg.content or ""}
    if getattr(msg, "tool_calls", None):
        out["tool_calls"] = [{"id": t.id, "type": "function",
                              "function": {"name": t.function.name, "arguments": t.function.arguments or "{}"}}
                             for t in msg.tool_calls]
    return out


def parse_args(raw: str | None) -> dict:
    try:
        v = json.loads(raw or "{}")
        return v if isinstance(v, dict) else {}
    except json.JSONDecodeError:
        return {}
