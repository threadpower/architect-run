#!/bin/bash
# cage/prove.sh -- prove the cage. No model, no network of its own, costs $0.
#
#   bash cage/prove.sh
#
# Starts a throwaway container twice and tries to get out of it every way listed
# in Grok's gate 3. One probe succeeding fails the script. Asks for sudo once, to
# check that user `architect` still cannot run docker. Changes nothing on the box:
# its work folder is under work/ and is removed at the end.
#
# PASS here does not touch gate 2 and does not authorize a builder.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
. "$ROOT/cage/cage.sh"
FAILS=0
ok()   { echo "  ok   $*"; }
bad()  { echo "  FAIL $*"; FAILS=$((FAILS+1)); }
stop() { echo "CANNOT RUN: $*"; exit 2; }

[ "$(id -u)" != 0 ] || stop "run this as yourself, not as root"
docker version >/dev/null 2>&1 || stop "docker is not answering (is Docker Desktop up?)"
IMAGE="$(cage_image)" || true
[ -n "${IMAGE:-}" ] || stop "no local python image. Pull one once, by hand: python:3.12-slim. This script never pulls."

STAMP="$(date +%Y%m%d-%H%M%S)-$$"
WORK="$ROOT/work/cage-proof-$STAMP"
NAME="architect-cage-proof-$STAMP"
mkdir -p "$WORK" && chmod 0777 "$WORK" || stop "cannot make $WORK"
cleanup() { [ "${KEEP:-0}" = 1 ] || rm -rf "$WORK"; }
trap cleanup EXIT
cp "$ROOT/cage/probe.py" "$WORK/probe.py" && chmod 0644 "$WORK/probe.py"

echo "=== cage proof  $(date -Iseconds) ==="
echo "image: $IMAGE (already on this box; nothing is pulled)"
echo "work:  $WORK"

# What the probe will try to reach: this host's addresses, every published port,
# every running container by name, and everything on forge-net.
docker ps --format '{{.Names}}|{{.Ports}}' > "$WORK/.ps" 2>/dev/null
docker network inspect forge-net > "$WORK/.net" 2>/dev/null || echo '[]' > "$WORK/.net"
hostname -I > "$WORK/.ips" 2>/dev/null || : > "$WORK/.ips"
python3 - "$WORK" <<'PY' || stop "could not build the target list"
import json, re, sys
work = sys.argv[1]
names, ports, ips = {"warp", "amp", "reverb", "forge-ads", "plane"}, set(), set(open(work + "/.ips").read().split())
for line in open(work + "/.ps"):
    name, _, p = line.strip().partition("|")
    if name:
        names.add(name)
    ports.update(int(x) for x in re.findall(r":(\d+)->", p))
    ports.update(int(x) for x in re.findall(r"->(\d+)/", p))
    ports.update(int(x) for x in re.findall(r"(?:^|, )(\d+)/tcp", p))
try:
    for net in json.load(open(work + "/.net")):
        for cfg in (net.get("IPAM", {}).get("Config") or []):
            if cfg.get("Gateway"):
                ips.add(cfg["Gateway"])
        for c in (net.get("Containers") or {}).values():
            ips.add(c.get("IPv4Address", "").split("/")[0])
            names.add(c.get("Name", ""))
except Exception:
    pass
ips = sorted(i for i in ips if i and ":" not in i)[:24]
json.dump({"ips": ips, "ports": sorted(ports)[:40], "names": sorted(n for n in names if n)[:40]},
          open(work + "/targets.json", "w"))
print("targets: %d addresses, %d ports, %d names" % (len(ips), len(sorted(ports)[:40]), len([n for n in names if n][:40])))
PY
rm -f "$WORK/.ps" "$WORK/.net" "$WORK/.ips"
chmod 0644 "$WORK/targets.json"

gone() {   # the container must not exist after it exits
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    [ -z "$(docker ps -a -q --filter "name=^$1\$" 2>/dev/null)" ] && return 0
    sleep 1
  done
  return 1
}

inside() {   # check the probe's own report, not just its exit code
  local mode="$1" out="$2" rc="$3"
  echo "$out" | sed 's/^/    /'
  if [ "$rc" = 0 ] && echo "$out" | grep -q "^PROBE-COMPLETE mode=$mode checks=[0-9]* fails=0\$"; then
    ok "$mode: every probe inside failed to get out"
  else
    bad "$mode: a probe got out, or the probe did not finish (exit $rc)"
  fi
}

echo
echo "1. how the container is made:"
cage_args "$WORK" "$NAME-1"
docker create "${CAGE_ARGS[@]}" "$IMAGE" "${CAGE_ENV[@]}" python3 /work/probe.py run1 >/dev/null 2>"$WORK/.err" \
  || { cat "$WORK/.err"; rm -f "$WORK/.err"; stop "docker could not create the container"; }
rm -f "$WORK/.err"
docker inspect "$NAME-1" | python3 "$ROOT/cage/inspect_check.py" "$WORK"
[ $? = 0 ] && ok "container config is what cage.sh asked for" || bad "container config is not the cage"

echo
echo "2. run 1, from inside:"
OUT="$(docker start -a "$NAME-1" 2>&1)"; RC=$?
inside run1 "$OUT" "$RC"
if gone "$NAME-1"; then ok "after exit, docker ps -a does not show it"; else bad "the container is still listed after exit"; docker rm -f "$NAME-1" >/dev/null 2>&1; fi

echo
echo "3. run 2, a fresh container on the same work directory:"
cage_args "$WORK" "$NAME-2"
OUT="$(docker run "${CAGE_ARGS[@]}" "$IMAGE" "${CAGE_ENV[@]}" python3 /work/probe.py run2 2>&1)"; RC=$?
inside run2 "$OUT" "$RC"
if gone "$NAME-2"; then ok "after exit, docker ps -a does not show it"; else bad "the container is still listed after exit"; docker rm -f "$NAME-2" >/dev/null 2>&1; fi

echo
echo "4. on the host:"
if [ -f "$WORK/from-run1.txt" ]; then
  OWNER="$(stat -c %u "$WORK/from-run1.txt")"
  if [ "$OWNER" != 0 ]; then ok "the file the container wrote is owned by uid $OWNER, not root"; else bad "the file the container wrote is owned by root"; fi
else
  bad "the container wrote nothing to the work directory, so the run proved nothing"
fi
EXTRA="$(ls -A "$WORK" | grep -vxE 'probe\.py|targets\.json|from-run[12]\.txt' || true)"
[ -z "$EXTRA" ] && ok "the work directory holds only the probe's files" || bad "unexpected files in the work directory: $EXTRA"

echo
echo "5. who can run docker:"
ME="$(id -un)"
ok "$ME ran every docker command above"
if id architect >/dev/null 2>&1; then
  case " $(id -Gn architect) " in
    *" docker "*|*" sudo "*) bad "architect is in the docker or sudo group" ;;
    *) ok "architect is in neither the docker nor the sudo group" ;;
  esac
  if sudo runuser -u architect -- env -i PATH=/usr/bin:/bin docker version >/dev/null 2>&1; then
    bad "architect CAN run docker"
  else
    ok "architect cannot run docker (tried it)"
  fi
else
  bad "no architect user (run setup/5a-make-user.sh)"
fi

echo
if [ "$FAILS" = 0 ]; then
  echo "=== PASS: the cage held. This does not authorize a builder. ==="
else
  echo "=== FAIL ($FAILS) ==="; exit 1
fi
