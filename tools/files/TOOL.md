# 文件操作领域知识

## 可用工具
| 工具 | 功能 | 依赖 |
|------|------|------|
| `file_read` | 读取文件内容 | 无（标准库） |
| `file_write` | 写入/创建文件（自动建父目录） | 无（标准库） |
| `file_manage` | 删除/重命名文件、创建目录 | 无（标准库） |
| `file_search` | 列出目录内容、搜索文件 | 无（标准库） |
| `file_edit` | 文件精确编辑：读取、精确替换、多笔编辑、文本搜索 | 无（标准库） |

## 工具选择指南
- **查看文件内容** → `file_read`
- **创建或修改文件** → `file_write`
- **删除/重命名/建目录** → `file_manage`
- **浏览目录/搜索文件** → `file_search`
- **精确字符串替换** → `file_edit`

## 技能协作流程
- **文件搜索 → 读取**：先用 `file_search` (search_files) 定位文件，再用 `file_read` 读取内容
- **目录浏览 → 操作**：先用 `file_search` (list_directory) 查看目录结构，再执行具体操作
- **精确编辑流程**：先用 `file_edit` (read) 查看文件内容，再用 `file_edit` (edit) 做精确字符串替换

## 常见陷阱
- **`file_read` 的 file_path 参数必填**
- **`file_write` 的 file_path 和 content 参数必填**，自动创建父目录
- **`file_manage` 的 operation 参数必填**，决定执行哪种操作（delete_file / rename_file / create_directory）
- **`file_search` 的 operation 参数必填**：list_directory / search_files
- **`file_edit` 的 operation 参数必填**：edit（精确替换）/ multi_edit（多笔编辑）/ read（读取）/ search（文本搜索）
- **写文件时自动创建父目录**，无需先调 create_directory
- **搜索文件支持 glob 通配符**，recursive 模式下使用 `**/*.py` 语法
- **file_edit 的 old_string 必须完全一致**，包含空白和缩进。不唯一时会报错，需提供更多上下文或开启 replace_all
