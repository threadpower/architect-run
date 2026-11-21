#!/bin/bash
# cage/cage.sh -- the one place the cage's container flags are written.
# Sourced by cage/prove.sh. It starts nothing by itself.
#
# The cage is a throwaway container for running code a builder wrote:
# no network, no secrets, one work directory, gone when it exits.
# It is not a builder and it does not authorize one.

# Pick a Python image that is already on this box. Never pulls.
cage_image() {
  if [ -n "${CAGE_IMAGE:-}" ]; then
    docker image inspect "$CAGE_IMAGE" >/dev/null 2>&1 && { echo "$CAGE_IMAGE"; return 0; }
    return 1
  fi
  local all pick
  all="$(docker image ls --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -E '^python:[0-9]' | sort -V)"
  pick="$(echo "$all" | grep -- '-slim' | tail -1)"
  [ -n "$pick" ] || pick="$(echo "$all" | tail -1)"
  [ -n "$pick" ] && echo "$pick"
}

# cage_args WORKDIR NAME -> fills the array CAGE_ARGS (everything before the image).
cage_args() {
  local work="$1" name="$2"
  CAGE_ARGS=(
    --rm
    --name "$name"
    --network none
    --ipc none
    --cgroupns private
    --cap-drop ALL
    --security-opt no-new-privileges
    --user 65534:65534
    --pids-limit 256
    --memory 2g
    --mount "type=bind,source=$work,target=/work"
    --workdir /work
    --entrypoint /usr/bin/env
  )
}

# What runs inside: an empty environment, then the command.
CAGE_ENV=(-i PATH=/usr/local/bin:/usr/bin:/bin HOME=/work)
