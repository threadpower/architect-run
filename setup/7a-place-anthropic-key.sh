#!/bin/bash
# Step 7a. Park the NEW Anthropic key (workspace architect-builder) in keys/anthropic.
# Paste it when asked; the typing is hidden and nothing about the key is printed.
# Never copy the key from secrets.env: that one is Amp's. This script calls nothing,
# reads no secrets file, and will not overwrite a key that is already there.
# Parking a key does not start a builder. Nothing in this repo uses this file yet.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
KF="$ROOT/keys/anthropic"
grep -qxF "keys/" "$ROOT/.gitignore" 2>/dev/null || { echo "FAIL: keys/ is not in .gitignore. Stop."; exit 1; }
[ -e "$KF" ] && { echo "keys/anthropic already exists. Nothing changed. Remove it by hand first if it is the wrong key."; exit 1; }
umask 077
mkdir -p "$ROOT/keys" && chmod 700 "$ROOT/keys"
k=""
read -rs -p "New Anthropic key from workspace architect-builder (hidden): " k; echo
[ -n "$k" ] || { echo "Nothing entered. Nothing saved."; exit 1; }
[ "${#k}" -ge 20 ] || { k=""; echo "That is too short to be a key. Nothing saved."; exit 1; }
printf '%s\n' "$k" > "$KF" && chmod 600 "$KF"
k=""
echo "keys/anthropic saved, mode $(stat -c '%a' "$KF"). Now run: bash setup/7-prove-anthropic-key.sh"
