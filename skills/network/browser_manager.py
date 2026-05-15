"""Shared Playwright browser manager — singleton, lazy-init, headed mode."""

import asyncio
import logging

logger = logging.getLogger(__name__)


class BrowserManager:
    """模块级单例，管理 Playwright + Microsoft Edge 浏览器实例。

    使用有头模式（headless=False），浏览器窗口对用户可见，
    便于手动解决人机验证（CAPTCHA / Turnstile / 登录等）。

    使用 async_api 避免与 uvicorn asyncio 事件循环的 greenlet 冲突。
    """

    _instance: "BrowserManager | None" = None
    _playwright = None
    _browser = None
    _loop_id: int | None = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "BrowserManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def _ensure_browser(self):
        loop_id = id(asyncio.get_running_loop())
        if self._browser is not None and self._loop_id != loop_id:
            logger.info("事件循环已变更，重新创建浏览器实例")
            await self._close_locked()
        if self._browser is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=False,
                channel="msedge",
            )
            self._loop_id = loop_id
            logger.info("Microsoft Edge 浏览器已启动（有头模式）")

    async def get_browser(self):
        async with self._lock:
            await self._ensure_browser()
            return self._browser

    async def new_page(self):
        """创建新页面，默认 1920x1080 视口。"""
        browser = await self.get_browser()
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        return await context.new_page()

    async def _close_locked(self):
        """关闭资源（需在持有 _lock 时调用）。"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._loop_id = None

    async def close(self):
        async with self._lock:
            await self._close_locked()
            BrowserManager._instance = None
            logger.info("浏览器已关闭")


def get_browser_manager() -> BrowserManager:
    """获取全局 BrowserManager 单例。"""
    return BrowserManager()
