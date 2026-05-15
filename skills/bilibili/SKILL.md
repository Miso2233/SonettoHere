# Bilibili 视频下载

## bilibili_set_cookie
设置/更新 B 站 Cookie，用于视频下载鉴权。

Cookie 获取方式：
1. 在浏览器中登录 B 站 (bilibili.com)
2. 按 F12 打开开发者工具
3. 进入 Application > Cookies > bilibili.com
4. 复制完整 Cookie 字符串

Cookie 约 30 天过期，过期后需重新设置。
Cookie 保存在本地文件中，不会上传到任何服务器。

## bilibili_download
下载 B 站视频。若失败，则需要先用 bilibili_set_cookie 设置有效 Cookie。

### 参数
- url: B 站视频链接。支持格式：
  - https://www.bilibili.com/video/BVxxx/
  - https://www.bilibili.com/video/BVxxx/?p=2（多 P 视频指定分 P）
  - https://www.bilibili.com/video/avxxx/
- quality: 画质偏好，默认 "highest"（自动选最高可用画质）

### 画质选项
| 选项 | 说明 |
|------|------|
| 8K | 超高清，需大会员 |
| 4K | 超清，需大会员 |
| 1080P | 高清，需登录 |
| 720P | 高清 |
| 480P | 清晰 |
| 360P | 流畅（无需登录） |
| highest | 自动选最高可用 |

### 下载流程
1. 抓取视频页面提取流地址
2. 并发下载视频+音频（DASH 格式）或单文件（DURL 格式）
3. 使用 ffmpeg / moviepy 合并音视频
4. 输出到 output/bilibili/ 目录

### 注意事项
- 需安装 ffmpeg（推荐）或 moviepy 用于合并
- 下载的临时文件会自动清理
- 视频仅用于个人学习，请遵守 B 站用户协议
