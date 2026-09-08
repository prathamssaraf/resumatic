"""
LLM client with structured JSON output.
Supports local LM Studio (Gemma 4) and remote K2 Think V2.
Every resume-builder call goes through here.
"""
from __future__ import annotations
import json
import re
import httpx

# ── Provider config (set LLM_BASE_URL and LLM_MODEL in .env) ──────────────────
import config as _cfg
API_KEY  = "lm-studio"
BASE_URL = _cfg.LLM_BASE_URL.rstrip("/") + "/chat/completions"
MODEL    = _cfg.LLM_MODEL


def _strip_think(text: str) -> str:
    """Remove K2 reasoning blocks. K2 sometimes omits <think> but always closes with </think>."""
    # Standard <think>...</think> block
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # K2 variant: reasoning prose followed by bare </think> (no opening tag)
    # Only apply if there's actual content after the closing tag
    if "</think>" in text:
        after = text[text.index("</think>") + len("</think>"):].strip()
        if after:
            text = after
    return text.strip()


def _extract_json(text: str, prefer_dict: bool = True) -> str:
    """
    Pull the last complete JSON object or array from a response.
    K2 Think outputs reasoning prose BEFORE the JSON.
    When prefer_dict=True, prefers { } objects over [ ] arrays.
    """
    import json as _json

    # Try a fenced code block first
    m = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if m:
        return m.group(1)

    # Collect all candidate start positions by type
    obj_positions = [i for i, ch in enumerate(text) if ch == "{"]
    arr_positions = [i for i, ch in enumerate(text) if ch == "["]

    def _try_positions(positions: list[int], end_char: str) -> str | None:
        for pos in reversed(positions):
            candidate = text[pos:]
            end = candidate.rfind(end_char)
            while end >= 0:
                snippet = candidate[:end + 1]
                try:
                    parsed = _json.loads(snippet)
                    # For dicts: must have at least 2 keys (sanity check)
                    if isinstance(parsed, dict) and len(parsed) >= 2:
                        return snippet
                    if isinstance(parsed, list) and len(parsed) >= 1:
                        return snippet
                except _json.JSONDecodeError:
                    pass
                end = candidate.rfind(end_char, 0, end)
        return None

    # Try dicts first if preferred
    if prefer_dict:
        result = _try_positions(obj_positions, "}")
        if result:
            return result
        result = _try_positions(arr_positions, "]")
        if result:
            return result
    else:
        result = _try_positions(arr_positions, "]")
        if result:
            return result
        result = _try_positions(obj_positions, "}")
        if result:
            return result

    return text


def call(
    system: str,
    user: str,
    *,
    max_tokens: int = 131072,
    temperature: float = 0.3,
    retries: int = 3,
) -> str:
    """Raw K2 call — returns the assistant text (think blocks stripped). Retries on 5xx."""
    import time
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = httpx.post(BASE_URL, json=payload, headers=headers, timeout=180)
            if resp.status_code in (502, 503, 504) and attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            return _strip_think(raw)
        except (httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
            continue
    raise RuntimeError(f"K2 API failed after {retries} attempts: {last_err}")


def call_json(
    system: str,
    user: str,
    *,
    max_tokens: int = 131072,
    temperature: float = 0.25,
    prefer_dict: bool = True,
    retries: int = 3,
) -> dict | list:
    """
    LLM call that returns parsed JSON. Retries the entire call (new model
    response) on JSON parse failure — local models sometimes emit malformed
    JSON and a fresh sample usually parses. Raises ValueError after `retries`
    consecutive parse failures; raises RuntimeError if the underlying call
    times out. No silent fallbacks.
    """
    system_with_json = (
        system.rstrip()
        + "\n\nCRITICAL: Your ENTIRE response must be valid JSON only. "
        "No prose, no markdown, no code fences. Start with { or [ and end with } or ]."
    )
    last_err: Exception | None = None
    raw = ""
    for attempt in range(retries):
        raw = call(system_with_json, user, max_tokens=max_tokens, temperature=temperature)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            try:
                extracted = _extract_json(raw, prefer_dict=prefer_dict)
                parsed = json.loads(extracted)
            except json.JSONDecodeError as exc:
                last_err = exc
                continue  # retry the LLM call

        # If we expected a dict but got a list, try to find a dict candidate.
        # If we can't, raise — callers will .get() on the result and crash
        # later in a much less useful place than here.
        if prefer_dict and isinstance(parsed, list):
            dict_extracted = _extract_json(raw, prefer_dict=True)
            try:
                candidate = json.loads(dict_extracted)
                if isinstance(candidate, dict):
                    return candidate
            except (json.JSONDecodeError, ValueError):
                pass
            raise ValueError(
                f"LLM returned a list but caller asked for a dict "
                f"(no dict candidate in raw output, len={len(raw)})"
            )

        return parsed

    raise ValueError(
        f"LLM JSON parse failed after {retries} attempts (last len={len(raw)}): "
        f"{last_err}\nRaw tail: {raw[-300:]!r}"
    )


def call_json_list(system: str, user: str, **kwargs) -> list:
    """
    Wrapper that always returns a list. Propagates ValueError/RuntimeError
    on failure — callers should let the build fail loud, not silently use [].
    """
    result = call_json(system, user, prefer_dict=False, **kwargs)
    if isinstance(result, dict):
        for key in ("bullets", "paragraphs", "items", "categories"):
            if key in result:
                return result[key]
        return list(result.values())
    if not isinstance(result, list):
        raise ValueError(f"Expected list from LLM, got {type(result).__name__}")
    return result
