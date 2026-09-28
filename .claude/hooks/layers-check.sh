#!/usr/bin/env bash
# layers-check.sh
# PostToolUse hook: checks a written/edited Python file against the repo's hard
# conventions (see CLAUDE.md — presentation/infrastructure -> application -> domain).
# Non-blocking — emits additionalContext so Claude fixes them before finishing.
# The import direction itself is enforced by scripts/check_ddd_layering.py; this
# catches the rules that are not about imports.

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[[ -z "$FILE_PATH" ]] && exit 0
[[ -f "$FILE_PATH" ]] || exit 0

case "$FILE_PATH" in
  *.py) ;;
  *) exit 0 ;;
esac
# core/, alembic/ and tests/ are excluded from linting by code_quality/.ruff.toml.
case "$FILE_PATH" in
  */.venv/*|*/core/*|*/alembic/*|*/tests/*|*_test.py|test_*.py) exit 0 ;;
esac

ISSUES=()

# ── Repo-wide rules ───────────────────────────────────────────────────────────

# Config is read in core/config.py and imported from there.
if grep -nE "os\.environ|os\.getenv" "$FILE_PATH" >/dev/null 2>&1; then
  ISSUES+=("reads the environment directly — add the setting to core/config.py and import \`config\` from there")
fi

# Naive datetimes are ruff's DTZ rules; layering is scripts/check_ddd_layering.py.
# Only what neither of them sees belongs below.

# ── Layer rules ───────────────────────────────────────────────────────────────

ORM_CALL='\bselect\(|\bsession\.|\bAsyncSession\b|\bMapped\b|\bmapped_column\('
VIDEO_CALL='\byt_dlp\b|\bffmpeg\b|\bffprobe\b|\bsubprocess\b|create_subprocess_exec|\bcv2\b'

case "$FILE_PATH" in
  */domain/*)
    if grep -nE "$ORM_CALL|$VIDEO_CALL" "$FILE_PATH" >/dev/null 2>&1; then
      ISSUES+=("domain is pure Python — no ORM, no ffmpeg, no yt-dlp; declare the dependency as an abstract port here and implement it in infrastructure/")
    fi
    ;;
  */application/*)
    if grep -nE "$ORM_CALL|$VIDEO_CALL" "$FILE_PATH" >/dev/null 2>&1; then
      ISSUES+=("use case touches a session, ffmpeg or yt-dlp — go through the port; only infrastructure/ knows a library exists")
    fi
    ;;
  */presentation/*)
    if grep -nE "$ORM_CALL|$VIDEO_CALL" "$FILE_PATH" >/dev/null 2>&1; then
      ISSUES+=("query or video tool call in the presentation layer — a route maps the request to a DTO, awaits one use case, and maps the result back")
    fi
    if grep -nE "await\s+request\.(json|body)\(" "$FILE_PATH" >/dev/null 2>&1; then
      ISSUES+=("route parses the request body by hand — validation lives in a pydantic schema")
    fi
    ;;
  # The only direction check_ddd_layering.py does not cover: it checks the inner layers.
  */infrastructure/*)
    if grep -nE "^\s*from\s+src\.[a-z_]+\.(application|presentation)\b" "$FILE_PATH" >/dev/null 2>&1; then
      ISSUES+=("infrastructure imports an outer layer — it implements the domain's interfaces and depends on nothing above it")
    fi
    ;;
esac

# A download or an ffmpeg render inside a session/transaction holds a connection for minutes.
if grep -nE "$VIDEO_CALL" "$FILE_PATH" >/dev/null 2>&1 &&
   grep -nE "session\.begin\(|async with .*[Ss]ession" "$FILE_PATH" >/dev/null 2>&1; then
  ISSUES+=("a download or render inside a session scope — commit the status first, then run; each transition is its own short write")
fi

# A shell string is how a URL or a caption becomes a command.
if grep -nE "shell\s*=\s*True|create_subprocess_shell|os\.system\(" "$FILE_PATH" >/dev/null 2>&1; then
  ISSUES+=("a shell command — run ffmpeg/yt-dlp with an argument list (create_subprocess_exec), never a shell string")
fi

[[ ${#ISSUES[@]} -eq 0 ]] && exit 0

WARNING=$(printf "Convention check — %s" "$FILE_PATH")
for issue in "${ISSUES[@]}"; do
  WARNING=$(printf "%s\n- %s" "$WARNING" "$issue")
done
WARNING=$(printf "%s\nFix before finishing, then run: make check" "$WARNING")

jq -n --arg msg "$WARNING" '{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": $msg
  }
}'

exit 0
