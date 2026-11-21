#!/bin/bash
# r2.sh -- architect-run R2: one spec round. One reviewer call, to api.x.ai only.
#
#   bash r2.sh inbox/<task>.yaml --fixture tests/fixtures/ok.json   dry run, no network, $0
#   ARCHITECT_LIVE=1 bash r2.sh inbox/<task>.yaml                    the real call (asks for sudo)
#
# The live call is made by user `architect` from an empty environment. The spec is
# read, never written. Rulings land in rulings/. Exit codes are the same as run.sh.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$ROOT/r2.py" "$@"
