"""Kimi K2.5 client over OpenRouter, with on-disk caching for dev iteration.

Why caching: during development and demo recording, identical prompts are
sent repeatedly. Without a cache, you burn rate-limit budget and waste
time waiting on the network. Cache key is a sha256 of model + messages,
stored under ~/.cache/storyboard/. Bypass with --no-cache or by passing
``use_cache=False``.

Why httpx: the project plan uses it; it works for both sync (here) and
async (future viewer streaming endpoint) without a rewrite.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"
KIMI_MODEL = os.environ.get("STORYBOARD_KIMI_MODEL", "moonshotai/kimi-k2.5")

CACHE_DIR = Path(os.environ.get("STORYBOARD_CACHE_DIR", str(Path.home() / ".cache" / "storyboard")))
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class KimiError(RuntimeError):
    """Raised when Kimi/OpenRouter returns something we cannot use."""


def _cache_key(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _cache_get(key: str) -> dict[str, Any] | None:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _cache_put(key: str, response: dict[str, Any]) -> None:
    path = CACHE_DIR / f"{key}.json"
    try:
        path.write_text(json.dumps(response, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        # Cache failures should never break the pipeline.
        print(f"[kimi_client] cache write failed: {exc}", file=sys.stderr)


def kimi_call(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    multimodal: bool = False,
    temperature: float | None = None,
    max_tokens: int = 4000,
    response_format: dict[str, Any] | None = None,
    reasoning: dict[str, Any] | None = None,
    provider: dict[str, Any] | None = None,
    timeout: float | None = None,
    use_cache: bool = True,
    retries: int = 2,
) -> dict[str, Any]:
    """Call Kimi K2.5 via OpenRouter. Returns the parsed JSON response.

    Multimodal mode lowers temperature (we want deterministic critique)
    and is otherwise identical at the wire level — vision blocks live
    inside ``messages`` already.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise KimiError(
            "OPENROUTER_API_KEY is not set. Get a key at https://openrouter.ai "
            "and run: export OPENROUTER_API_KEY=sk-or-..."
        )

    if temperature is None:
        temperature = 0.3 if multimodal else 0.7

    payload = {
        "model": model or KIMI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "provider": provider or _default_provider(response_format=response_format),
    }
    if response_format is not None:
        payload["response_format"] = response_format
    if reasoning is None:
        effort = os.environ.get("STORYBOARD_KIMI_REASONING_EFFORT", "none").strip()
        if effort:
            reasoning = {"effort": effort, "exclude": True}
    if reasoning is not None:
        payload["reasoning"] = reasoning

    cache_key = _cache_key(payload)
    if use_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Zhekinmaksim/storyboard",
        "X-Title": "storyboard skill for Hermes Agent",
    }

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            request_timeout = (
                timeout if timeout is not None
                else float(os.environ.get("STORYBOARD_KIMI_TIMEOUT", "12"))
            )
            http_timeout = httpx.Timeout(
                request_timeout,
                connect=5.0,
                read=request_timeout,
                write=5.0,
                pool=5.0,
            )
            with httpx.Client(timeout=http_timeout) as client:
                resp = client.post(OPENROUTER_BASE, headers=headers, json=payload)
                # 429 / 5xx → retry with backoff
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"transient {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                data = resp.json()
            if not _response_has_text(data):
                last_exc = KimiError(f"empty response content; got {_short_response(data)}")
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                raise last_exc
            if use_cache:
                _cache_put(cache_key, data)
            return data
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise KimiError(f"Kimi API error after {retries + 1} attempts: {exc}") from exc
        except httpx.RequestError as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise KimiError(f"Kimi network error: {exc}") from exc
    # Defensive — loop always returns or raises.
    raise KimiError(f"Unreachable: {last_exc}")


def extract_text(response: dict[str, Any]) -> str:
    """Pull the first message content out of an OpenRouter response."""
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise KimiError(f"unexpected response shape: {exc}; got {response}") from exc
    if not isinstance(content, str) or not content.strip():
        raise KimiError(f"empty response content; got {response}")
    return content


def _response_has_text(response: dict[str, Any]) -> bool:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return False
    return isinstance(content, str) and bool(content.strip())


def _short_response(response: dict[str, Any], limit: int = 500) -> str:
    text = json.dumps(response, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "…"


def _default_provider(*, response_format: dict[str, Any] | None = None) -> dict[str, Any]:
    provider: dict[str, Any] = {"sort": "latency", "allow_fallbacks": True}
    if response_format is not None:
        provider["require_parameters"] = True
    return provider


def kimi_text(prompt: str, system: str | None = None, **kwargs: Any) -> str:
    """Convenience: send one user prompt, return the response text."""
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return extract_text(kimi_call(messages, **kwargs))


def kimi_vision(
    prompt: str,
    image_bytes: bytes,
    *,
    system: str | None = None,
    image_mime: str = "image/png",
    **kwargs: Any,
) -> str:
    """Send a text prompt + one image, return the response text.

    Encodes the image as base64 inline. K2.5 on OpenRouter accepts
    data URLs in the image_url block.
    """
    b64 = base64.b64encode(image_bytes).decode("ascii")
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{b64}"}},
        ],
    })
    kwargs.setdefault("multimodal", True)
    return extract_text(kimi_call(messages, **kwargs))


__all__ = ["kimi_call", "kimi_text", "kimi_vision", "extract_text", "KimiError", "KIMI_MODEL"]
