from __future__ import annotations

from typing import Sequence

import pygame as pg


class PolylineRenderService:
    """硬朗连接折线（Miter Join）渲染服务。"""

    def draw_smooth_polyline(
        self,
        *,
        window: pg.Surface,
        color: pg.Color,
        points: Sequence[pg.math.Vector2],
        width: int,
    ) -> None:
        if len(points) < 2:
            return

        vectors = points
        half_width = width / 2

        upper_edge = []
        lower_edge = []

        for i in range(len(vectors)):
            curr = vectors[i]

            if i == 0:
                tangent = (vectors[1] - vectors[0]).normalize()
            elif i == len(vectors) - 1:
                tangent = (vectors[-1] - vectors[-2]).normalize()
            else:
                v_in = (curr - vectors[i - 1]).normalize()
                v_out = (vectors[i + 1] - curr).normalize()
                tangent = v_in + v_out
                if tangent.length() < 0.01:
                    tangent = pg.math.Vector2(-v_in.y, v_in.x)
                else:
                    tangent = tangent.normalize()

            normal = pg.math.Vector2(-tangent.y, tangent.x)

            if 0 < i < len(vectors) - 1:
                real_segment_normal = pg.math.Vector2(
                    -(vectors[i + 1] - curr).y, (vectors[i + 1] - curr).x
                ).normalize()
                cos_half_angle = normal.dot(real_segment_normal)
                if abs(cos_half_angle) < 0.1:
                    miter_length = half_width
                else:
                    miter_length = half_width / cos_half_angle
            else:
                miter_length = half_width

            p_upper = curr + normal * miter_length
            p_lower = curr - normal * miter_length

            upper_edge.append(p_upper)
            lower_edge.append(p_lower)

        full_poly = upper_edge + lower_edge[::-1]
        pg.draw.polygon(window, color, full_poly)
