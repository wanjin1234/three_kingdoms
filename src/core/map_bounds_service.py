from __future__ import annotations

from math import sqrt
from typing import Sequence

import pygame as pg

SQRT3 = sqrt(3)


class MapBoundsService:
    """地图像素包围盒查询服务。"""

    def get_map_bounds_rect(
        self,
        *,
        provinces: Sequence,
        hex_side: float,
        screen_width: int,
        screen_height: int,
    ) -> pg.Rect:
        if not provinces:
            return pg.Rect(0, 0, screen_width, screen_height)

        x_min = float("inf")
        y_min = float("inf")
        x_max = float("-inf")
        y_max = float("-inf")

        half_h = (SQRT3 * hex_side) / 2
        for province in provinces:
            center = (
                province.center_cache
                if province.center_cache
                else province.compute_center(hex_side)
            )
            cx, cy = center
            x_min = min(x_min, cx - hex_side)
            x_max = max(x_max, cx + hex_side)
            y_min = min(y_min, cy - half_h)
            y_max = max(y_max, cy + half_h)

        left = max(0, int(x_min))
        top = max(0, int(y_min))
        right = min(screen_width, int(x_max))
        bottom = min(screen_height, int(y_max))
        return pg.Rect(left, top, max(1, right - left), max(1, bottom - top))
