#!/usr/bin/env python3
"""r2.py -- architect-run R2: one spec round. Started by r2.sh.

One reviewer call to api.x.ai, made by r2_child.py as the `architect` user.
The spec is read, never written. Rulings land in rulings/<date>-<id>.md.
Exit: 0 OK | 2 refused | 3 denylist | 4 FAIL | 5 preflight | 10 HALT
"""
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess
import sys

REVIEWER_MODEL = "grok-4.7"  # pinned here. A task file cannot choose its reviewer.
ROOT = os.path.dirname(os.path.realpath(__file__))
ARGS = sys.argv[1:]
OK, REFUSED, DENY, FAIL, ENV, HALT = 0, 2, 3, 4, 5, 10
WORK, INBOX, OUTBOX, BUDGET, LOGDIR, RULINGS, KEYS = (os.path.join(ROOT, d) for d in (
    "work", "inbox", "outbox", "budget", "log", "rulings", "keys"))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
LEDGER = os.path.join(BUDGET, "ledger.json")  # re-pointed below for a fixture run
CHILD = os.path.join(ROOT, "r2_child.py")
NOW = datetime.datetime.now().astimezone()
lines = []


def say(text):
    lines.append(str(text)[:110])


def finish(code, result):
    say("result: " + result)
    block = ["--- %s architect-run R2" % NOW.isoformat(timespec="seconds")] + lines
    print("\n".join(block))
    os.makedirs(LOGDIR, exist_ok=True)
    with open(os.path.join(LOGDIR, "run.log"), "a") as fh:
        fh.write("\n".join(block) + "\n")
    os.makedirs(OUTBOX, exist_ok=True)
    with open(os.path.join(OUTBOX, "notify.txt"), "w") as fh:
        fh.write("%s architect-run: %s\n" % (NOW.isoformat(timespec="seconds"), result))
    sys.exit(code)


def under(path, base):
    base = base.rstrip("/")
    return path == base or path.startswith(base + "/")


def file_in(path, bases, what):
    for start in (os.getcwd(), ROOT):
        full = os.path.realpath(path if os.path.isabs(path) else os.path.join(start, path))
        if os.path.isfile(full) and any(under(full, b) for b in bases):
            return full
    finish(REFUSED, "REFUSED %s must be a file inside %s" % (
        what, " or ".join(os.path.relpath(b, ROOT) + "/" for b in bases)))


def save_ledger(ledger):
    os.makedirs(BUDGET, exist_ok=True)
    tmp = LEDGER + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(ledger, fh, indent=2, sort_keys=True)
    os.replace(tmp, LEDGER)


# ---------------------------------------------------------------- arguments
fixture = None
task_path = None
i = 0
while i < len(ARGS):
    if ARGS[i] == "--fixture" and i + 1 < len(ARGS):
        i += 1
        fixture = ARGS[i]
    elif ARGS[i].startswith("-"):
        finish(REFUSED, "REFUSED unknown option %s" % ARGS[i])
    else:
        task_path = ARGS[i]
    i += 1
if not task_path:
    finish(REFUSED, "REFUSED usage: r2.sh inbox/<task>.yaml [--fixture FILE]")
if os.path.realpath(os.getcwd()) == "/forge":
    finish(ENV, "REFUSED current directory is /forge; run from %s" % ROOT)

live = os.environ.get("ARCHITECT_LIVE") == "1"
if live and fixture:
    finish(REFUSED, "REFUSED choose one: ARCHITECT_LIVE=1 or --fixture, not both")
if not live and not fixture:
    finish(REFUSED, "REFUSED no live call without ARCHITECT_LIVE=1. For a dry run pass --fixture FILE")

# A fixture run never touches the real ledger: a dry run must not be able to open
# a hold that blocks R1 or a live call. run.sh only ever reads budget/ledger.json.
if not live:
    LEDGER = os.path.join(BUDGET, "ledger.fixture.json")

# ---------------------------------------------------------------- limits and denylist
KEYS_NEEDED = ("TASK_USD", "TASK_HALT_PCT", "MONTH_USD", "MONTH_HALT_PCT", "WALL_CLOCK_S",
               "R2_TASK_USD", "XAI_MONTH_USD", "XAI_IN_PER_M", "XAI_CACHED_IN_PER_M",
               "XAI_OUT_PER_M", "R2_MAX_OUTPUT_TOKENS", "R2_MAX_SPEC_KB")
raw_limits = {}
try:
    with open(os.path.join(ROOT, "limits.env")) as fh:
        for raw in fh:
            raw = raw.strip()
            if raw and not raw.startswith("#") and "=" in raw:
                k, v = raw.split("=", 1)
                raw_limits[k.strip()] = v.strip()
except OSError:
    finish(REFUSED, "REFUSED limits.env is missing or unreadable")
