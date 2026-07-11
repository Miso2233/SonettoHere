# 配置迁移脚本

## 命名规则

```
<唯一标识>.py
```

示例：`from0to1.py`、`m3-context-windows.py`

## 职责

每个脚本处理一项具体的本地配置变更：
- 读取旧格式的配置文件
- 按需转换数据结构
- 写入新格式的配置文件

## 执行顺序

`upgrade.py` 扫描 `scripts/migrations/` 目录，过滤掉 `.applied` 已记录的脚本，按文件名字母序依次执行。

## 约定

- 脚本应可安全重复执行（幂等）—— 用 `if "field" not in data` 等短路写法
- 每个脚本只做一件事，不依赖其他迁移脚本是否已执行
- 升级失败时应给出明确的错误提示
- 脚本位于 `scripts/migrations/` 目录下
- 迁移脚本**无需**修改任何 git 跟踪的文件 —— `upgrade.py` 执行成功后自动写入 `.applied`
- `local-config-manifest.yaml` 作为配置总览需人工维护：新增本地配置文件时，同步添加 `paths` 条目（路径、用途、来源模板等）
