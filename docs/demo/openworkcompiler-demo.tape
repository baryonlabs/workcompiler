# OpenWorkCompiler terminal demo — rendered with vhs (https://github.com/charmbracelet/vhs)
# Regenerate from the repo root:  vhs docs/demo/openworkcompiler-demo.tape

Output docs/demo/openworkcompiler-demo.gif

Set Shell "bash"
Set FontSize 15
Set Width 1100
Set Height 760
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms
Set PlaybackSpeed 1.0

Hide
Type "export PS1='\[\e[1;32m\]openworkflow\[\e[0m\] $ ' && clear"
Enter
Show

Sleep 800ms
Type "# 1) Trace -> BEHAVIOR.md -> Work IR -> Durable Runtime -> Oracle Gate -> SLM"
Enter
Sleep 600ms
Type "python3 examples/run_customer_renewal_demo.py"
Sleep 400ms
Enter
Sleep 5s

Type "clear"
Enter
Sleep 400ms
Type "# 2) Full test suite"
Enter
Sleep 500ms
Type "python3 -m pytest tests/ -q"
Sleep 400ms
Enter
Sleep 4s
