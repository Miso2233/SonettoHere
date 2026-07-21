## 改动

在 `upgrade.py` 的 `git pull` 流程后，新增**依赖自动安装**和**版本检查**机制，解决拉取代码后因缺少新增依赖导致启动失败的问题（如 v3.2.0 引入 Pinia 后需手动执行 `npm install`）。

### 新增功能

1. **前端 npm 依赖自动安装** — 检测 `web/package.json` 或 `web/package-lock.json` 在 pull 中有变更时，自动执行 `npm install`
2. **后端 Python 依赖自动安装** — 检测 `pyproject.toml` 或 `requirements.txt` 有变更时，自动执行 `pip install -e .`
3. **Node.js 版本检查** — 每次拉取更新后检查 Node.js 版本是否 >= 18，不满足时给出警告
4. **设计原则**：
   - 无侵入：依赖安装失败不会中断升级流程（仅警告），用户可手动修复
   - 精确检测：通过 `git diff --name-only` 对比 pull 前后的 HEAD，仅在有实际变更时才触发安装
   - 超时保护：npm install 和 pip install 均有超时限制，避免挂死

### 涉及文件

- `upgrade.py` — 新增 `_get_head_hash`、`_get_changed_files`、`_install_npm_dependencies`、`_install_python_dependencies`、`_check_node_version`、`_handle_dependency_changes` 函数；修改 `main()` 集成依赖检测流程

Closes #254
