#!/usr/bin/env bash
# spec-staleness-check.sh
# PostToolUse hook: warns when a modified source file is covered by a spec.
# Non-blocking — Claude receives the warning as additionalContext and can
# mention it when it finishes its current task.

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$FILE_PATH" ]] && exit 0

# Only application code is spec-covered.
case "$FILE_PATH" in
  *.py) ;;
  *) exit 0 ;;
esac
case "$FILE_PATH" in
  */.venv/*|*/alembic/*|*/tests/*|*_test.py|test_*.py|*/__init__.py) exit 0 ;;
esac

BASENAME=$(basename "$FILE_PATH")
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)}"
[[ -z "$PROJECT_DIR" ]] && exit 0

# Specs live in specs/<type>/<context>/<behavior>.md, indexed by specs/INDEX.md.
MATCHES=()
while IFS= read -r spec_file; do
  # The `context:` frontmatter block sits in the first lines of every spec.
  if head -20 "$spec_file" | grep -q "$BASENAME" 2>/dev/null; then
    MATCHES+=("${spec_file#"$PROJECT_DIR"/}")
  fi
done < <(find "$PROJECT_DIR/specs" -name '*.md' -not -name 'INDEX.md' 2>/dev/null)

if [[ ${#MATCHES[@]} -gt 0 ]]; then
  WARNING=$(printf "Spec coverage detected for: %s" "$FILE_PATH")
  for match in "${MATCHES[@]}"; do
    WARNING=$(printf "%s\n-> %s" "$WARNING" "$match")
  done
  WARNING=$(printf "%s\nConsider running: /spec-verify %s" "$WARNING" "$FILE_PATH")

  # Non-blocking: additionalContext is silently added to Claude's context.
  jq -n --arg msg "$WARNING" '{
    "hookSpecificOutput": {
      "hookEventName": "PostToolUse",
      "additionalContext": $msg
    }
  }'
fi

exit 0
