"""todo_list_labels 工具测试。"""

from unittest.mock import MagicMock, PropertyMock

import pytest

from tests.test_todo.helpers import apaginate
from tools.todo.tool_list_labels import TodoListLabelsTool


def _make_tool(mock_api, mock_client):
    tool = TodoListLabelsTool(client=mock_client)
    helper = tool.helper
    type(helper).api = PropertyMock(return_value=mock_api)
    return tool


class TestListLabels:
    @pytest.mark.asyncio
    async def test_returns_labels(self, mock_api, mock_client):
        l = MagicMock()
        l.id = "l1"
        l.name = "urgent"
        l.color = "red"
        l.order = 1
        l.is_favorite = False
        mock_api.get_labels = apaginate([[l]])

        tool = _make_tool(mock_api, mock_client)
        result = await tool._arun(get_doc=False)
        assert "success" in result
        assert "labels" in result
