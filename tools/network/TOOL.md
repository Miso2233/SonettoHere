# 网络服务领域知识

## 可用服务
| Skill | 功能 | 底层 API |
|-------|------|---------|
| `get_current_weather` | 实时天气/预报/生活指数 | UAPI misc.get_misc_weather |
| `tavily_search` | 网络搜索 | Tavily Search API |
| `tavily_extract` | 网页内容提取 | Tavily Extract API |
| `holiday_calendar` | 节假日/万年历查询 | UAPI misc.get_misc_holiday_calendar |
| `analyze_image` | 图片理解/OCR/描述 | GLM-5V-Turbo 多模态模型 |

## 技能协作流程
- **天气 + 节假日**：用户问"国庆节北京天气如何"时，先调 `holiday_calendar` 确认日期，再调 `get_current_weather`
- **搜索 + 提取**：`tavily_search` 返回摘要和 URL，如需详细内容再用 `tavily_extract` 提取全文。两个工具独立调用
- **天气查询**：城市名和 adcode 二选一即可，不需要两个都填

## 常见陷阱
- **天气 city vs adcode**：传城市名时不要同时传 adcode，避免API混淆
- **tavily_search 全文**：如需全文，设置 `include_raw_content=true`；如只需摘要看结果，保持 `include_raw_content=false` 以节省上下文
- **tavily_extract 批量**：最多一次 20 个 URL，JS 渲染页面用 `extract_depth="advanced"`
- **holiday_calendar 参数互斥**：date / month / year 三选一，不要同时传多个
- **analyze_image 图片来源**：本地用 `local:绝对路径`，网络用 `url:https://...`。prompt 默认"请描述这张图片"，可自定义提问如"文字是啥？""这是什么物体？"
- **天气 minutely 仅国内**：分钟级降水预报仅支持中国大陆城市
