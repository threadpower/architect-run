#!/bin/bash
# Step 5b. Prove what the `architect` user can and cannot do. Changes nothing.
# Prints PASS only if architect cannot read any secrets file, env file or key,
# cannot write the orchestrator, and can read the one file it has to run.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
FAILS=0
as() { sudo runuser -u architect -- "$@"; }
id architect >/dev/null 2>&1 || { echo "FAIL: no architect user (run setup/5a-make-user.sh)"; exit 1; }
echo "architect is: $(id architect)"
case " $(id -Gn architect) " in *" docker "*|*" sudo "*) echo "  FAIL in docker or sudo group"; FAILS=$((FAILS+1)) ;; esac

echo "must NOT be readable by architect:"
while IFS= read -r f; do
  [ -e "$f" ] || continue
  if as test -r "$f"; then echo "  FAIL readable: $f"; FAILS=$((FAILS+1)); else echo "  ok   $f"; fi
done < <( { ls /forge/secrets.env /forge/secrets.qa.env /forge/.env 2>/dev/null
            find /forge -maxdepth 3 \( -name '.env' -o -name '.env.*' -o -name 'secrets*.env' \) -not -path '*/_stray-*' 2>/dev/null
            find "$ROOT/keys" -type f 2>/dev/null; } | sort -u )
[ -d "$ROOT/keys" ] && { if as test -r "$ROOT/keys"; then echo "  FAIL keys/ can be listed"; FAILS=$((FAILS+1)); else echo "  ok   $ROOT/keys/ (cannot be listed)"; fi; }

echo "must NOT be writable by architect:"
for f in "$ROOT" "$ROOT/r2_child.py" "$ROOT/r2.py" "$ROOT/run.sh" "$ROOT/limits.env" "$ROOT/denylist.txt" "$ROOT/inbox"; do
  if as test -w "$f"; then echo "  FAIL writable: $f"; FAILS=$((FAILS+1)); else echo "  ok   $f"; fi
done

echo "must be readable by architect:"
if as test -r "$ROOT/r2_child.py"; then echo "  ok   $ROOT/r2_child.py"; else echo "  FAIL cannot read r2_child.py"; FAILS=$((FAILS+1)); fi

echo
if [ "$FAILS" = 0 ]; then echo "=== PASS ==="; else echo "=== FAIL ($FAILS) ==="; exit 1; fi
