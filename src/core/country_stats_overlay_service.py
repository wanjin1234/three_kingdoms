from __future__ import annotations

from typing import List

import pygame as pg


class CountryStatsOverlayService:
    """三国民心/政治点数叠层渲染服务。"""

    def draw_country_stats_overlay(self, app) -> None:
        self = app
        map_rect = self._get_map_bounds_rect()
        title_font = self.country_stat_title_font
        body_font = self.country_stat_font
        self.country_stat_choice_btns = {}
        self.evt_info_btns = {}

        content_specs = {}
        panel_w = 0
        panel_h = 0
        for country in self.turn_order:
            stats = self.country_stats.get(country, {})
            temp_pp = self.evt_temp_pp.get(country, 0)
            pp_display = stats.get("political_points", 0)
            pp_text = (
                f"政治点数：{pp_display}(+{temp_pp}临)"
                if temp_pp > 0
                else f"政治点数：{pp_display}"
            )
            lines = [
                self.country_labels.get(country, country),
                f"民心点数：{stats.get('people_support', 0)}",
                pp_text,
            ]
            title_surf = title_font.render(lines[0], True, pg.Color("black"))
            line1_surf = body_font.render(lines[1], True, pg.Color("black"))
            line2_surf = body_font.render(lines[2], True, pg.Color("black"))
            content_specs[country] = (title_surf, line1_surf, line2_surf)

            local_w = max(
                title_surf.get_width(), line1_surf.get_width(), line2_surf.get_width()
            )
            panel_w = max(panel_w, local_w + 22)
            local_h = (
                title_surf.get_height()
                + line1_surf.get_height()
                + line2_surf.get_height()
                + 18
            )
            panel_h = max(panel_h, local_h)

        left_x = max(10, map_rect.left - panel_w - 16)

        wei_x = left_x
        wei_y = max(
            10,
            min(self.screen_height - panel_h - 10, map_rect.top + int(panel_h * 0.45)),
        )

        shu_x = left_x
        shu_y = max(
            10, min(self.screen_height - panel_h - 10, map_rect.centery - panel_h // 2)
        )

        control_rects = [btn["rect"] for btn in getattr(self, "control_btns", [])]
        safe_bottom = self.screen_height - 12
        if control_rects:
            safe_bottom = min(safe_bottom, min(r.top for r in control_rects) - 10)

        gap = 8

        wei_rect = pg.Rect(wei_x, wei_y, panel_w, panel_h)
        try_count = 0
        while wei_rect.colliderect(map_rect) and try_count < 20:
            wei_rect.y = min(self.screen_height - panel_h - 10, wei_rect.y + 12)
            try_count += 1
        try_count = 0
        while wei_rect.colliderect(map_rect) and try_count < 20:
            wei_rect.x = max(10, wei_rect.x - 12)
            try_count += 1

        wei_x, wei_y = wei_rect.x, wei_rect.y

        if shu_y < wei_y + panel_h + gap:
            shu_y = min(self.screen_height - panel_h - 10, wei_y + panel_h + gap)

        wu_x = map_rect.right - panel_w + 60
        wu_x = max(10, min(self.screen_width - panel_w - 10, wu_x))

        left_margin = min(shu_x, wei_x)
        wu_y = self.screen_height - panel_h - left_margin
        wu_y = max(10, min(self.screen_height - panel_h - 10, wu_y))

        wu_min_y = max(wei_y + panel_h + gap, shu_y + panel_h + gap)
        if wu_y < wu_min_y:
            wu_y = min(self.screen_height - panel_h - 10, wu_min_y)

        blockers: List[pg.Rect] = []
        if self.info_panel:
            blockers.append(self.info_panel.rect)
        if self.card_panel:
            blockers.append(self.card_panel.rect)

        wu_rect = pg.Rect(wu_x, wu_y, panel_w, panel_h)
        try_count = 0
        while (
            blockers
            and any(wu_rect.colliderect(r) for r in blockers)
            and try_count < 30
        ):
            wu_rect.x = max(10, wu_rect.x - 12)
            try_count += 1

        wu_x, wu_y = wu_rect.x, wu_rect.y

        placements = {
            "SHU": pg.Rect(shu_x, shu_y, panel_w, panel_h),
            "WEI": pg.Rect(wei_x, wei_y, panel_w, panel_h),
            "WU": pg.Rect(wu_x, wu_y, panel_w, panel_h),
        }

        for country in self.turn_order:
            rect = placements[country]
            title_surf, line1_surf, line2_surf = content_specs[country]

            pg.draw.rect(self.window, pg.Color(245, 245, 245), rect, border_radius=8)
            pg.draw.rect(
                self.window,
                self.country_button_colors.get(country, pg.Color("black")),
                rect,
                2,
                border_radius=8,
            )

            _btn_r = 18
            _btn_cx = rect.right - _btn_r - 5
            _btn_cy = rect.top + _btn_r + 5
            _btn_rect = pg.Rect(
                _btn_cx - _btn_r, _btn_cy - _btn_r, _btn_r * 2, _btn_r * 2
            )
            _mouse = self._get_logical_mouse_pos()
            _has_cards = (
                bool(self.evt_applied_this_round.get(country))
                or bool(self.jingnang_applied.get(country))
                or bool(self.evt_applied_major_round.get(country))
                or bool(self.jingnang_applied_major.get(country))
            )
            _hovered_btn = _btn_rect.collidepoint(_mouse)
            if _has_cards:
                _btn_bg = pg.Color("#ffaa00") if _hovered_btn else pg.Color("#c87800")
            else:
                _btn_bg = pg.Color("#cccccc") if _hovered_btn else pg.Color("#aaaaaa")
            pg.draw.circle(self.window, _btn_bg, (_btn_cx, _btn_cy), _btn_r)
            pg.draw.circle(
                self.window, pg.Color(60, 60, 60), (_btn_cx, _btn_cy), _btn_r, 1
            )
            _excl_surf = body_font.render("!", True, pg.Color("white"))
            self.window.blit(_excl_surf, _excl_surf.get_rect(center=(_btn_cx, _btn_cy)))
            self.evt_info_btns[country] = _btn_rect

            x = rect.x + 10
            y = rect.y + 6
            self.window.blit(title_surf, (x, y))

            if self.major_round_choice_pending:
                if not self.major_round_choice_done.get(country, False):
                    top_gap = 4
                    bottom_gap = 6
                    row_gap = 4
                    btn_w = rect.width - 16
                    btn_x = rect.x + 8

                    available_h = rect.height - (
                        title_surf.get_height() + top_gap + bottom_gap
                    )
                    btn_h = min(
                        max(18, body_font.get_height() + 4),
                        (available_h - row_gap) // 2,
                    )
                    btn_h = max(16, btn_h)

                    btn1_y = y + title_surf.get_height() + top_gap
                    btn2_y = btn1_y + btn_h + row_gap

                    support_rect = pg.Rect(btn_x, btn1_y, btn_w, btn_h)
                    politics_rect = pg.Rect(btn_x, btn2_y, btn_w, btn_h)

                    support_color = pg.Color("#7a1f1f")
                    if support_rect.collidepoint(self._get_logical_mouse_pos()):
                        support_color = pg.Color("#9b2a2a")
                    politics_color = pg.Color("#1f4f7a")
                    if politics_rect.collidepoint(self._get_logical_mouse_pos()):
                        politics_color = pg.Color("#2b6aa2")

                    pg.draw.rect(
                        self.window, support_color, support_rect, border_radius=6
                    )
                    pg.draw.rect(
                        self.window, politics_color, politics_rect, border_radius=6
                    )

                    support_surf = body_font.render(
                        "+2 民心点数", True, pg.Color("white")
                    )
                    politics_surf = body_font.render(
                        "+2 政治点数", True, pg.Color("white")
                    )
                    self.window.blit(
                        support_surf,
                        support_surf.get_rect(center=support_rect.center),
                    )
                    self.window.blit(
                        politics_surf,
                        politics_surf.get_rect(center=politics_rect.center),
                    )

                    self.country_stat_choice_btns[country] = {
                        "support": support_rect,
                        "politics": politics_rect,
                    }
                else:
                    done_surf = body_font.render("已选择", True, pg.Color("black"))
                    done_x = min(
                        rect.right - done_surf.get_width() - 8,
                        x + title_surf.get_width() + 8,
                    )
                    done_y = y + max(
                        0, (title_surf.get_height() - done_surf.get_height()) // 2
                    )
                    self.window.blit(
                        done_surf,
                        (done_x, done_y),
                    )
                    y2 = y + title_surf.get_height() + 4
                    self.window.blit(line1_surf, (x, y2))
                    y2 += line1_surf.get_height() + 2
                    self.window.blit(line2_surf, (x, y2))
            else:
                y += title_surf.get_height() + 4
                self.window.blit(line1_surf, (x, y))
                y += line1_surf.get_height() + 2
                self.window.blit(line2_surf, (x, y))
