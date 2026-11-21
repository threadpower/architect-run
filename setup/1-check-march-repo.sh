#!/bin/bash
# Step 1. Read-only. Is a secrets file tracked in the March Architect repo?
# If anything is listed under "tracked", stop and send the output to Grok. Commit nothing there.
set -u
echo "tracked:"; git -C /forge/architect ls-files -- .env '**/.env' '*.pem' '*.key' | head
echo "ignore:"; git -C /forge/architect check-ignore -v .env || echo "NOT IGNORED"
