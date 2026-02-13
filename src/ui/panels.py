"""
负责 UI 面板的绘制，比如选中单位时的高亮框。
"""
from __future__ import annotations

from typing import Callable, List, Sequence, Tuple

import pygame as pg

from src.map.province import Province

# 定义一些类型别名，方便阅读
# RectProvider 是一个函数，接收中心点和单位数量，返回一组矩形区域
RectProvider = Callable[[Tuple[int, int], int], List[pg.Rect]]
# ProvinceLookup 是一个函数，接收 ID，返回 Province 对象
ProvinceLookup = Callable[[int], Province | None]
SelectionEntry = Tuple[int, int]


class SelectionOverlay:
    """
    选中状态的覆盖层。
    当玩家选中某个兵时，这个类负责在那个兵的头上画个框框，表示“我被选中了”。
    """
    
    def __init__(self, *, color: str = "yellow", border_width: int = 3) -> None:
        self._color = pg.Color(color)
        self._border_width = border_width

    def draw(
        self,
        *,
        surface: pg.Surface,
        selections: Sequence[SelectionEntry], # 选中的列表 (格子ID, 兵的索引)
        province_lookup: Callable[[int], Province | None],
        rect_provider: Callable[[tuple[int, int], int], Sequence[pg.Rect]],
        hex_side: float,
    ) -> None:
        """
        绘制高亮框。
        """
        if not selections:
            return

        for province_id, slot_index in selections:
            # 找到被选中的格子
            province = province_lookup(province_id)
            if province is None:
                continue

            # 找到格子的屏幕位置
            # 优先使用缓存的中心点
            center = province.center_cache if province.center_cache else province.compute_center(hex_side)
            
            # 找到该格子里那个兵的具体矩形位置
            rects = rect_provider(center, len(province.units))
            if slot_index < len(rects):
                target_rect = rects[slot_index]
                
                # 画一个黄色的矩形框，宽度为 3 像素
                pg.draw.rect(surface, self._color, target_rect, self._border_width)
