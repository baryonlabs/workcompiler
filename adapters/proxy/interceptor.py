"""OpenWorkflow Zero-Code Agent Proxy Trajectory Interceptor.

Intercepts and reconstructs standard OpenAI (/v1/chat/completions), OpenAI
Responses API (/v1/responses, used by Codex CLI) and Anthropic (/v1/messages)
API requests and responses into canonical TraceIR instances.
"""

from __future__ import annotations

import json
import re
import shlex
import time
import uuid
from typing import Any, Dict, List, Optional
from core.work_ir import TraceIR, TraceStep, TraceResult, TraceStatus, TokenUsage


# Tool names that Codex CLI / OpenAI agents use for running shell commands. For these the
# trajectory action is refined to ``shell_<program>`` so that a multi-step agent session
# compiles into distinct workflow actions instead of one opaque "shell" node.
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


def _code_mode_command(snippet: str) -> Optional[str]:
    """Extract the ``cmd`` string from a Codex code-mode ``exec_command`` call."""
    match = _CODE_MODE_CMD_RE.search(snippet)
    if not match:
        return None
    literal = match.group(1)
    quote, body = literal[0], literal[1:-1]
    if quote == '"':
        try:
            return json.loads(literal)
        except Exception:
            return body
    return body.replace("\\" + quote, quote).replace("\\n", "\n")


def _shell_program(arguments: Dict[str, Any]) -> Optional[str]:
    """Best-effort extraction of the program name from shell tool-call arguments."""
    command = arguments.get("command") or arguments.get("cmd")
    if command is None and isinstance(arguments.get("raw_args"), str):
        command = _code_mode_command(arguments["raw_args"])
        if command is not None:
            arguments["cmd"] = command
    if isinstance(command, list) and command:
        tokens = [str(t) for t in command]
        # Codex wraps commands as ["bash", "-lc", "<script>"]; unwrap the script.
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
                continue  # skip leading VAR=value assignments
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
    """Reconstruct the final Responses API object from a streamed SSE body.

    Output items are taken from ``response.output_item.done`` events, because some
    backends (e.g. the ChatGPT Codex backend) send ``response.completed`` with an empty
    ``output`` list; ``id``/``status``/``usage`` come from the terminal event when present.
    """
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


