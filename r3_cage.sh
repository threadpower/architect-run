#!/bin/bash
# r3_cage.sh -- run one test module inside the cage. Started by r3.py, never by hand.
#
#   r3_cage.sh <run directory under work/> <test module> <seconds>
#
# The container flags come from cage/cage.sh and are used exactly as that file gives
# them. This script adds no flag, no mount, no network and no environment variable.
# Exit: the tests' own exit code | 124 timed out | 90 the cage could not be started.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
. "$ROOT/cage/cage.sh"
RUN="${1:-}"; MOD="${2:-}"; SECS="${3:-}"
case "$RUN" in "$ROOT"/work/?*) ;; *) echo "cage: run directory must be under work/"; exit 90 ;; esac
[ -d "$RUN" ] && [ ! -L "$RUN" ] || { echo "cage: run directory is missing or a link"; exit 90; }
[[ "$MOD" =~ ^[a-z_][a-z0-9_]*$ ]] || { echo "cage: bad test module name"; exit 90; }
[[ "$SECS" =~ ^[0-9]+$ ]] && [ "$SECS" -ge 1 ] && [ "$SECS" -le 600 ] || { echo "cage: bad time limit"; exit 90; }
docker version >/dev/null 2>&1 || { echo "cage: docker is not answering"; exit 90; }
IMAGE="$(cage_image)" || true
[ -n "${IMAGE:-}" ] || { echo "cage: no local python image (this never pulls one)"; exit 90; }
NAME="architect-r3-$(date +%Y%m%d-%H%M%S)-$$"
cage_args "$RUN" "$NAME"
timeout "$SECS" docker run "${CAGE_ARGS[@]}" "$IMAGE" "${CAGE_ENV[@]}" python3 -B -m unittest "$MOD"
RC=$?
if [ "$RC" = 124 ]; then docker kill "$NAME" >/dev/null 2>&1; fi
if [ "$RC" -ge 125 ] && [ "$RC" -le 127 ]; then echo "cage: docker could not run the container ($RC)"; exit 90; fi
exit "$RC"
