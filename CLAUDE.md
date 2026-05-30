# SonettoHere

## 更新动态发布流程

每次合并 PR 或发布版本后，Claude Code 应根据以下规则评估是否添加系统更新动态：

1. **评估标准**：仅当 PR 属于以下类型时值得加入新闻
   - `feat` — 新增用户可见的功能、页面、能力（如湾区计划、万花筒计划）
   - `enhance` — 对现有功能有重大增强或用户体验提升
   - `refactor` — 影响用户视觉或交互的重构（如 UI 重设计）
   - 以下类型通常**不值得**加入：纯 `fix`（非关键修复）、`chore`、`docs`、内部重构
2. **添加方式**：打开 `api/data/news.yaml`，在 `news` 列表的**最前面**插入一条新条目
   ```yaml
   - id: "简短-kebab-标识"
     title: "更新标题（中文，15字以内）"
     description: "更新内容描述，1-3句话概括变更内容和用户收益"
     type: "feat"       # feat | enhance | fix | refactor | docs
     date: "2026-05-30"  # ISO 日期 YYYY-MM-DD
     tags: ["标签1", "标签2"]
     version: "v1.3.0"   # 有版本号时填写，否则留空
     pr_number: 42       # 有 PR 编号时填写，否则留空
   ```
3. **提交流程**：`git add api/data/news.yaml && git commit -m "docs: 添加更新动态 <title>"` → 通过常规 PR 流程合入 main

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
