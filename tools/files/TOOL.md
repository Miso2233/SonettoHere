# 文件操作领域知识

## 可用工具
| 工具 | 功能 | 依赖 |
|------|------|------|
| `file_read` | 读取文件全文 | 无（标准库） |
| `file_write` | 写入/创建文件（自动建父目录） | 无（标准库） |
| `file_delete` | 删除文件或目录 | 无（标准库） |
| `file_rename` | 重命名/移动文件或目录 | 无（标准库） |
| `file_create_directory` | 创建目录（自动建父目录） | 无（标准库） |
| `file_list_directory` | 列出目录内容 | 无（标准库） |
| `file_search` | glob 通配符搜索文件路径 | 无（标准库） |
| `file_edit` | 多笔精确字符串替换 | 无（标准库） |
| `file_search_text` | 文件内容正则文本搜索 | 无（标准库） |

## 工具选择指南
- **查看文件内容** → `file_read`
- **创建或修改文件** → `file_write`
- **删除** → `file_delete`
- **重命名/移动** → `file_rename`
- **创建目录** → `file_create_directory`
- **浏览目录内容** → `file_list_directory`
- **按模式找文件路径** → `file_search`（glob）
- **按字符串/正则替换文件内容** → `file_edit`
- **在文件内容中搜索匹配** → `file_search_text`

## 技能协作流程
- **文件搜索 → 读取**：先用 `file_search`（search_files）定位文件路径，再用 `file_read` 读取内容
- **目录浏览 → 操作**：先用 `file_list_directory` 查看目录结构，再执行具体操作
- **精确编辑流程**：先用 `file_read` 查看文件内容，再用 `file_edit` 做多笔精确字符串替换

## 常见陷阱
- **`file_read` 的 file_path 参数必填**
- **`file_write` 的 file_path 和 content 参数必填**，自动创建父目录
- **`file_delete` 的 file_path 必填**，删除目录会递归删除
- **`file_rename` 的 file_path 和 new_path 必填**，目标已存在时报错
- **`file_create_directory` 的 directory_path 必填**
- **`file_list_directory` 的 directory_path 可选**，留空列出当前目录
- **`file_search` 的 search_pattern 必填**，支持 glob 通配符，recursive 模式下使用 `**/*.py` 语法
- **`file_edit` 的 edits 参数必填**：JSON 数组，单笔替换也需放入数组
- **`file_edit` 的 old_string 必须完全一致**，包含空白和缩进。不唯一时会报错，需提供更多上下文或开启 replace_all
- **`file_search_text` 的 pattern 必填**，支持正则
- **写文件时自动创建父目录**，无需先调 file_create_directory
