# OpenWorkCompiler × Codex CLI — one-line install (pipx → owc), then everything runs inside the interactive Codex TUI.
# Rendered with vhs (https://github.com/charmbracelet/vhs). Regenerate from the repo root:
#
#   mkdir -p build/codex-home && cp ~/.codex/auth.json build/codex-home/   # + the config.toml below (the tape exports CODEX_HOME=$PWD/build/codex-home)
#   vhs docs/demo/openworkcompiler-codex-demo.tape
#
# codex-home/config.toml — Codex talks to the OpenWorkCompiler proxy, ChatGPT login reused as-is:
#
#   model_provider = "openworkcompiler"
#   approval_policy = "never"
#   sandbox_mode = "workspace-write"
#   [sandbox_workspace_write]
#   network_access = true                      # lets Codex curl the local proxy
#   [model_providers.openworkcompiler]
#   name = "OpenWorkCompiler Proxy"
#   base_url = "http://127.0.0.1:8787/backend-api/codex"
#   wire_api = "responses"
#   requires_openai_auth = true
#   [projects."/abs/path/to/open-workflow"]
#   trust_level = "trusted"
#
# The $ow-* skills are discovered automatically from .agents/skills/ in this repository.
# Step 5 needs a local model server: `ollama pull qwen2.5:7b` (Ollama listens on 127.0.0.1:11434). The 3B model
# fails the gate on this session's long build-tree summary (it leaves a placeholder), so the demo promotes to 7B.
#
# Post-process to keep the GIF small (raw vhs output is ~36 MB; this brings it to ~8.5 MB):
#
#   ffmpeg -y -i docs/demo/openworkcompiler-codex-demo.gif \
#     -vf "fps=5,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=48:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" \
#     build/codex-demo.gif && gifsicle -O3 --lossy=140 build/codex-demo.gif -o docs/demo/openworkcompiler-codex-demo.gif

Output docs/demo/openworkcompiler-codex-demo.gif

Set Shell "bash"
Set FontFamily "D2Coding"
Set FontSize 15
Set Width 1240
Set Height 860
Set Padding 18
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms
Set Framerate 20

# --- prelude: one-line install, detect agents, start the zero-code proxy (everything else runs inside Codex) ---
Hide
Type "export CODEX_HOME=$PWD/build/codex-home PS1='\[\e[1;32m\]openworkcompiler\[\e[0m\] $ ' && mkdir -p build && clear"
Enter
Show
Type `pipx install --force "git+https://github.com/baryonlabs/workcompiler.git"`
Enter
Wait+Screen@180s /installed package openworkcompiler/
Sleep 1s
Type "owc version && owc agent list"
Enter
Sleep 4s
Type "(owc proxy --port 8787 > build/openworkcompiler-proxy.log 2>&1 &) && sleep 2 && head -4 build/openworkcompiler-proxy.log"
Enter
Sleep 4s

Type "codex"
Enter
Sleep 10s

# 1) OpenWorkLang (.work) -> Work IR, via the $ow-compile-work skill
Type "$ow-compile-work"
Sleep 1.5s
Enter
Type " examples/quality_analysis.work"
Sleep 1s
Enter
# fixed waits: vhs screen matching is unreliable once the Codex TUI scrolls
Sleep 60s

# 2) What did the proxy capture from this very session?
Type "$ow-traces"
Sleep 1.5s
Enter
Sleep 800ms
Enter
Sleep 35s

# 3) Compile the captured Codex session itself into work.yaml
Type "$ow-compile-trace"
Sleep 1.5s
Enter
Type " codex-session"
Sleep 1s
Enter
Sleep 80s

# 4) Benchmark the compiled build against the recorded session: result, tokens, speed
Type "$ow-bench"
Sleep 1.5s
Enter
Type " codex-session"
Sleep 1s
Enter
Sleep 70s

# 5) Promote the one step still on the frontier LLM (the final summary) to a small local model — gated
Type "$ow-promote"
Sleep 1.5s
Enter
Type " codex-session respond qwen2.5:7b"
Sleep 1s
Enter
Sleep 100s

# 6) Benchmark again: the SLM now really runs, split from the frontier model in the token ledger
Type "$ow-bench"
Sleep 1.5s
Enter
Type " codex-session"
Sleep 1s
Enter
Sleep 90s

Type "/quit"
Sleep 500ms
Enter
Sleep 3s
