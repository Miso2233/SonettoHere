# Tool 与 Skill 系统

## Tool 在 LangChain 中的定位

在 LangChain 中，**Tool** 是 LLM 与外部世界交互的唯一通道。LLM 本身不能执行代码、访问网络或读写文件——它只能通过 tool_call 机制"请求"框架代为执行某个工具函数，然后接收返回结果。

LangChain 的 Tool 体系由三个核心抽象组成：

```
BaseTool           ← 所有 Tool 的基类，定义 name / description / _run()
    ↑
args_schema        ← Pydantic BaseModel，定义工具的输入参数和类型约束
    ↑
bind_tools(model)  ← 将工具列表绑定到 LLM，使 LLM 能生成 tool_calls
```

---

## 本项目 Tool 体系的层次结构

```
LangChain BaseTool
    ↓
ToolBase (tools/base.py)         ← 本项目的 Tool 基类
    ↓              ↓
  简单 Skill      复杂 Skill（领域 Skill）
  (time_skill)    (todo_add, nearby_search, weather...)
                    ↓
              两步调用模式：get_doc=true → 读 TOOL.md → 带真实参数执行
```

---

## ToolBase: 本项目的 Tool 基类

在 [tools/base.py](../tools/base.py) 中：

```python
class ToolBase(BaseTool):
    client: SharedAPIClient | None = None

    def _load_doc(self) -> str:
        """读取同目录下的 TOOL.md，作为领域知识返回给 LLM。"""
        mod = sys.modules.get(self.__class__.__module__)
        if mod is not None and hasattr(mod, "__file__") and mod.__file__ is not None:
            skill_dir = Path(mod.__file__).parent
        else:
            skill_dir = Path(".")
        doc_path = skill_dir / "TOOL.md"
        if doc_path.exists():
            return doc_path.read_text(encoding="utf-8")
        return "（本 Skill 暂无文档）"
```

### 关键设计点

**1. 继承 `BaseTool`**

`ToolBase` 继承了 LangChain 的 `BaseTool`，因此所有 Skill 实例都可以直接传入 `create_react_agent(tools=...)`。`BaseTool` 要求子类必须提供：
- `name`：工具的唯一标识符，LLM 用它指定要调用哪个工具
- `description`：工具的功能描述，LLM 用它判断"当前场景该用哪个工具"
- `_run()`：工具的实际执行逻辑

**2. `_load_doc()` 方法**

这是两步调用模式的核心。当 LLM 以 `get_doc=true` 调用 Skill 时，`_run()` 不执行实际逻辑，而是调用 `_load_doc()` 返回同目录下 `TOOL.md` 的内容。LLM 阅读文档后，在下一轮推理中就会理解该领域的参数约定、协作流程和常见陷阱。

**为什么需要领域文档？**
- 领域知识（如"高德地图经纬度顺序是 `lng,lat`，不能搞反"）写在代码注释中 LLM 看不到
- 将所有领域知识塞入系统提示词会超出上下文限制
- 将知识放在每个 Skill 文件夹的 `TOOL.md` 中，按需加载，精准且不浪费 token

**3. `client` 属性**

所有 Skill 共享同一个 `SharedAPIClient` 实例，避免重复加载 API Key 和重复创建 HTTP 连接。

---

## `get_doc=true` 两步调用模式（完整流程）

以 `todo_add` Skill 为例：

```
第 1 轮：
  LLM Thought:  用户想添加任务，但我还不了解 Todoist 的参数规则
  Action:        todo_add(get_doc=true)
  Observation:   [TOOL.md 全文返回给 LLM]

第 2 轮：
  LLM Thought:  了解了——需要先调用 todo_list_projects 确认项目名存在，
                 due_date 支持自然语言，priority 1-4
  Action:        todo_list_projects()
  Observation:   [{"name": "工作", "id": "xxx"}, {"name": "个人", "id": "yyy"}]

第 3 轮：
  LLM Thought:  用户的项目"工作"存在，现在可以添加任务了
  Action:        todo_add(content="完成项目报告", project_name="工作", priority=2, due_date="明天下午5点")
  Observation:   {"success": true, "data": {"task_id": "...", ...}}

第 4 轮：
  LLM Thought:  任务已成功添加
  Answer:        "已在'工作'项目中为你添加了'完成项目报告'，优先级中等，截止时间为明天下午5点～"
```

