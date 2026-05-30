# Git 提交与分支命名规范

## 一、Commit Message 规范

采用 **Conventional Commits** 格式：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 1.1 Type（必填）

| Type       | 说明                                       |
| ---------- | ------------------------------------------ |
| `feat`     | 新功能                                     |
| `fix`      | 修复 bug                                   |
| `docs`     | 仅文档变更                                 |
| `style`    | 代码格式调整（不影响逻辑，如空格、分号等） |
| `refactor` | 重构（既非新功能也非修 bug）               |
| `perf`     | 性能优化                                   |
| `test`     | 添加或修改测试                             |
| `chore`    | 构建、依赖、工具等杂项                     |
| `ci`       | CI/CD 配置变更                             |
| `revert`   | 回滚某次提交                               |

### 1.2 Scope（选填）

用英文小写表示影响范围，如：`agent`、`callbacks`、`clients`、`config`、`api` 等。

### 1.3 Subject（必填）

- 使用祈使句
- 不加句号
- 不超过 72 个字符
- 用中文

### 1.4 Body（选填）

- 描述 **为什么** 做这个改动，而非做了什么
- 每行不超过 72 字符

### 1.5 Footer（选填）

- 关联 issue：`Closes #123`、`Refs #456`
- Breaking Change：以 `BREAKING CHANGE:` 开头

### 1.6 示例

```
feat(agent): 添加多轮对话支持

Closes #42
```

```
fix(callbacks): 修复重连时回调未触发的 bug

ZMQ socket 重连时的竞态条件导致回调被丢弃。添加了回调队列和刷新逻辑。

Refs #58
```

```
chore: 从 setup.py 迁移到 pyproject.toml
```

```
refactor(config)!: 使用 pydantic 重新设计配置加载

BREAKING CHANGE: Config 现在通过 ConfigurationManager 加载，
而非直接字典访问。
```

---

## 二、分支命名规范

### 2.1 分支类型前缀

| 前缀            | 用途                       | 示例                              |
| --------------- | -------------------------- | --------------------------------- |
| `feat/`         | 新功能开发                 | `feat/multi-agent`                |
| `fix/`          | Bug 修复                   | `fix/zmq-reconnect-crash`         |
| `hotfix/`       | 生产环境紧急修复           | `hotfix/api-auth-bypass`          |
| `refactor/`     | 重构                       | `refactor/session-manager`        |
| `perf/`         | 性能优化                   | `perf/reduce-memory-usage`        |
| `docs/`         | 文档                       | `docs/api-reference`              |
| `chore/`        | 杂项（依赖、工具等）       | `chore/update-zmq-binding`        |
| `test/`         | 测试                       | `test/integration-coverage`       |
| `exp/`          | 实验性分支（可能不合并）   | `exp/new-protocol`                |
| `release/`      | 发布分支                   | `release/v1.2.0`                  |

### 2.2 命名规则

- 全小写，单词间用 `-`（短横线）连接
- 简短且语义清晰，控制在 3~5 个单词以内
- 分支名总长度建议不超过 50 字符

### 2.3 示例

```
feat/audio-streaming
fix/callback-memory-leak
hotfix/login-crash
refactor/config-manager
release/v1.0.0
```

---

## 三、分支工作流

采用简化版 **Trunk-Based Development**：

```
main
  └── feat/xxx        # 功能分支，从 main 切出，完成后合并回 main
  └── fix/xxx         # 修复分支，同上
  └── hotfix/xxx      # 紧急修复，从 main 切出，合并回 main
  └── release/x.x.x   # 发布分支（仅发布前创建，打 tag 后合并）
```

### 3.1 基本规则

1. `main` 分支始终保持可发布状态
2. 所有变更通过分支开发，合并进 `main`
3. 合并前先 rebase 到最新的 `main`（保持历史线性）
4. 合并时使用 `--no-ff`（保留分支痕迹）或 squash merge（按需）
5. 发布时在 `main` 上打 tag：`v<major>.<minor>.<patch>`

### 3.2 Tag 规范

```
v1.0.0          # 正式发布
v1.0.0-rc1      # 候选发布
v1.0.0-alpha1   # Alpha 预览
```

---

## 四、检查清单

提交前确认：

- [ ] Commit message 符合 Conventional Commits 格式
- [ ] 分支名符合命名规范
- [ ] 代码已自测，无明显的 lint 错误
- [ ] 未包含敏感信息（密钥、token、密码等）
- [ ] 相关测试已更新
