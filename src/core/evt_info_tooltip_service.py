from __future__ import annotations

from typing import List, Tuple

import pygame as pg


class EvtInfoTooltipService:
    """国家事件信息按钮浮窗渲染服务。"""

    def draw_evt_info_tooltip(self, app) -> None:
        self = app
        playing_state = getattr(type(self.state), "PLAYING", None)
        if playing_state is None or self.state != playing_state:
            return
        mouse_pos = self._get_logical_mouse_pos()
        hovered_country: str | None = None
        for country, btn_rect in self.evt_info_btns.items():
            if btn_rect.collidepoint(mouse_pos):
                hovered_country = country
                break
        if hovered_country is None:
            return

        # 合并小回合+大回合持久记录
        _jn_minor = self.jingnang_applied.get(hovered_country, [])
        _jn_major = self.jingnang_applied_major.get(hovered_country, [])
        jn_cards = _jn_minor + [x for x in _jn_major if x not in _jn_minor]
        _evt_minor = self.evt_applied_this_round.get(hovered_country, [])
        _evt_major = self.evt_applied_major_round.get(hovered_country, [])
        evt_cards = _evt_minor + [x for x in _evt_major if x not in _evt_minor]
        font_title = self.country_stat_font
        font_body = self.tooltip_font
        country_name = self.country_labels.get(hovered_country, hovered_country)

        max_content_w = 280
        padding = 10
        line_gap = 3

        def _wrap(text: str, font: pg.font.Font, max_w: int) -> List[str]:
            lines: List[str] = []
            cur = ""
            for ch in text:
                test = cur + ch
                if font.size(test)[0] <= max_w:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = ch
            if cur:
                lines.append(cur)
            return lines or [""]

        # 构建行列表：(text, font, color)
        all_lines: List[Tuple[str, pg.font.Font, pg.Color]] = []
        header = f"【本回合生效卡牌 · {country_name}】"
        all_lines.append((header, font_title, pg.Color("#333333")))

        if not jn_cards and not evt_cards:
            all_lines.append(
                ("（本回合尚无已生效卡牌）", font_body, pg.Color("#888888"))
            )
        else:
            # ── 锦囊卡 ──
            if jn_cards:
                all_lines.append(("— 锦囊卡 —", font_title, pg.Color("#1a6620")))
                for i, (name, desc) in enumerate(jn_cards):
                    if i > 0:
                        all_lines.append(("", font_body, pg.Color("white")))
                    all_lines.append((f"◆ {name}", font_title, pg.Color("#1a6620")))
                    for dline in _wrap(desc, font_body, max_content_w - padding * 2):
                        all_lines.append((dline, font_body, pg.Color("#444444")))
            # ── 事件卡 ──
            if evt_cards:
                if jn_cards:
                    all_lines.append(("", font_body, pg.Color("white")))
                all_lines.append(("— 事件卡 —", font_title, pg.Color("#b06800")))
                for i, (name, desc) in enumerate(evt_cards):
                    if i > 0:
                        all_lines.append(("", font_body, pg.Color("white")))
                    all_lines.append((f"◆ {name}", font_title, pg.Color("#b06800")))
                    for dline in _wrap(desc, font_body, max_content_w - padding * 2):
                        all_lines.append((dline, font_body, pg.Color("#444444")))

        # 计算面板尺寸
        actual_w = max_content_w
        total_h = padding
        for text, font, color in all_lines:
            w = font.size(text)[0] + padding * 2
            if w > actual_w:
                actual_w = w
            total_h += 3 if text == "" else font.get_height() + line_gap
        total_h += padding

        # 定位：靠近按钮，避免超出屏幕
        hbtn = self.evt_info_btns[hovered_country]
        tx = hbtn.right + 6
        ty = hbtn.top
        if tx + actual_w > self.screen_width - 5:
            tx = hbtn.left - actual_w - 6
        if ty + total_h > self.screen_height - 5:
            ty = self.screen_height - total_h - 5
        ty = max(5, ty)

        # 绘制背景
        bg_surf = pg.Surface((actual_w, total_h), pg.SRCALPHA)
        bg_surf.fill((255, 252, 225, 235))
        self.window.blit(bg_surf, (tx, ty))
        pg.draw.rect(
            self.window,
            pg.Color("#c8a040"),
            pg.Rect(tx, ty, actual_w, total_h),
            1,
            border_radius=6,
        )

        # 绘制文字
        cy = ty + padding
        for text, font, color in all_lines:
            if text == "":
                cy += 3
                continue
            surf = font.render(text, True, color)
            self.window.blit(surf, (tx + padding, cy))
            cy += font.get_height() + line_gap
