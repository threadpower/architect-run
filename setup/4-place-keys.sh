#!/bin/bash
# Step 4. Put the two NEW keys in keys/, mode 600, owned by you. Nothing is printed.
# Paste each key when asked; the typing is hidden. Never copy a key from secrets.env.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
grep -qxF "keys/" "$ROOT/.gitignore" 2>/dev/null || { echo "FAIL: keys/ is not in .gitignore. Stop."; exit 1; }
umask 077
mkdir -p "$ROOT/keys" && chmod 700 "$ROOT/keys"
place() { # name prompt
  local k=""
  read -rs -p "$2 (hidden; press Enter to skip): " k; echo
  [ -z "$k" ] && { echo "  $1: skipped"; return; }
  [ "${#k}" -lt 20 ] && { echo "  $1: that is too short to be a key; nothing saved"; return; }
  printf '%s\n' "$k" > "$ROOT/keys/$1" && chmod 600 "$ROOT/keys/$1"
  echo "  $1: saved (${#k} characters, mode $(stat -c '%a' "$ROOT/keys/$1"))"
}
place xai "New xAI key"
place anthropic "New Anthropic key"
echo "Now record the console caps in limits.env: CONSOLE_CAP_XAI_USD and CONSOLE_CAP_ANTHROPIC_USD."