L = {}
for k in KEYS_NEEDED:
    try:
        L[k] = float(raw_limits[k])
        if L[k] < 0:
            raise ValueError
    except (KeyError, ValueError):
        finish(REFUSED, "REFUSED limits.env: %s is missing or not a number" % k)
if L["R2_TASK_USD"] > L["TASK_USD"]:
    finish(REFUSED, "REFUSED limits.env: R2_TASK_USD may not exceed TASK_USD")
try:
    with open(os.path.join(ROOT, "denylist.txt")) as fh:
        if not [x for x in fh if x.strip() and not x.strip().startswith("#")]:
            raise OSError
except OSError:
    finish(DENY, "REFUSED denylist.txt is missing, empty or unreadable (failing closed)")

# ---------------------------------------------------------------- task and spec
task_file = file_in(task_path, [INBOX], "the task file")
task = {}
with open(task_file) as fh:
    for raw in fh:
        raw = raw.rstrip("\n")
        if raw.strip() and not raw.lstrip().startswith("#") and ":" in raw:
            k, v = raw.split(":", 1)
            task[k.strip()] = v.strip().strip('"').strip("'")
say("task: %s" % os.path.relpath(task_file, ROOT))
if task.get("kind") != "r2":
    finish(REFUSED, "REFUSED r2.sh only runs kind: r2")
if not re.fullmatch(r"[A-Za-z0-9._-]{1,60}", task.get("id", "")):
    finish(REFUSED, "REFUSED task needs an id of letters, digits, dot, dash, underscore")
for forbidden in ("reviewer", "reviewer_model", "model", "host", "url"):
    if forbidden in task:
        finish(REFUSED, "REFUSED a task may not set %s" % forbidden)
expect = task.get("expect_sha256", "").lower()
if not re.fullmatch(r"[0-9a-f]{64}", expect):
    finish(REFUSED, "REFUSED no expect_sha256 line for the spec (64 hex). No expect line, no run.")
if not task.get("spec"):
    finish(REFUSED, "REFUSED task has no spec line")
spec_file = file_in(task["spec"], [INBOX], "the spec")
with open(spec_file, "rb") as fh:  # read-only, once
    spec_bytes = fh.read()
spec_sha = hashlib.sha256(spec_bytes).hexdigest()
say("spec: %s  sha256 %s..." % (os.path.relpath(spec_file, ROOT), spec_sha[:16]))
if spec_sha != expect:
    finish(FAIL, "FAIL spec does not match its expect_sha256 line. No call made.")
if len(spec_bytes) > L["R2_MAX_SPEC_KB"] * 1024:
    finish(REFUSED, "REFUSED spec is larger than %d KB" % L["R2_MAX_SPEC_KB"])
try:
    spec_text = spec_bytes.decode("utf-8")
except UnicodeDecodeError:
    finish(REFUSED, "REFUSED spec is not UTF-8 text")

# ---------------------------------------------------------------- build the request
with open(os.path.join(ROOT, "rubric.json")) as fh:
    rubric_text = fh.read()
with open(os.path.join(ROOT, "rulings.schema.json")) as fh:
    schema = json.load(fh)
request = {
    "model": REVIEWER_MODEL,
    "messages": [
        {"role": "system", "content":
            "You are the pinned reviewer for architect-run, a small build pipeline. Rule on the spec "
            "you are given, clause by clause: agree, amend or reject, with a one-paragraph reason and, "
            "for amend, replacement wording that could go straight into the spec. List what blocks a "
            "build and every clause that no test could check. Blocking means only a contradiction, or a "
            "proof no test can fail, that this review does not already close with an amendment. An amend "
            "is not blocking. An unset secret is not blocking. Do not list the same clause twice. Be "
            "blunt. Do not rewrite the spec, do not add features, and return only JSON that matches the "
            "schema."},
        {"role": "user", "content":
            "RUBRIC a later build of this spec will be judged by:\n" + rubric_text +
            "\n\nSPEC (sha256 " + spec_sha + "):\n" + spec_text},
    ],
    "response_format": {"type": "json_schema",
                        "json_schema": {"name": "spec_rulings", "schema": schema, "strict": True}},
    "max_completion_tokens": int(L["R2_MAX_OUTPUT_TOKENS"]),  # caps visible output only, not reasoning
    "reasoning_effort": "low",
}
request_bytes = json.dumps(request).encode()

# ---------------------------------------------------------------- live only: key and preflight
key = None
if live:
    key_file = os.path.join(KEYS, "xai")
    try:
        st = os.stat(key_file)
        if stat.S_IMODE(st.st_mode) != 0o600 or st.st_uid != os.getuid():
            finish(ENV, "REFUSED keys/xai must be mode 600 and owned by you")
        with open(key_file) as fh:
            key = fh.read().strip()
    except OSError:
        finish(ENV, "REFUSED keys/xai is missing (run setup/place-keys.sh)")
    pre = subprocess.run(["bash", os.path.join(ROOT, "preflight.sh"), "--model"],
                         capture_output=True, text=True, cwd=ROOT)
    if pre.returncode != 0:
        for ln in [x for x in pre.stdout.splitlines() if "FAIL:" in x][:4]:
            say("preflight" + ln.strip()[4:])
        finish(ENV, "REFUSED preflight --model did not pass. No call made.")
    say("preflight: --model passed")

