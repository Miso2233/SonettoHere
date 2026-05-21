# 后端 StaticFiles WebSocket 阻塞修复

> 更新日期：2026-05-21

## 问题

Starlette 1.0.0 的 `StaticFiles` 在 `__call__` 中有 `assert scope["type"] == "http"`。当 `app.mount("/", StaticFiles(...))` 挂载在根路径时，会拦截所有 WebSocket 请求并触发 `AssertionError`：

```
File "starlette/staticfiles.py", line 91, in __call__
    assert scope["type"] == "http"
AssertionError
```

## 根因

`app.mount("/", ...)` 在 Starlette 路由表中匹配所有路径，包括 `/ws/chat/{session_id}` 的 WebSocket 升级请求。挂载点先于 WebSocket 路由匹配并尝试以 HTTP 处理，导致断言失败。

## 修复

**文件**：`api/server.py`

```python
# 之前：挂载在 "/" 会拦截 WebSocket
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="static")

# 之后：挂载在 "/assets"，SPA 路由用 404 fallback
app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")

@app.exception_handler(404)
async def spa_fallback(request, exc):
    return FileResponse(WEB_DIR / "index.html")
```

## 路由解析顺序

修改后请求匹配链路：

1. 显式路由（`/api/*` REST、`/ws/*` WebSocket）— 优先匹配
2. `/assets/*` — 静态文件
3. 其余路径 — 404 → `spa_fallback` 返回 `index.html`（SPA 前端路由）

WebSocket 请求不再被 StaticFiles 拦截。
