"""cage/probe.py -- runs INSIDE the cage. Every probe must fail to get out.

Prints one line per check. Exits 1 if any single probe succeeds in reaching
something it should not, or if a control shows the probe itself is blind.
"""
import fnmatch
import json
import os
import socket
import sys

MODE = sys.argv[1] if len(sys.argv) > 1 else "run1"
FAILS = []
COUNT = 0
MARKER = "/var/tmp/cage-marker"
ENV_ALLOWED = {"PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "PWD"}


def check(name, passed, detail=""):
    global COUNT
    COUNT += 1
    print("  %s %s%s" % ("ok  " if passed else "FAIL", name, (" -- " + detail) if detail else ""))
    if not passed:
        FAILS.append(name)


def can_connect(host, port, timeout=2.0):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True, "connected"
    except Exception as e:  # noqa: BLE001 -- any failure is the wanted result
        return False, type(e).__name__


def can_resolve(name):
    try:
        socket.getaddrinfo(name, 443)
        return True
    except Exception:  # noqa: BLE001
        return False


def can_read(path):
    try:
        if os.path.isdir(path):
            os.listdir(path)
        else:
            with open(path, "rb") as fh:
                fh.read(1)
        return True
    except Exception:  # noqa: BLE001
        return False


print("controls (these must work, or the probe is blind):")
srv = socket.socket()
srv.bind(("127.0.0.1", 0))
srv.listen(1)
ok, _ = can_connect("127.0.0.1", srv.getsockname()[1])
srv.close()
check("control: a loopback connection inside the cage works", ok)
check("control: the probe can read its own file in /work", can_read("/work/probe.py"))

print("identity:")
check("not root inside (uid %d, gid %d)" % (os.getuid(), os.getgid()), os.getuid() != 0 and os.getgid() != 0)
status = open("/proc/self/status").read()
capeff = [l.split()[1] for l in status.splitlines() if l.startswith("CapEff:")]
check("no capabilities", capeff == ["0000000000000000"], ",".join(capeff))
nnp = [l.split()[1] for l in status.splitlines() if l.startswith("NoNewPrivs:")]
check("no-new-privileges is set", nnp == ["1"], ",".join(nnp))

print("environment:")
extra = sorted(set(os.environ) - ENV_ALLOWED)
check("environment holds no key (%d names, all of them plain)" % len(os.environ), not extra, "not allowed: " + ", ".join(extra[:12]))

print("network:")
try:
    ifaces = sorted(os.listdir("/sys/class/net"))
except OSError:
    ifaces = ["?"]
check("only the loopback interface exists", ifaces == ["lo"], ",".join(ifaces))
targets = {"ips": [], "ports": [], "names": []}
try:
    targets = json.load(open("/work/targets.json"))
except Exception:  # noqa: BLE001
    check("targets.json is readable", False)
for host, port in (("1.1.1.1", 443), ("1.1.1.1", 53), ("8.8.8.8", 53)):
    ok, why = can_connect(host, port)
    check("cannot connect to %s:%d" % (host, port), not ok, why)
for name in ["api.x.ai", "api.anthropic.com", "host.docker.internal", "gateway.docker.internal"] + targets["names"]:
    check("DNS fails for %s" % name, not can_resolve(name))
    ok, why = can_connect(name, 443)
    check("cannot connect to %s:443" % name, not ok, why)
ports = sorted(set(targets["ports"] + [80, 443, 8000, 8080]))
for ip in targets["ips"]:
    reached = [p for p in ports if can_connect(ip, p, 1.0)[0]]
    check("cannot reach %s on %d ports (Warp, Amp, Reverb and the rest)" % (ip, len(ports)), not reached,
          "open: %s" % reached if reached else "")

print("files:")
for path in ("/var/run/docker.sock", "/run/docker.sock"):
    check("no docker socket at %s" % path, not os.path.exists(path))
for path in ("/forge", "/mnt/c", "/mnt/wsl", "/keys", "/work/keys", "/run/secrets"):
    check("%s does not exist" % path, not os.path.exists(path))
for path in ("/forge/secrets.env", "/forge/architect-run/keys", "/forge/architect-run/keys/xai",
             "/forge/architect-run/.env", "/forge/.env"):
    check("cannot read %s" % path, not can_read(path))
hits = []
for base, dirs, files in os.walk("/"):
    dirs[:] = [d for d in dirs if os.path.join(base, d) not in ("/proc", "/sys", "/dev")]
    for f in files:
        if f == ".env" or fnmatch.fnmatch(f, ".env.*") or fnmatch.fnmatch(f, "*.env"):
            hits.append(os.path.join(base, f))
check("no .env or secrets file anywhere in the cage", not hits, ", ".join(hits[:5]))
mounts = set()
for line in open("/proc/self/mountinfo"):
    point = line.split()[4]
    if point == "/" or point.startswith(("/proc", "/sys", "/dev")):
        continue
    mounts.add(point)
expected = {"/work", "/etc/resolv.conf", "/etc/hostname", "/etc/hosts"}
check("the only mount from outside is /work", mounts <= expected and "/work" in mounts, ", ".join(sorted(mounts - expected)))
listing = sorted(os.listdir("/work")) if os.path.isdir("/work") else ["(no /work)"]
allowed = {"probe.py", "targets.json", "from-run1.txt", "from-run2.txt"}
check("/work holds only the probe's own files", set(listing) <= allowed, ", ".join(sorted(set(listing) - allowed)))
try:
    with open("/work/from-%s.txt" % MODE, "w") as fh:
        fh.write(MODE + "\n")
    wrote = True
except OSError:
    wrote = False
check("/work is writable", wrote)

print("throwaway:")
if MODE == "run1":
    try:
        with open(MARKER, "w") as fh:
            fh.write("left by run1\n")
        left = True
    except OSError:
        left = False
    check("run 1 left a marker inside the container (%s)" % MARKER, left)
else:
    check("run 2 does not see the marker run 1 left inside the container", not os.path.exists(MARKER))

print("PROBE-COMPLETE mode=%s checks=%d fails=%d" % (MODE, COUNT, len(FAILS)))
sys.exit(1 if FAILS else 0)
