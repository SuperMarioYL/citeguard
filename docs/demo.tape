# vhs tape — CiteGuard happy path.
# Render in CI via .github/workflows/demo.yml, or locally:
#   vhs docs/demo.tape        (needs the `citeguard` CLI on PATH + vhs installed)
# Output lands at assets/demo.gif.
Output assets/demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 720
Set Theme "Dracula"
Set Padding 18
Set TypingSpeed 55ms

Type "citeguard --version"
Enter
Sleep 1s

Type "# A withdrawn paper: red rows + nearest-match hints"
Enter
Sleep 500ms
Type "citeguard tests/fixtures/withdrawn_paper.md"
Enter
Sleep 5s

Type "# A clean paper: every identifier resolves green"
Enter
Sleep 500ms
Type "citeguard tests/fixtures/clean_paper.tex"
Enter
Sleep 4s

Type "# Same tool on an OSS bug report — fabricated CVEs / commits stand out"
Enter
Sleep 500ms
Type "citeguard tests/fixtures/bug_report.md"
Enter
Sleep 4s

Type "# The JSON sidecar feeds downstream desk-reject scripts"
Enter
Sleep 500ms
Type "jq '.results[0]' tests/fixtures/withdrawn_paper.md.citeguard.json"
Enter
Sleep 3s
