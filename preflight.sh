#!/bin/bash
# preflight.sh -- architect-run: is this box safe to run on right now?
#
#   bash preflight.sh            the no-model path (R1)
#   bash preflight.sh --model    everything a live reviewer call needs (r2.sh runs this itself)
#
# Prints facts and PASS or FAIL. Changes nothing. Reads no secrets file and
# prints no secret value. Exit 0 = pass, 1 = fail.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
MODEL=0; [ "${1:-}" = "--model" ] && MODEL=1
FAILS=(); WARNS=()
fail() { FAILS+=("$1"); }
warn() { WARNS+=("$1"); }
row()  { printf '  %-14s %s\n' "$1" "$2"; }

echo "=== architect-run preflight  $(date -Is)  model=$MODEL ==="

# who and where
UID_NOW="$(id -u)"; GROUPS_NOW="$(id -Gn)"
row "uid" "$UID_NOW ($(id -un 2>/dev/null))"
row "groups" "$GROUPS_NOW"
CWD="$(pwd -P)"
row "cwd" "$CWD"
[ "$CWD" = "/forge" ] && fail "current directory is /forge; run this from $ROOT"

# docker: looked at, never driven
if ! command -v docker >/dev/null 2>&1; then
  DOCKER="not installed"
elif docker info >/dev/null 2>&1; then
  DOCKER="up"
else
  DOCKER="not answering"
fi
row "docker info" "$DOCKER"
if [ "$DOCKER" != "up" ]; then
  if [ "$MODEL" = 1 ]; then fail "docker is $DOCKER"; else warn "docker is $DOCKER (not needed for R1)"; fi
fi

# beacon-seo must be exactly "inactive". failed, unknown and anything else are failures.
SEO="unknown"
command -v systemctl >/dev/null 2>&1 && SEO="$(systemctl is-active beacon-seo.service 2>/dev/null | head -1)"
SEO="${SEO:-unknown}"
row "beacon-seo" "$SEO"
[ "$SEO" = "inactive" ] || fail "beacon-seo.service is $SEO; it must be inactive"

# denylist: present, has entries, and cannot be quietly rewritten by others
DL="$ROOT/denylist.txt"
if [ ! -r "$DL" ]; then
  row "denylist" "MISSING or unreadable"; fail "denylist.txt is missing or unreadable"
else
  N="$(grep -cvE '^[[:space:]]*(#|$)' "$DL")"
  MODE="$(stat -c '%a' "$DL")"
  row "denylist" "$N entries, mode $MODE (run.sh refuses to run without it)"
  [ "$N" -gt 0 ] || fail "denylist.txt has no entries"
  [ -z "$(find "$DL" -perm /022)" ] || fail "denylist.txt is writable by group or others"
fi

# limits: every number present
LM="$ROOT/limits.env"
MISSING=""
for k in TASK_USD TASK_HALT_PCT MONTH_USD MONTH_HALT_PCT ROUNDS DIFF_MAX_LINES DIFF_MAX_FILES NEIGHBOR_MAX_FILES NEIGHBOR_MAX_KB WALL_CLOCK_S R2_TASK_USD ANTHROPIC_MONTH_USD XAI_MONTH_USD XAI_IN_PER_M XAI_CACHED_IN_PER_M XAI_OUT_PER_M R2_MAX_OUTPUT_TOKENS R2_MAX_SPEC_KB; do
  grep -qE "^$k=[0-9]+(\.[0-9]+)?[[:space:]]*$" "$LM" 2>/dev/null || MISSING="$MISSING $k"
done
if [ -n "$MISSING" ]; then row "limits" "missing:$MISSING"; fail "limits.env is missing:$MISSING"
else row "limits" "all present"; fi

# files: nothing here may be writable by group or others
LOOSE="$(find "$ROOT" -maxdepth 2 -not -path '*/.git/*' \( -name '*.sh' -o -name '*.env' -o -name '*.txt' -o -name '*.json' -o -name '*.py' \) -perm /022 2>/dev/null | head -5)"
if [ -n "$LOOSE" ]; then row "file modes" "too open"; fail "writable by group or others: $(echo $LOOSE)"
else row "file modes" "ok"; fi

# .gitignore must keep keys and run output out of git
GI="$ROOT/.gitignore"; GMISS=""
for p in keys/ budget/ work/ outbox/ log/; do grep -qxF "$p" "$GI" 2>/dev/null || GMISS="$GMISS $p"; done
if [ -n "$GMISS" ]; then row "gitignore" "missing:$GMISS"; fail ".gitignore does not ignore:$GMISS"
else row "gitignore" "ok"; fi

