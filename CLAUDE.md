# SonettoHere

## 提交规范

每次创建 git commit 前，必须先阅读 `dev_docs/git-conventions.md`，确保 commit message 和分支命名符合规范。

## Git PR 工作流（Skill）

完整流程：开分支 → commit → push → PR → merge → 回 main。

方式一（一键脚本）：
```bash
./scripts/git-pr-flow.sh <branch-name> "<commit-msg>" ["<pr-title>"] ["<pr-body-file>"]
```

方式二（手动步骤，Claude Code 每次应遵循此顺序）：
1. `git checkout -b <type>/<short-desc>`
2. `git add <files> && git commit -m "<msg>"`
3. `git push -u origin <branch>`
4. `gh pr create --title "<title>" --body "<body>"`
5. `gh pr merge <branch> --squash --delete-branch`
6. `git checkout main && git pull origin main`

依赖：`gh` (GitHub CLI) 需已登录。

### 长期分支

`feat/kep` — KEP 试验性功能分支，合并后不删除，PR 合入时不加 `--delete-branch`。
定期 rebase 到 latest main：
```bash
git checkout feat/kep && git rebase origin/main && git push --force-with-lease
```