### TOOL.md 的规范结构

以 Todo 领域的 [TOOL.md](../tools/todo/TOOL.md) 为例，文档包含：
1. **技能协作流程**：多个 Skill 之间的调用顺序建议
2. **常见陷阱**：容易出错的地方和正确做法
3. **参数约定**：每个参数的含义、格式和有效值
4. **错误处理规范**：各类错误场景的应对策略表格

这种结构化文档让 LLM 能快速获取领域知识，减少试错次数。

---

## 简单 Skill vs 复杂 Skill

### 简单 Skill（无需领域文档）

`time_skill` 是一个典型例子。它没有 `get_doc` 参数，`description` 直接告诉 LLM "直接调用即可，无需先读文档"：

```python
class TimeTool(ToolBase):
    name: str = "time_skill"
    description: str = "获取当前日期和时间。直接调用即可，无需先读文档。"
    args_schema: type[BaseModel] = TimeInput  # 空参数模型

    def _run(self) -> str:
        now = datetime.now()
        return format_success({
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": now.strftime("%A"),
            "timezone": "Asia/Shanghai",
        })
```

这类 Skill 的 `_run()` 只做纯粹的计算或查询，无外部 API 依赖，无复杂参数规则。

### 复杂 Skill（需要领域文档）

`nearby_search` 是典型的需要领域文档的 Skill：

```python
class NearbySearchInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    location: str = Field(default="", description='中心点坐标，格式为"经度,纬度"')
    keywords: str | None = Field(default=None, description="搜索关键字")
    types: str | None = Field(default=None, description="POI类型码")
    radius: int = Field(default=1000, description="搜索半径（米）")
    sortrule: int = Field(default=1, description="0=距离排序，1=综合排序")
    ...

def _run(self, get_doc=False, ...):
    if get_doc:
        return self._load_doc()  # ← 先返回领域知识
    # 实际业务逻辑...
```

关键模式：`get_doc` 作为第一个参数，`_run()` 第一行检查 `get_doc`，为 `True` 时直接返回 `TOOL.md` 内容。

---

## Pydantic 参数校验

每个 Skill 的输入参数由 Pydantic `BaseModel` 定义，作为 `args_schema` 绑定到 Tool 上：

```python
class TodoAddInput(BaseModel):
    content: str = Field(default="", description="任务名称/内容")
    due_date: str | None = Field(default=None, description="截止日期...")
    priority: int = Field(default=1, description="1=低, 2=中, 3=高, 4=紧急")
    project_name: str = Field(default="Inbox", description="所属项目名")
```

### Pydantic 在 Tool 系统中的三重作用

1. **Schema 生成**：LangChain 自动将 `BaseModel` 转换为 OpenAI function calling 的 `parameters` JSON Schema，LLM 据此生成合法的 tool_call 参数

2. **类型校验**：框架在调用 `_run()` 前自动校验参数类型。若 LLM 传了 `priority="high"` 而非 `int`，Pydantic 抛出 `ValidationError`，工具不会执行

3. **默认值**：`Field(default=...)` 定义了未传参数时的回退值，减少 LLM 必须填写的参数数量

### Field description 的重要性

`description` 是 LLM 理解参数含义的**唯一渠道**。一个模糊的 description（如 `description="搜索关键字"`）和一个精确的 description（如 `description="POI类型码，如'050000'（餐饮）。与 keywords 二选一"`）对 LLM 的决策质量有显著影响。

---

## SharedAPIClient: 共享 HTTP 客户端

在 [tools/base.py](../tools/base.py) 中：

