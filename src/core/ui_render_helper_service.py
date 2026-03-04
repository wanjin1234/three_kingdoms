from __future__ import annotations

import logging
from math import sqrt
from typing import List, Sequence, Tuple

import pygame as pg

logger = logging.getLogger(__name__)
SQRT3 = sqrt(3)


class UIRenderHelperService:
    """渲染与UI辅助服务（阶段5-C：继续瘦身 GameApp）。"""

    def is_hovering_ban_line(self, app, mouse_pos: Tuple[int, int]) -> bool:
        return self.is_hovering_polyline(app, mouse_pos, [app.ban_line_polyline])

    def is_hovering_river(self, app, mouse_pos: Tuple[int, int]) -> bool:
        polylines = []
        polylines.extend(app.yangtze_polylines)
        polylines.append(app.yellow_river_polyline)
        return self.is_hovering_polyline(app, mouse_pos, polylines)

    def is_hovering_polyline(self, app, mouse_pos: Tuple[int, int], polylines_list) -> bool:
        threshold = 10.0
        m_vec = pg.math.Vector2(mouse_pos)

        for polyne in polylines_list:
            if len(polyne) < 2:
                continue

            for i in range(len(polyne) - 1):
                p1 = polyne[i]
                p2 = polyne[i + 1]

                line_vec = p2 - p1
                p1_m_vec = m_vec - p1

                line_len_sq = line_vec.length_squared()
                if line_len_sq == 0:
                    continue

                t = p1_m_vec.dot(line_vec) / line_len_sq
                t = max(0.0, min(1.0, t))

                closest_point = p1 + line_vec * t
                dist_sq = m_vec.distance_squared_to(closest_point)

                if dist_sq < threshold * threshold:
                    return True
        return False

    def scale_points(
        self,
        app,
        normalized_points: Sequence[Tuple[float, float]],
    ) -> List[pg.math.Vector2]:
        scaled = []
        for point in normalized_points:
            x_factor, y_factor = point
            x = x_factor * app.hex_side
            y = y_factor * SQRT3 * app.hex_side
            scaled.append(pg.math.Vector2(x, y))
        return scaled

    def load_ui_image(
        self,
        app,
        filename: str,
        size: Tuple[int, int] | None,
    ) -> pg.Surface:
        filepath = app.settings.ui_graphics_dir / filename

        try:
            surface = pg.image.load(filepath).convert_alpha()
            if size is not None:
                if surface.get_width() != size[0] or surface.get_height() != size[1]:
                    return pg.transform.smoothscale(surface, size)
            return surface
        except Exception as e:
            logger.error(f"Error loading image {filename}: {e}")
            err_size = size if size is not None else (100, 100)
            err_surf = pg.Surface(err_size)
            err_surf.fill(pg.Color("magenta"))
            return err_surf

    def font(self, app, filename: str, size: int) -> pg.font.Font:
        font_path = app.settings.fonts_dir / filename
        cache_key = (str(font_path), int(size))

        font_cache = getattr(app, "_font_cache", None)
        if font_cache is None:
            font_cache = {}
            app._font_cache = font_cache

        cached = font_cache.get(cache_key)
        if cached is None:
            cached = pg.font.Font(font_path, size)
            font_cache[cache_key] = cached
        return cached

    def render_text(
        self,
        app,
        filename: str,
        size: int,
        text: str,
        color: pg.Color | str = "black",
    ) -> pg.Surface:
        font = self.font(app, filename, size)
        return font.render(text, True, pg.Color(color))
