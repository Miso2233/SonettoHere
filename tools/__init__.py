"""工具（Tool）集中注册 — ALL_TOOLS 供 Agent 使用。"""

from langchain_core.tools import BaseTool

from tools.base import SharedAPIClient

# 懒加载 client，避免循环导入
_client: SharedAPIClient | None = None


def _get_client() -> SharedAPIClient:
    global _client
    if _client is None:
        _client = SharedAPIClient()
    return _client


def get_all_tools() -> list[BaseTool]:
    """返回所有已注册的 Tool 实例。"""
    client = _get_client()

    # System
    from tools.system.tool_time import TimeTool
    from tools.system.tool_python import RunPythonTool

    # Todo
    from tools.todo.tool_add import TodoAddTool
    from tools.todo.tool_list import TodoListTool
    from tools.todo.tool_complete import TodoCompleteTool
    from tools.todo.tool_uncomplete import TodoUncompleteTool
    from tools.todo.tool_delete import TodoDeleteTool
    from tools.todo.tool_update import TodoUpdateTool
    from tools.todo.tool_query import TodoQueryTool
    from tools.todo.tool_list_projects import TodoListProjectsTool
    from tools.todo.tool_list_sections import TodoListSectionsTool
    from tools.todo.tool_list_labels import TodoListLabelsTool

    # Map
    from tools.map.tool_nearby import NearbySearchTool
    from tools.map.tool_geocode import GeocodeTool
    from tools.map.tool_transit import TransitRouteTool
    from tools.map.tool_cycling import CyclingRouteTool
    from tools.map.tool_fuzzy_addr import FuzzyAddressTool

    # Network
    from tools.network.tool_weather import WeatherTool
    from tools.network.tool_holiday import HolidayCalendarTool
    from tools.network.tool_image_understand import ImageUnderstandTool
    from tools.network.tavily import TavilySearchTool, TavilyExtractTool

    # Files
    from tools.files.tool_file_ops import FileOperationsTool
    from tools.files.tool_file_edit import FileEditTool
    from tools.files.tool_pdf_reader import PDFReaderTool
    from tools.files.tool_doc_reader import DocReaderTool

    # Development
    from tools.development.tool_syntax import SyntaxCheckerTool
    from tools.development.tool_code_quality import CodeQualityTool
    from tools.development.tool_unit_test import UnitTestTool
    from tools.development.tool_debug import DebuggerTool

    # Task
    from tools.task.tool_tracker import TaskTrackerTool

    # SubAgent
    from tools.sub_agent.tool_call_sub_agent import CallSubAgentTool

    # Interaction
    from tools.interaction.tool_ask_qa import AskUserQATool
    from tools.interaction.tool_single_choice import AskUserSingleChoiceTool
    from tools.interaction.tool_multi_choice import AskUserMultiChoiceTool

    # Entertainment
    from tools.entertainment.tool_answer_book import AnswerBookTool
    from tools.entertainment.tool_tarot import TarotTool

    # Memory
    from tools.memory.tool_list_memories import ListMemoriesTool
    from tools.memory.tool_read_memories import ReadMemoriesTool
    from tools.memory.tool_create_memory import CreateMemoryTool
    from tools.memory.tool_update_memory import UpdateMemoryTool
    from tools.memory.tool_delete_memory import DeleteMemoryTool
    from tools.memory.tool_merge_memories import MergeMemoriesTool

    return [
        # System
        TimeTool(client=client),
        RunPythonTool(client=client),
        # Todo
        TodoAddTool(client=client),
        TodoListTool(client=client),
        TodoCompleteTool(client=client),
        TodoUncompleteTool(client=client),
        TodoDeleteTool(client=client),
        TodoUpdateTool(client=client),
        TodoQueryTool(client=client),
        TodoListProjectsTool(client=client),
        TodoListSectionsTool(client=client),
        TodoListLabelsTool(client=client),
        # Map
        NearbySearchTool(client=client),
        GeocodeTool(client=client),
        TransitRouteTool(client=client),
        CyclingRouteTool(client=client),
        FuzzyAddressTool(client=client),
        # Network
        WeatherTool(client=client),
        HolidayCalendarTool(client=client),
        ImageUnderstandTool(client=client),
        TavilySearchTool(client=client),
        TavilyExtractTool(client=client),
        # Files
        FileOperationsTool(client=client),
        FileEditTool(client=client),
        PDFReaderTool(client=client),
        DocReaderTool(client=client),
        # Development
        SyntaxCheckerTool(client=client),
        CodeQualityTool(client=client),
        UnitTestTool(client=client),
        DebuggerTool(client=client),
        # Task
        TaskTrackerTool(client=client),
        # SubAgent
        CallSubAgentTool(client=client),
        # Interaction
        AskUserQATool(client=client),
        AskUserSingleChoiceTool(client=client),
        AskUserMultiChoiceTool(client=client),
        # Entertainment
        AnswerBookTool(client=client),
        TarotTool(client=client),
        # Memory
        ListMemoriesTool(client=client),
        ReadMemoriesTool(client=client),
        CreateMemoryTool(client=client),
        UpdateMemoryTool(client=client),
        DeleteMemoryTool(client=client),
        MergeMemoriesTool(client=client),
    ]
