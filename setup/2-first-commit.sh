#!/bin/bash
# Step 2. Make architect-run its own git repo and take the first commit, locally.
# Refuses to commit if a key, env file, ledger or run output would be included.
# It does not push. Creating the private remote is a step you do on GitHub.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT" || exit 1
[ -f .gitignore ] || { echo "FAIL: .gitignore is missing. Stop."; exit 1; }
[ -d .git ] || git init -q -b main
git add -A
BAD="$(git diff --cached --name-only | grep -E '(^|/)(keys|budget|work|outbox|log)/|(^|/)\.env|secrets.*\.env|ledger\.json|\.pem$|\.key$' || true)"
if [ -n "$BAD" ]; then
  echo "FAIL: these must never be committed:"; echo "$BAD" | sed 's/^/  /'
  git reset -q; exit 1
fi
echo "Will commit:"; git diff --cached --name-only | sed 's/^/  /'
git commit -q -m "architect-run v0.2: R1 and the R2 spec round, reviewed by Grok" || { echo "FAIL: commit did not go through (is git user.name / user.email set?)"; exit 1; }
git log -1 --format='committed %h %s'
echo
echo "Next, by hand: create a NEW PRIVATE repo on GitHub (not the-architect), then"
echo "  git -C $ROOT remote add origin <its URL> && git -C $ROOT push -u origin main"
