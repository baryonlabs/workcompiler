"""Which agent is talking to the proxy, and which conversation a request belongs to.

Every protocol (OpenAI Responses, Anthropic Messages, OpenAI chat/completions) is spoken by
several clients. Two pieces of context are derived per request:

* ``source_agent`` — a normalized name (``claude-code``, ``codex-cli``, ``cursor`` …) recorded on
  the TraceIR; the raw User-Agent / originator go to provenance.
* ``run_id`` — the conversation key that groups the turns of one agent session into one trace.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Mapping, Optional, Tuple

SOURCE_AGENTS = ("claude-code", "codex-cli", "cursor", "windsurf", "aider", "opencode", "continue", "gemini-cli",
                 "openai-client", "openai-responses-client", "anthropic-client", "zero-code-proxy")

_VERSION_RE = re.compile(r"[/ ]v?(\d+\.\d+(?:\.\d+)?)")
_SESSION_RE = re.compile(r"_session_([0-9a-fA-F-]{36})")


def _version_of(user_agent: str, prefix: str) -> Optional[str]:
    idx = user_agent.lower().find(prefix)
    if idx < 0:
        return None
    m = _VERSION_RE.search(user_agent[idx:])
    return m.group(1) if m else None


def detect_source_agent(headers: Mapping[str, str], protocol: str) -> Tuple[str, Optional[str]]:
    """(normalized agent name, version) from request headers; ``protocol`` decides the fallback."""
    override = headers.get("x-openworkcompiler-source-agent")
    if override:
        return override.strip().lower(), None
    originator = (headers.get("originator") or "").lower()
    ua = headers.get("user-agent") or ""
    ual = ua.lower()
    if originator.startswith("codex"):
        return "codex-cli", _version_of(ua, "codex")
    if ual.startswith("claude-cli") or headers.get("x-app") == "cli":
        return "claude-code", _version_of(ua, "claude-cli")
    for key, name in (("cursor", "cursor"), ("windsurf", "windsurf"), ("codeium", "windsurf"), ("aider", "aider"),
                      ("opencode", "opencode"), ("continue", "continue"), ("gemini", "gemini-cli"), ("codex", "codex-cli")):
        if key in ual:
            return name, _version_of(ua, key)
    return {"anthropic": "anthropic-client", "responses": "openai-responses-client"}.get(protocol, "openai-client"), None


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") in (None, "text", "input_text"))
    return ""


def _strip_reminders(text: str) -> str:
    return re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S).strip()


def conversation_fingerprint(payload: Dict[str, Any], agent_key: str = "") -> str:
    """Stable id for one conversation: hash of (agent key, system prompt, first user message)."""
    system = payload.get("system")
    if system is None:
        for msg in payload.get("messages") or []:
            if isinstance(msg, dict) and msg.get("role") == "system":
                system = msg.get("content"); break
    first_user = ""
    for msg in payload.get("messages") or []:
        if isinstance(msg, dict) and msg.get("role") == "user":
            first_user = _strip_reminders(_text_of(msg.get("content")))
            if first_user:
                break
    inp = payload.get("input")
    if not first_user and isinstance(inp, (str, list)):
        if isinstance(inp, str):
            first_user = inp
        else:
            for item in inp:
                if isinstance(item, dict) and item.get("role") == "user":
                    first_user = _text_of(item.get("content")); break
    h = hashlib.sha1()
    h.update(agent_key.encode()); h.update(b"|")
    h.update(hashlib.sha1(_text_of(system).encode()).hexdigest().encode()); h.update(b"|")
    h.update(first_user[:2000].encode())
    return "conv_" + h.hexdigest()[:16]


def claude_session_id(user_id: str) -> Optional[str]:
    """Claude Code encodes its session in ``metadata.user_id`` — as JSON
    (``{"device_id":…,"account_uuid":…,"session_id":…}``) in current versions, or as a
    ``user_<hash>_account_<uuid>_session_<uuid>`` string in older ones."""
    if not user_id:
        return None
    if user_id.lstrip().startswith("{"):
        try:
            data = json.loads(user_id)
            sid = data.get("session_id") if isinstance(data, dict) else None
            if sid:
                return str(sid)
        except Exception:
            pass
    m = _SESSION_RE.search(user_id)
    return m.group(1) if m else None


def resolve_run_id(headers: Mapping[str, str], payload: Dict[str, Any], protocol: str) -> Optional[str]:
    """Conversation key for grouping turns. Explicit header > client session ids > fingerprint."""
    for header in ("x-openworkcompiler-run-id", "session_id", "conversation_id"):
        value = headers.get(header)
        if value:
            return value
    if protocol == "responses":
        cache_key = payload.get("prompt_cache_key")
        if isinstance(cache_key, str) and cache_key:
            return cache_key
        return None
    if protocol == "anthropic":
        meta = payload.get("metadata") or {}
        user_id = str(meta.get("user_id") or "")
        session = claude_session_id(user_id)
        if session:
            return f"claude_{session}"
        return conversation_fingerprint(payload, _SESSION_RE.sub("", user_id))
    if protocol == "chat":
        user = payload.get("user")
        return conversation_fingerprint(payload, str(user or ""))
    return None
