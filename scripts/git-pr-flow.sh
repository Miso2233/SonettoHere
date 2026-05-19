#!/usr/bin/env bash
# git-pr-flow.sh — 开分支 → commit → push → PR → merge → 回 main
# 用法:
#   ./scripts/git-pr-flow.sh <branch-name> <commit-msg> [pr-title] [pr-body-file]
#
# 示例:
#   ./scripts/git-pr-flow.sh feat/my-feature "feat: 添加xxx功能"
#   ./scripts/git-pr-flow.sh fix/ugly-bug "fix: 修复xxxbug" "PR标题" pr-body.md
#
# 依赖: gh (GitHub CLI), git

set -euo pipefail

BRANCH="$1"
COMMIT_MSG="$2"
PR_TITLE="${3:-$COMMIT_MSG}"
PR_BODY="${4:-"## Summary\n- $COMMIT_MSG"}"

ORIG_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "=== 1. 创建并切换到分支: $BRANCH ==="
git checkout -b "$BRANCH"

echo "=== 2. 暂存所有变更并提交 ==="
git add -A
git commit -m "$COMMIT_MSG"

echo "=== 3. 推送到远端 ==="
git push -u origin "$BRANCH"

echo "=== 4. 创建 PR ==="
if [ -f "$PR_BODY" ]; then
  BODY_ARG="--body-file $PR_BODY"
else
  BODY_ARG="--body $(echo -e "$PR_BODY")"
fi
# shellcheck disable=SC2086
PR_URL=$(gh pr create --title "$PR_TITLE" $BODY_ARG)
echo "PR: $PR_URL"

echo "=== 5. Squash merge ==="
gh pr merge "$BRANCH" --squash --delete-branch

echo "=== 6. 切回 $ORIG_BRANCH 并拉取最新 ==="
git checkout "$ORIG_BRANCH"
git pull origin "$ORIG_BRANCH"

echo "=== 完成 ==="
