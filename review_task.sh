#!/bin/bash
# review_task.sh -- write the R4 review task for a built slice. No model, no network, no sudo, $0.
#
#   bash review_task.sh inbox/<slice>.yaml inbox/<spec>.md
#
# Writes inbox/<id>-review.yaml from the hashes of the files in work/<id>/ and never overwrites
# one. It does not run the review. It prints the command for a person to run.
set -u
unset ARCHITECT_LIVE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$ROOT/review_task.py" "$@"
