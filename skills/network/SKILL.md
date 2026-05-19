# 网络服务领域知识

## 可用服务（均通过 UAPI）
| Skill | 功能 | 底层 API |
|-------|------|---------|
| `get_current_weather` | 实时天气/预报/生活指数 | UAPI misc.get_misc_weather |
| `smart_search` | 网络搜索 | UAPI zhi_neng_sou_suo.post_search_aggregate |
| `scrape_webpage` | 网页内容抓取 | Playwright 真实 Chromium 浏览器（有头模式） |
| `holiday_calendar` | 节假日/万年历查询 | UAPI misc.get_misc_holiday_calendar |
| `analyze_image` | 图片理解/OCR/描述 | GLM-5V-Turbo 多模态模型 |

## 技能协作流程
- **天气 + 节假日**：用户问"国庆节北京天气如何"时，先调 `holiday_calendar` 确认日期，再调 `get_current_weather`
- **搜索 + 抓取**：`smart_search` 返回摘要和 URL，如需详细内容再用 `scrape_webpage` 抓取全文。两个 Skill 独立调用，不要在一个 Skill 内部嵌套另一个
- **天气查询**：城市名和 adcode 二选一即可，不需要两个都填

## 常见陷阱
- **天气 city vs adcode**：传城市名时不要同时传 adcode，避免API混淆
- **smart_search 的 fetch_full**：本 Skill 不支持 fetch_full 参数。如需全文，先用 smart_search 获取 URL 列表，再逐条调用 scrape_webpage
- **scrape_webpage 人机验证**：默认无头模式（静默抓取）。如遇到 CAPTCHA/Turnstile/登录等需要手动交互的页面，可设置 `headless=false` 切换为有头模式，用户可在浏览器窗口中手动完成验证。此时可通过 `wait_ms` 调整等待时间（默认 5000ms）。导航超时 60 秒。
- **holiday_calendar 参数互斥**：date / month / year 三选一，不要同时传多个
- **analyze_image 图片来源**：本地用 `local:绝对路径`，网络用 `url:https://...`。prompt 默认"请描述这张图片"，可自定义提问如"文字是啥？""这是什么物体？"
- **天气 minutely 仅国内**：分钟级降水预报仅支持中国大陆城市
