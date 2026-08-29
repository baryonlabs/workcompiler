# OpenWorkCompiler × Codex CLI — everything runs inside the interactive Codex TUI.
# Rendered with vhs (https://github.com/charmbracelet/vhs). Regenerate from the repo root:
#
#   export CODEX_HOME=/path/to/codex-home   # contains auth.json + the config.toml below
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
#
# Post-process to keep the GIF small (raw vhs output is ~24 MB; this brings it to ~6.8 MB):
#
#   ffmpeg -y -i docs/demo/openworkcompiler-codex-demo.gif \
#     -vf "fps=6,scale=1000:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle" \
#     build/codex-demo.gif && gifsicle -O3 --lossy=120 build/codex-demo.gif -o docs/demo/openworkcompiler-codex-demo.gif

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

# --- prelude: the only thing outside Codex is starting the zero-code proxy ---
Hide
Type "export PS1='\[\e[1;32m\]openworkflow\[\e[0m\] $ ' && mkdir -p build && clear"
Enter
Show
Type "python3 -m uvicorn adapters.proxy.server:app --port 8787 > build/openworkcompiler-proxy.log 2>&1 &"
Enter
Sleep 2s

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

Type "/quit"
Sleep 500ms
Enter
Sleep 3s
