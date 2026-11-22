#!/bin/bash
# slice.sh -- one slice from build to review, in one command, with one report to paste.
#
#   ARCHITECT_LIVE=1 bash slice.sh <slice id> inbox/<spec>.md
#
# It runs, in order and once each: r3.sh (one builder call), review_task.sh (no call), r4.sh
# (one reviewer call). It stops at the first step that does not exit 0 and runs nothing after
# it. It commits the review task and the review, and nothing else. It never runs a slice
# twice, never starts a second slice, never changes limits.env or any cap, never clears a
# hold, never writes under work/, and never copies anything to the landing place.
# The next slice waits for a person: this script ends after one.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$ROOT" || exit 5
ID="${1:-}"
SPEC="${2:-}"
if [ $# -ne 2 ] || ! [[ "$ID" =~ ^[a-z0-9][a-z0-9-]{0,40}$ ]] || ! [[ "$SPEC" =~ ^inbox/[A-Za-z0-9._-]+\.md$ ]]; then
  echo "REFUSED usage: ARCHITECT_LIVE=1 bash slice.sh <slice id> inbox/<spec>.md"; exit 2
fi
if [ "${ARCHITECT_LIVE:-}" != "1" ]; then
  echo "REFUSED this makes one builder call and one reviewer call. Set ARCHITECT_LIVE=1 to say so."; exit 2
fi
if [ ! -f "inbox/$ID.yaml" ] || [ ! -f "$SPEC" ]; then
  echo "REFUSED inbox/$ID.yaml or $SPEC is not there. Nothing run."; exit 2
fi
if [ -e "work/$ID" ] || [ -e "inbox/$ID-review.yaml" ]; then
  echo "REFUSED $ID already has built files or a review task. A slice is never run twice. Nothing run."; exit 2
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "REFUSED the working tree is not clean. Nothing run."; exit 2
fi
REPORT_DIR="/mnt/c/forge/reports"
[ -d "$REPORT_DIR" ] || REPORT_DIR="$ROOT/outbox"
mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/slice-$ID-$(date +%Y%m%d-%H%M%S).txt"
{
  echo "=== slice $ID  $(date -Iseconds) ==="
  echo "before: $(git log -1 --format='%h %s')"
  echo "--- 1 of 3: build (one builder call)"
  bash "$ROOT/r3.sh" "inbox/$ID.yaml"
  RC=$?
  if [ "$RC" != 0 ]; then
    echo "RESULT: STOPPED at the build, exit $RC. No review was run and nothing was committed. Do not run it again."
    exit "$RC"
  fi
  echo "--- 2 of 3: review task (no call)"
  bash "$ROOT/review_task.sh" "inbox/$ID.yaml" "$SPEC"
  RC=$?
  if [ "$RC" != 0 ]; then
    echo "RESULT: STOPPED at the review task, exit $RC. No review call was made and nothing was committed."
    exit "$RC"
  fi
  git add "inbox/$ID-review.yaml" && git commit -q -m "Review task for $ID"
  echo "--- 3 of 3: review (one reviewer call)"
  bash "$ROOT/r4.sh" "inbox/$ID-review.yaml"
  RC=$?
  if ls rulings/*-"$ID"-review*.md >/dev/null 2>&1; then
    git add rulings/ && git commit -q -m "Review of $ID"
  fi
  git push 2>&1 | tail -1
  echo "--- the build report"
  cat outbox/*-"$ID".md 2>/dev/null
  echo "--- the review"
  cat rulings/*-"$ID"-review*.md 2>/dev/null
  echo "after:  $(git log -1 --format='%h %s')"
  if [ "$RC" != 0 ]; then
    echo "RESULT: STOPPED at the review, exit $RC. The files stay where they are. Do not run it again."
    exit "$RC"
  fi
  echo "RESULT: OK $ID is built and reviewed with nothing blocking. Stop here. The next slice waits for a ruling."
} 2>&1 | tee "$REPORT"
RC=${PIPESTATUS[0]}
echo "report: $REPORT  (paste or attach this one file)"
exit "$RC"