# ---------------------------------------------------------------- budget: check, then hold
month = NOW.strftime("%Y-%m")
ledger = {"version": 1, "months": {}, "successes": {}, "holds": []}
if os.path.exists(LEDGER):
    try:
        with open(LEDGER) as fh:
            ledger = json.load(fh)
        ledger["months"], ledger["successes"]
    except (OSError, ValueError, KeyError, TypeError):
        finish(REFUSED, "REFUSED budget/ledger.json is unreadable (failing closed)")
ledger.setdefault("holds", [])
m = ledger["months"].setdefault(month, {"spent_usd": 0.0})
spent, xai_spent = float(m.get("spent_usd", 0.0)), float(m.get("xai_usd", 0.0))
r2max = L["R2_TASK_USD"]
month_halt = L["MONTH_USD"] * L["MONTH_HALT_PCT"] / 100.0
xai_halt = L["XAI_MONTH_USD"] * L["MONTH_HALT_PCT"] / 100.0
say("ledger: %s" % os.path.relpath(LEDGER, ROOT))
say("budget: %s spent $%.2f of $%.2f (halt $%.2f)  xAI $%.2f of $%.2f  this task max $%.2f"
    % (month, spent, L["MONTH_USD"], month_halt, xai_spent, L["XAI_MONTH_USD"], r2max))
if ledger["holds"]:
    finish(HALT, "HALT an unreconciled spending hold is open (%s). %s" % (
        ledger["holds"][0].get("id", "?"),
        "Clear it with setup/clear-hold.sh" if live else "Fixture ledger only: delete budget/ledger.fixture.json"))
if spent + r2max > month_halt:
    finish(HALT, "HALT month spend $%.2f plus this task's $%.2f passes the halt line $%.2f"
           % (spent, r2max, month_halt))
if xai_spent + r2max > xai_halt:
    finish(HALT, "HALT xAI spend $%.2f plus this task's $%.2f passes the halt line $%.2f"
           % (xai_spent, r2max, xai_halt))
worst = ((len(request_bytes) + 1) // 2 * L["XAI_IN_PER_M"]
         + L["R2_MAX_OUTPUT_TOKENS"] * L["XAI_OUT_PER_M"]) / 1e6
if worst > r2max:
    finish(REFUSED, "REFUSED worst-case cost $%.2f is over this task's $%.2f" % (worst, r2max))
hold = {"id": task["id"], "usd": r2max, "provider": "xai", "at": NOW.isoformat(timespec="seconds")}
ledger["holds"].append(hold)
save_ledger(ledger)
say("hold: $%.2f placed before the call (worst case estimated at $%.2f)" % (r2max, worst))

# ---------------------------------------------------------------- the one call
os.makedirs(WORK, exist_ok=True)
with open(os.path.join(WORK, task["id"] + ".request.json"), "w") as fh:
    json.dump(request, fh, indent=1)  # the request body never contains the key
clean = ["env", "-i", "PATH=/usr/bin:/bin", "python3", CHILD]
if live:
    cmd = ["sudo", "runuser", "-u", "architect", "--"] + clean + ["--live"]
    packet = {"key": key, "request": request}
else:
    cmd = clean + ["--fixture", file_in(fixture, [FIXTURES, INBOX], "the fixture")]
    packet = {"request": request}
try:
    proc = subprocess.run(cmd, input=json.dumps(packet), capture_output=True, text=True,
                          timeout=min(int(L["WALL_CLOCK_S"]), 300))
    res = json.loads(proc.stdout)
    if not isinstance(res, dict):
        raise ValueError
except subprocess.TimeoutExpired:
    res = {"ok": False, "error": "timed out"}
except (ValueError, OSError):
    res = {"ok": False, "error": "the child returned nothing usable"}
key = packet = None
say("call: %s %s" % ("live" if live else "fixture",
                     "ok" if res.get("ok") else "failed (%s)" % str(res.get("error"))[:60]))

