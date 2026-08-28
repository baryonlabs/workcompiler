# adapters/proxy

OpenWorkflow Zero-Code Agent Proxy Adapter (LLM API & MCP Interceptor).

Inspired by transparent proxy architectures like `opencodex`, this adapter intercepts standard LLM API traffic (`/v1/chat/completions`, `/v1/messages`) and MCP tool calls between any existing AI agent (Claude Code, Cursor, AutoGen, LangChain, CrewAI) and LLM providers.

## Key Capabilities

1. **Zero Agent Code Modification**: Existing agents simply set `OPENAI_BASE_URL=http://localhost:8080/v1` or `ANTHROPIC_BASE_URL=http://localhost:8080/v1`.
2. **Transparent Trajectory Capture**: Automatically records prompts, tool calls, tool outputs, and reasoning steps, streaming them into **Trace IR**.
3. **Instant Work Compilation**: Feeds recorded trajectories into the OpenWorkflow kernel for automated `Work IR` (`work.yaml`) compilation upon task approval.
