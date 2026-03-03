from __future__ import annotations

from math import dist
from typing import Sequence, Tuple


class ProvinceQueryService:
    """地图点击拾取查询服务。"""

    def get_unit_slot_at(
        self,
        *,
        provinces: Sequence,
        unit_renderer,
        hex_side: float,
        pos: Tuple[int, int],
    ) -> Tuple[int, int] | None:
        for p in provinces:
            if not p.units:
                continue

            center = (p.center_cache if p.center_cache else p.compute_center(hex_side))
            if dist(pos, center) > hex_side:
                continue

            rects = unit_renderer.selection_rects(center, len(p.units))
            for i, r in enumerate(rects):
                if r.collidepoint(pos):
                    return (p.province_id, i)
        return None

    def get_province_at(
        self,
        *,
        provinces: Sequence,
        hex_side: float,
        pos: Tuple[int, int],
    ):
        best_p = None
        min_dist = float("inf")
        threshold = hex_side * 0.9

        for province in provinces:
            center = (
                province.center_cache
                if province.center_cache
                else province.compute_center(hex_side)
            )
            d = dist(pos, center)
            if d < min_dist:
                min_dist = d
                best_p = province

        if min_dist <= threshold:
            return best_p
        return None
