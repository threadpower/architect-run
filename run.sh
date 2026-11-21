#!/bin/bash
# run.sh -- architect-run: one R1 run. No model, no Docker, no network.
#
#   bash run.sh                      run inbox/r1.yaml
#   bash run.sh inbox/other.yaml     run another task file from inbox/
#   bash run.sh --halt-test          prove the budget ceiling stops a run
#   bash run.sh --verdict inbox/v.json   apply a reviewer verdict (rubric.json rules)
#
# Writes only under work/, outbox/, budget/ and log/ next to this script.
# Reads only limits.env, denylist.txt, rubric.json and files in inbox/.
# Exit: 0 OK | 2 refused | 3 denylist | 4 FAIL | 5 wrong directory | 10 HALT
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
exec python3 - "$ROOT" "$@" <<'PY'
import datetime, hashlib, json, os, re, signal, sys

ROOT = sys.argv[1]
ARGS = sys.argv[2:]
OK, REFUSED, DENY, FAIL, ENV, HALT = 0, 2, 3, 4, 5, 10
WORK, INBOX, OUTBOX, BUDGET, LOGDIR = (os.path.join(ROOT, d) for d in
                                       ("work", "inbox", "outbox", "budget", "log"))
LEDGER = os.path.join(BUDGET, "ledger.json")
NOW = datetime.datetime.now().astimezone()
lines = []


def say(text):
    lines.append(str(text)[:110])


def finish(code, result):
    """Print, append one short block to the log, drop a notify line, exit."""
    say("result: " + result)
    block = ["--- %s architect-run R1" % NOW.isoformat(timespec="seconds")] + lines
    print("\n".join(block))
    try:
        os.makedirs(LOGDIR, exist_ok=True)
        with open(os.path.join(LOGDIR, "run.log"), "a") as fh:
            fh.write("\n".join(block) + "\n")
        os.makedirs(OUTBOX, exist_ok=True)
        # run.sh never sends anything: this file is the only notification.
        with open(os.path.join(OUTBOX, "notify.txt"), "w") as fh:
            fh.write("%s architect-run: %s\n" % (NOW.isoformat(timespec="seconds"), result))
    except OSError as exc:
        print("could not write log/outbox: %s" % exc)
        code = code or ENV
    sys.exit(code)


def under(path, base):
    base = base.rstrip("/")
    return path == base or path.startswith(base + "/")


# ---------------------------------------------------------------- arguments
halt_test = False
verdict_path = None
task_path = os.path.join(INBOX, "r1.yaml")
i = 0
while i < len(ARGS):
    a = ARGS[i]
    if a == "--halt-test":
        halt_test = True
    elif a == "--verdict" and i + 1 < len(ARGS):
        i += 1
        verdict_path = ARGS[i]
    elif a.startswith("-"):
        finish(REFUSED, "REFUSED unknown option %s" % a)
    else:
        task_path = a
    i += 1

if os.path.realpath(os.getcwd()) == "/forge":
    finish(ENV, "REFUSED current directory is /forge; run from %s" % ROOT)


def inbox_file(path, what):
    full = os.path.realpath(path if os.path.isabs(path) else os.path.join(os.getcwd(), path))
    if not os.path.isfile(full):
        alt = os.path.realpath(os.path.join(ROOT, path))
        full = alt if os.path.isfile(alt) else full
    if not under(full, INBOX) or not os.path.isfile(full):
        finish(REFUSED, "REFUSED %s must be a file inside inbox/" % what)
    return full


# ---------------------------------------------------------------- limits.env
LIMIT_KEYS = ("TASK_USD", "TASK_HALT_PCT", "MONTH_USD", "MONTH_HALT_PCT", "ROUNDS",
              "DIFF_MAX_LINES", "DIFF_MAX_FILES", "NEIGHBOR_MAX_FILES",
              "NEIGHBOR_MAX_KB", "WALL_CLOCK_S")
