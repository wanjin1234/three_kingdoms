from __future__ import annotations

from typing import Callable, Sequence, Tuple


class SelectionService:
    """单位选择相关服务。"""

    def handle_selection_click(
        self,
        *,
        player_country: str | None,
        provinces: Sequence,
        unit_renderer,
        hex_side: float,
        mouse_pos: Tuple[int, int],
        on_add_selection: Callable[[int, int], None],
    ) -> None:
        if not player_country:
            return

        for province in provinces:
            if province.country != player_country or not province.units:
                continue
            center = (
                province.center_cache
                if province.center_cache
                else province.compute_center(hex_side)
            )
            rects = unit_renderer.selection_rects(center, len(province.units))
            for idx, rect in enumerate(rects):
                if rect.collidepoint(mouse_pos):
                    on_add_selection(province.province_id, idx)
                    return
