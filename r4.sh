#!/bin/bash
# r4.sh -- architect-run R4: one review of a built slice. One reviewer call, to api.x.ai only.
#
#   bash r4.sh inbox/<task>.yaml --fixture tests/fixtures/r4_clean.json   dry run, no network, $0
#   ARCHITECT_LIVE=1 bash r4.sh inbox/<task>.yaml                          the real call (asks for sudo)
#
# The live call is made by user `architect` from an empty environment, through the same
# child R2 uses. The built files and the test are read, never changed, and nothing under
# work/ is written. The review lands in rulings/. Exit codes are the same as run.sh.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$ROOT/r4.py" "$@"
