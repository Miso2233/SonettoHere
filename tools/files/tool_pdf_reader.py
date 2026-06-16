"""Tool: pdf_reader — PDF 文件阅读。"""

import os

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class PDFReaderInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    operation: str = Field(
        default="",
        description="操作: get_metadata/extract_text/extract_pages/search_text/get_toc/get_page_count",
    )
    file_path: str = Field(default="", description="PDF 文件路径")
    start_page: int = Field(default=0, description="起始页码（从0开始）")
    end_page: int | None = Field(default=None, description="结束页码（从0开始）")
    pages: list[int] = Field(default_factory=list, description="指定页码列表（extract_pages 操作）")
    query: str = Field(default="", description="搜索关键词（search_text 操作）")
    case_sensitive: bool = Field(default=False, description="搜索是否区分大小写")
    max_length: int = Field(default=10000, description="文本最大长度")


class PDFReaderTool(ToolBase):
    name: str = "pdf_reader"
    description: str = (
        "读取 PDF 文件：元数据、文本提取、关键词搜索、目录、页数。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = PDFReaderInput

    def _run(
        self,
        get_doc: bool = False,
        operation: str = "",
        file_path: str = "",
        start_page: int = 0,
        end_page: int | None = None,
        pages: list[int] | None = None,
        query: str = "",
        case_sensitive: bool = False,
        max_length: int = 10000,
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not operation:
            return format_error("operation 不能为空")
        if not file_path:
            return format_error("file_path 不能为空")
        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")
        if not file_path.lower().endswith(".pdf"):
            return format_error(f"不是 PDF 文件: {file_path}")

        try:
            from PyPDF2 import PdfReader

            if operation == "get_metadata":
                return self._get_metadata(file_path)
            elif operation == "extract_text":
                return self._extract_text(file_path, start_page, end_page, max_length)
            elif operation == "extract_pages":
                return self._extract_pages(file_path, pages or [], max_length)
            elif operation == "search_text":
                return self._search_text(file_path, query, case_sensitive)
            elif operation == "get_toc":
                return self._get_toc(file_path)
            elif operation == "get_page_count":
                return self._get_page_count(file_path)
            else:
                return format_error(f"未知操作: {operation}")
        except ImportError:
            return format_error("PyPDF2 未安装，请运行: pip install PyPDF2")
        except Exception as e:
            return format_error(f"PDF 处理失败: {e}")

    def _get_metadata(self, file_path: str) -> str:
        from PyPDF2 import PdfReader

        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            meta = {}
            if reader.metadata:
                for key in reader.metadata.keys():
                    val = reader.metadata.get(key, "")
                    if isinstance(val, bytes):
                        try:
                            val = val.decode("utf-8", errors="ignore")
                        except Exception:
                            val = str(val)
                    meta[key] = val

            return format_success({
                "metadata": meta,
                "page_count": len(reader.pages),
                "file_path": os.path.abspath(file_path),
            })

    def _extract_text(self, file_path: str, start_page: int, end_page: int | None, max_length: int) -> str:
        from PyPDF2 import PdfReader

        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            total = len(reader.pages)

            if end_page is None or end_page >= total:
                end_page = total - 1
            if start_page < 0:
                start_page = 0
            if start_page >= total:
                return format_error(f"起始页码超出范围: {start_page}，总页数: {total}")

            parts = []
            for pn in range(start_page, end_page + 1):
                pt = reader.pages[pn].extract_text()
                if pt:
                    parts.append(f"--- 第 {pn + 1} 页 ---\n{pt}")

            text = "\n\n".join(parts)
            if len(text) > max_length:
                text = text[:max_length] + "\n\n[内容已截断]"

            return format_success({
                "text": text,
                "page_range": [start_page, end_page],
                "total_pages": total,
                "text_length": len(text),
            })

    def _extract_pages(self, file_path: str, pages: list[int], max_length: int) -> str:
        from PyPDF2 import PdfReader

        if not pages:
            return format_error("请提供页码列表")

        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            total = len(reader.pages)
            result = {}

            for pn in pages:
                if pn < 0 or pn >= total:
                    result[pn] = {"error": f"页码 {pn} 超出范围"}
                    continue
                pt = reader.pages[pn].extract_text()
                if len(pt) > max_length:
                    pt = pt[:max_length] + "[内容已截断]"
                result[pn] = {"page_number": pn + 1, "text": pt}

            return format_success({"page_contents": result, "total_pages": total})

    def _search_text(self, file_path: str, query: str, case_sensitive: bool) -> str:
        from PyPDF2 import PdfReader

        if not query:
            return format_error("请提供搜索关键词")

        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            total = len(reader.pages)
            q = query if case_sensitive else query.lower()
            results = []

            for pn in range(total):
                pt = reader.pages[pn].extract_text()
                if not pt:
                    continue
                check = pt if case_sensitive else pt.lower()
                if q in check:
                    matched = [
                        {"line_number": i + 1, "content": line.strip()}
                        for i, line in enumerate(pt.split("\n"))
                        if q in (line if case_sensitive else line.lower())
                    ]
                    results.append({"page_number": pn + 1, "matched_lines": matched})

            return format_success({
                "query": query,
                "total_pages": total,
                "results": results,
                "total_matches": sum(r["matched_lines"].__len__() for r in results),
            })

    def _get_toc(self, file_path: str) -> str:
        from PyPDF2 import PdfReader

        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            toc = []

            def parse_outlines(outlines, level=0):
                for item in outlines:
                    if isinstance(item, list):
                        parse_outlines(item, level + 1)
                    else:
                        page_num = None
                        try:
                            if hasattr(item, "page") and item.page:
                                page_num = reader.get_page_number(item.page) + 1
                        except Exception:
                            pass
                        toc.append({
                            "title": item.title if hasattr(item, "title") else str(item),
                            "level": level,
                            "page_number": page_num,
                        })

            try:
                parse_outlines(reader.outlines)
            except Exception:
                pass

            return format_success({"toc": toc, "total_pages": len(reader.pages)})

    def _get_page_count(self, file_path: str) -> str:
        from PyPDF2 import PdfReader

        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            return format_success({"page_count": len(reader.pages), "file_path": os.path.abspath(file_path)})
