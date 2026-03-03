from __future__ import annotations

from math import radians
from typing import Callable

import pygame as pg


class VolumeUIService:
    """音量滑块与喇叭图标渲染/交互服务。"""

    def draw_speaker_icon(
        self, window: pg.Surface, cx: int, cy: int, radius: int
    ) -> None:
        s = max(4, int(radius * 0.44))
        ic = pg.Color("white")
        lw = max(1, s // 4)

        # 整体图标向左偏移，为右侧声波留空间
        ox = cx - s // 3

        # 扬声器盒体（左侧小矩形）
        bw = max(2, s // 2)
        bh = max(2, int(s * 0.85))
        bx = ox - bw - s // 2
        by = cy - bh // 2
        pg.draw.rect(window, ic, pg.Rect(bx, by, bw, bh))

        # 喇叭锥形（向右展开的梯形）
        cone_rx = bx + bw + s
        cone_pts = [
            (bx + bw, cy - bh // 2),
            (cone_rx, cy - s),
            (cone_rx, cy + s),
            (bx + bw, cy + bh // 2),
        ]
        pg.draw.polygon(window, ic, cone_pts)

        # 声波弧线（两条，圆弧角 ±55°，仅绘制右半侧）
        wave_cx = cx + s // 2
        for arc_r in (int(s * 0.9), int(s * 1.55)):
            arc_rect = pg.Rect(wave_cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2)
            pg.draw.arc(window, ic, arc_rect, -radians(55), radians(55), lw)

    def calculate_volume_from_y(self, y: int, ty_top: int, ty_bot: int) -> float | None:
        track_h = ty_bot - ty_top
        if track_h <= 0:
            return None
        ratio = (y - ty_top) / track_h
        return max(0.0, min(1.0, 1.0 - ratio))

    def render_volume_slider(
        self,
        *,
        window: pg.Surface,
        slider_rect: pg.Rect | None,
        track_x: int,
        track_top: int,
        track_bottom: int,
        volume_level: float,
        font_loader: Callable[[str, int], pg.font.Font],
        tooltip_font: pg.font.Font | None,
        combat_ui_font: pg.font.Font | None,
    ) -> None:
        sr = slider_rect
        if sr is None:
            return

        # 半透明背景面板
        panel_surf = pg.Surface((sr.width, sr.height), pg.SRCALPHA)
        panel_surf.fill((20, 20, 20, 210))
        window.blit(panel_surf, sr.topleft)
        pg.draw.rect(window, pg.Color("#52b788"), sr, 2, border_radius=8)

        tx = track_x
        ty_top = track_top
        ty_bot = track_bottom
        track_h = ty_bot - ty_top

        # 轨道（灰色底层）
        pg.draw.line(window, pg.Color("#555555"), (tx, ty_top), (tx, ty_bot), 4)

        # 轨道已填充部分（绿色，从旋钮往下到底）
        knob_y = int(ty_top + (1.0 - volume_level) * track_h)
        if knob_y < ty_bot:
            pg.draw.line(
                window, pg.Color("#52b788"), (tx, knob_y), (tx, ty_bot), 4
            )

        # 旋钮
        pg.draw.circle(window, pg.Color("white"), (tx, knob_y), 9)
        pg.draw.circle(window, pg.Color("#2d6a4f"), (tx, knob_y), 7)

        # 百分比文字（使用专用小号字体居中显示在浮窗底部）
        pct_text = f"{int(round(volume_level * 100))}%"
        # 使用固定小号字体（14px），确保"100%"不超出72px宽的浮窗
        try:
            pct_font = font_loader("msyh.ttc", 14)
        except Exception:
            pct_font = tooltip_font or combat_ui_font
        if pct_font:
            pct_surf = pct_font.render(pct_text, True, pg.Color("white"))
            # 若仍超宽则等比缩小，保证不超出浮窗左右边界
            max_w = sr.width - 8
            if pct_surf.get_width() > max_w:
                scale = max_w / pct_surf.get_width()
                new_w = max(1, int(pct_surf.get_width() * scale))
                new_h = max(1, int(pct_surf.get_height() * scale))
                pct_surf = pg.transform.smoothscale(pct_surf, (new_w, new_h))
            pct_rect = pct_surf.get_rect(centerx=sr.centerx, bottom=sr.bottom - 4)
            window.blit(pct_surf, pct_rect)
