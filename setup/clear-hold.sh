#!/bin/bash
# Clear a spending hold left open by a call that returned no usage.
# Check the xAI console first, then say whether the call was charged.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
L="$ROOT/budget/ledger.json"
[ -f "$L" ] || { echo "no ledger, nothing to clear"; exit 0; }
python3 - "$L" show <<'PY' || exit 0
import json, sys
holds = json.load(open(sys.argv[1])).get("holds", [])
if not holds:
    print("no open holds"); sys.exit(1)
for h in holds:
    print("open hold: %s  $%.2f  %s  %s" % (h.get("id"), h.get("usd", 0), h.get("provider"), h.get("at")))
PY
read -r -p "Was it charged? [c = count the hold as spent / d = drop it, nothing was charged / Enter = leave it] " a
case "$a" in c|C) MODE=count ;; d|D) MODE=drop ;; *) echo "left as it is"; exit 0 ;; esac
python3 - "$L" "$MODE" <<'PY'
import json, os, sys, datetime
path, mode = sys.argv[1], sys.argv[2]
led = json.load(open(path))
month = datetime.datetime.now().strftime("%Y-%m")
m = led["months"].setdefault(month, {"spent_usd": 0.0})
for h in led.get("holds", []):
    if mode == "count":
        m["spent_usd"] = round(m.get("spent_usd", 0.0) + h.get("usd", 0), 4)
        m["xai_usd"] = round(m.get("xai_usd", 0.0) + h.get("usd", 0), 4)
led["holds"] = []
tmp = path + ".tmp"
json.dump(led, open(tmp, "w"), indent=2, sort_keys=True)
os.replace(tmp, path)
print("holds cleared (%s). Month spend now $%.2f" % (mode, m.get("spent_usd", 0.0)))
PY
