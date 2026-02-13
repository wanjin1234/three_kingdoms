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
    
    def __init__(self, *, color: str = "#FFD700", border_width: int = 4) -> None:
        # 使用更显眼的金色 (Gold) 替代纯黄
        self._color = pg.Color(color)
        self._border_width = border_width
        # Arial 比较难看，改为使用 Verdana，它在屏幕显示上清晰且数字居中效果较好
        self._font = pg.font.SysFont("Verdana", 24, bold=True)

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

        badges = [] # 暂存标号信息，最后统一绘制，防止被遮挡

        for order_idx, (province_id, slot_index) in enumerate(selections):
            # 找到被选中的格子
            province = province_lookup(province_id)
            if province is None:
                continue

            # 找到格子的屏幕位置
            center = province.center_cache if province.center_cache else province.compute_center(hex_side)
            
            # 找到该格子里那个兵的具体矩形位置
            rects = rect_provider(center, len(province.units))
            if slot_index < len(rects):
                target_rect = rects[slot_index]
                
                # 1. 绘制主体框 (Gold)
                pg.draw.rect(surface, self._color, target_rect, width=self._border_width, border_radius=3)
                
                # 2. 绘制内部阴影 (Inner Shadow)
                # 使用一个比主体框稍微小一点的框，画深色边线，营造内陷感
                inner_rect = target_rect.inflate(-self._border_width, -self._border_width)
                pg.draw.rect(surface, pg.Color(139, 101, 8), inner_rect, width=1, border_radius=2)
                
                # 收集标号信息
                badges.append((order_idx + 1, target_rect))

        # 3. 统一绘制所有标号 (Ensure Z-Index Top)
        for num, rect in badges:
            label_num = str(num)
            text_surf = self._font.render(label_num, True, pg.Color("white"))
            
            # 标号圆圈位置
            circle_radius = 16 # 加大圆圈 (原本12)
            cx = rect.right
            cy = rect.top
            
            pg.draw.circle(surface, pg.Color("black"), (cx, cy), circle_radius)
            pg.draw.circle(surface, pg.Color("white"), (cx, cy), circle_radius, 1) # 白色边框
            
            # 文字居中
            text_rect = text_surf.get_rect(center=(cx, cy))
            surface.blit(text_surf, text_rect)
