"""OpenWorkCompiler Zero-Code Agent Proxy — trajectory interceptor.

Reconstructs agent turns from three wire protocols into canonical TraceIR steps:

* OpenAI Responses API (``/v1/responses`` — Codex CLI, Agents SDK)
* Anthropic Messages API (``/v1/messages`` — Claude Code and other Anthropic clients)
* OpenAI chat/completions (``/v1/chat/completions`` — Cursor, opencode, Aider, Continue …)

Whatever the protocol, every step ends up with the same shape: an action name
(``shell_<prog>`` / ``write_<file>`` / ``read_<file>`` / ``respond`` …), ``input`` carrying a
replayable ``cmd``/``cmds`` or ``patch``, ``output`` with the assistant text and ``tool_calls``,
the tool's actual result attached as ``tool_result`` once the client feeds it back, and the
model / token / cache accounting used by the benchmark ledger.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

from adapters.proxy.tools import NormalizedCall, ToolKind, merge_calls, normalize_call
from core.work_ir import Provenance, TraceIR, TraceStep, TraceResult, TraceStatus, TokenUsage, normalize_tool_output


# Tool names that Codex CLI / OpenAI agents use for running shell commands (kept for callers).
SHELL_TOOL_NAMES = {"shell", "shell_command", "exec_command", "local_shell", "container.exec", "exec"}

# Codex "code mode" wraps shell calls in a JS snippet, e.g.
#   tools.exec_command({cmd:"ls -la", workdir:"/repo"})
#   tools.exec_command({ "cmd": 'git status' })
#   tools.exec_command({cmd: `python3 -m x`})
_CODE_MODE_CMD_RE = re.compile(
    r'exec_command\s*\(\s*\{.*?["\']?\bcmd["\']?\s*:\s*'
    r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`)',
    re.S,
)
_CODE_MODE_PATCH_RE = re.compile(r'("\*\*\* Begin Patch(?:[^"\\]|\\.)*")', re.S)
_PATCH_FILE_RE = re.compile(r"^\*\*\* (Add|Update|Delete) File: (.+)$", re.M)
_SYSTEM_REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
_LINE_NUMBER_RE = re.compile(r"^\s*\d+(?:→|\t)", re.M)   # Claude Code Read: "   12→line" (docs) / "12\tline" (2.1.x)


def _code_mode_commands(snippet: str) -> List[str]:
    """Extract every ``cmd`` string from a Codex code-mode snippet (one snippet may batch several)."""
    commands: List[str] = []
    for match in _CODE_MODE_CMD_RE.finditer(snippet):
        literal = match.group(1)
        quote, body = literal[0], literal[1:-1]
        if quote == '"':
            try:
                commands.append(json.loads(literal))
                continue
            except Exception:
                commands.append(body)
                continue
        commands.append(body.replace("\\" + quote, quote).replace("\\n", "\n"))
    return commands


def _code_mode_command(snippet: str) -> Optional[str]:
    """First ``cmd`` of a Codex code-mode ``exec_command`` call, if any."""
    commands = _code_mode_commands(snippet)
    return commands[0] if commands else None


def _code_mode_patch(snippet: str) -> Optional[str]:
    """Return the apply_patch text embedded in a Codex code-mode snippet, if any."""
    if "apply_patch" not in snippet:
        return None
    match = _CODE_MODE_PATCH_RE.search(snippet)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except Exception:
        return None


def patch_files(patch: str) -> List[Dict[str, str]]:
    """List the files an apply_patch text touches: [{"op": "Add", "path": ...}, ...]."""
    return [{"op": op, "path": path.strip()} for op, path in _PATCH_FILE_RE.findall(patch)]


def _shell_program(arguments: Dict[str, Any]) -> Optional[str]:
    """Best-effort extraction of the program name from shell tool-call arguments."""
    command = arguments.get("command") or arguments.get("cmd")
    if command is None and isinstance(arguments.get("raw_args"), str):
        commands = _code_mode_commands(arguments["raw_args"])
        if commands:
            command = commands[0]
            arguments["cmd"] = command
            if len(commands) > 1:
                arguments["cmds"] = commands
    if isinstance(command, list) and command:
        tokens = [str(t) for t in command]
        if len(tokens) >= 3 and tokens[0] in {"bash", "sh", "zsh"} and tokens[1] in {"-lc", "-c"}:
            command = tokens[2]
        else:
            return tokens[0].rsplit("/", 1)[-1]
    if isinstance(command, str) and command.strip():
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = command.split()
        for tok in tokens:
            if "=" in tok and not tok.startswith("="):
                continue
            return tok.rsplit("/", 1)[-1]
    return None


def _parse_json_arguments(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"raw_args": parsed}
        except Exception:
            return {"raw_args": raw}
    return {}


# --------------------------------------------------------------------------- SSE reconstruction

def parse_sse_events(sse_text: str) -> List[Dict[str, Any]]:
    """Parse a Server-Sent-Events body into a list of JSON ``data`` payloads."""
    events: List[Dict[str, Any]] = []
    for block in sse_text.replace("\r\n", "\n").split("\n\n"):
        data_lines = [line[5:].lstrip() for line in block.split("\n") if line.startswith("data:")]
        if not data_lines:
            continue
        data = "\n".join(data_lines)
        if data.strip() == "[DONE]":
            continue
        try:
            parsed = json.loads(data)
        except Exception:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def responses_object_from_sse(sse_text: str) -> Optional[Dict[str, Any]]:
    """Reconstruct the final Responses API object from a streamed SSE body."""
    events = parse_sse_events(sse_text)
    output_items = [
        e.get("item") for e in events
        if e.get("type") == "response.output_item.done" and isinstance(e.get("item"), dict)
    ]
    final: Optional[Dict[str, Any]] = None
    for event in reversed(events):
        if event.get("type") in {"response.completed", "response.incomplete", "response.failed"}:
            response = event.get("response")
            if isinstance(response, dict):
                final = dict(response)
                break
    if final is None:
        if not output_items:
            return None
        final = {"object": "response", "status": "incomplete", "usage": {}}
    if not final.get("output") and output_items:
        final["output"] = output_items
    return final


def anthropic_message_from_sse(sse_text: str) -> Optional[Dict[str, Any]]:
    """Reconstruct a final Anthropic ``message`` from its streaming events."""
    events = parse_sse_events(sse_text)
    message: Optional[Dict[str, Any]] = None
    blocks: Dict[int, Dict[str, Any]] = {}
    parts: Dict[int, List[str]] = {}
    for ev in events:
        et = ev.get("type")
        if et == "message_start" and isinstance(ev.get("message"), dict):
            message = dict(ev["message"])
            message["usage"] = dict(message.get("usage") or {})
        elif et == "content_block_start":
            idx = int(ev.get("index", len(blocks)))
            blocks[idx] = dict(ev.get("content_block") or {})
            parts[idx] = []
            if blocks[idx].get("type") == "text":
                blocks[idx].setdefault("text", "")
            if blocks[idx].get("type") == "thinking":
                blocks[idx].setdefault("thinking", "")
        elif et == "content_block_delta":
            idx = int(ev.get("index", 0))
            block = blocks.setdefault(idx, {"type": "text", "text": ""})
            delta = ev.get("delta") or {}
            dt = delta.get("type")
            if dt == "text_delta":
                block["text"] = block.get("text", "") + str(delta.get("text", ""))
            elif dt == "input_json_delta":
                parts.setdefault(idx, []).append(str(delta.get("partial_json", "")))
            elif dt == "thinking_delta":
                block["thinking"] = block.get("thinking", "") + str(delta.get("thinking", ""))
            elif dt == "signature_delta":
                block["signature"] = delta.get("signature")
        elif et == "content_block_stop":
            idx = int(ev.get("index", 0))
            block = blocks.get(idx)
            if block is not None and block.get("type") in ("tool_use", "server_tool_use"):
                joined = "".join(parts.get(idx, []))
                if joined.strip():
                    try:
                        block["input"] = json.loads(joined)
                    except Exception:
                        block["input"] = {"raw_args": joined}
                elif not isinstance(block.get("input"), dict) or not block["input"]:
                    block["input"] = {}
        elif et == "message_delta":
            if message is None:
                message = {"usage": {}}
            delta = ev.get("delta") or {}
            if delta.get("stop_reason") is not None:
                message["stop_reason"] = delta.get("stop_reason")
            if "stop_sequence" in delta:
                message["stop_sequence"] = delta.get("stop_sequence")
            for k, v in (ev.get("usage") or {}).items():
                if isinstance(v, (int, float)):
                    message["usage"][k] = max(int(v), int(message["usage"].get(k) or 0))
        elif et == "error":
            return None
    if message is None:
        return None
    message["content"] = [blocks[i] for i in sorted(blocks)]
    message.setdefault("type", "message")
    message.setdefault("role", "assistant")
    return message


def chat_completion_from_sse(sse_text: str) -> Optional[Dict[str, Any]]:
    """Reconstruct a ``chat.completion`` object from ``chat.completion.chunk`` events."""
    events = parse_sse_events(sse_text)
    if not events:
        return None
    result: Dict[str, Any] = {"object": "chat.completion"}
    role = "assistant"
    content_parts: List[str] = []
    tool_calls: Dict[int, Dict[str, Any]] = {}
    finish_reason = None
    usage: Dict[str, Any] = {}
    for ev in events:
        for key in ("id", "model", "created", "system_fingerprint"):
            if ev.get(key) and key not in result:
                result[key] = ev[key]
        if isinstance(ev.get("usage"), dict) and ev["usage"]:
            usage = ev["usage"]
        for choice in ev.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta") or {}
            if delta.get("role"):
                role = delta["role"]
            if delta.get("content"):
                content_parts.append(str(delta["content"]))
            for tc in delta.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                idx = int(tc.get("index", 0))
                entry = tool_calls.setdefault(idx, {"id": None, "type": "function", "function": {"name": "", "arguments": ""}})
                if tc.get("id"):
                    entry["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    entry["function"]["name"] = fn["name"]
                if fn.get("arguments"):
                    entry["function"]["arguments"] += str(fn["arguments"])
            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]
    message: Dict[str, Any] = {"role": role, "content": "".join(content_parts) or None}
    if tool_calls:
        message["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls)]
    result["choices"] = [{"index": 0, "message": message, "finish_reason": finish_reason}]
    result["usage"] = usage
    return result


# --------------------------------------------------------------------------- helpers

def _claude_result_text(content: Any) -> str:
    """Plain text of an Anthropic ``tool_result`` content (text blocks joined, reminders stripped)."""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    chunks.append(str(part.get("text", "")))
                elif part.get("type") == "image":
                    chunks.append("[image]")
            else:
                chunks.append(str(part))
        text = "\n".join(chunks)
    else:
        text = "" if content is None else str(content)
    text = _SYSTEM_REMINDER_RE.sub("", text)
    return text.strip("\n")


def strip_line_numbers(text: str) -> str:
    """Claude Code's Read tool renders ``   12→line`` / ``12<TAB>line``; return the bare lines.
    Only applied when *every* non-empty line carries a number, so numbered data is left alone."""
    lines = text.splitlines()
    if not lines or not all(_LINE_NUMBER_RE.match(l) for l in lines if l.strip()):
        return text
    return "\n".join(_LINE_NUMBER_RE.sub("", line, count=1) for line in lines)


def is_side_call(payload: Dict[str, Any]) -> bool:
    """Bookkeeping calls an agent makes besides the work (session titles, suggestions)."""
    if payload.get("tools"):
        return False
    model = str(payload.get("model") or "").lower()
    max_tokens = payload.get("max_tokens")
    return "haiku" in model or (isinstance(max_tokens, int) and max_tokens <= 512)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [str(c.get("text")) for c in content if isinstance(c, dict) and c.get("text") and c.get("type") != "tool_result"]
        return "\n".join(texts)
    return ""


class TrajectoryInterceptor:
    """Buffers and transforms live LLM API traffic into OpenWorkCompiler TraceIR."""

    def __init__(
        self,
        run_id: Optional[str] = None,
        source_agent: str = "zero-code-proxy",
        protocol: str = "unknown",
        agent_version: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self.run_id = run_id or f"run_proxy_{uuid.uuid4().hex[:8]}"
        self.source_agent = source_agent
        self.protocol = protocol
        self.agent_version = agent_version
        self.user_agent = user_agent
        self.steps: List[TraceStep] = []
        self.raw_requests: List[Dict[str, Any]] = []
        self.raw_responses: List[Dict[str, Any]] = []
        self.prompt_tokens_accumulated = 0
        self.completion_tokens_accumulated = 0
        self.aux_prompt_tokens = 0
        self.aux_completion_tokens = 0
        self.start_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # ------------------------------------------------------------------ shared building blocks

    def _remember_raw(self, request_payload: Dict[str, Any], response_payload: Dict[str, Any]) -> None:
        if os.environ.get("OPENWORKCOMPILER_KEEP_RAW", "").lower() in {"1", "true", "yes"}:
            self.raw_requests.append(request_payload)
        else:
            trimmed = {k: request_payload.get(k) for k in ("model", "metadata", "user", "prompt_cache_key") if k in request_payload}
            messages = request_payload.get("messages") or request_payload.get("input")
            if isinstance(messages, list) and messages:
                trimmed["last_message"] = messages[-1]
                trimmed["message_count"] = len(messages)
            tools = request_payload.get("tools")
            if isinstance(tools, list):
                trimmed["tool_names"] = [t.get("name") or (t.get("function") or {}).get("name") for t in tools if isinstance(t, dict)]
            self.raw_requests.append(trimmed)
        self.raw_responses.append(response_payload)

    def _build_step(
        self,
        *,
        user_input: Dict[str, Any],
        text: Optional[str],
        tool_calls: List[Dict[str, Any]],
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int,
        model: str,
        response_id: Optional[str],
        status: Optional[str],
        duration_ms: float,
        extra_output: Optional[Dict[str, Any]] = None,
    ) -> TraceStep:
        normalized = [normalize_call(tc.get("name") or "", tc.get("arguments")) for tc in tool_calls]
        merged = merge_calls(normalized) if normalized else None
        action = merged.action if merged else "respond"
        inputs: Dict[str, Any] = dict(user_input)
        if merged:
            inputs.update(merged.input)
        output: Dict[str, Any] = {
            "content": text if text else None,
            "tool_calls": tool_calls,
            "role": "assistant",
            "response_id": response_id,
            "status": status,
        }
        if extra_output:
            output.update(extra_output)
        total = prompt_tokens + completion_tokens
        self.prompt_tokens_accumulated += prompt_tokens
        self.completion_tokens_accumulated += completion_tokens
        step = TraceStep(
            step_id=f"step_{len(self.steps) + 1}",
            actor="agent",
            action=action,
            input=inputs,
            output=output,
            latency_ms=duration_ms,
            token_usage=TokenUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total),
            model=model,
            cached_tokens=cached_tokens,
        )
        self.steps.append(step)
        return step

    def _attach(self, call_id: Any, raw: Any, text: str, is_error: bool = False) -> bool:
        """Attach one tool result to the step that issued ``call_id``. Idempotent."""
        if not call_id:
            return False
        for step in reversed(self.steps):
            step_output = step.output if isinstance(step.output, dict) else {}
            for call in step_output.get("tool_calls", []) or []:
                if isinstance(call, dict) and call.get("id") == call_id:
                    if "result" in call:
                        return False
                    call["result"] = text
                    if is_error:
                        call["is_error"] = True
                        step_output["tool_error"] = True
                    # concatenate results of batched calls in call order
                    ordered = [c.get("result") for c in step_output.get("tool_calls", []) if isinstance(c, dict) and "result" in c]
                    step_output["tool_result"] = "".join(r if r.endswith("\n") else r + "\n" for r in ordered).rstrip("\n") + ("\n" if ordered and ordered[-1].endswith("\n") else "")
                    if len(ordered) == 1:
                        step_output["tool_result"] = ordered[0]
                    prev_raw = step_output.get("tool_result_raw")
                    step_output["tool_result_raw"] = raw if prev_raw is None else (prev_raw if isinstance(prev_raw, list) else [prev_raw]) + [raw]
                    return True
        return False

    # ------------------------------------------------------------------ tool-result extractors

    def _responses_tool_outputs(self, payload: Dict[str, Any]) -> Iterable[Tuple[Any, Any, str, bool]]:
        items = payload.get("input")
        if not isinstance(items, list):
            return []
        out = []
        for item in items:
            if isinstance(item, dict) and str(item.get("type", "")).endswith("_call_output"):
                raw = item.get("output")
                if item.get("call_id") and raw is not None:
                    out.append((item.get("call_id"), raw, normalize_tool_output(raw), False))
        return out

    def _anthropic_tool_outputs(self, payload: Dict[str, Any]) -> Iterable[Tuple[Any, Any, str, bool]]:
        messages = payload.get("messages") or []
        out = []
        for msg in reversed(messages):
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        raw = block.get("content")
                        text = strip_line_numbers(_claude_result_text(raw))
                        out.append((block.get("tool_use_id"), raw, text, bool(block.get("is_error"))))
            break  # only the latest user turn carries new results
        return out

    def _chat_tool_outputs(self, payload: Dict[str, Any]) -> Iterable[Tuple[Any, Any, str, bool]]:
        messages = payload.get("messages") or []
        out = []
        for msg in reversed(messages):
            if not isinstance(msg, dict):
                continue
            if msg.get("role") == "tool":
                raw = msg.get("content")
                out.append((msg.get("tool_call_id"), raw, _content_text(raw) if not isinstance(raw, str) else raw, False))
                continue
            break  # trailing tool messages only
        return list(reversed(out))

    def _absorb_results(self, outputs: Iterable[Tuple[Any, Any, str, bool]]) -> None:
        for call_id, raw, text, is_error in outputs:
            self._attach(call_id, raw, text, is_error)

    # ------------------------------------------------------------------ protocol intercepts

    def intercept_openai_request_response(
        self, request_payload: Dict[str, Any], response_payload: Dict[str, Any], duration_ms: float = 0.0
    ) -> TraceStep:
        """Intercept a completed OpenAI chat/completions turn (Cursor, opencode, Aider, SDKs)."""
        self._remember_raw(request_payload, response_payload)
        self._absorb_results(self._chat_tool_outputs(request_payload))

        user_input: Dict[str, Any] = {}
        for msg in reversed(request_payload.get("messages", []) or []):
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_input = {"content": _content_text(msg.get("content")) or msg.get("content")}
                break

        choices = response_payload.get("choices", [])
        assistant_msg = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
        tool_calls: List[Dict[str, Any]] = []
        for tc in assistant_msg.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            tool_calls.append({"id": tc.get("id"), "name": fn.get("name") or tc.get("type") or "tool_call",
                               "arguments": _parse_json_arguments(fn.get("arguments"))})

        usage = response_payload.get("usage") or {}
        p_tokens = int(usage.get("prompt_tokens", 0) or 0)
        c_tokens = int(usage.get("completion_tokens", 0) or 0)
        cached = int(((usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)) or 0)
        return self._build_step(
            user_input=user_input, text=assistant_msg.get("content"), tool_calls=tool_calls,
            prompt_tokens=p_tokens, completion_tokens=c_tokens, cached_tokens=cached,
            model=str(response_payload.get("model") or request_payload.get("model") or ""),
            response_id=response_payload.get("id"),
            status=(choices[0].get("finish_reason") if choices and isinstance(choices[0], dict) else None),
            duration_ms=duration_ms,
        )

    def intercept_anthropic_request_response(
        self, request_payload: Dict[str, Any], response_payload: Dict[str, Any], duration_ms: float = 0.0
    ) -> TraceStep:
        """Intercept a completed Anthropic Messages turn (Claude Code, Anthropic SDK)."""
        self._remember_raw(request_payload, response_payload)
        self._absorb_results(self._anthropic_tool_outputs(request_payload))

        user_input: Dict[str, Any] = {}
        for msg in reversed(request_payload.get("messages", []) or []):
            if isinstance(msg, dict) and msg.get("role") == "user":
                text = _SYSTEM_REMINDER_RE.sub("", _content_text(msg.get("content"))).strip()
                if text:
                    user_input = {"content": text}
                break

        tool_calls: List[Dict[str, Any]] = []
        text_parts: List[str] = []
        for block in response_payload.get("content", []) or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool_calls.append({"id": block.get("id"), "name": block.get("name") or "tool_use",
                                   "arguments": block.get("input") if isinstance(block.get("input"), dict) else {"raw_args": block.get("input")}})
            elif block.get("type") == "text" and block.get("text"):
                text_parts.append(str(block["text"]))

        usage = response_payload.get("usage") or {}
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
        cache_creation = int(usage.get("cache_creation_input_tokens", 0) or 0)
        c_tokens = int(usage.get("output_tokens", 0) or 0)
        stop_reason = response_payload.get("stop_reason")
        status = {"end_turn": "completed", "tool_use": "completed", "max_tokens": "incomplete"}.get(str(stop_reason), stop_reason)
        return self._build_step(
            user_input=user_input, text="\n".join(text_parts) if text_parts else None, tool_calls=tool_calls,
            prompt_tokens=input_tokens + cache_read + cache_creation, completion_tokens=c_tokens, cached_tokens=cache_read,
            model=str(response_payload.get("model") or request_payload.get("model") or ""),
            response_id=response_payload.get("id"), status=status, duration_ms=duration_ms,
            extra_output={"stop_reason": stop_reason, "cache_creation_tokens": cache_creation},
        )

    def record_side_call(self, response_payload: Dict[str, Any]) -> None:
        """Account tokens of a bookkeeping call (title/suggestion) without creating a step."""
        usage = response_payload.get("usage") or {}
        self.aux_prompt_tokens += int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0) \
            + int(usage.get("cache_read_input_tokens", 0) or 0) + int(usage.get("cache_creation_input_tokens", 0) or 0)
        self.aux_completion_tokens += int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)

    def intercept_responses_request_response(
        self, request_payload: Dict[str, Any], response_payload: Dict[str, Any], duration_ms: float = 0.0
    ) -> TraceStep:
        """Intercept a completed OpenAI Responses API turn (Codex CLI, Agents SDK, ...)."""
        self._remember_raw(request_payload, response_payload)
        self._absorb_results(self._responses_tool_outputs(request_payload))

        user_input: Dict[str, Any] = {}
        request_input = request_payload.get("input", [])
        if isinstance(request_input, str):
            user_input = {"content": request_input}
        elif isinstance(request_input, list):
            for item in reversed(request_input):
                if not isinstance(item, dict):
                    continue
                if item.get("type") in (None, "message") and item.get("role") == "user":
                    content = item.get("content")
                    if isinstance(content, list):
                        texts = [c.get("text") for c in content if isinstance(c, dict) and c.get("text")]
                        content = "\n".join(texts) if texts else content
                    user_input = {"content": content}
                    break

        output_items = response_payload.get("output", [])
        if not isinstance(output_items, list):
            output_items = []
        tool_calls: List[Dict[str, Any]] = []
        text_parts: List[str] = []
        for item in output_items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type in {"function_call", "custom_tool_call", "local_shell_call"}:
                name = item.get("name") or item_type
                arguments = _parse_json_arguments(item.get("arguments") or item.get("input") or item.get("action"))
                # Codex "code mode": unwrap the JS snippet into cmd/cmds or a patch
                if isinstance(arguments.get("raw_args"), str):
                    patch = _code_mode_patch(arguments["raw_args"])
                    if patch:
                        arguments["patch"] = patch
                        arguments["files"] = [f["path"] for f in patch_files(patch)]
                    else:
                        _shell_program(arguments)
                if isinstance(arguments.get("patch"), str) and not arguments.get("files"):
                    arguments["files"] = [f["path"] for f in patch_files(arguments["patch"])]
                if item_type == "local_shell_call" and not arguments.get("cmd"):
                    action = item.get("action") or {}
                    if isinstance(action, dict) and action.get("command"):
                        arguments["command"] = action["command"]
                tool_calls.append({"id": item.get("call_id") or item.get("id"), "name": name, "arguments": arguments})
            elif item_type == "message":
                for part in item.get("content", []) or []:
                    if isinstance(part, dict) and part.get("type") == "output_text" and part.get("text"):
                        text_parts.append(part["text"])

        usage = response_payload.get("usage") or {}
        p_tokens = int(usage.get("input_tokens", 0) or 0)
        c_tokens = int(usage.get("output_tokens", 0) or 0)
        cached = int(((usage.get("input_tokens_details") or {}).get("cached_tokens", 0)) or 0)
        return self._build_step(
            user_input=user_input, text="\n".join(text_parts) if text_parts else None, tool_calls=tool_calls,
            prompt_tokens=p_tokens, completion_tokens=c_tokens, cached_tokens=cached,
            model=str(response_payload.get("model") or request_payload.get("model") or ""),
            response_id=response_payload.get("id"), status=response_payload.get("status"), duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------ finalize

    def finalize_trace(self, status: str = "success") -> TraceIR:
        """Construct canonical TraceIR object from intercepted steps."""
        result = TraceResult(
            status=TraceStatus.SUCCESS if status == "success" else TraceStatus.FAILURE,
            outputs={"intercepted_steps_count": len(self.steps)},
        )
        last_model = next((getattr(s, "model", "") for s in reversed(self.steps) if getattr(s, "model", "")), "")
        provenance = Provenance(
            framework=self.source_agent,
            agent_version=self.agent_version,
            model_name=last_model or None,
            environment="proxy",
            metadata={"protocol": self.protocol, "user_agent": self.user_agent,
                      "aux_prompt_tokens": self.aux_prompt_tokens, "aux_completion_tokens": self.aux_completion_tokens},
        )
        return TraceIR(
            run_id=self.run_id,
            source_agent=self.source_agent,
            start_time=self.start_time,
            end_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            steps=list(self.steps),
            result=result,
            provenance=provenance,
        )
