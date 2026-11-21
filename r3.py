#!/usr/bin/env python3
"""r3.py -- architect-run R3: one caged run. Started by r3.sh.

One builder call to api.anthropic.com, made by r3_child.py as the `architect` user.
The model writes ONE file of at most 40 lines. The test file is the contract: it is
hash-pinned in the task, it is never sent to the model, and it is never changed.
The file the model wrote is run only inside the cage (r3_cage.sh, which uses
cage/cage.sh unchanged). This program never loads or runs it on the host.
No tools, no retry, no second call, no reviewer, no promotion, no commit.
Exit: 0 OK (tests passed) | 2 refused | 3 denylist | 4 FAIL | 5 preflight or cage | 10 HALT
"""
import datetime
import hashlib
import json
import os
import re
import stat
import subprocess
import sys

BUILDER_MODEL = "claude-haiku-5-5"  # pinned here. A task file cannot choose its builder.
MAX_TOKENS = 1024                   # pinned here.
MAX_LINES = 40                      # one function, one file.
MAX_BYTES = 8 * 1024
ROOT = os.path.dirname(os.path.realpath(__file__))
ARGS = sys.argv[1:]
OK, REFUSED, DENY, FAIL, ENV, HALT = 0, 2, 3, 4, 5, 10
WORK, INBOX, OUTBOX, BUDGET, LOGDIR, KEYS = (os.path.join(ROOT, d) for d in (
    "work", "inbox", "outbox", "budget", "log", "keys"))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
LEDGER = os.path.join(BUDGET, "ledger.json")  # re-pointed below for a fixture run
CHILD = os.path.join(ROOT, "r3_child.py")
CAGE = os.path.join(ROOT, "r3_cage.sh")
NOW = datetime.datetime.now().astimezone()
lines = []


def say(text):
    lines.append(str(text)[:200])


def finish(code, result):
    say("result: " + result)
    block = ["--- %s architect-run R3" % NOW.isoformat(timespec="seconds")] + lines
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


