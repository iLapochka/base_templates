#!/usr/bin/env bash
# PreToolUse hook: puts CLAUDE.md's hard rules in front of Claude before it writes code.

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$FILE_PATH" ]] && exit 0

case "$FILE_PATH" in
  *.py) ;;
  *) exit 0 ;;
esac

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)}"
RULES_FILE="$PROJECT_DIR/CLAUDE.md"
[[ -f "$RULES_FILE" ]] || exit 0

# The lead-in of every bullet in the Rules section — the checklist, not the prose.
RULES=$(sed -n '/^## Rules$/,/^## Architecture$/p' "$RULES_FILE" |
  grep -o '^- \*\*[^*]*\*\*' |
  sed 's/^- \*\*/- /; s/\*\*$//')
[[ -z "$RULES" ]] && exit 0

jq -n --arg msg "CLAUDE.md — the rules this file is held to:
$RULES
Read the full rule in CLAUDE.md before departing from any of them." '{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": $msg
  }
}'

exit 0
