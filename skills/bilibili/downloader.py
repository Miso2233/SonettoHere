"""Bilibili 视频下载核心逻辑。

基于 https://github.com/tyokyo320/bilibili-downloader 适配，
感谢原作者的开源贡献。
"""

import asyncio
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

from skills.bilibili.models import QUALITY_ALIAS, VideoInfo

logger = logging.getLogger(__name__)

BASE_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "max-age=0",
    "Content-Type": "application/json; charset=utf-8",
    "pragma": "no-cache",
    "referer": "https://space.bilibili.com/",
    "sec-ch-ua": '"Not?A_Brand";v="8", "Chromium";v="108", "Microsoft Edge";v="108"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/108.0.0.0 Safari/537.36 Edg/108.0.1462.46"
    ),
}

ILLEGAL_CHARS = re.compile(r'[<>:"/\\|?*]')


class BilibiliDownloader:
    """B 站视频下载器：抓取 → 下载 → 合并。"""

    def __init__(self, cookie: str, output_dir: str):
        self.cookie = cookie
        self.output_dir = Path(output_dir)
        self.temp_dir = self.output_dir / "temp"
        self._headers = {**BASE_HEADERS, "cookie": cookie}

    # ── 公开入口 ──────────────────────────────────────────────

    async def run(self, url: str, quality: str = "highest") -> VideoInfo:
        """完整下载流水线：抓取信息 → 下载流 → 合并 → 返回 VideoInfo。"""
        url = self._normalize_url(url)
        video = await self._fetch_video_info(url, quality)
        logger.info("开始下载: %s [%s]", video.title, video.get_quality_name())

        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        await self._download_video(video)
        video.output_path = self._merge(video)
        video.cover_path = self._extract_cover_frame(video)
        self._cleanup(video)

        logger.info("下载完成: %s", video.title)
        return video

    # ── URL 处理 ──────────────────────────────────────────────

    @staticmethod
    def _normalize_url(url: str) -> str:
        """确保 /video/BVxxx/?p=N 格式，避免重定向导致清晰度降级。"""
        return re.sub(r"(/video/(?:BV[0-9A-Za-z]+|av\d+))(\?)", r"\1/\2", url)

    @staticmethod
    def _extract_part_number(url: str) -> int:
        try:
            qs = parse_qs(urlparse(url).query)
            return int(qs.get("p", ["1"])[0])
        except (ValueError, IndexError):
            return 1

    # ── 页面抓取 ──────────────────────────────────────────────

    async def _fetch_video_page(self, url: str, max_retries: int = 3) -> BeautifulSoup:
        timeout = httpx.Timeout(60.0, connect=15.0)
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
                    resp = await client.get(url, headers=self._headers)
                    resp.raise_for_status()
                    return BeautifulSoup(resp.text, "html.parser")
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RequestError):
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 5
                    logger.warning("页面抓取超时，%d秒后重试 (%d/%d)", wait, attempt + 1, max_retries)
                    await asyncio.sleep(wait)
                else:
                    raise

    @staticmethod
    def _extract_title(bs: BeautifulSoup) -> str:
        h1 = bs.find("h1")
        if h1:
            return h1.get_text()
        title_tag = bs.find("title")
        if title_tag:
            return title_tag.get_text()
        raise ValueError("无法获取视频标题")

    @staticmethod
    def _extract_playinfo(bs: BeautifulSoup) -> dict:
        pattern = re.compile(r"window\.__playinfo__=(.*?)$", re.MULTILINE | re.DOTALL)
        script = bs.find("script", text=pattern)
        if script is None:
            raise ValueError(
                "未找到视频数据 (window.__playinfo__)。\n"
                "可能原因：视频已下架、需要大会员、或不是普通视频类型"
            )
        return __import__("json").loads(pattern.search(script.next).group(1))

    # ── 视频信息解析 ──────────────────────────────────────────

    async def _fetch_video_info(self, url: str, quality: str = "highest") -> VideoInfo:
        bs = await self._fetch_video_page(url)
        title = ILLEGAL_CHARS.sub("", self._extract_title(bs))
        data = self._extract_playinfo(bs)["data"]
        target_id = QUALITY_ALIAS.get(quality)

        if "dash" in data:
            return self._parse_dash(url, title, data["dash"], target_id)
        elif "durl" in data:
            return self._parse_durl(url, title, data)
        else:
            raise ValueError("未找到可下载的流 (dash 或 durl)")

    def _parse_dash(self, url: str, title: str, dash: dict, target_id: int | None) -> VideoInfo:
        video_streams = dash["video"]
        audio_streams = dash["audio"]

        if target_id is not None:
            matches = [v for v in video_streams if v["id"] == target_id]
            best_video = matches[0] if matches else video_streams[0]
        else:
            best_video = video_streams[0]

        return VideoInfo(
            url=url,
            title=title,
            quality_id=best_video["id"],
            video_url=best_video["baseUrl"],
            audio_url=audio_streams[0]["baseUrl"],
            is_durl=False,
            part_number=self._extract_part_number(url),
        )

    def _parse_durl(self, url: str, title: str, data: dict) -> VideoInfo:
        durl = data["durl"][0]
        return VideoInfo(
            url=url,
            title=title,
            quality_id=data.get("quality", 32),
            video_url=durl["url"],
            audio_url="",
            is_durl=True,
            part_number=self._extract_part_number(url),
        )

    # ── 下载 ──────────────────────────────────────────────────

    async def _download_video(self, video: VideoInfo) -> None:
        base = self.temp_dir / video.title
        video_path = f"{base}.mp4"
        audio_path = f"{base}.mp3"

        async with httpx.AsyncClient() as client:
            if video.is_durl:
                await self._download(client, video.video_url, video_path, "视频")
            else:
                results = await asyncio.gather(
                    self._download(client, video.video_url, video_path, "视频"),
                    self._download(client, video.audio_url, audio_path, "音频"),
                )
                if not all(results):
                    raise RuntimeError("视频或音频下载失败")

    async def _download(
        self, client: httpx.AsyncClient, url: str, filename: str,
        label: str = "文件", max_retries: int = 5,
    ) -> bool:
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                file_size = os.path.getsize(filename) if os.path.exists(filename) else 0
                headers = {**self._headers, "Range": f"bytes={file_size}-"}

                async with client.stream("GET", url, headers=headers) as resp:
                    if resp.status_code == 416:
                        logger.info("%s 已下载完毕", label)
                        return True

                    total = int(resp.headers.get("content-length", 0)) + file_size
                    mode = "ab" if file_size > 0 else "wb"
                    downloaded = file_size

                    with open(filename, mode) as f:
                        async for chunk in resp.aiter_bytes():
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)

                size_mb = (downloaded - file_size) / 1048576
                logger.info("%s 下载完成 (%.1f MB)", label, size_mb)
                return True
            except (httpx.RemoteProtocolError, httpx.RequestError) as e:
                logger.warning("%s 下载出错: %s，重试 (%d/%d)", label, e, attempt + 1, max_retries)
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)

        logger.error("%s 下载失败，已达最大重试次数", label)
        return False

    # ── 合并 ──────────────────────────────────────────────────

    def _merge(self, video: VideoInfo) -> str:
        base = self.temp_dir / video.title
        video_path = f"{base}.mp4"
        audio_path = f"{base}.mp3"
        output_path = str(self._resolve_output(video.title))

        if video.is_durl:
            shutil.move(video_path, output_path)
            logger.info("文件已移至: %s", output_path)
            return output_path

        if shutil.which("ffmpeg"):
            logger.info("使用 ffmpeg 合并...")
            result = subprocess.run(
                ["ffmpeg", "-i", video_path, "-i", audio_path,
                 "-c:v", "copy", "-c:a", "copy", output_path, "-y"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg 合并失败，退出码: {result.returncode}")
        else:
            logger.info("使用 moviepy 合并...")
            from moviepy import VideoFileClip
            clip = VideoFileClip(video_path)
            clip.write_videofile(output_path, audio=audio_path)
        logger.info("合并完成: %s", output_path)
        return output_path

    def _resolve_output(self, title: str) -> Path:
        """返回不冲突的输出路径，已存在则追加 _1, _2 等后缀。"""
        path = self.output_dir / f"{title}.mp4"
        if not path.exists():
            return path
        i = 1
        while (self.output_dir / f"{title}_{i}.mp4").exists():
            i += 1
        return self.output_dir / f"{title}_{i}.mp4"

    # ── 清理 ──────────────────────────────────────────────────

    def _extract_cover_frame(self, video: VideoInfo) -> str:
        """提取视频第一帧作为封面图（优先 ffmpeg，回退到 moviepy）。"""
        cover_path = str(self.output_dir / f"{video.title}_cover.jpg")
        try:
            if shutil.which("ffmpeg"):
                result = subprocess.run(
                    ["ffmpeg", "-i", video.output_path, "-vframes", "1",
                     "-q:v", "2", cover_path, "-y"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=30,
                )
                if result.returncode == 0:
                    return cover_path
                logger.warning("封面提取失败 (ffmpeg 退出码 %d)", result.returncode)
            else:
                logger.info("使用 moviepy 提取封面...")
                from moviepy import VideoFileClip
                clip = VideoFileClip(video.output_path)
                clip.save_frame(cover_path, t=0)
                clip.close()
                return cover_path
        except Exception as e:
            logger.warning("封面提取异常: %s", e)
        return ""

    def _cleanup(self, video: VideoInfo) -> None:
        base = self.temp_dir / video.title
        for ext in (".mp4", ".mp3"):
            p = f"{base}{ext}"
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            self.temp_dir.rmdir()
        except OSError:
            pass
