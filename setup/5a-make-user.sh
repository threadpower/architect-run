#!/bin/bash
# Step 5a. Create the `architect` user: no password, no login shell, no home, no extra groups.
set -u
if id architect >/dev/null 2>&1; then
  echo "architect already exists: $(id architect)"
else
  sudo useradd --system --no-create-home --shell /usr/sbin/nologin architect || { echo "FAIL: could not create the user"; exit 1; }
  echo "created: $(id architect)"
fi
case " $(id -Gn architect) " in
  *" docker "*|*" sudo "*|*" adm "*) echo "FAIL: architect is in a group it must not be in: $(id -Gn architect)"; exit 1 ;;
esac
echo "OK. Now run setup/5b-prove-user.sh"
