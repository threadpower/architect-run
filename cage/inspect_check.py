"""cage/inspect_check.py -- reads `docker inspect` JSON on stdin and checks it is the cage."""
import json, re, sys
work = sys.argv[1]
c = json.load(sys.stdin)[0]
h, cfg, fails = c["HostConfig"], c["Config"], 0
def check(name, passed, detail=""):
    global fails
    print("  %s %s%s" % ("ok  " if passed else "FAIL", name, (" -- " + str(detail)) if detail and not passed else ""))
    fails += 0 if passed else 1
check("removed when it exits (--rm)", h.get("AutoRemove") is True)
check("not privileged", h.get("Privileged") is False)
check("network is none", h.get("NetworkMode") == "none", h.get("NetworkMode"))
nets = sorted((c.get("NetworkSettings", {}).get("Networks") or {}).keys())
check("attached to no network but none (not forge-net)", nets == ["none"], nets)
for key, want in (("PidMode", ("",)), ("UTSMode", ("",)), ("UsernsMode", ("",)), ("IpcMode", ("none",)), ("CgroupnsMode", ("private",))):
    check("%s is not the host's" % key, h.get(key) in want, h.get(key))
check("no capability added, all dropped", not h.get("CapAdd") and "ALL" in (h.get("CapDrop") or []))
check("no-new-privileges", any("no-new-privileges" in s for s in (h.get("SecurityOpt") or [])))
check("runs as 65534, not root", cfg.get("User") == "65534:65534", cfg.get("User"))
asked = h.get("Mounts") or []
check("one mount asked for: the work directory", len(asked) == 1 and asked[0].get("Type") == "bind"
      and asked[0].get("Source") == work and asked[0].get("Target") == "/work", asked)
got = c.get("Mounts") or []
check("one mount made, at /work", [m.get("Destination") for m in got] == ["/work"], [m.get("Destination") for m in got])
for key in ("Binds", "VolumesFrom", "Tmpfs", "Devices", "DeviceRequests"):
    check("no %s" % key, not h.get(key), h.get(key))
check("no image volume", not cfg.get("Volumes"), cfg.get("Volumes"))
check("no docker socket anywhere in its config", "docker.sock" not in json.dumps(c))
names = sorted(e.split("=", 1)[0] for e in (cfg.get("Env") or []))
risky = [n for n in names if n != "GPG_KEY" and re.search(r"API|SECRET|TOKEN|PASSW|ANTHROPIC|XAI|OPENAI|META|SIGNAL|KEY", n)]
check("image environment holds no key (names: %s)" % ", ".join(names), not risky, risky)
sys.exit(1 if fails else 0)
