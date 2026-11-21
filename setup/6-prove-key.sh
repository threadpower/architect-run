#!/bin/bash
# Step 6. Is keys/xai a different key from the XAI_API_KEY line in /forge/secrets.env?
# Prints exactly one word and nothing else:
#   DIFFER  (exit 0)  the Architect has its own key
#   MATCH   (exit 1)  keys/xai is a copy of the shared key
# Prints nothing and exits 2 if either one cannot be read. No key and no hash is ever printed.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
norm() { tr -d ' \t\r\n"'"'"; }
[ -r "$ROOT/keys/xai" ] && [ -r /forge/secrets.env ] || exit 2
A="$(norm < "$ROOT/keys/xai")"
B="$(grep -m1 '^XAI_API_KEY=' /forge/secrets.env | cut -d= -f2- | norm)"
[ -n "$A" ] && [ -n "$B" ] || exit 2
HA="$(printf '%s' "$A" | sha256sum)"; HB="$(printf '%s' "$B" | sha256sum)"
A=""; B=""
if [ "$HA" = "$HB" ]; then echo MATCH; exit 1; fi
echo DIFFER; exit 0
