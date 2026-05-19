"""Skill: scrape_webpage — 基于 Playwright 的网页内容抓取。

使用真实 Chromium 浏览器（有头模式）抓取网页，用户可手动解决人机验证。
提取内容远超标题+正文：元数据、Open Graph、JSON-LD、标题层级、链接、图片等。
"""

import asyncio
import base64
import json
import logging

from pydantic import BaseModel, Field

from skills.base import SkillBase, format_error, format_success
from skills.network.browser_manager import get_browser_manager

logger = logging.getLogger(__name__)


class ScraperInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    url: str = Field(default="", description="目标网页 URL，须以 http:// 或 https:// 开头")
    wait_ms: int = Field(
        default=5000,
        description="页面加载后额外等待毫秒数，给用户时间解决人机验证（默认 5000）",
    )
    screenshot: bool = Field(default=False, description="是否同时截取页面首屏截图（base64）")
    headless: bool = Field(
        default=True,
        description="是否使用无头模式（默认 true：不显示浏览器窗口，后台静默抓取；设为 false 则弹出浏览器窗口，适用于需要手动解决人机验证的场景）",
    )


CONTENT_SELECTORS = [
    "article",
    "main",
    '[role="main"]',
    ".content",
    "#content",
    ".post",
    ".article",
    ".post-content",
    ".article-content",
]

MAX_CONTENT_LENGTH = 50000
MAX_LINKS = 200
MAX_IMAGES = 100


async def _extract_meta(page) -> dict:
    """提取 <meta name/property> 标签。"""
    meta = {}
    for tag in await page.query_selector_all('meta[name], meta[property]'):
        key = await tag.get_attribute("name") or await tag.get_attribute("property") or ""
        content = await tag.get_attribute("content")
        if key and content:
            meta[key] = content
    return meta


async def _extract_open_graph(page) -> dict:
    """提取 Open Graph 标签。"""
    og = {}
    for tag in await page.query_selector_all('meta[property^="og:"]'):
        prop = await tag.get_attribute("property") or ""
        content = await tag.get_attribute("content") or ""
        if prop and content:
            og[prop.replace("og:", "")] = content
    return og


async def _extract_twitter_card(page) -> dict:
    """提取 Twitter Card 标签。"""
    tc = {}
    for tag in await page.query_selector_all('meta[name^="twitter:"]'):
        name = await tag.get_attribute("name") or ""
        content = await tag.get_attribute("content") or ""
        if name and content:
            tc[name.replace("twitter:", "")] = content
    return tc


async def _extract_jsonld(page) -> list[dict]:
    """提取 JSON-LD 结构化数据。"""
    items = []
    for el in await page.query_selector_all('script[type="application/ld+json"]'):
        try:
            text = await el.inner_text()
            if text.strip():
                items.append(json.loads(text))
        except (json.JSONDecodeError, Exception):
            pass
    return items


async def _extract_headings(page) -> list[dict]:
    """提取页面标题层级 (h1-h6)。"""
    headings = []
    for level in range(1, 7):
        for el in await page.query_selector_all(f"h{level}"):
            text = (await el.inner_text()).strip()
            if text:
                headings.append({"level": level, "text": text})
    return headings


async def _extract_links(page) -> list[dict]:
    """提取页面链接，去重并过滤 javascript: 等。"""
    links = []
    seen: set[str] = set()
    for el in await page.query_selector_all("a[href]"):
        href = ((await el.get_attribute("href")) or "").strip()
        if not href or href.startswith("javascript:") or href.startswith("#"):
            continue
        if href in seen:
            continue
        seen.add(href)
        text = (await el.inner_text()).strip() or ""
        links.append({"text": text, "href": href})
        if len(links) >= MAX_LINKS:
            break
    return links


async def _extract_images(page) -> list[dict]:
    """提取页面图片。"""
    images = []
    for el in await page.query_selector_all("img[src]"):
        src = (await el.get_attribute("src")) or ""
        alt = (await el.get_attribute("alt")) or ""
        if src and not src.startswith("data:"):
            images.append({"src": src, "alt": alt})
            if len(images) >= MAX_IMAGES:
                break
    return images


async def _extract_content(page) -> str:
    """提取正文 HTML，优先语义标签，保留链接等丰富结构。"""
    for selector in CONTENT_SELECTORS:
        el = await page.query_selector(selector)
        if el:
            html = await el.inner_html()
            if len(html.strip()) > 100:
                return html

    html = await page.evaluate("""() => {
        const body = document.body;
        if (!body) return '';
        const clone = body.cloneNode(true);
        for (const sel of ['script', 'style']) {
            for (const el of clone.querySelectorAll(sel)) {
                el.remove();
            }
        }
        return clone.innerHTML;
    }""")
    return html or ""


class WebScraperSkill(SkillBase):
    name: str = "scrape_webpage"
    description: str = (
        "使用真实 Microsoft Edge 浏览器抓取网页内容。"
        "提取：标题、元数据、Open Graph、JSON-LD 结构化数据、标题层级、链接、图片、正文 HTML（保留链接等丰富结构）。"
        "支持 JavaScript 渲染页面。默认无头模式后台静默抓取，"
        "可设置 headless=false 切换为有头模式以手动解决人机验证。"
        "★ 首次使用先 get_doc=true。"
    )
    args_schema: type[BaseModel] = ScraperInput

    async def _arun(
        self,
        get_doc: bool = False,
        url: str = "",
        wait_ms: int = 5000,
        screenshot: bool = False,
        headless: bool = True,
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not url:
            return format_error("url 不能为空")

        try:
            manager = get_browser_manager()
            page = await manager.new_page(headless=headless)

            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(wait_ms)

            result: dict = {
                "url": page.url,
                "title": await page.title(),
            }

            meta = await _extract_meta(page)
            if meta:
                result["meta"] = meta

            og = await _extract_open_graph(page)
            if og:
                result["open_graph"] = og

            tc = await _extract_twitter_card(page)
            if tc:
                result["twitter_card"] = tc

            jsonld = await _extract_jsonld(page)
            if jsonld:
                result["structured_data"] = jsonld

            headings = await _extract_headings(page)
            if headings:
                result["headings"] = headings

            links = await _extract_links(page)
            if links:
                result["links"] = links

            images = await _extract_images(page)
            if images:
                result["images"] = images

            content = await _extract_content(page)
            if len(content) > MAX_CONTENT_LENGTH:
                content = content[:MAX_CONTENT_LENGTH] + "\n\n<!-- 内容已截断 -->"
            result["content"] = content

            if screenshot:
                screenshot_bytes = await page.screenshot(full_page=False)
                result["screenshot_base64"] = base64.b64encode(screenshot_bytes).decode()

            return format_success(result)

        except Exception as e:
            logger.exception("网页抓取失败: %s", url)
            return format_error(f"网页抓取失败: {e}")

    def _run(
        self,
        get_doc: bool = False,
        url: str = "",
        wait_ms: int = 5000,
        screenshot: bool = False,
        headless: bool = True,
    ) -> str:
        """同步包装，供 CLI 等同步调用方使用。"""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._arun(
                get_doc=get_doc, url=url, wait_ms=wait_ms, screenshot=screenshot,
                headless=headless,
            ))

        # 运行中的事件循环不可嵌套 — 用独立线程执行
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                self._arun(get_doc=get_doc, url=url, wait_ms=wait_ms, screenshot=screenshot,
                           headless=headless),
            )
            return future.result()
