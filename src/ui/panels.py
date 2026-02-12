"""User interface overlays and panels."""
from __future__ import annotations

from typing import Callable, Sequence, Tuple

import pygame as pg

from src.map.province import Province

SelectionEntry = Tuple[int, int]


class SelectionOverlay:
    """Draws highlight rectangles for selected unit slots."""

    def __init__(self, *, color: str = "yellow", border_width: int = 3) -> None:
        self._color = pg.Color(color)
        self._border_width = border_width

    def draw(
        self,
        *,
        surface: pg.Surface,
        selections: Sequence[SelectionEntry],
        province_lookup: Callable[[int], Province | None],
        rect_provider: Callable[[tuple[int, int], int], Sequence[pg.Rect]],
        hex_side: float,
    ) -> None:
        for province_id, slot_index in selections:
            province = province_lookup(province_id)
            if province is None:
                continue
            center = province.compute_center(hex_side)
            rects = rect_provider(center, len(province.units))
            if slot_index < len(rects):
                pg.draw.rect(surface, self._color, rects[slot_index], self._border_width)
