"""Todo 测试共享的异步 mock 辅助。"""
from unittest.mock import AsyncMock


async def _apages(pages):
    """把「每页一个 list」的列表逐页 yield（模拟 AsyncResultsPaginator）。"""
    for page in pages:
        yield page


def apaginate(pages):
    """把分页 api 方法 mock 成 async：await → async iterable of pages。"""
    return AsyncMock(return_value=_apages(pages))
