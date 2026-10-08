#!/usr/bin/env bash
# Mirror the committed code to cnt:~/prjs/event_coding/repo and stamp the commit.
# One-way; results/, docs/ and .git are never sent, and nothing remote is deleted outside repo/.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
stamp=$(git rev-parse HEAD)
git diff --quiet HEAD -- ec scripts tests config vendor pyproject.toml || stamp="${stamp}-dirty"
if ssh -o BatchMode=yes cnt "ps -u \"\$(whoami)\" -o args= | grep -q '[s]cripts/mp_'"; then
    echo "mp workers are running on cnt; refusing to sync" >&2; exit 1
fi
rsync -a --delete --exclude .git --exclude results --exclude docs --exclude archive --exclude '__pycache__' \
    --exclude .pytest_cache ./ cnt:prjs/event_coding/repo/
ssh -o BatchMode=yes cnt "echo $stamp > ~/prjs/event_coding/repo/COMMIT && cat ~/prjs/event_coding/repo/COMMIT"
