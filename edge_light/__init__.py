"""屏幕边缘灯原生覆盖层（Computer Use 状态提示）。

- ``overlay``: 独立 PySide6 子进程入口，通过 stdin 接收状态指令
  （off / steady / blink），在全屏边缘渲染白色辉光环。
- 该包不得导入 ``api`` / ``agent`` 等后端模块，保证可被后端以子进程方式
  独立运行；后端侧控制器见 :mod:`api.edge_light`。
"""

__all__: list[str] = []
