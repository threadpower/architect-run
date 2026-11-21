#!/bin/bash
# r3.sh -- architect-run R3: one caged run. One builder call, to api.anthropic.com only.
#
#   bash r3.sh inbox/<task>.yaml --fixture tests/fixtures/r3_ok.json   dry run, no network, $0
#   ARCHITECT_LIVE=1 bash r3.sh inbox/<task>.yaml                       the real call (asks for sudo)
#
# The model writes one file. That file is only ever run inside the cage (cage/cage.sh,
# unchanged), never on this host. Nothing is promoted, committed or sent anywhere.
# A live call is refused while ANTHROPIC_MONTH_USD is 0. Exit codes are the same as run.sh.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$ROOT/r3.py" "$@"
