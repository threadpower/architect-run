#!/bin/bash
# land.sh -- copy one reviewed slice to the landing place. No model, no network, no sudo, $0.
#
#   bash land.sh <slice id>
#
# Copies only a slice that is named in landing.txt, whose test is unchanged, and whose built
# files are the ones its one live review read. Never overwrites. Jeremy runs it, by hand.
set -u
unset ARCHITECT_LIVE
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 "$ROOT/land.py" "$@"
