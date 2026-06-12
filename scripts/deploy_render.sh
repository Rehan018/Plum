#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_URL="${GITHUB_REMOTE_URL:-git@github.com:Rehan018/Plum.git}"

cd "$ROOT_DIR"

echo "==> Running backend tests"
if [[ "${SKIP_CHECKS:-0}" != "1" ]]; then
  if [[ ! -x backend/.venv/bin/pytest ]]; then
    python3 -m venv backend/.venv
    backend/.venv/bin/pip install -r backend/requirements.txt
  fi
  (cd backend && .venv/bin/pytest)

  echo "==> Building frontend"
  (cd frontend && npm ci && npm run build)
else
  echo "Skipping tests/build because SKIP_CHECKS=1"
fi

echo "==> Preparing Git remote"
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
fi

git branch -M main

echo "==> Committing pending changes, if any"
git add .
if git diff --cached --quiet; then
  echo "No changes to commit"
else
  git commit -m "Prepare Render deployment"
fi

echo "==> Pushing to GitHub"
git push -u origin main

if [[ -n "${RENDER_DEPLOY_HOOK_URL:-}" ]]; then
  echo "==> Triggering Render deploy hook"
  curl -fsS -X POST "$RENDER_DEPLOY_HOOK_URL"
  echo
  echo "Render deploy hook triggered."
else
  cat <<'MSG'

Pushed to GitHub.

For first Render deploy:
1. Open Render Dashboard
2. New + > Blueprint
3. Connect git@github.com:Rehan018/Plum.git or https://github.com/Rehan018/Plum
4. Render will read render.yaml and create the web service.

After the first deploy, add your Render Deploy Hook URL and rerun:

  RENDER_DEPLOY_HOOK_URL="https://api.render.com/deploy/srv-..." ./scripts/deploy_render.sh

MSG
fi
