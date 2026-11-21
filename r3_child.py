#!/usr/bin/env python3
"""r3_child.py -- the only code in architect-run that may talk to api.anthropic.com.

Started by r3.py, never by hand:
  live     sudo runuser -u architect -- env -i PATH=/usr/bin:/bin python3 r3_child.py --live
  fixture  env -i PATH=/usr/bin:/bin python3 r3_child.py --fixture FILE     (no network at all)

Reads one JSON object on stdin: {"request": {...}} plus "key" when live.
Writes one JSON object on stdout: {"ok", "status", "error", "body"}. Never prints the key.
The only host it will talk to is api.anthropic.com. One POST to /v1/messages, no tools.
"""
import json
import os
import sys

HOST = "api.anthropic.com"
URL = "https://" + HOST + "/v1/messages"
ALLOWED_ENV = {"PATH", "LC_CTYPE"}  # LC_CTYPE is set by Python itself under an empty environment


def out(ok, status=None, error=None, body=None):
    sys.stdout.write(json.dumps({"ok": ok, "status": status, "error": error, "body": body}))
    sys.exit(0 if ok else 1)


def main():
    args = sys.argv[1:]
    live = args == ["--live"]
    fixture = args[1] if len(args) == 2 and args[0] == "--fixture" else None
    if not live and not fixture:
        out(False, error="usage: --live | --fixture FILE")

    extra = sorted(set(os.environ) - ALLOWED_ENV)
    if extra:
        out(False, error="environment is not clean (%d unexpected variables)" % len(extra))

    try:
        packet = json.loads(sys.stdin.read())
        request = packet["request"]
    except (ValueError, KeyError, TypeError):
        out(False, error="no request on stdin")

    need, may = {"model", "max_tokens", "system", "messages"}, {"thinking"}
    if not isinstance(request, dict) or not need <= set(request) <= need | may:
        out(False, error="request may hold only model, max_tokens, system, messages and thinking (no tools)")

    if fixture:
        if "key" in packet:
            out(False, error="a fixture run must not be given a key")
        try:
            with open(fixture) as fh:
                out(True, status=200, body=json.load(fh))
        except (OSError, ValueError):
            out(False, error="fixture is unreadable")

    # ---- live: who am I? Checked before anything touches the network. ----
    import grp
    uid = os.getuid()
    owner = os.stat(os.path.realpath(__file__)).st_uid
    groups = set()
    for gid in set(os.getgroups()) | {os.getgid()}:
        try:
            groups.add(grp.getgrgid(gid).gr_name)
        except KeyError:
            pass
    if uid == 0 or uid == 1000 or uid == owner or groups & {"docker", "sudo", "adm"}:
        out(False, error="identity refused: a live call must run as the architect user "
                         "(not root, not uid 1000, not the script owner, not in docker or sudo)")
    key = packet.get("key")
    if not isinstance(key, str) or len(key) < 20:
        out(False, error="no key supplied")

    import urllib.error
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_a, **_k):
            return None  # a redirect could point at another host; never follow one

    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(URL, data=json.dumps(request).encode(), method="POST", headers={
        "content-type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": key})
    try:
        with opener.open(req, timeout=240) as resp:
            out(True, status=resp.status, body=json.loads(resp.read().decode()))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode())
        except (ValueError, OSError):
            body = None
        out(False, status=exc.code, error="HTTP %d from %s" % (exc.code, HOST), body=body)
    except Exception as exc:  # network down, timeout, bad JSON
        out(False, error="call failed: %s" % type(exc).__name__)


if __name__ == "__main__":
    main()
