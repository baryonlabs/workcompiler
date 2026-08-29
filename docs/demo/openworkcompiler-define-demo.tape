# A complete beginner (no prompt-engineering knowledge) defines the WHAT of a refund-approval job
# from raw materials only, by chatting with Codex: $ow-define runs the grilling interview and the
# beginner mostly accepts the recommended answers. Rendered with vhs; fixed waits per interview round.
#
#   export CODEX_HOME=/path/to/codex-home     # auth.json + trusted project, no proxy needed for this step
#   vhs docs/demo/openworkcompiler-define-demo.tape

Output docs/demo/openworkcompiler-define-demo.gif

Set Shell "bash"
Set FontFamily "D2Coding"
Set FontSize 15
Set Width 1240
Set Height 860
Set Padding 18
Set Theme "Catppuccin Mocha"
Set TypingSpeed 35ms
Set Framerate 20

Hide
Type "export PS1='\[\e[1;32m\]openworkflow\[\e[0m\] $ ' && clear"
Enter
Show
Type "ls examples/cases/_tui-demo/materials examples/cases/_tui-demo/materials/data"
Enter
Sleep 3s
Type "codex"
Enter
Sleep 10s

Type "$ow-define"
Sleep 1.5s
Enter
Type " 환불 승인 업무. 저는 프롬프트 같은 건 몰라요. 팀장님 메모랑 제 노트, 예전에 쓴 판정서, 데이터 파일이 examples/cases/_tui-demo/materials 에 있어요. 이걸로 업무 정의를 만들어 주세요 (파일은 examples/cases/_tui-demo/ 아래에)."
Sleep 1s
Enter
Sleep 100s

Type "네, 전부 추천안대로 해 주세요. 하나만: 재무팀 승인은 10만원 '초과'일 때예요."
Sleep 1s
Enter
Sleep 100s

Type "추천안대로 진행해 주세요."
Sleep 1s
Enter
Sleep 100s

Type "네 좋아요. 그대로 파일 만들어 주세요."
Sleep 1s
Enter
Sleep 120s

Type "/quit"
Sleep 500ms
Enter
Sleep 3s
Type "find examples/cases/_tui-demo -type f -newer examples/cases/_tui-demo/materials/notes.txt | sort"
Enter
Sleep 6s
