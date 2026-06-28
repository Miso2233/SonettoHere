"""REST API — 本地文件服务（封面图等）。"""

import asyncio
from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/select-file")
async def select_file(type: str = "file"):
    """打开系统原生文件选择对话框，返回所选文件或文件夹的绝对路径。

    仅在本地开发环境可用（对话框在服务器端弹出）。
    type: "file" 选择文件, "folder" 选择文件夹
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        import sys

        def _set_dpi_awareness() -> None:
            """启用 Windows DPI 感知，避免对话框在高 DPI 下模糊。"""
            if sys.platform == "win32":
                import ctypes

                try:
                    # PROCESS_PER_MONITOR_DPI_AWARE = 1
                    ctypes.windll.shcore.SetProcessDpiAwareness(1)
                except (AttributeError, OSError):
                    try:
                        ctypes.windll.user.SetProcessDPIAware()
                    except (AttributeError, OSError):
                        pass

        def _open_dialog() -> str | None:
            _set_dpi_awareness()
            root = tk.Tk()
            root.withdraw()
            try:
                dpi = root.winfo_fpixels("1i")
                root.tk.call("tk", "scaling", dpi / 72.0)
            except Exception:
                pass
            root.attributes("-topmost", True)

            if type == "folder":
                path = filedialog.askdirectory(title="选择要引用的文件夹")
            else:
                path = filedialog.askopenfilename(
                    title="选择要引用的文件",
                    filetypes=[
                        ("所有文件", "*.*"),
                        ("文本文件", "*.txt"),
                        ("图片", "*.png;*.jpg;*.jpeg;*.gif;*.bmp"),
                        ("PDF", "*.pdf"),
                        ("文档", "*.doc;*.docx"),
                        ("代码", "*.py;*.js;*.ts;*.vue;*.html;*.css"),
                    ],
                )
            root.destroy()
            return path if path else None

        loop = asyncio.get_event_loop()
        path = await loop.run_in_executor(None, _open_dialog)
        return {"path": path}
    except ImportError:
        raise HTTPException(
            status_code=500, detail="tkinter 不可用，无法打开文件对话框"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"打开文件对话框失败: {str(e)}")
