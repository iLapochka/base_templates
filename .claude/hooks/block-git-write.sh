#!/usr/bin/env bash
# block-git-write.sh
# PreToolUse hook: enforces the repo's hard rules — never commit, never push.
# Blocks any Bash command that would write to history or to a remote.

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

# Normalize whitespace for matching.
NORM=$(echo "$COMMAND" | tr '\n' ' ' | tr -s ' ')

# Global options before the subcommand, including the ones that take a value: `-C dir`, `-c k=v`.
GIT_OPTIONS='(-[Cc]\s+[^ ]+\s+|-[^ ]+\s+)*'

if echo "$NORM" | grep -qE "(^|[;&|(]\s*)git\s+${GIT_OPTIONS}commit\b"; then
  deny "Blocked by CLAUDE.md: never run 'git commit' in this repo. Leave the changes staged/unstaged and report them to the user."
fi

if echo "$NORM" | grep -qE "(^|[;&|(]\s*)git\s+${GIT_OPTIONS}(push|remote\s+add|remote\s+set-url)\b"; then
  deny "Blocked by CLAUDE.md: never run 'git push' or modify remotes in this repo."
fi

exit 0
