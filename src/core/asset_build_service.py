from __future__ import annotations

from typing import Sequence

import pygame as pg


class AssetBuildService:
    """资产与布局构建服务（阶段4：从 GameApp 拆分初始化细节）。"""

    def build_mode_select_assets(self, app) -> None:
        height = app.screen_height
        width = app.screen_width

        app.mode_select_title_surface = app._render_text(
            "STLITI.TTF", int(width * 0.08), "选择模式"
        )
        app.mode_select_title_pos = (int(width * 0.32), 0)

        btn_w = int(width * 0.28)
        btn_h = int(height * 0.12)
        btn_y = int(height * 0.65)

        app.mode_single_rect = pg.Rect(int(width * 0.18), btn_y, btn_w, btn_h)
        app.mode_multi_rect = pg.Rect(int(width * 0.54), btn_y, btn_w, btn_h)

        app.mode_single_surface = app._render_text(
            "STXINGKA.TTF", int(height * 0.08), "单人游戏"
        )
        app.mode_multi_surface = app._render_text(
            "STXINGKA.TTF", int(height * 0.08), "三人游戏"
        )

        sw = app.mode_single_surface.get_width()
        sh = app.mode_single_surface.get_height()
        app.mode_single_text_pos = (
            app.mode_single_rect.centerx - sw // 2,
            app.mode_single_rect.centery - sh // 2,
        )
        mw = app.mode_multi_surface.get_width()
        mh = app.mode_multi_surface.get_height()
        app.mode_multi_text_pos = (
            app.mode_multi_rect.centerx - mw // 2,
            app.mode_multi_rect.centery - mh // 2,
        )

    def build_loading_assets(self, app) -> None:
        height = app.screen_height
        width = app.screen_width

        app.loading_image_right = app._load_ui_image(
            "start_ZHUGELIANG.jpg", (int(height * 0.6), int(height * 0.7))
        )
        app.loading_image_right_pos = (int(width - height * 0.65), int(height * 0.2))

        raw_left = app._load_ui_image(
            "start_SIMAYI.jpg", (int(height * 0.5), int(height * 0.625))
        )
        app.loading_image_left = pg.transform.flip(raw_left, True, False)
        app.loading_image_left_pos = (int(height * 0.03), int(height * 0.25))

        app.start_button_rect = pg.Rect(
            int(width * 0.3),
            int(height * 0.75),
            int(width * 0.4),
            int(height * 0.1),
        )

        app.loading_title_surface = app._render_text(
            "STLITI.TTF", int(width * 0.1), "三足鼎立"
        )
        app.loading_title_pos = (int(width * 0.3), 0)

        app.loading_button_surface = app._render_text(
            "STXINGKA.TTF", int(height * 0.1), "开始游戏"
        )
        app.loading_button_pos = (int(width * 0.5 - height * 0.2), int(height * 0.75))

    def build_choosing_assets(self, app) -> None:
        height = app.screen_height
        width = app.screen_width
        image_size = (int(height * 0.3), int(height * 0.3))
        app.choosing_portraits = [
            (
                app._load_ui_image("choosing_LIUBEI.jpg", image_size),
                (int(width * 0.4 - height * 0.45), int(height * 0.2)),
            ),
            (
                app._load_ui_image("choosing_SUNQUAN.jpg", image_size),
                (int(width * 0.5 - height * 0.15), int(height * 0.2)),
            ),
            (
                app._load_ui_image("choosing_CAOCAO.jpg", image_size),
                (int(width * 0.6 + height * 0.15), int(height * 0.2)),
            ),
        ]

        app.choosing_title_surface = app._render_text(
            "SIMLI.TTF", int(height * 0.1), "选择势力"
        )
        app.choosing_title_pos = (int(width * 0.5 - height * 0.2), 0)

        app.faction_button_radius = int(height * 0.1)
        app.faction_buttons = {}

        label_surfaces = {
            country: app._render_text("STLITI.TTF", int(height * 0.1), label)
            for country, label in app.country_labels.items()
        }

        app.faction_buttons["SHU"] = {
            "center": (int(width * 0.4 - height * 0.3), int(height * 0.7)),
            "color": app.country_button_colors["SHU"],
            "label_surface": label_surfaces["SHU"],
            "label_pos": (int(width * 0.4 - height * 0.35), int(height * 0.65)),
        }
        app.faction_buttons["WU"] = {
            "center": (int(width * 0.5), int(height * 0.7)),
            "color": app.country_button_colors["WU"],
            "label_surface": label_surfaces["WU"],
            "label_pos": (int(width * 0.5 - height * 0.05), int(height * 0.65)),
        }
        app.faction_buttons["WEI"] = {
            "center": (int(width * 0.6 + height * 0.3), int(height * 0.7)),
            "color": app.country_button_colors["WEI"],
            "label_surface": label_surfaces["WEI"],
            "label_pos": (int(width * 0.6 + height * 0.25), int(height * 0.65)),
        }

    def build_play_assets(
        self,
        app,
        *,
        yangtze_points_1: Sequence[tuple[float, float]],
        yangtze_points_2: Sequence[tuple[float, float]],
        yellow_river_points: Sequence[tuple[float, float]],
        ban_line_points: Sequence[tuple[float, float]],
    ) -> None:
        height = app.screen_height
        width = app.screen_width

        app.bg_image = app._load_ui_image("背景.png", None)
        bg_orig_width, bg_orig_height = app.bg_image.get_size()
        scale = height / bg_orig_height
        app.bg_image = pg.transform.smoothscale(
            app.bg_image, (int(bg_orig_width * scale), height)
        )

        app.round_counter_font = app._font("msyhbd.ttc", int(height * 0.032))
        app.country_stat_title_font = app._font("STZHONGS.TTF", int(height * 0.038))
        app.country_stat_font = app._font("msyh.ttc", int(height * 0.022))

        app.country_tag_font = app._font("STZHONGS.TTF", int(height * 0.1))
        app.country_tag_surfaces = {
            country: app.country_tag_font.render(label, True, pg.Color("black"))
            for country, label in app.country_labels.items()
        }

        btn_font = app._font("msyh.ttc", int(height * 0.025))
        labels = ["重开一局", "退出游戏", "当前各国分数", "", ""]
        actions = ["RESTART", "EXIT", "SCORE", "VOLUME", "HELP"]

        app.control_btns = []
        current_x_right = int(width - 20)

        for label, action in zip(labels, actions):
            surf = btn_font.render(label, True, pg.Color("white"))
            base_h = surf.get_height() + 10
            if action in ("VOLUME", "HELP"):
                w = h = base_h
            else:
                w = surf.get_width() + 20
                h = base_h

            x = current_x_right - w
            y = int(height - h - 12)
            rect = pg.Rect(x, y, w, h)

            btn_color = (
                pg.Color("#1a5276")
                if action == "SCORE"
                else pg.Color("#2d6a4f")
                if action == "VOLUME"
                else pg.Color("#7b3f00")
                if action == "HELP"
                else pg.Color("#444444")
            )
            if action in ("VOLUME", "HELP"):
                text_pos = surf.get_rect(center=rect.center).topleft
            else:
                text_pos = (x + 10, y + 5)

            app.control_btns.append(
                {
                    "rect": rect,
                    "surface": surf,
                    "text_pos": text_pos,
                    "action": action,
                    "bg_color": btn_color,
                    "border_color": pg.Color("white"),
                    "shape": "circle" if action in ("VOLUME", "HELP") else "rect",
                }
            )
            current_x_right -= w + 10

        vol_btn_entry = next(
            (b for b in app.control_btns if b["action"] == "VOLUME"), None
        )
        if vol_btn_entry:
            vr = vol_btn_entry["rect"]
            slider_w, slider_h = 72, 140
            sx = vr.centerx - slider_w // 2
            sy = vr.top - slider_h - 8
            app._vol_slider_rect = pg.Rect(sx, sy, slider_w, slider_h)
            app._vol_track_top = sy + 14
            app._vol_track_bottom = sy + slider_h - 30
            app._vol_track_x = sx + slider_w // 2

        app.country_tag_pos = (int(width - height * 0.12), 0)

        app.yangtze_polylines = tuple(
            app._scale_points(points)
            for points in (yangtze_points_1, yangtze_points_2)
        )
        app.yellow_river_polyline = tuple(app._scale_points(yellow_river_points))
        app.ban_line_polyline = tuple(app._scale_points(ban_line_points))
