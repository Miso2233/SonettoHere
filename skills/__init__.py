"""Skill 集中注册 — ALL_SKILLS 供 Agent 使用。"""

from langchain_core.tools import BaseTool

from skills.base import SharedAPIClient

# 懒加载 client，避免循环导入
_client: SharedAPIClient | None = None


def _get_client() -> SharedAPIClient:
    global _client
    if _client is None:
        _client = SharedAPIClient()
    return _client


def get_all_skills() -> list[BaseTool]:
    """返回所有已注册的 Skill 实例。"""
    client = _get_client()

    # System
    from skills.system.skill_time import TimeSkill
    from skills.system.skill_python import RunPythonSkill

    # Todo
    from skills.todo.skill_add import TodoAddSkill
    from skills.todo.skill_list import TodoListSkill
    from skills.todo.skill_complete import TodoCompleteSkill
    from skills.todo.skill_uncomplete import TodoUncompleteSkill
    from skills.todo.skill_delete import TodoDeleteSkill
    from skills.todo.skill_update import TodoUpdateSkill
    from skills.todo.skill_query import TodoQuerySkill
    from skills.todo.skill_list_projects import TodoListProjectsSkill

    # Map
    from skills.map.skill_nearby import NearbySearchSkill
    from skills.map.skill_geocode import GeocodeSkill
    from skills.map.skill_transit import TransitRouteSkill
    from skills.map.skill_cycling import CyclingRouteSkill
    from skills.map.skill_fuzzy_addr import FuzzyAddressSkill

    # Network
    from skills.network.skill_weather import WeatherSkill
    from skills.network.skill_search import SmartSearchSkill
    from skills.network.skill_scraper import WebScraperSkill
    from skills.network.skill_holiday import HolidayCalendarSkill
    from skills.network.skill_image_understand import ImageUnderstandSkill

    # Files
    from skills.files.skill_file_ops import FileOperationsSkill
    from skills.files.skill_file_edit import FileEditSkill
    from skills.files.skill_pdf_reader import PDFReaderSkill
    from skills.files.skill_doc_reader import DocReaderSkill

    # Development
    from skills.development.skill_syntax import SyntaxCheckerSkill
    from skills.development.skill_code_quality import CodeQualitySkill
    from skills.development.skill_unit_test import UnitTestSkill
    from skills.development.skill_debug import DebuggerSkill

    # Task
    from skills.task.skill_tracker import TaskTrackerSkill

    # SubAgent
    from skills.sub_agent.skill_call_sub_agent import CallSubAgentSkill

    # Interaction
    from skills.interaction.skill_ask_qa import AskUserQASkill
    from skills.interaction.skill_ask_single_choice import AskUserSingleChoiceSkill
    from skills.interaction.skill_ask_multi_choice import AskUserMultiChoiceSkill

    # Entertainment
    from skills.entertainment.skill_answer_book import AnswerBookSkill
    from skills.entertainment.skill_tarot import TarotSkill

    # Bilibili
    from skills.bilibili.skill_download import BilibiliDownloadSkill
    from skills.bilibili.skill_set_cookie import BilibiliSetCookieSkill

    # Memory
    from skills.memory.skill_list_memories import ListMemoriesSkill
    from skills.memory.skill_read_memories import ReadMemoriesSkill
    from skills.memory.skill_create_memory import CreateMemorySkill
    from skills.memory.skill_update_memory import UpdateMemorySkill
    from skills.memory.skill_delete_memory import DeleteMemorySkill
    from skills.memory.skill_merge_memories import MergeMemoriesSkill

    return [
        # System
        TimeSkill(client=client),
        RunPythonSkill(client=client),
        # Todo
        TodoAddSkill(client=client),
        TodoListSkill(client=client),
        TodoCompleteSkill(client=client),
        TodoUncompleteSkill(client=client),
        TodoDeleteSkill(client=client),
        TodoUpdateSkill(client=client),
        TodoQuerySkill(client=client),
        TodoListProjectsSkill(client=client),
        # Map
        NearbySearchSkill(client=client),
        GeocodeSkill(client=client),
        TransitRouteSkill(client=client),
        CyclingRouteSkill(client=client),
        FuzzyAddressSkill(client=client),
        # Network
        WeatherSkill(client=client),
        SmartSearchSkill(client=client),
        WebScraperSkill(client=client),
        HolidayCalendarSkill(client=client),
        ImageUnderstandSkill(client=client),
        # Files
        FileOperationsSkill(client=client),
        FileEditSkill(client=client),
        PDFReaderSkill(client=client),
        DocReaderSkill(client=client),
        # Development
        SyntaxCheckerSkill(client=client),
        CodeQualitySkill(client=client),
        UnitTestSkill(client=client),
        DebuggerSkill(client=client),
        # Task
        TaskTrackerSkill(client=client),
        # SubAgent
        CallSubAgentSkill(client=client),
        # Interaction
        AskUserQASkill(client=client),
        AskUserSingleChoiceSkill(client=client),
        AskUserMultiChoiceSkill(client=client),
        # Entertainment
        AnswerBookSkill(client=client),
        TarotSkill(client=client),
        # Bilibili
        BilibiliSetCookieSkill(client=client),
        BilibiliDownloadSkill(client=client),
        # Memory
        ListMemoriesSkill(client=client),
        ReadMemoriesSkill(client=client),
        CreateMemorySkill(client=client),
        UpdateMemorySkill(client=client),
        DeleteMemorySkill(client=client),
        MergeMemoriesSkill(client=client),
    ]
