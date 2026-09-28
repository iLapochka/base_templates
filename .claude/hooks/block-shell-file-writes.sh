#!/usr/bin/env bash

set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
[[ -z "$COMMAND" ]] && exit 0

deny() {
  jq -n --arg reason "$1" '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "permissionDecisionReason": $reason
    }
  }'
  exit 0
}

NORM=$(echo "$COMMAND" | tr '\n' ' ' | tr -s ' ')
USE_THE_TOOL="Blocked by CLAUDE.md: edit files with the Write/Edit tools, not the shell — the repo's spec and layering hooks only run on those. Offending form:"

# In-place stream edits.
if echo "$NORM" | grep -qE '(^|[;&|(]\s*)(sed|perl|gsed)\s+(-[^ ]*\s+)*-i'; then
  deny "$USE_THE_TOOL in-place sed/perl."
fi

# Python one-liners and heredocs that write files.
if echo "$NORM" | grep -qE '\.write_text\(|\.writelines\(|open\([^)]*[",'"'"']w' \
  && echo "$NORM" | grep -qE '(^|[;&|(]\s*)(python|python3|uv run python)\b'; then
  deny "$USE_THE_TOOL a python script writing a file."
fi

# Redirects and tee into a source or config file that is not a scratch path — each target on its
# own, so one harmless `> /tmp/x` does not excuse a `> src/main.py` later in the same command.
REDIRECT_TARGETS=$(echo "$NORM" |
  grep -oE '(>>?|tee(\s+-[^ ]+)*)\s*"?'"'"'?[^ ;&|"'"'"']*\.(py|md|toml|json|ya?ml|cfg|ini|txt|sh|html|css|js)\b' |
  sed -E 's/^(>>?|tee([[:space:]]+-[^ ]+)*)[[:space:]]*["'"'"']?//' || true)
while IFS= read -r target; do
  [[ -z "$target" ]] && continue
  case "$target" in
    /tmp/*|/private/tmp/*|/dev/null) ;;
    *) deny "$USE_THE_TOOL a shell redirect into a source file ($target)." ;;
  esac
done <<< "$REDIRECT_TARGETS"

exit 0
