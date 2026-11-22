#!/usr/bin/env python3
"""r4.py -- architect-run R4: one review of a built slice. Started by r4.sh.

One reviewer call to api.x.ai, made by r2_child.py as the `architect` user, exactly as R2 does.
The reviewer is sent four things and nothing else: the prose the builder was given, the built
files, the frozen test, and the spec paragraphs the slice covers. It is asked two questions:
does the code contradict those paragraphs, and does the code read a file, open a socket, start
a process, read the clock, or import anything outside the standard library.
The built files are read, never changed. Nothing under work/ is written. The review cannot
un-accept the files and may not return code. The verdict lands in rulings/<date>-<id>.md.
Exit: 0 OK (nothing blocking) | 2 refused | 3 denylist | 4 FAIL or BLOCKING | 5 preflight | 10 HALT
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
MAX_OUTPUT_TOKENS = 4000     # pinned here.
MAX_FILE_BYTES = 16 * 1024
MAX_DETAIL = 800
BLOCKING_KINDS = ("contradiction", "forbidden")
ROOT = os.path.dirname(os.path.realpath(__file__))
ARGS = sys.argv[1:]
OK, REFUSED, DENY, FAIL, ENV, HALT = 0, 2, 3, 4, 5, 10
WORK, INBOX, OUTBOX, BUDGET, LOGDIR, RULINGS, KEYS = (os.path.join(ROOT, d) for d in (
    "work", "inbox", "outbox", "budget", "log", "rulings", "keys"))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
LEDGER = os.path.join(BUDGET, "ledger.json")  # re-pointed below for a fixture run
CHILD = os.path.join(ROOT, "r2_child.py")     # the same child R2 uses, unchanged
NOW = datetime.datetime.now().astimezone()
lines = []


def say(text):
    lines.append(str(text)[:200])


def finish(code, result):
    say("result: " + result)
    block = ["--- %s architect-run R4" % NOW.isoformat(timespec="seconds")] + lines
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


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def yaml_lines(path):
    out = {}
    with open(path) as fh:
        for raw in fh:
            raw = raw.rstrip("\n")
            if raw.strip() and not raw.lstrip().startswith("#") and ":" in raw:
                k, v = raw.split(":", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def plain(text):
    """Text with markdown marks and spacing removed, for checking that a pasted sentence is really in the spec."""
    return " ".join(re.sub(r"[*`\\_]", "", text).split())


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
    finish(REFUSED, "REFUSED usage: r4.sh inbox/<task>.yaml [--fixture FILE]")
if os.path.realpath(os.getcwd()) == "/forge":
    finish(ENV, "REFUSED current directory is /forge; run from %s" % ROOT)

live = os.environ.get("ARCHITECT_LIVE") == "1"
if live and fixture:
    finish(REFUSED, "REFUSED choose one: ARCHITECT_LIVE=1 or --fixture, not both")
if not live and not fixture:
    finish(REFUSED, "REFUSED no live call without ARCHITECT_LIVE=1. For a dry run pass --fixture FILE")
if not live:    # a dry run has a ledger of its own and can never block R1, R2, R3 or a live call
    LEDGER = os.path.join(BUDGET, "ledger.r4.fixture.json")

# ---------------------------------------------------------------- limits and denylist
KEYS_NEEDED = ("TASK_USD", "MONTH_USD", "MONTH_HALT_PCT", "WALL_CLOCK_S", "R2_TASK_USD", "XAI_MONTH_USD",
               "XAI_IN_PER_M", "XAI_CACHED_IN_PER_M", "XAI_OUT_PER_M")
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

# ---------------------------------------------------------------- the review task
task_file = file_in(task_path, [INBOX], "the task file")
task = yaml_lines(task_file)
say("task: %s" % os.path.relpath(task_file, ROOT))
if task.get("kind") != "r4":
    finish(REFUSED, "REFUSED r4.sh only runs kind: r4")
if not re.fullmatch(r"[A-Za-z0-9._-]{1,60}", task.get("id", "")):
    finish(REFUSED, "REFUSED task needs an id of letters, digits, dot, dash, underscore")
for forbidden in ("reviewer", "reviewer_model", "model", "host", "url", "max_tokens", "tools", "questions"):
    if forbidden in task:
        finish(REFUSED, "REFUSED a task may not set %s" % forbidden)
for needed in ("slice", "spec", "excerpt", "expect_excerpt_sha256", "files_sha256"):
    if not task.get(needed):
        finish(REFUSED, "REFUSED task has no %s line" % needed)

# ---------------------------------------------------------------- the slice: prose, frozen test, built files
slice_file = file_in(task["slice"], [INBOX], "the slice task")
piece = yaml_lines(slice_file)
names = piece.get("impl", "").split()
if (piece.get("kind") != "r3" or not re.fullmatch(r"[A-Za-z0-9._-]{1,60}", piece.get("id", ""))
        or len(names) not in (1, 3) or not all(re.fullmatch(r"[a-z_][a-z0-9_]{0,40}\.py", n) for n in names)
        or not piece.get("prose") or not piece.get("test")):
    finish(REFUSED, "REFUSED the slice line must name an R3 task with prose, impl and test")
test_file = file_in(piece["test"], [INBOX], "the test file")
test_bytes = read_bytes(test_file)
if sha(test_bytes) != piece.get("expect_sha256", "").lower():
    finish(FAIL, "FAIL the test file does not match the slice's expect_sha256 line. No call made.")
wanted = task["files_sha256"].lower().split()
if len(wanted) != len(names) or not all(re.fullmatch(r"[0-9a-f]{64}", h) for h in wanted):
    finish(REFUSED, "REFUSED files_sha256 needs one 64-hex hash for each of: %s" % " ".join(names))
if os.path.islink(WORK):
    finish(DENY, "REFUSED work/ is a symlink")
built_dir = os.path.join(WORK, piece["id"])
built = {}
for name, want in zip(names, wanted):
    path = os.path.join(built_dir, name)
    try:
        st = os.lstat(path)
    except OSError:
        finish(REFUSED, "REFUSED %s is missing. There is nothing to review." % os.path.relpath(path, ROOT))
    if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE_BYTES or os.path.realpath(path) != os.path.join(
            os.path.realpath(built_dir), name):
        finish(DENY, "REFUSED %s is not a plain file inside its run directory" % os.path.relpath(path, ROOT))
    built[name] = read_bytes(path)
    if sha(built[name]) != want:
        finish(FAIL, "FAIL %s does not match its files_sha256 hash. No call made." % os.path.relpath(path, ROOT))
listing = sorted(os.listdir(built_dir))
say("slice: %s  files %s  (hashes match)" % (piece["id"], ", ".join(names)))
say("test: %s  sha256 %s...  (frozen; the reviewer may read it and may not amend it)"
    % (os.path.relpath(test_file, ROOT), sha(test_bytes)[:16]))

# ---------------------------------------------------------------- the spec paragraphs this slice covers
excerpt_file = file_in(task["excerpt"], [INBOX], "the excerpt")
excerpt_bytes = read_bytes(excerpt_file)
if sha(excerpt_bytes) != task["expect_excerpt_sha256"].lower():
    finish(FAIL, "FAIL the excerpt does not match its expect_excerpt_sha256 line. No call made.")
spec_file = file_in(task["spec"], [INBOX], "the spec")
try:
    spec_plain = plain(read_bytes(spec_file).decode("utf-8"))
    paragraphs = [ln.strip() for ln in excerpt_bytes.decode("utf-8").splitlines()
                  if ln.strip() and not ln.lstrip().startswith("#")]
except UnicodeDecodeError:
    finish(REFUSED, "REFUSED the spec or the excerpt is not UTF-8 text")
if not paragraphs or len(excerpt_bytes) > MAX_FILE_BYTES:
    finish(REFUSED, "REFUSED the excerpt is empty or larger than %d KB" % (MAX_FILE_BYTES // 1024))
for n, para in enumerate(paragraphs, 1):
    if plain(para) not in spec_plain:      # every pasted sentence must really be in the spec
        finish(REFUSED, "REFUSED excerpt paragraph %d is not in %s word for word: \"%s...\". No call made."
               % (n, os.path.relpath(spec_file, ROOT), para[:50]))
say("excerpt: %s  %d paragraphs, each found word for word in %s (the rest of the spec is not sent)"
    % (os.path.relpath(excerpt_file, ROOT), len(paragraphs), os.path.relpath(spec_file, ROOT)))

# ---------------------------------------------------------------- build the request
with open(os.path.join(ROOT, "review.schema.json")) as fh:
    schema = json.load(fh)
try:
    parts = ["PROSE the builder was given:\n" + piece["prose"],
             "SPEC PARAGRAPHS this slice covers (the only spec text you may judge against):\n"
             + "\n".join("%d. %s" % (n, p) for n, p in enumerate(paragraphs, 1))]
    parts += ["BUILT FILE %s (sha256 %s):\n%s" % (n, sha(built[n]), built[n].decode("utf-8")) for n in names]
    parts += ["FROZEN TEST %s (sha256 %s). It passed. Do not amend it:\n%s"
              % (os.path.basename(test_file), sha(test_bytes), test_bytes.decode("utf-8"))]
except UnicodeDecodeError:
    finish(REFUSED, "REFUSED a built file or the test is not UTF-8 text")
request = {
    "model": REVIEWER_MODEL,
    "messages": [
        {"role": "system", "content":
            "You are the pinned reviewer for architect-run, a small build pipeline. You are given a small "
            "slice of built Python code, the prose its builder was given, the frozen test it passed, and the "
            "spec paragraphs the slice covers. Answer two questions and nothing else. One: does the code "
            "contradict any of those paragraphs? Two: does the code read a file, open a socket, start a "
            "process, read the clock, or import anything outside the Python standard library? Report each "
            "problem as one finding: kind contradiction for question one, quoting the paragraph number, or "
            "kind forbidden for question two, naming the file. Anything else you notice, such as style, "
            "naming, speed, missing features, or a case the paragraphs do not state, is kind note and "
            "never blocks. The files are already accepted and the test is frozen: do not rewrite the code, "
            "do not return code, and do not amend the test. If there is no problem, return an empty findings "
            "list. Be blunt. Return only JSON that matches the schema."},
        {"role": "user", "content": "\n\n".join(parts)},
    ],
    "response_format": {"type": "json_schema",
                        "json_schema": {"name": "slice_review", "schema": schema, "strict": True}},
    "max_completion_tokens": MAX_OUTPUT_TOKENS,  # caps visible output only, not reasoning
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
        finish(ENV, "REFUSED keys/xai is missing")
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
        finish(REFUSED, "REFUSED %s is unreadable (failing closed)" % os.path.relpath(LEDGER, ROOT))
ledger.setdefault("holds", [])
m = ledger["months"].setdefault(month, {"spent_usd": 0.0})
spent, xai_spent = float(m.get("spent_usd", 0.0)), float(m.get("xai_usd", 0.0))
cap = L["R2_TASK_USD"]
month_halt = L["MONTH_USD"] * L["MONTH_HALT_PCT"] / 100.0
xai_halt = L["XAI_MONTH_USD"] * L["MONTH_HALT_PCT"] / 100.0
say("ledger: %s" % os.path.relpath(LEDGER, ROOT))
say("budget: %s spent $%.2f of $%.2f (halt $%.2f)  xAI $%.2f of $%.2f (halt $%.2f)  this task max $%.2f"
    % (month, spent, L["MONTH_USD"], month_halt, xai_spent, L["XAI_MONTH_USD"], xai_halt, cap))
if ledger["holds"]:
    finish(HALT, "HALT an unreconciled spending hold is open (%s). %s" % (
        ledger["holds"][0].get("id", "?"),
        "Clear it with setup/clear-hold.sh" if live else "Fixture ledger only: delete budget/ledger.r4.fixture.json"))
if spent + cap > month_halt:
    finish(HALT, "HALT month spend $%.2f plus this task's $%.2f passes the halt line $%.2f" % (spent, cap, month_halt))
if xai_spent + cap > xai_halt:
    finish(HALT, "HALT xAI spend $%.2f plus this task's $%.2f passes the halt line $%.2f" % (xai_spent, cap, xai_halt))
worst = ((len(request_bytes) + 1) // 2 * L["XAI_IN_PER_M"] + MAX_OUTPUT_TOKENS * L["XAI_OUT_PER_M"]) / 1e6
if worst > cap:
    finish(REFUSED, "REFUSED worst-case cost $%.2f is over this task's $%.2f" % (worst, cap))
hold = {"id": task["id"], "usd": cap, "provider": "xai", "at": NOW.isoformat(timespec="seconds")}
ledger["holds"].append(hold)
save_ledger(ledger)
say("hold: $%.2f placed before the call (worst case estimated at $%.4f)" % (cap, worst))

# ---------------------------------------------------------------- the one call
clean = ["env", "-i", "PATH=/usr/bin:/bin", "python3", CHILD]
if live:
    cmd = ["sudo", "runuser", "-u", "architect", "--"] + clean + ["--live"]
    packet = {"key": key, "request": request}       # the key travels on stdin only
else:
    cmd = clean + ["--fixture", file_in(fixture, [FIXTURES, INBOX], "the fixture")]
    packet = {"request": request}
child_err = ""
try:
    proc = subprocess.run(cmd, input=json.dumps(packet), capture_output=True, text=True,
                          timeout=min(int(L["WALL_CLOCK_S"]), 300))
    child_err = ((proc.stderr or "").strip().splitlines()[-1:] or [""])[0]
    child_err = child_err.replace(key, "[key]") if key else child_err
    res = json.loads(proc.stdout)
    if not isinstance(res, dict):
        raise ValueError
except subprocess.TimeoutExpired:
    res = {"ok": False, "error": "timed out"}
except (ValueError, OSError):
    res = {"ok": False, "error": "the child returned nothing usable"}
key = packet = None
say("call: %s %s, reviewer %s" % ("live" if live else "fixture",
    "ok" if res.get("ok") else "failed (%s)" % str(res.get("error"))[:60], REVIEWER_MODEL))
if not res.get("ok") and child_err:
    say("child said: %s" % child_err[:150])

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
        cost = ((pt - cached) * L["XAI_IN_PER_M"] + cached * L["XAI_CACHED_IN_PER_M"]
                + (ct + reasoning) * L["XAI_OUT_PER_M"]) / 1e6
    ticks = usage.get("cost_in_usd_ticks")
    if isinstance(ticks, (int, float)) and not isinstance(ticks, bool) and ticks >= 0:
        cost = max(cost or 0.0, ticks / 1e10)
if cost is None:
    finish(HALT, "HALT no token usage came back; the $%.2f hold stays open and blocks the next run" % cap)
ledger["holds"] = [h for h in ledger["holds"] if h is not hold]
m["spent_usd"] = round(spent + cost, 4)
m["xai_usd"] = round(xai_spent + cost, 4)
save_ledger(ledger)
say("cost: $%.4f (greater of token formula and provider figure); xAI this month now $%.4f" % (cost, m["xai_usd"]))
if cost > cap:
    finish(HALT, "HALT the call cost $%.2f, over this task's $%.2f. Recorded. No review written." % (cost, cap))

# ---------------------------------------------------------------- nothing that was read may have changed
unchanged = (sha(read_bytes(test_file)) == sha(test_bytes) and sha(read_bytes(excerpt_file)) == sha(excerpt_bytes)
             and all(sha(read_bytes(os.path.join(built_dir, n))) == sha(built[n]) for n in names)
             and sorted(os.listdir(built_dir)) == listing)
if not unchanged:
    finish(HALT, "HALT a file changed during the review. No review written.")
if not res.get("ok"):
    finish(FAIL, "FAIL the call did not succeed (%s). No review written." % str(res.get("error"))[:60])

# ---------------------------------------------------------------- validate the answer and write the review
allowed_files = set(names) | {os.path.basename(test_file), ""}
try:
    data = json.loads(body["choices"][0]["message"]["content"])
    assert isinstance(data, dict) and set(data) == {"summary", "findings"}
    assert isinstance(data["summary"], str) and isinstance(data["findings"], list)
    for f in data["findings"]:
        assert isinstance(f, dict) and set(f) == {"file", "kind", "detail"}
        assert f["kind"] in BLOCKING_KINDS + ("note",) and isinstance(f["file"], str) and isinstance(f["detail"], str)
        assert f["file"] in allowed_files
except (KeyError, IndexError, TypeError, ValueError, AssertionError):
    finish(FAIL, "FAIL the reviewer's answer did not match the review schema. No review written.")
texts = [data["summary"]] + [f["detail"] for f in data["findings"]]
if any("```" in t or len(" ".join(t.split())) > MAX_DETAIL
       or re.search(r"(?m)^\s*(def \w+\(|class \w+[(:])", t) for t in texts):
    finish(FAIL, "FAIL the reviewer returned code or an oversize finding. A review may not return code. "
                 "No review written.")
blocking = [f for f in data["findings"] if f["kind"] in BLOCKING_KINDS]


def cell(text):
    return " ".join(str(text).split()).replace("|", "\\|") or "-"


md = ["# Review: %s" % task["id"], "",
      "- Date: %s" % NOW.isoformat(timespec="seconds"),
      "- Slice: `%s`" % os.path.relpath(slice_file, ROOT),
      "- Reviewer: %s, one call, %s" % (REVIEWER_MODEL, "live" if live else "FIXTURE, not a real review"),
      "- Cost: $%.4f" % cost]
md += ["- Read, not changed: `%s` sha256 `%s`" % (os.path.relpath(os.path.join(built_dir, n), ROOT), sha(built[n]))
       for n in names]
md += ["- Frozen test: `%s` sha256 `%s`" % (os.path.relpath(test_file, ROOT), sha(test_bytes)),
       "- Spec paragraphs sent: %d, from `%s` sha256 `%s`" % (
           len(paragraphs), os.path.relpath(excerpt_file, ROOT), sha(excerpt_bytes)),
       "- Asked: does the code contradict those paragraphs; does it read a file, open a socket, start a "
       "process, read the clock, or import anything outside the standard library. Nothing else can block.", "",
       "## Summary", "", cell(data["summary"]), "",
       "## Findings", "", "| # | File | Kind | Detail |", "| --- | --- | --- | --- |"]
md += ["| %d | %s | %s | %s |" % (n, cell(f["file"]), f["kind"].upper(), cell(f["detail"]))
       for n, f in enumerate(data["findings"], 1)] or ["| - | - | - | none |"]
md += ["", "## Blocking", ""] + (["- %s: %s" % (cell(f["file"]), cell(f["detail"])) for f in blocking] or ["- none"])
md += ["", "---", "Written by the orchestrator from the reviewer's JSON. The built files and the test were read "
       "and not changed, and nothing was written under work/. This review returned no code and cannot "
       "un-accept the files. Only Jeremy decides what happens to them.", ""]
os.makedirs(RULINGS, exist_ok=True)
base = "%s-%s%s" % (NOW.strftime("%Y-%m-%d"), task["id"], "" if live else "-FIXTURE")  # fixture files are gitignored
out_path, n = os.path.join(RULINGS, base + ".md"), 1
while os.path.exists(out_path):
    n += 1
    out_path = os.path.join(RULINGS, "%s-%d.md" % (base, n))
with open(out_path, "w") as fh:
    fh.write("\n".join(md))
say("review: %s (%d findings, %d blocking)" % (os.path.relpath(out_path, ROOT), len(data["findings"]), len(blocking)))
if blocking:
    finish(FAIL, "BLOCKING %d finding(s). The slice stops here. The files stay where they are. No fix-up call."
           % len(blocking))
finish(OK, "OK %s: nothing blocking" % task["id"])