# ---------------------------------------------------------------- reconcile the ledger
body = res.get("body") if isinstance(res.get("body"), dict) else {}
usage = body.get("usage") if isinstance(body.get("usage"), dict) else None
cost = None
if usage:
    pt = usage.get("prompt_tokens", usage.get("input_tokens"))
    ct = usage.get("completion_tokens", usage.get("output_tokens"))
    if isinstance(pt, int) and isinstance(ct, int):
        pd = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
        cd = usage.get("completion_tokens_details") or usage.get("output_tokens_details") or {}
        cached = pd.get("cached_tokens", 0) if isinstance(pd.get("cached_tokens", 0), int) else 0
        reasoning = cd.get("reasoning_tokens", 0) if isinstance(cd.get("reasoning_tokens", 0), int) else 0
        # xAI reports reasoning tokens outside completion_tokens and bills them at the
        # completion price, so they are added here. That is the correct count, not padding.
        cost = ((pt - cached) * L["XAI_IN_PER_M"] + cached * L["XAI_CACHED_IN_PER_M"]
                + (ct + reasoning) * L["XAI_OUT_PER_M"]) / 1e6
    # The provider's own figure, when present: dollars = ticks / 10,000,000,000. It can
    # include charges the token formula cannot see, so the greater of the two is recorded.
    ticks = usage.get("cost_in_usd_ticks")
    if isinstance(ticks, (int, float)) and not isinstance(ticks, bool) and ticks >= 0:
        cost = max(cost or 0.0, ticks / 1e10)
if cost is None:
    finish(HALT, "HALT no token usage came back; the $%.2f hold stays open and blocks the next run" % r2max)
ledger["holds"] = [h for h in ledger["holds"] if h is not hold]
m["spent_usd"] = round(spent + cost, 4)
m["xai_usd"] = round(xai_spent + cost, 4)
save_ledger(ledger)
say("cost: $%.4f (greater of token formula and provider figure); month now $%.2f" % (cost, m["spent_usd"]))

# ---------------------------------------------------------------- the spec must be untouched
with open(spec_file, "rb") as fh:
    if hashlib.sha256(fh.read()).hexdigest() != spec_sha:
        finish(HALT, "HALT the spec file changed during the run. No rulings written.")

# ---------------------------------------------------------------- validate and write rulings
try:
    data = json.loads(body["choices"][0]["message"]["content"])
    assert isinstance(data["summary"], str) and isinstance(data["rulings"], list) and data["rulings"]
    assert isinstance(data["blocking"], list) and isinstance(data["untestable_clauses"], list)
    for r in data["rulings"]:
        assert r["verdict"] in ("agree", "amend", "reject")
        assert all(isinstance(r[f], str) for f in ("clause", "reason", "amendment"))
    assert all(isinstance(x, str) for x in data["blocking"] + data["untestable_clauses"])
except (KeyError, IndexError, TypeError, ValueError, AssertionError):
    finish(FAIL, "FAIL the reviewer's answer did not match the rulings schema. No rulings written.")


def cell(text):
    return " ".join(str(text).split()).replace("|", "\\|") or "-"


md = ["# Rulings: %s" % task["id"], "",
      "- Date: %s" % NOW.isoformat(timespec="seconds"),
      "- Spec: `%s`" % os.path.relpath(spec_file, ROOT),
      "- Spec sha256: `%s` (unchanged by this run)" % spec_sha,
      "- Reviewer: %s, one call, %s" % (REVIEWER_MODEL, "live" if live else "FIXTURE, not a real review"),
      "- Cost: $%.4f" % cost, "",
      "## Summary", "", " ".join(data["summary"].split()), "",
      "## Rulings", "", "| # | Clause | Verdict | Reason | Amendment |", "| --- | --- | --- | --- | --- |"]
for n, r in enumerate(data["rulings"], 1):
    md.append("| %d | %s | %s | %s | %s |" % (n, cell(r["clause"]), r["verdict"].upper(),
                                               cell(r["reason"]), cell(r["amendment"])))
md += ["", "## Blocking", ""] + (["- " + cell(x) for x in data["blocking"]] or ["- none"])
md += ["", "## Clauses no test could check", ""] + (
    ["- " + cell(x) for x in data["untestable_clauses"]] or ["- none"])
md += ["", "---", "Written by the orchestrator from the reviewer's JSON. The spec was not edited. "
       "Only Jeremy changes and freezes a spec.", ""]
os.makedirs(RULINGS, exist_ok=True)
base = "%s-%s%s" % (NOW.strftime("%Y-%m-%d"), task["id"], "" if live else "-FIXTURE")  # fixture files are gitignored
out_path, n = os.path.join(RULINGS, base + ".md"), 1
while os.path.exists(out_path):
    n += 1
    out_path = os.path.join(RULINGS, "%s-%d.md" % (base, n))
with open(out_path, "w") as fh:
    fh.write("\n".join(md))
say("rulings: %s (%d rulings, %d blocking)" % (
    os.path.relpath(out_path, ROOT), len(data["rulings"]), len(data["blocking"])))
if cost > r2max:
    finish(HALT, "HALT rulings written, but the call cost $%.2f, over this task's $%.2f" % (cost, r2max))
finish(OK, "OK %s" % task["id"])
