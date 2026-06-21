import type { Component } from 'vue'
import TodoBubble from './TodoBubble.vue'
import TaskTrackerBubble from './TaskTrackerBubble.vue'
import PythonBubble from './PythonBubble.vue'
import FilesBubble from './FilesBubble.vue'
import FileEditBubble from './FileEditBubble.vue'
import TarotBubble from './TarotBubble.vue'
import AnswerBookBubble from './AnswerBookBubble.vue'
import MapBubble from './MapBubble.vue'
import WeatherBubble from './WeatherBubble.vue'
import HolidayBubble from './HolidayBubble.vue'
import TimeBubble from './TimeBubble.vue'
import SyntaxBubble from './SyntaxBubble.vue'
import ImageBubble from './ImageBubble.vue'
import PdfReaderBubble from './PdfReaderBubble.vue'
import DocReaderBubble from './DocReaderBubble.vue'
import CodeQualityBubble from './CodeQualityBubble.vue'
import UnitTestBubble from './UnitTestBubble.vue'
import DebuggerBubble from './DebuggerBubble.vue'
import TavilySearchBubble from './TavilySearchBubble.vue'
import TavilyExtractBubble from './TavilyExtractBubble.vue'
import AskUserBubble from './AskUserBubble.vue'
import MemoryBubble from './MemoryBubble.vue'

/** 工具注册表：tool_name → 专属气泡组件 */
const registry: Record<string, Component> = {
  'todo_add': TodoBubble,
  'todo_list': TodoBubble,
  'todo_complete': TodoBubble,
  'todo_uncomplete': TodoBubble,
  'todo_delete': TodoBubble,
  'todo_update': TodoBubble,
  'todo_query': TodoBubble,
  'todo_list_projects': TodoBubble,
  'todo_add_quick': TodoBubble,
  'todo_list_sections': TodoBubble,
  'todo_list_labels': TodoBubble,
  'task_tracker': TaskTrackerBubble,
  'run_python': PythonBubble,
  'file_read': FilesBubble,
  'file_write': FilesBubble,
  'file_list': FilesBubble,
  'file_operations': FilesBubble,
  'file_edit': FileEditBubble,
  'tarot': TarotBubble,
  'answer_book': AnswerBookBubble,
  'nearby_search': MapBubble,
  'fuzzy_address_search': MapBubble,
  'geocode_address': MapBubble,
  'get_transit_route': MapBubble,
  'get_cycling_route': MapBubble,
  'get_current_weather': WeatherBubble,
  'holiday_calendar': HolidayBubble,
  'time_tool': TimeBubble,
  'syntax_checker': SyntaxBubble,
  'analyze_image': ImageBubble,
  'tavily_search': TavilySearchBubble,
  'pdf_reader': PdfReaderBubble,
  'doc_reader': DocReaderBubble,
  'code_quality_analyzer': CodeQualityBubble,
  'unit_test_runner': UnitTestBubble,
  'debugger': DebuggerBubble,
  'tavily_extract': TavilyExtractBubble,
  'ask_user_for_info': AskUserBubble,
  'ask_user_qa': AskUserBubble,
  'ask_user_single_choice': AskUserBubble,
  'ask_user_multi_choice': AskUserBubble,

  /* Memory */
  'list_memories': MemoryBubble,
  'read_memories': MemoryBubble,
  'create_memory': MemoryBubble,
  'update_memory': MemoryBubble,
  'delete_memory': MemoryBubble,
  'merge_memories': MemoryBubble,
}

export function getBubbleComponent(name: string): Component | null {
  if (registry[name]) return registry[name]
  return null
}

export function getRegisteredTools(): string[] {
  return Object.keys(registry)
}