limits = {}
try:
    with open(os.path.join(ROOT, "limits.env")) as fh:
        for raw in fh:
            raw = raw.strip()
            if raw and not raw.startswith("#") and "=" in raw:
                k, v = raw.split("=", 1)
                limits[k.strip()] = v.strip()
except OSError:
    finish(REFUSED, "REFUSED limits.env is missing or unreadable")
L = {}
for k in LIMIT_KEYS:
    try:
        L[k] = float(limits[k])
        if L[k] < 0:
            raise ValueError
    except (KeyError, ValueError):
        finish(REFUSED, "REFUSED limits.env: %s is missing or not a number" % k)
if L["WALL_CLOCK_S"] < 1 or L["ROUNDS"] < 1:
    finish(REFUSED, "REFUSED limits.env: WALL_CLOCK_S and ROUNDS must be at least 1")


def on_alarm(_sig, _frm):
    finish(HALT, "HALT wall clock of %ds reached" % L["WALL_CLOCK_S"])


signal.signal(signal.SIGALRM, on_alarm)
signal.alarm(int(L["WALL_CLOCK_S"]))

# ---------------------------------------------------------------- denylist
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


# ---------------------------------------------------------------- task file
task_file = inbox_file(task_path, "the task file")
task = {}
with open(task_file) as fh:
    for raw in fh:
        raw = raw.rstrip("\n")
        if raw.strip() and not raw.lstrip().startswith("#") and ":" in raw:
            k, v = raw.split(":", 1)
            task[k.strip()] = v.strip().strip('"').strip("'")
say("task: %s" % os.path.relpath(task_file, ROOT))
for key in ("id", "kind", "target", "content"):
    if not task.get(key):
        finish(REFUSED, "REFUSED task has no %s line" % key)
if not re.fullmatch(r"[A-Za-z0-9._-]{1,60}", task["id"]):
    finish(REFUSED, "REFUSED task id may only use letters, digits, dot, dash, underscore")
if task["kind"] != "r1":
    finish(REFUSED, "REFUSED run.sh only runs kind: r1 (use r2.sh for a spec round)")
expect = task.get("expect_sha256", "").lower()
if not re.fullmatch(r"[0-9a-f]{64}", expect):
    finish(REFUSED, "REFUSED no expect_sha256 line (64 hex). No expect line, no run.")

# ---------------------------------------------------------------- work plan vs denylist
if os.path.islink(WORK):
    finish(DENY, "REFUSED work/ is a symlink")
lexical = os.path.normpath(os.path.join(ROOT, task["target"]))
real = os.path.realpath(lexical)
for candidate in (lexical, real):
    hit = deny_hit(candidate)
    if hit:
        finish(DENY, "REFUSED target is on the denylist (%s). Nothing written." % hit)
    if not under(candidate, WORK) or candidate == WORK:
        finish(DENY, "REFUSED target is outside work/. Nothing written.")
target = real
marker = os.path.join(WORK, task["id"] + ".ok")
say("target: %s" % os.path.relpath(target, ROOT))

# ---------------------------------------------------------------- budget
month = NOW.strftime("%Y-%m")
ledger = {"version": 1, "months": {}, "successes": {}}
if os.path.exists(LEDGER):
    try:
        with open(LEDGER) as fh:
            ledger = json.load(fh)
        ledger["months"], ledger["successes"]
    except (OSError, ValueError, KeyError, TypeError):
        finish(REFUSED, "REFUSED budget/ledger.json is unreadable (failing closed)")
spent = float(ledger["months"].get(month, {}).get("spent_usd", 0.0))
if ledger.get("holds"):
    say("budget: %s spent $%.2f" % (month, spent))
    finish(HALT, "HALT an unreconciled spending hold is open (%s). Clear it with setup/clear-hold.sh"
           % ledger["holds"][0].get("id", "?"))
month_usd = L["MONTH_USD"]
if halt_test:
    month_usd = spent - 0.01
    say("halt-test: month ceiling moved to $%.2f, below what is already spent" % month_usd)
