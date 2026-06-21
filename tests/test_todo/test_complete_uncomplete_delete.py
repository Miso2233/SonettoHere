"""todo_complete / todo_uncomplete / todo_delete 工具测试。"""

from unittest.mock import MagicMock, PropertyMock

from tools.todo.tool_complete import TodoCompleteTool
from tools.todo.tool_uncomplete import TodoUncompleteTool
from tools.todo.tool_delete import TodoDeleteTool


class _BaseTest:
    def _make_tool(self, tool_cls, mock_api, mock_client):
        tool = tool_cls(client=mock_client)
        helper = tool.helper
        type(helper).api = PropertyMock(return_value=mock_api)
        return tool


class TestComplete(_BaseTest):
    def test_empty_id_returns_error(self, mock_api, mock_client):
        tool = self._make_tool(TodoCompleteTool, mock_api, mock_client)
        result = tool._run(get_doc=False, task_id="")
        assert "不能为空" in result

    def test_complete_success(self, mock_api, mock_client):
        t = MagicMock()
        t.id = "t1"
        t.content = "Task"
        mock_api.get_task.return_value = t
        mock_api.complete_task.return_value = True

        tool = self._make_tool(TodoCompleteTool, mock_api, mock_client)
        result = tool._run(get_doc=False, task_id="t1")
        assert "success" in result
        mock_api.complete_task.assert_called_once_with("t1")


class TestUncomplete(_BaseTest):
    def test_uncomplete_success(self, mock_api, mock_client):
        t = MagicMock()
        t.id = "t1"
        t.content = "Task"
        mock_api.get_task.return_value = t
        mock_api.uncomplete_task.return_value = True

        tool = self._make_tool(TodoUncompleteTool, mock_api, mock_client)
        result = tool._run(get_doc=False, task_id="t1")
        assert "success" in result
        mock_api.uncomplete_task.assert_called_once_with("t1")


class TestDelete(_BaseTest):
    def test_delete_success(self, mock_api, mock_client):
        mock_api.delete_task.return_value = True

        tool = self._make_tool(TodoDeleteTool, mock_api, mock_client)
        result = tool._run(get_doc=False, task_id="t1")
        assert "success" in result
        mock_api.delete_task.assert_called_once_with("t1")