```python
class SharedAPIClient:
    def __init__(self):
        settings = get_settings()
        self._session = requests.Session()
        self._uapi: UapiClient | None = None
        self._todoist: TodoistAPI | None = None
        self._amap_key = settings.amap_api_key

    @property
    def uapi(self) -> UapiClient:
        if self._uapi is None:
            self._uapi = UapiClient("https://uapis.cn", token=self._uapis_key)
        return self._uapi

    @property
    def todoist(self) -> TodoistAPI:
        if self._todoist is None:
            self._todoist = TodoistAPI(self._todoist_token)
        return self._todoist
```

### 设计意图

- **懒加载**：只有在 LLM 真正调用某个 Skill 时，对应的 API 客户端才被初始化
- **单例共享**：所有 Skill 共享同一个 `SharedAPIClient`，避免为每个 Skill 创建一个 HTTP session
- **Key 集中管理**：所有 API Key 从 `Settings` 一次性加载，不在 Skill 代码中硬编码

---

## Skill 集中注册

在 [tools/__init__.py](../tools/__init__.py) 中，`get_all_tools()` 集中注册了全部 30 个 Skill：

```python
def get_all_tools() -> list[BaseTool]:
    client = _get_client()
    return [
        # System
        TimeTool(client=client),
        RunPythonSkill(client=client),
        # Todo
        TodoAddSkill(client=client),
        TodoListSkill(client=client),
        ...
        # 共 30 个
    ]
```

这种集中注册的好处：
- **一目了然**：所有可用工具在一个地方声明
- **有序排列**：按领域分组，便于维护
- **类型安全**：返回类型 `list[BaseTool]` 确保每个元素都是合法的 LangChain Tool

---

## Skill 列表与分类

| 领域 | Skill 名称 | 外部依赖 | 领域文档 |
|------|-----------|----------|----------|
| **System** | `time_skill` | 无 | 无 |
| | `run_python` | 无（本地执行） | 无 |
| **Todo** | `todo_add` / `todo_list` / `todo_complete` / `todo_uncomplete` / `todo_delete` / `todo_update` / `todo_query` / `todo_list_projects` | Todoist API | [TOOL.md](../tools/todo/TOOL.md) |
| **Map** | `nearby_search` / `geocode_address` / `get_transit_route` / `get_cycling_route` / `fuzzy_address_search` | 高德地图 API | [TOOL.md](../tools/map/TOOL.md) |
| **Network** | `get_current_weather` / `smart_search` / `web_scraper` / `holiday_calendar` | UAPI + HTTP | [TOOL.md](../tools/network/TOOL.md) |
| **Files** | `file_operations` / `pdf_reader` / `doc_reader` | 本地文件系统 | [TOOL.md](../tools/files/TOOL.md) |
| **Development** | `syntax_checker` / `code_quality` / `unit_test` / `debugger` | 本地执行 | [TOOL.md](../tools/development/TOOL.md) |
| **Task** | `task_tracker` | 无（内存状态） | [TOOL.md](../tools/task/TOOL.md) |
| **Interaction** | `ask_user` | 无 | [TOOL.md](../tools/interaction/TOOL.md) |
| **Entertainment** | `answer_book` / `tarot` | UAPI + 内置塔罗牌库 | [TOOL.md](../tools/entertainment/TOOL.md) |

---

## 响应格式统一

所有 Skill 的返回值使用统一的 JSON 格式：

```python
def format_success(data: dict) -> str:
    return json.dumps({"success": True, "data": data}, ensure_ascii=False)

def format_error(message: str) -> str:
    return json.dumps({"success": False, "error": message}, ensure_ascii=False)
```

统一的格式让 LLM 能一致地解析成功和失败结果，不需要为每个 Skill 学习不同的响应格式。

---

## 下一节

[记忆系统](04-记忆系统.md) — 深入分析三层记忆架构：短期记忆的 token 裁剪策略、长期记忆的多维度评分检索、以及用户偏好画像的聚合维护。
