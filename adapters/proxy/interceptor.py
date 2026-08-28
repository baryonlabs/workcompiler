"""OpenWorkflow Zero-Code Agent Proxy Trajectory Interceptor.

Intercepts and reconstructs standard OpenAI (/v1/chat/completions) and
Anthropic (/v1/messages) API requests and responses into canonical TraceIR instances.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional
from core.work_ir import TraceIR, TraceStep, TraceResult, TraceStatus, TokenUsage


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