class TrajectoryInterceptor:
    """Buffers and transforms live LLM API traffic into OpenWorkflow TraceIR."""

    def __init__(self, run_id: Optional[str] = None, source_agent: str = "zero-code-proxy") -> None:
        self.run_id = run_id or f"run_proxy_{uuid.uuid4().hex[:8]}"
        self.source_agent = source_agent
        self.steps: List[TraceStep] = []
        self.raw_requests: List[Dict[str, Any]] = []
        self.raw_responses: List[Dict[str, Any]] = []
        self.prompt_tokens_accumulated = 0
        self.completion_tokens_accumulated = 0
        self.start_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def intercept_openai_request_response(
        self, request_payload: Dict[str, Any], response_payload: Dict[str, Any], duration_ms: float = 0.0
    ) -> TraceStep:
        """Intercept a non-streaming or completed OpenAI chat completion turn."""
        self.raw_requests.append(request_payload)
        self.raw_responses.append(response_payload)

        messages = request_payload.get("messages", [])

        # Extract last user message and assistant response
        user_input = {}
        if messages:
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    user_input = {"content": msg.get("content")}
                    break

        choices = response_payload.get("choices", [])
        assistant_msg = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
        action_name = "call_llm"
        tool_calls = assistant_msg.get("tool_calls", [])

        if tool_calls and isinstance(tool_calls, list):
            first_tool = tool_calls[0].get("function", {}) if isinstance(tool_calls[0], dict) else {}
            action_name = first_tool.get("name", "tool_call")
            tool_args = first_tool.get("arguments", {})
            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except Exception:
                    tool_args = {"raw_args": tool_args}
            if isinstance(tool_args, dict):
                user_input.update(tool_args)

        output_payload = {
            "content": assistant_msg.get("content"),
            "tool_calls": tool_calls,
            "role": assistant_msg.get("role", "assistant"),
        }

        usage = response_payload.get("usage", {})
        p_tokens = usage.get("prompt_tokens", 0)
        c_tokens = usage.get("completion_tokens", 0)
        t_tokens = usage.get("total_tokens", p_tokens + c_tokens)

        self.prompt_tokens_accumulated += p_tokens
        self.completion_tokens_accumulated += c_tokens

        token_usage = TokenUsage(
            prompt_tokens=p_tokens, completion_tokens=c_tokens, total_tokens=t_tokens
        )

        step = TraceStep(
            step_id=f"step_{len(self.steps) + 1}",
            actor="agent",
            action=action_name,
            input=user_input,
            output=output_payload,
            latency_ms=duration_ms,
            token_usage=token_usage,
        )

        self.steps.append(step)
        return step

    def intercept_anthropic_request_response(
        self, request_payload: Dict[str, Any], response_payload: Dict[str, Any], duration_ms: float = 0.0
    ) -> TraceStep:
        """Intercept a non-streaming or completed Anthropic message turn."""
        self.raw_requests.append(request_payload)
        self.raw_responses.append(response_payload)

        messages = request_payload.get("messages", [])
        user_input = {}
        if messages:
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    user_input = {"content": msg.get("content")}
                    break

        content_blocks = response_payload.get("content", [])
        action_name = "call_llm"
        output_payload = {"content_blocks": content_blocks}

        if isinstance(content_blocks, list):
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    action_name = block.get("name", "tool_use")
                    if isinstance(block.get("input"), dict):
                        user_input.update(block.get("input"))
                    break

        usage = response_payload.get("usage", {})
        p_tokens = usage.get("input_tokens", 0)
        c_tokens = usage.get("output_tokens", 0)
        token_usage = TokenUsage(
            prompt_tokens=p_tokens, completion_tokens=c_tokens, total_tokens=p_tokens + c_tokens
        )

        step = TraceStep(
            step_id=f"step_{len(self.steps) + 1}",
            actor="agent",
            action=action_name,
            input=user_input,
            output=output_payload,
            latency_ms=duration_ms,
            token_usage=token_usage,
        )

        self.steps.append(step)
        return step

    def intercept_responses_request_response(
        self, request_payload: Dict[str, Any], response_payload: Dict[str, Any], duration_ms: float = 0.0
    ) -> TraceStep:
        """Intercept a completed OpenAI Responses API turn (Codex CLI, Agents SDK, ...)."""
        self.raw_requests.append(request_payload)
        self.raw_responses.append(response_payload)

        # --- Request side: the latest user message and any tool outputs fed back in ---
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

        # --- Response side: message text and the first tool call issued this turn ---
        output_items = response_payload.get("output", [])
        if not isinstance(output_items, list):
            output_items = []

        action_name = "respond"
        tool_calls: List[Dict[str, Any]] = []
        text_parts: List[str] = []
        for item in output_items:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type in {"function_call", "custom_tool_call", "local_shell_call"}:
                name = item.get("name") or item_type
                arguments = _parse_json_arguments(item.get("arguments") or item.get("input") or item.get("action"))
                tool_calls.append({"id": item.get("call_id") or item.get("id"), "name": name, "arguments": arguments})
                if len(tool_calls) == 1:
                    program = _shell_program(arguments) if name in SHELL_TOOL_NAMES or item_type == "local_shell_call" else None
                    action_name = f"shell_{program}" if program else name
                    user_input.update(arguments)
            elif item_type == "message":
                for part in item.get("content", []) or []:
                    if isinstance(part, dict) and part.get("type") == "output_text" and part.get("text"):
                        text_parts.append(part["text"])

        output_payload = {
            "content": "\n".join(text_parts) if text_parts else None,
            "tool_calls": tool_calls,
            "role": "assistant",
            "response_id": response_payload.get("id"),
            "status": response_payload.get("status"),
        }

        usage = response_payload.get("usage") or {}
        p_tokens = int(usage.get("input_tokens", 0) or 0)
        c_tokens = int(usage.get("output_tokens", 0) or 0)
        t_tokens = int(usage.get("total_tokens", p_tokens + c_tokens) or 0)
        self.prompt_tokens_accumulated += p_tokens
        self.completion_tokens_accumulated += c_tokens

        step = TraceStep(
            step_id=f"step_{len(self.steps) + 1}",
            actor="agent",
            action=action_name,
            input=user_input,
            output=output_payload,
            latency_ms=duration_ms,
            token_usage=TokenUsage(prompt_tokens=p_tokens, completion_tokens=c_tokens, total_tokens=t_tokens),
        )
        self.steps.append(step)
        return step

    def finalize_trace(self, status: str = "success") -> TraceIR:
        """Construct canonical TraceIR object from intercepted steps."""
        result = TraceResult(
            status=TraceStatus.SUCCESS if status == "success" else TraceStatus.FAILURE,
            outputs={"intercepted_steps_count": len(self.steps)},
        )

        return TraceIR(
            run_id=self.run_id,
            source_agent=self.source_agent,
            start_time=self.start_time,
            end_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            steps=list(self.steps),
            result=result,
        )
