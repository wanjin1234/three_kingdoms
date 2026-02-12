"""
输入事件管理器。
负责把 pygame 的原始事件（按下键盘、点击鼠标、退出游戏）
转换成游戏内好理解的动作。
"""
from __future__ import annotations

import pygame as pg
from typing import TYPE_CHECKING

# 这是一个防止循环引用的技巧。
# 只有在做类型检查的时候才导入 GameApp，运行时不导入。
if TYPE_CHECKING:
    from src.core.app import GameApp


class EventManager:
    """
    事件管家。
    每一帧，它都会去问 pygame："刚才发生了什么？"
    然后把这些事件分发给 GameApp 的 handle_event 方法去处理。
    """
    
    def __init__(self, app: "GameApp") -> None:
        self.app = app

    def process(self) -> None:
        """
        处理所有挂起的事件。
        这个函数应该在游戏主循环的每一帧被调用。
        """
        # pg.event.get() 会获取自从上一帧以来发生的所有事件列表
        for event in pg.event.get():
            # 把事件扔给 app 去决定具体怎么回应
            self.app.handle_event(event)