month_halt = month_usd * L["MONTH_HALT_PCT"] / 100.0
task_halt = L["TASK_USD"] * L["TASK_HALT_PCT"] / 100.0
task_spent = 0.0  # R1 makes no paid call
say("limits: task $%.2f (halt $%.2f)  month $%.2f (halt $%.2f)  rounds %d  diff %d/%d  wall %ds"
    % (L["TASK_USD"], task_halt, month_usd, month_halt, L["ROUNDS"],
       L["DIFF_MAX_LINES"], L["DIFF_MAX_FILES"], L["WALL_CLOCK_S"]))
say("budget: %s spent $%.2f" % (month, spent))
if spent >= month_halt:
    finish(HALT, "HALT month spend $%.2f is at or over the halt line $%.2f" % (spent, month_halt))
if task_spent >= task_halt:
    finish(HALT, "HALT task spend $%.2f is at or over the halt line $%.2f" % (task_spent, task_halt))

# ---------------------------------------------------------------- do the work
os.makedirs(os.path.dirname(target), exist_ok=True)
with open(target, "w") as fh:
    fh.write(task["content"] + "\n")
with open(target, "rb") as fh:
    digest = hashlib.sha256(fh.read()).hexdigest()
mechanical_ok = digest == expect
say("sha256: %s" % digest)
say("expect: %s" % ("match" if mechanical_ok else "MISMATCH (expected %s...)" % expect[:12]))

# ---------------------------------------------------------------- reviewer verdict (optional)
reviewer_ok = True
reviewer_halt = False
if verdict_path:
    reviewer_ok = False
    try:
        with open(os.path.join(ROOT, "rubric.json")) as fh:
            need = json.load(fh)["x-pass-requires"]
        with open(inbox_file(verdict_path, "the verdict file")) as fh:
            v = json.load(fh)
        why = []
        if v.get("verdict") != "pass":
            why.append("verdict is %s" % v.get("verdict"))
        reviewer_halt = v.get("verdict") == "halt"
        for key, want in need.items():
            if key == "notes_max":
                if not isinstance(v.get("notes"), list) or len(v["notes"]) > want:
                    why.append("notes not empty")
            elif v.get(key) is not want:
                why.append("%s is not %s" % (key, str(want).lower()))
        if not mechanical_ok:
            why.append("mechanical gate failed")
        reviewer_ok = not why
        say("verdict: %s" % ("pass accepted" if reviewer_ok else "not a legal pass (" + "; ".join(why)[:70] + ")"))
    except (OSError, ValueError, KeyError, TypeError):
        say("verdict: unreadable verdict or rubric, treated as not a pass")

# A reviewer can never overrule the mechanical gate.
if not (mechanical_ok and reviewer_ok):
    if os.path.exists(marker):
        os.remove(marker)
    if not mechanical_ok and os.path.exists(target):
        os.remove(target)  # a file that failed its checksum is not left behind
    if mechanical_ok and reviewer_halt:
        finish(HALT, "HALT the reviewer returned halt")
    finish(FAIL, "FAIL %s" % ("checksum mismatch" if not mechanical_ok else "reviewer did not pass"))

# ---------------------------------------------------------------- record success once per expect line
first = expect not in ledger["successes"]
if first:
    ledger["successes"][expect] = {"id": task["id"], "first_at": NOW.isoformat(timespec="seconds")}
ledger["months"].setdefault(month, {"spent_usd": 0.0})
os.makedirs(BUDGET, exist_ok=True)
tmp = LEDGER + ".tmp"
with open(tmp, "w") as fh:
    json.dump(ledger, fh, indent=2, sort_keys=True)
os.replace(tmp, LEDGER)
with open(marker, "w") as fh:
    fh.write("%s %s\n" % (expect, ledger["successes"][expect]["first_at"]))
finish(OK, "OK %s (%s)" % (task["id"], "first success" if first else "already recorded, not counted twice"))
PY
