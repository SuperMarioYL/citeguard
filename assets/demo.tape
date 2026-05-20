# VHS tape for the 30-second CiteGuard demo.
# Render with:  vhs assets/demo.tape  (https://github.com/charmbracelet/vhs)
#
# The output GIF + cast file land alongside this tape file:
#   assets/demo.gif  (preview)
#   assets/demo.cast (asciinema record for README badge)

Output assets/demo.cast
Output assets/demo.gif

Set FontSize 16
Set Width 1200
Set Height 700
Set Theme "Dracula"
Set TypingSpeed 60ms

Type "citeguard --version"
Enter
Sleep 800ms

Type "# A withdrawn paper: red rows + nearest-match hints"
Enter
Type "citeguard tests/fixtures/withdrawn_paper.md"
Enter
Sleep 4s

Type "# A clean paper: all green"
Enter
Type "citeguard tests/fixtures/clean_paper.tex"
Enter
Sleep 3s

Type "# OSS bug report: same tool, same answer"
Enter
Type "citeguard tests/fixtures/bug_report.md"
Enter
Sleep 3s

Type "cat tests/fixtures/withdrawn_paper.md.citeguard.json | jq '.results[0]'"
Enter
Sleep 2s