def sha_of(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


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
    finish(REFUSED, "REFUSED usage: r3.sh inbox/<task>.yaml [--fixture FILE]")
if os.path.realpath(os.getcwd()) == "/forge":
    finish(ENV, "REFUSED current directory is /forge; run from %s" % ROOT)

live = os.environ.get("ARCHITECT_LIVE") == "1"
if live and fixture:
    finish(REFUSED, "REFUSED choose one: ARCHITECT_LIVE=1 or --fixture, not both")
if not live and not fixture:
    finish(REFUSED, "REFUSED no live call without ARCHITECT_LIVE=1. For a dry run pass --fixture FILE")

# A fixture run never touches the real ledger, and has a ledger of its own so that a
# dry run cannot open a hold that blocks R1, R2 or a live call.
if not live:
    LEDGER = os.path.join(BUDGET, "ledger.r3.fixture.json")

# ---------------------------------------------------------------- limits and denylist
KEYS_NEEDED = ("TASK_USD", "MONTH_USD", "MONTH_HALT_PCT", "WALL_CLOCK_S", "R3_TASK_USD", "R3_HOLD_USD", "R3_LIVE_MAX",
               "ANTHROPIC_MONTH_USD",
               "ANTHROPIC_IN_PER_M", "ANTHROPIC_OUT_PER_M", "ANTHROPIC_CACHE_WRITE_PER_M",
               "ANTHROPIC_CACHE_READ_PER_M")
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
r3max = L["R3_TASK_USD"]
if r3max <= 0 or r3max > 2 or r3max > L["TASK_USD"]:
    finish(REFUSED, "REFUSED limits.env: R3_TASK_USD must be above 0 and no higher than 2")
# The month is the whole Anthropic budget, with no percentage line: a run starts only if
# what is spent plus one full task cap still fits. At 0 no live call is authorized.
hold_usd, live_max = L["R3_HOLD_USD"], L["R3_LIVE_MAX"]
if hold_usd <= 0 or hold_usd > r3max:
    finish(REFUSED, "REFUSED limits.env: R3_HOLD_USD must be above 0 and no higher than R3_TASK_USD")
if live_max != int(live_max) or live_max > 2:
    finish(REFUSED, "REFUSED limits.env: R3_LIVE_MAX must be a whole number no higher than 2")


def usd(x):
    return "$%.2f" % x if x >= 0.01 or x == 0 else "$%.4f" % x


if live and hold_usd > L["ANTHROPIC_MONTH_USD"]:
    finish(REFUSED, "REFUSED no builder call is authorized: ANTHROPIC_MONTH_USD is $%.2f and one run "
                    "needs %s. No hold placed, no call made." % (L["ANTHROPIC_MONTH_USD"], usd(hold_usd)))
deny = []
try:
    with open(os.path.join(ROOT, "denylist.txt")) as fh:
        deny = [x.strip() for x in fh if x.strip() and not x.strip().startswith("#")]
except OSError:
    pass
if not deny:
    finish(DENY, "REFUSED denylist.txt is missing, empty or unreadable (failing closed)")


def deny_hit(path):
    for entry in deny:
        if entry.startswith("**/"):
            if entry[3:] in path.split("/"):
                return entry
        elif entry == "@self":
            if under(path, ROOT) and not under(path, WORK) and not under(path, INBOX):
                return entry
        elif entry.startswith("@self/"):
            if under(path, os.path.join(ROOT, entry[6:])):
                return entry
        elif under(path, entry):
            return entry
    return None


# ---------------------------------------------------------------- task and the hashed test
task_file = file_in(task_path, [INBOX], "the task file")
task = {}
with open(task_file) as fh:
    for raw in fh:
        raw = raw.rstrip("\n")
        if raw.strip() and not raw.lstrip().startswith("#") and ":" in raw:
            k, v = raw.split(":", 1)
            task[k.strip()] = v.strip().strip('"').strip("'")
say("task: %s" % os.path.relpath(task_file, ROOT))
if task.get("kind") != "r3":
    finish(REFUSED, "REFUSED r3.sh only runs kind: r3")
if not re.fullmatch(r"[A-Za-z0-9._-]{1,60}", task.get("id", "")):
    finish(REFUSED, "REFUSED task needs an id of letters, digits, dot, dash, underscore")
for forbidden in ("model", "builder", "host", "url", "max_tokens", "tools", "reviewer", "retries", "rounds"):
    if forbidden in task:
        finish(REFUSED, "REFUSED a task may not set %s" % forbidden)
prose = task.get("prose", "")
if not 20 <= len(prose) <= 2000:
    finish(REFUSED, "REFUSED task needs a prose line of 20 to 2000 characters")
impl = task.get("impl", "")
if not re.fullmatch(r"[a-z_][a-z0-9_]{0,40}\.py", impl):
    finish(REFUSED, "REFUSED impl must be one plain file name like slug.py")
expect = task.get("expect_sha256", "").lower()
if not re.fullmatch(r"[0-9a-f]{64}", expect):
    finish(REFUSED, "REFUSED no expect_sha256 line for the test file (64 hex). No expect line, no run.")
if not task.get("test"):
    finish(REFUSED, "REFUSED task has no test line")
test_file = file_in(task["test"], [INBOX], "the test file")
test_name = os.path.basename(test_file)
if not re.fullmatch(r"[a-z_][a-z0-9_]{0,40}\.py", test_name) or test_name == impl:
    finish(REFUSED, "REFUSED the test file needs a plain module name different from impl")
with open(test_file, "rb") as fh:  # read-only, once
    test_bytes = fh.read()
test_sha = hashlib.sha256(test_bytes).hexdigest()
say("test: %s  sha256 %s...  (never sent to the model)" % (os.path.relpath(test_file, ROOT), test_sha[:16]))
if test_sha != expect:
    finish(FAIL, "FAIL the test file does not match its expect_sha256 line. No call made. Nothing written.")
if len(test_bytes) > 64 * 1024:
    finish(REFUSED, "REFUSED the test file is larger than 64 KB")

# ---------------------------------------------------------------- where the one file may go
if os.path.islink(WORK):
    finish(DENY, "REFUSED work/ is a symlink")
run_dir = os.path.join(WORK, task["id"] + ("" if live else "-FIXTURE"))
target = os.path.join(run_dir, impl)
for candidate in (os.path.normpath(target), os.path.realpath(target)):
    hit = deny_hit(candidate)
    if hit:
        finish(DENY, "REFUSED impl is on the denylist (%s). Nothing written." % hit)
    if not under(candidate, WORK) or os.path.dirname(candidate) != os.path.realpath(run_dir):
        finish(DENY, "REFUSED impl is outside this run's directory. Nothing written.")
if not live and os.path.isdir(run_dir) and not os.path.islink(run_dir):
    for name in (impl, test_name):          # a dry run may clear only its own two files
        leftover = os.path.join(run_dir, name)
        if os.path.isfile(leftover) and not os.path.islink(leftover):
            os.remove(leftover)
    try:
        os.rmdir(run_dir)
    except OSError:
        pass
if os.path.lexists(run_dir):
    finish(REFUSED, "REFUSED %s already exists. A run never overwrites. Nothing written."
           % os.path.relpath(run_dir, ROOT))
say("target: %s" % os.path.relpath(target, ROOT))

# ---------------------------------------------------------------- build the request
request = {
    "model": BUILDER_MODEL,
    "max_tokens": MAX_TOKENS,
    "system": ("You write one small Python file for a build pipeline. Reply with exactly one JSON object "
               "and nothing else: {\"path\": \"%s\", \"content\": \"<the whole file>\"}. The path must be "
               "exactly that file name. The file must be at most %d lines, use only the Python standard "
               "library, define what is asked and nothing else, and must not read files, open sockets or "
               "start processes. No explanation, no second file." % (impl, MAX_LINES)),
    "messages": [{"role": "user", "content": prose}],
    # claude-haiku-5-5 thinks by default and then answers after a thinking block. This run wants
    # the answer only. No effort field is sent: the default is the one that accepts "disabled".
    "thinking": {"type": "disabled"},
}
request_bytes = json.dumps(request).encode()

# ---------------------------------------------------------------- live only: key and preflight
key = None
if live:
    key_file = os.path.join(KEYS, "anthropic")
    try:
        st = os.lstat(key_file)
        if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o600 or st.st_uid != os.getuid():
            finish(ENV, "REFUSED keys/anthropic must be a plain file, mode 600 and owned by you")
        with open(key_file) as fh:
            key = fh.read().strip()
    except OSError:
        finish(ENV, "REFUSED keys/anthropic is missing (run setup/7a-place-anthropic-key.sh)")
    pre = subprocess.run(["bash", os.path.join(ROOT, "preflight.sh"), "--model"],
                         capture_output=True, text=True, cwd=ROOT)
    if pre.returncode != 0:
        for ln in [x for x in pre.stdout.splitlines() if "FAIL:" in x][:4]:
            say("preflight" + ln.strip()[4:])
        finish(ENV, "REFUSED preflight --model did not pass. No call made.")
    say("preflight: --model passed")
    # The call runs as architect. If architect cannot read the child, it would never start,
    # so that is checked here, before any hold is placed.
    try:
        can = subprocess.run(["sudo", "runuser", "-u", "architect", "--", "test", "-r", CHILD],
                             capture_output=True, text=True, timeout=120).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        can = False
    if not can:
        finish(ENV, "REFUSED user architect cannot read r3_child.py (it needs mode 644). No hold placed, no call made.")
    say("child: architect can read r3_child.py")

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
spent, a_spent = float(m.get("spent_usd", 0.0)), float(m.get("anthropic_usd", 0.0))
# A dry run plays with a month of exactly one hold, so "one hold fills the month" can be seen at $0.
a_month = L["ANTHROPIC_MONTH_USD"] if live else hold_usd
month_halt = L["MONTH_USD"] * L["MONTH_HALT_PCT"] / 100.0
# Live calls started this month. A month that already shows Anthropic spend but no counter
# was written before the counter existed, and that spend was one call.
attempts = m.get("r3_live_attempts", 1 if a_spent > 0 else 0)
attempts = attempts if isinstance(attempts, int) and not isinstance(attempts, bool) and attempts >= 0 else int(live_max)
say("ledger: %s" % os.path.relpath(LEDGER, ROOT))
say("budget: %s Anthropic $%.4f of $%.2f  all providers $%.2f (halt $%.2f)  hold %s  task cap $%.2f"
    % (month, a_spent, a_month, spent, month_halt, usd(hold_usd), r3max))
if ledger["holds"]:
    finish(HALT, "HALT an unreconciled spending hold is open (%s). %s" % (
        ledger["holds"][0].get("id", "?"),
        "Clear it with setup/clear-hold.sh" if live else "Fixture ledger only: delete budget/ledger.r3.fixture.json"))
if a_spent + hold_usd > a_month:
    finish(HALT, "HALT Anthropic spend $%.4f plus this run's hold of %s would pass the month's %s%s"
           % (a_spent, usd(hold_usd), usd(a_month), "" if live else ". Fixture ledger only: delete budget/ledger.r3.fixture.json"))
if live and spent + hold_usd > month_halt:
    finish(HALT, "HALT month spend $%.2f plus this run's hold of %s passes the halt line $%.2f"
           % (spent, usd(hold_usd), month_halt))
if live and attempts >= live_max:
    finish(HALT, "HALT live R3 calls started this month: %d of %d allowed. No hold placed, no call made."
           % (attempts, int(live_max)))
worst = ((len(request_bytes) + 1) // 2 * L["ANTHROPIC_IN_PER_M"] + MAX_TOKENS * L["ANTHROPIC_OUT_PER_M"]) / 1e6
if worst > hold_usd:
    finish(REFUSED, "REFUSED worst-case cost $%.4f is over this run's hold of %s. No hold placed." % (worst, usd(hold_usd)))
hold = {"id": task["id"], "usd": hold_usd, "provider": "anthropic", "at": NOW.isoformat(timespec="seconds")}
ledger["holds"].append(hold)
if live:
    m["r3_live_attempts"] = attempts + 1
save_ledger(ledger)
say("hold: %s placed before the call (worst case estimated at $%.4f)%s"
    % (usd(hold_usd), worst, "; live call %d of %d this month" % (attempts + 1, int(live_max)) if live else ""))

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
    child_err = (proc.stderr or "").strip().splitlines()[-1:] or [""]
    child_err = child_err[0].replace(key, "[key]") if key else child_err[0]
    res = json.loads(proc.stdout)
    if not isinstance(res, dict):
        raise ValueError
except subprocess.TimeoutExpired:
    res = {"ok": False, "error": "timed out"}
except (ValueError, OSError):
    res = {"ok": False, "error": "the child returned nothing usable"}
key = packet = None
if not res.get("ok") and child_err:
    say("child said: %s" % child_err[:150])     # why it failed, so the log can say; the key is never in it
say("call: %s %s, model %s, max_tokens %d" % ("live" if live else "fixture",
    "ok" if res.get("ok") else "failed (%s)" % str(res.get("error"))[:60], BUILDER_MODEL, MAX_TOKENS))

# ---------------------------------------------------------------- reconcile the ledger
body = res.get("body") if isinstance(res.get("body"), dict) else {}
usage = body.get("usage") if isinstance(body.get("usage"), dict) else None
cost = None
if usage:
    def count(name):
        v = usage.get(name, 0)
        return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0
    it, ot = usage.get("input_tokens"), usage.get("output_tokens")
    if isinstance(it, int) and isinstance(ot, int) and not isinstance(it, bool) and it >= 0 and ot >= 0:
        cost = (it * L["ANTHROPIC_IN_PER_M"] + ot * L["ANTHROPIC_OUT_PER_M"]
                + count("cache_creation_input_tokens") * L["ANTHROPIC_CACHE_WRITE_PER_M"]
                + count("cache_read_input_tokens") * L["ANTHROPIC_CACHE_READ_PER_M"]) / 1e6
    for name in ("cost_usd", "total_cost_usd"):     # a dollar figure, if the provider ever sends one
        d = usage.get(name)
        if isinstance(d, (int, float)) and not isinstance(d, bool) and d >= 0:
            cost = max(cost or 0.0, float(d))
if cost is None:
    finish(HALT, "HALT no token usage came back; the %s hold stays open and blocks the next run. "
                 "Nothing written." % usd(hold_usd))
ledger["holds"] = [h for h in ledger["holds"] if h is not hold]
m["spent_usd"] = round(spent + cost, 4)
m["anthropic_usd"] = round(a_spent + cost, 4)
save_ledger(ledger)
say("cost: $%.4f recorded; Anthropic this month now $%.4f" % (cost, m["anthropic_usd"]))
if cost > r3max:
    finish(HALT, "HALT the call cost $%.2f, over this task's $%.2f. Recorded. Nothing written." % (cost, r3max))
if not res.get("ok"):
    finish(FAIL, "FAIL the call did not succeed (%s). Nothing written." % str(res.get("error"))[:60])

# ---------------------------------------------------------------- the reply: one object, one path
raw_blocks = body.get("content") if isinstance(body.get("content"), list) else []
block_types = [str(b.get("type")) if isinstance(b, dict) else "?" for b in raw_blocks]
text_blocks = [b["text"] for b in raw_blocks
               if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str)]
# Only text is ever read or reported. A thinking block's content and signature are never kept.
reply_text = "\n".join(text_blocks).strip()


def reject(code, result):
    """A refused reply is kept as evidence in outbox/ only. It is never written under work/ and never run."""
    os.makedirs(OUTBOX, exist_ok=True)
    name = "%s-%s%s-REJECTED" % (NOW.strftime("%Y-%m-%d"), task["id"], "" if live else "-FIXTURE")
    where, k = os.path.join(OUTBOX, name + ".md"), 1
    while os.path.exists(where):
        k += 1
        where = os.path.join(OUTBOX, "%s-%d.md" % (name, k))
    shown = reply_text[:4000].replace("~~~~", "~~~ ~")
    with open(where, "w") as fh:
        fh.write("\n".join([
            "# R3 rejected reply: %s" % task["id"], "",
            "- Date: %s" % NOW.isoformat(timespec="seconds"),
            "- Mode: %s" % ("live" if live else "FIXTURE, not a real builder call"),
            "- Builder: %s, one call, max_tokens %d" % (BUILDER_MODEL, MAX_TOKENS),
            "- Why: %s" % result,
            "- Content block types, in order: %s" % (", ".join(block_types) or "none"),
            "- stop_reason: %s" % str(body.get("stop_reason"))[:40],
            "- Usage: input %s, output %s tokens" % (usage.get("input_tokens"), usage.get("output_tokens")),
            "- Cost: $%.4f" % cost,
            "- Text length: %d characters%s" % (len(reply_text), " (first 4000 shown)" if len(reply_text) > 4000 else ""),
            "", "## The reply text, as data", "", "~~~~", shown, "~~~~", "",
            "---", "Kept as evidence only. Nothing was written under work/ and nothing was run.", ""]))
    say("evidence: %s" % os.path.relpath(where, ROOT))
    finish(code, result)


try:
    # Exactly one text block. Thinking blocks may come before it and are ignored. Any other block type is refused.
    assert raw_blocks and all(t in ("text", "thinking", "redacted_thinking") for t in block_types)
    assert len(text_blocks) == 1 and block_types.count("text") == 1 and reply_text
    fenced = re.fullmatch(r"```(?:json)?\s*\n(.*)\n```", reply_text, re.S)   # one code fence around it is tolerated
    reply = json.loads(fenced.group(1) if fenced else reply_text)
except (KeyError, IndexError, TypeError, ValueError, AssertionError, AttributeError):
    reject(FAIL, "FAIL the reply was not one JSON object of text. Nothing written.")
if not isinstance(reply, dict) or set(reply) != {"path", "content"}:
    reject(FAIL, "FAIL the reply must be exactly one object with path and content "
                 "(a second file is refused). Nothing written.")
path, content = reply["path"], reply["content"]
if not isinstance(path, str) or not isinstance(content, str) or not path:
    reject(FAIL, "FAIL path and content must be text. Nothing written.")
if os.path.isabs(path) or path.startswith("~") or re.match(r"[A-Za-z]:", path):
    reject(DENY, "REFUSED the reply names an absolute path. Nothing written.")
if ".." in re.split(r"[/\\]", path):
    reject(DENY, "REFUSED the reply's path contains '..'. Nothing written.")
if os.path.basename(path) == test_name:
    reject(DENY, "REFUSED the reply names the test file. Nothing written.")
hit = deny_hit(os.path.normpath(os.path.join(run_dir, path)))
if hit:
    reject(DENY, "REFUSED the reply's path is on the denylist (%s). Nothing written." % hit)
if path != impl:
    reject(DENY, "REFUSED the reply's path is not %s. Nothing written." % impl)
if "\x00" in content or len(content.encode()) > MAX_BYTES or len(content.splitlines()) > MAX_LINES:
    reject(FAIL, "FAIL the file is over %d lines or %d bytes. Nothing written." % (MAX_LINES, MAX_BYTES))
if not content.endswith("\n"):
    content += "\n"

# ---------------------------------------------------------------- write the one file, and the contract beside it
if sha_of(test_file) != test_sha:
    finish(HALT, "HALT the test file changed during the run. Nothing written.")
os.makedirs(WORK, exist_ok=True)
os.mkdir(run_dir, 0o755)
os.chmod(run_dir, 0o755)                     # the cage user may read this directory, never write it
test_copy = os.path.join(run_dir, test_name)
for dest, data in ((test_copy, test_bytes), (target, content.encode())):
    with open(dest, "xb") as fh:
        fh.write(data)
    os.chmod(dest, 0o644)
impl_sha = sha_of(target)
say("wrote: %s (%d lines, sha256 %s...)" % (os.path.relpath(target, ROOT), len(content.splitlines()), impl_sha[:16]))

# ---------------------------------------------------------------- the tests, inside the cage only
wall = max(10, min(int(L["WALL_CLOCK_S"]), 120))
try:
    caged = subprocess.run(["bash", CAGE, run_dir, test_name[:-3], str(wall)],
                           capture_output=True, text=True, timeout=wall + 60)
    cage_rc, cage_out = caged.returncode, (caged.stdout + caged.stderr)
except subprocess.TimeoutExpired:
    cage_rc, cage_out = 124, "the cage did not return in time"
tail = [ln[:160] for ln in cage_out.splitlines()[-25:]]
say("cage: r3_cage.sh (cage/cage.sh unchanged), exit %d" % cage_rc)
same = sha_of(test_file) == test_sha and sha_of(test_copy) == test_sha and sha_of(target) == impl_sha
extra = sorted(set(os.listdir(run_dir)) - {impl, test_name})

verdict = "PASS" if cage_rc == 0 and same and not extra else "FAIL"
if cage_rc == 90:
    verdict = "NOT RUN"
report = ["# R3 caged run: %s" % task["id"], "",
          "- Date: %s" % NOW.isoformat(timespec="seconds"),
          "- Mode: %s" % ("live" if live else "FIXTURE, not a real builder call"),
          "- Builder: %s, one call, max_tokens %d, no tools" % (BUILDER_MODEL, MAX_TOKENS),
          "- Cost: $%.4f" % cost,
          "- Test (the contract): `%s` sha256 `%s`, %s" % (
              os.path.relpath(test_file, ROOT), test_sha, "unchanged" if same else "CHANGED"),
          "- File written: `%s` sha256 `%s`" % (os.path.relpath(target, ROOT), impl_sha),
          "- Run by: `r3_cage.sh` with the flags of `cage/cage.sh`, unchanged. Never run on the host.",
          "- Cage exit code: %d" % cage_rc,
          "- Result: **%s**" % verdict, "",
          "## The file", "", "```python", content.rstrip("\n"), "```", "",
          "## Cage output (last lines)", "", "```"] + tail + ["```", "",
          "---", "Nothing was promoted, committed or sent anywhere. Only Jeremy decides what happens to this file.", ""]
os.makedirs(OUTBOX, exist_ok=True)
base = "%s-%s%s" % (NOW.strftime("%Y-%m-%d"), task["id"], "" if live else "-FIXTURE")
out_path, n = os.path.join(OUTBOX, base + ".md"), 1
while os.path.exists(out_path):
    n += 1
    out_path = os.path.join(OUTBOX, "%s-%d.md" % (base, n))
with open(out_path, "w") as fh:
    fh.write("\n".join(report))
say("report: %s" % os.path.relpath(out_path, ROOT))
if cage_rc == 90:
    finish(ENV, "NOT RUN the cage could not be started (%s). The file was written and not run." % (tail[-1] if tail else "?"))
if not same:
    finish(HALT, "HALT a file changed while the cage ran. See the report.")
if extra:
    finish(FAIL, "FAIL unexpected files appeared in the run directory: %s" % ", ".join(extra)[:60])
if cage_rc != 0:
    finish(FAIL, "FAIL the tests did not pass inside the cage (exit %d). No second call." % cage_rc)
finish(OK, "OK %s: the tests passed inside the cage" % task["id"])