# the model path: closed until every condition for a live call is met.
# These checks are about the user the call will run AS (architect), not about
# whoever runs this script: r2.sh is started by the operator and hands the call
# to architect through runuser with an empty environment.
if [ "$MODEL" = 1 ]; then
  OWNER="$(stat -c '%u' "$ROOT")"
  [ "$UID_NOW" = "$OWNER" ] || fail "preflight --model must be run by the owner of $ROOT"
  if A_UID="$(id -u architect 2>/dev/null)"; then
    A_GROUPS="$(id -Gn architect 2>/dev/null)"
    row "architect" "uid $A_UID, groups: $A_GROUPS"
    [ "$A_UID" = "1000" ] && fail "the architect user must not be uid 1000"
    [ "$A_UID" = "0" ] && fail "the architect user must not be root"
    [ "$A_UID" = "$OWNER" ] && fail "the architect user must not own the orchestrator"
    case " $A_GROUPS " in *" docker "*) fail "the architect user must not be in the docker group" ;; esac
    case " $A_GROUPS " in *" sudo "*) fail "the architect user must not be in the sudo group" ;; esac
  else
    row "architect" "no such user"; fail "user architect does not exist (run setup/make-user.sh)"
  fi
  # Console caps: a number means the console enforces it. No number may be a pretend one.
  val() { grep -m1 "^$1=" "$LM" 2>/dev/null | cut -d= -f2- | tr -d '[:space:]'; }
  num() { [[ "$1" =~ ^[0-9]+(\.[0-9]+)?$ ]]; }
  lte() { awk -v a="$1" -v b="$2" 'BEGIN { exit !(a + 0 <= b + 0) }'; }
  IS_REAL="$(val CONSOLE_CAP_XAI_IS_REAL)"; CAP_X="$(val CONSOLE_CAP_XAI_USD)"
  CAP_A="$(val CONSOLE_CAP_ANTHROPIC_USD)"; XM="$(val XAI_MONTH_USD)"; PCT="$(val MONTH_HALT_PCT)"
  case "$IS_REAL" in
    no)
      [ -z "$CAP_X" ] || fail "the xAI console-cap line holds a number while CONSOLE_CAP_XAI_IS_REAL=no"
      if num "$XM" && lte "$XM" 15; then
        echo "  console cap: none; in-code xAI halt is ${PCT}% of \$${XM}"
      else
        fail "XAI_MONTH_USD must be a number no higher than 15 while there is no console cap"
      fi ;;
    yes)
      if ! num "$CAP_X"; then fail "CONSOLE_CAP_XAI_IS_REAL=yes needs a number on the xAI console-cap line"
      elif ! num "$XM" || ! lte "$XM" "$CAP_X"; then fail "XAI_MONTH_USD must not be higher than the xAI console cap"
      else echo "  console cap: \$${CAP_X} on the xAI console; in-code halt is ${PCT}% of \$${XM}"; fi ;;
    *) fail "CONSOLE_CAP_XAI_IS_REAL must be yes or no" ;;
  esac
  # Anthropic: a parked key at most. Nothing here calls Anthropic, so the in-code budget is 0.
  A_REAL="$(val CONSOLE_CAP_ANTHROPIC_IS_REAL)"; AM="$(val ANTHROPIC_MONTH_USD)"; AF="$ROOT/keys/anthropic"
  if ! num "$AM" || ! lte "$AM" 0; then fail "ANTHROPIC_MONTH_USD must be 0: no builder call is authorized"; fi
  case "$A_REAL" in
    no)
      [ -z "$CAP_A" ] || fail "the Anthropic console-cap line holds a number while CONSOLE_CAP_ANTHROPIC_IS_REAL=no"
      [ -e "$AF" ] || [ -L "$AF" ] && fail "keys/anthropic exists while CONSOLE_CAP_ANTHROPIC_IS_REAL=no" ;;
    yes)
      if ! num "$CAP_A" || lte "$CAP_A" 0; then fail "CONSOLE_CAP_ANTHROPIC_IS_REAL=yes needs a number above 0 on the Anthropic console-cap line"
      else echo "  console cap: \$${CAP_A} on the Anthropic console; in-code Anthropic budget is \$0 (no builder)"; fi
      if [ -e "$AF" ] || [ -L "$AF" ]; then
        if [ -f "$AF" ] && [ ! -L "$AF" ] && [ "$(stat -c '%a %u' "$AF")" = "600 $UID_NOW" ]; then row "keys/anthropic" "parked, mode 600, yours (R2 does not use it)"
        else row "keys/anthropic" "wrong mode or owner"; fail "keys/anthropic must be a plain file, mode 600, owned by you"; fi
      else
        row "keys/anthropic" "not placed"
      fi ;;
    *) fail "CONSOLE_CAP_ANTHROPIC_IS_REAL must be yes or no" ;;
  esac
  KF="$ROOT/keys/xai"
  if [ -f "$KF" ] && [ "$(stat -c '%a %u' "$KF")" = "600 $UID_NOW" ]; then row "keys/xai" "present, mode 600, yours"
  else row "keys/xai" "missing or wrong mode"; fail "keys/xai must exist, mode 600, owned by you (run setup/place-keys.sh)"; fi
  row "model path" "checked"
else
  row "model path" "off (no model call on this path)"
fi

echo
for w in "${WARNS[@]:-}"; do [ -n "$w" ] && echo "  note: $w"; done
if [ "${#FAILS[@]}" -gt 0 ]; then
  for f in "${FAILS[@]}"; do echo "  FAIL: $f"; done
  echo "=== PREFLIGHT FAIL ==="; exit 1
fi
echo "=== PREFLIGHT PASS ==="; exit 0
