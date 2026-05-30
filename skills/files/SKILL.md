# 文件操作领域知识

## 可用 Skill
| Skill | 功能 | 依赖 |
|-------|------|------|
| `file_operations` | 文件 CRUD + 目录操作 + 搜索 | 无（标准库） |
| `file_edit` | 文件精确编辑：读取、精确替换、多笔编辑、文本搜索 | 无（标准库） |
| `pdf_reader` | PDF 元数据/文本提取/搜索 | PyPDF2 |
| `doc_reader` | DOCX 元数据/文本/段落/表格/搜索 | python-docx |

## 技能协作流程
- **文件搜索 → 读取**：先用 `file_operations` (search_files) 定位文件，再用 `file_operations` (read_file) 或 `pdf_reader` / `doc_reader` 读取内容
- **目录浏览 → 操作**：先用 list_directory 查看目录结构，再执行具体操作
- **精确编辑流程**：先用 `file_edit` (read) 查看文件内容，再用 `file_edit` (edit) 做精确字符串替换

## 常见陷阱
- **file_operations 的 operation 参数必填**，决定执行哪种操作（read_file / write_file / delete_file / rename_file / create_directory / list_directory / search_files）
- **file_edit 的 operation 参数必填**：edit（精确替换）/ multi_edit（多笔编辑）/ read（读取）/ search（文本搜索）
- **PDF 页码从 0 开始**（与 PyPDF2 一致），向用户展示时需 +1
- **doc_reader 仅支持 .docx**，旧版 .doc 格式需先转换为 .docx
- **写文件时自动创建父目录**，无需先调 create_directory
- **搜索文件支持 glob 通配符**，recursive 模式下使用 `**/*.py` 语法
- **file_edit 的 old_string 必须完全一致**，包含空白和缩进。不唯一时会报错，需提供更多上下文或开启 replace_all
