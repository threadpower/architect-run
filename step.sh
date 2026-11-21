#!/bin/bash
# step.sh -- apply one patch, test it, commit it, and write one report to paste. Operator tool.
#
#   bash step.sh /mnt/c/forge/<name>.patch "commit message"
#
# It replaces the apply / test / commit / copy-the-output routine with one command.
# It never makes a model call and never starts a live run. It refuses if the tree has
# changes of its own, applies with a umask that keeps new files readable by architect,
# and takes the patch back out if the tests fail. Commits and pushes only on a full pass.
# The report lands beside the patches, in /mnt/c/forge/reports/, never in this repo.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PATCH="${1:-}"; MSG="${2:-}"
unset ARCHITECT_LIVE
[ -n "$PATCH" ] && [ -n "$MSG" ] || { echo 'usage: bash step.sh /mnt/c/forge/<name>.patch "commit message"'; exit 2; }
[ -f "$PATCH" ] || { echo "REFUSED no such patch file: $PATCH"; exit 2; }
PATCH="$(realpath "$PATCH")"
case "$PATCH" in "$ROOT"/*) echo "REFUSED the patch is inside this repo. Keep patches in C:\\forge"; exit 2 ;; esac
cd "$ROOT" || exit 2
[ -z "$(git status --porcelain)" ] || { echo "REFUSED the tree has changes that are not committed:"; git status --short; exit 2; }
OUT="${STEP_REPORT_DIR:-/mnt/c/forge/reports}"
mkdir -p "$OUT" || { echo "REFUSED cannot write reports to $OUT"; exit 2; }
case "$(realpath "$OUT")" in "$ROOT"|"$ROOT"/*) echo "REFUSED reports may not be written inside this repo"; exit 2 ;; esac
REPORT="$OUT/step-$(date +%Y%m%d-%H%M%S).txt"
umask 022
{
  echo "=== step  $(date -Is) ==="
  echo "patch:  $(basename "$PATCH")  sha256 $(sha256sum "$PATCH" | cut -c1-16)..."
  echo "before: $(git log -1 --format='%h %s')"
  if ! git apply --check "$PATCH" 2>&1; then echo "RESULT: REFUSED the patch does not apply. Nothing changed."; exit 3; fi
  git apply "$PATCH" 2>&1
  for c in r2_child.py r3_child.py; do [ -f "$c" ] && chmod 644 "$c"; done
  echo "--- files changed"
  git status --short
  echo "--- tests"
  python3 -W ignore -m unittest discover -s tests 2>&1 | tail -4
  TESTS=${PIPESTATUS[0]}
  if [ "$TESTS" != 0 ]; then
    git apply -R "$PATCH" 2>&1 && git clean -fdq -- . 2>/dev/null
    echo "RESULT: FAIL the tests did not pass. The patch was taken back out. Nothing committed."
    exit 4
  fi
  echo "--- preflight --model (information only)"
  bash preflight.sh --model 2>&1 | tail -14
  echo "--- commit"
  git add -A && git commit -q -m "$MSG" && git push 2>&1 | tail -2
  echo "after:  $(git log -1 --format='%h %s')"
  git show --stat --format= HEAD | tail -25
  echo "RESULT: OK committed and pushed. No model call was made."
} 2>&1 | tee "$REPORT"
RC=${PIPESTATUS[0]}
echo
echo "report: $REPORT  (paste or attach this one file)"
exit "$RC"
