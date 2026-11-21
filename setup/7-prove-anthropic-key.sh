#!/bin/bash
# Step 7. Is keys/anthropic a parked key of its own, with nothing able to use it?
# Prints exactly one word on standard output:
#   DIFFER  (exit 0)  it differs from Amp's key and from keys/xai, and every item below holds
#   MATCH   (exit 1)  it is a copy of Amp's key or of keys/xai
#   FAIL    (exit 3)  the keys differ but an item below does not hold (the item is named on stderr)
# Exit 1 always and only means MATCH, so a caller that reads only the exit code can tell the two apart.
# Prints nothing and exits 2 if it cannot read the key files, cannot find exactly one
# Anthropic line in the shared secrets file, or cannot test what user architect can read.
# No key and no hash is ever printed. No network. Asks for sudo once, to test architect.
#
# The items: mode 600 and owned by you; ignored by git and not tracked; architect cannot
# read it; limits.env says the console cap is real at 40 and the in-code budget is 0;
# the xAI lines are as ruled; the R2 files never mention this key.
# A script cannot see the Anthropic console. The $40 limit there is Jeremy's written line.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SECRETS=/forge/secrets.env
KF="$ROOT/keys/anthropic"; XF="$ROOT/keys/xai"; LM="$ROOT/limits.env"
norm() { tr -d ' \t\r\n"'"'"; }
[ -f "$KF" ] && [ ! -L "$KF" ] && [ -r "$KF" ] && [ -r "$XF" ] && [ -r "$SECRETS" ] || exit 2
[ "$(grep -c '^ANTHROPIC_API_KEY=' "$SECRETS")" = 1 ] || exit 2
A="$(norm < "$KF")"
B="$(grep -m1 '^ANTHROPIC_API_KEY=' "$SECRETS" | cut -d= -f2- | norm)"
X="$(norm < "$XF")"
[ -n "$A" ] && [ -n "$B" ] && [ -n "$X" ] || exit 2
HA="$(printf '%s' "$A" | sha256sum)"; HB="$(printf '%s' "$B" | sha256sum)"; HX="$(printf '%s' "$X" | sha256sum)"
A=""; B=""; X=""
if [ "$HA" = "$HB" ] || [ "$HA" = "$HX" ]; then HA=""; HB=""; HX=""; echo MATCH; exit 1; fi
HA=""; HB=""; HX=""

# Can we test what architect can read at all? It must be able to read r2_child.py.
as() { sudo runuser -u architect -- "$@"; }
as test -r "$ROOT/r2_child.py" 2>/dev/null || exit 2

BAD=()
[ "$(stat -c '%a %u' "$KF")" = "600 $(id -u)" ] || BAD+=("keys/anthropic is not mode 600 and owned by you")
[ "$(stat -c '%a' "$ROOT/keys")" = "700" ] || BAD+=("keys/ is not mode 700")
git -C "$ROOT" check-ignore -q keys/anthropic 2>/dev/null || BAD+=("keys/anthropic is not ignored by git")
git -C "$ROOT" ls-files --error-unmatch keys/anthropic >/dev/null 2>&1 && BAD+=("keys/anthropic is tracked by git")
as test -r "$KF" 2>/dev/null && BAD+=("architect can read keys/anthropic")
as test -r "$ROOT/keys" 2>/dev/null && BAD+=("architect can list keys/")
val() { grep "^$1=" "$LM" 2>/dev/null | cut -d= -f2- | tr -d '[:space:]'; }
want() { [ "$(grep -c "^$1=" "$LM" 2>/dev/null)" = 1 ] && [ "$(val "$1")" = "$2" ] || BAD+=("limits.env: $1 is not '$2'"); }
want CONSOLE_CAP_ANTHROPIC_IS_REAL yes
want CONSOLE_CAP_ANTHROPIC_USD 40
want ANTHROPIC_MONTH_USD 0
want CONSOLE_CAP_XAI_IS_REAL no
want CONSOLE_CAP_XAI_USD ""
want XAI_MONTH_USD 15
want R2_TASK_USD 2
for f in r2.py r2_child.py r2.sh; do
  grep -qi "anthropic" "$ROOT/$f" 2>/dev/null && BAD+=("$f mentions the Anthropic key")
done

if [ "${#BAD[@]}" -gt 0 ]; then
  for b in "${BAD[@]}"; do echo "not proven: $b" >&2; done
  echo FAIL; exit 3
fi
echo DIFFER; exit 0
