from __future__ import annotations

import logging
from math import sqrt

import pygame as pg

logger = logging.getLogger(__name__)
SQRT3 = sqrt(3)


class RuntimeLoopService:
    """运行循环与窗口适配服务（阶段5-A：从 GameApp 拆分运行时壳）。"""

    def run(self, app) -> None:
        app._running = True
        logger.info(
            "Starting game loop at %s FPS, resolution %sx%s",
            app.settings.fps,
            app.screen_width,
            app.screen_height,
        )
        while app._running:
            app.event_manager.process()
            app._update()
            app._render()
            app._present_frame()
            app.clock.tick(app.settings.fps)

        pg.quit()

    def stop(self, app) -> None:
        app._running = False

    def reflow_after_window_change(self, app) -> None:
        app.display_width, app.display_height = app.display_surface.get_size()
        if app._direct_render:
            app._viewport_scale = 1.0
            app.viewport_rect = pg.Rect(0, 0, app.display_width, app.display_height)
            return

        base_w = app._base_screen_width
        base_h = app._base_screen_height
        scale_x = app.display_width / base_w
        scale_y = app.display_height / base_h

        if scale_x > scale_y:
            app._viewport_scale = scale_y
            new_logical_w = max(base_w, int(round(app.display_width / scale_y)))
            app.viewport_rect = pg.Rect(0, 0, app.display_width, app.display_height)
            if new_logical_w != app.screen_width or app.screen_height != base_h:
                app.screen_width = new_logical_w
                app.screen_height = base_h
                app.window = pg.Surface((app.screen_width, app.screen_height)).convert()
                app._rebuild_layout_for_screen_size()
        else:
            app._viewport_scale = min(scale_x, scale_y)
            target_w = max(1, int(base_w * app._viewport_scale))
            target_h = max(1, int(base_h * app._viewport_scale))
            offset_x = (app.display_width - target_w) // 2
            offset_y = (app.display_height - target_h) // 2
            app.viewport_rect = pg.Rect(offset_x, offset_y, target_w, target_h)
            if app.screen_width != base_w or app.screen_height != base_h:
                app.screen_width = base_w
                app.screen_height = base_h
                app.window = pg.Surface((app.screen_width, app.screen_height)).convert()
                app._rebuild_layout_for_screen_size()

    def rebuild_layout_for_screen_size(self, app) -> None:
        app.hex_side = app.screen_height * 2 / (19 * SQRT3)
        app.map_manager.set_hex_side(app.hex_side)
        app.unit_renderer.on_hex_side_changed(app.hex_side)

        if app._direct_render:
            panel_w = int(app.screen_width * 0.30)
        else:
            panel_w = int(app._base_screen_width * 0.30)
        panel_x = app.screen_width - panel_w
        panel_y = int(app.screen_height * 0.15)
        panel_h = int(app.screen_height * 0.45)
        panel_rect = pg.Rect(panel_x, panel_y, panel_w, panel_h)

        font_size = int(app.screen_height * 0.025)
        info_font = app._font("msyh.ttc", font_size)
        font_path = str(app.settings.fonts_dir / "msyh.ttc")

        if app.info_panel:
            app.info_panel.rect = panel_rect
            app.info_panel.font = info_font
            app.info_panel.font_path = font_path
            app.info_panel.base_font_size = font_size
            app.info_panel._font_cache = {}

        if app.card_panel:
            app.card_panel.rect = pg.Rect(
                panel_x,
                int(app.screen_height * 0.60),
                panel_w,
                int(app.screen_height * 0.25),
            )
            app.card_panel.font = info_font
            app.card_panel.font_path = font_path
            app.card_panel.base_font_size = font_size
            app.card_panel._font_cache = {}
            app.card_panel.tooltip_font = None

        app.combat_ui_font = info_font
        app._recover_btn_surf = app.combat_ui_font.render("解除混乱", True, pg.Color("white"))
        app._no_attack_btn_surf = app.combat_ui_font.render("不攻击", True, pg.Color("white"))
        app._morale_lv2_btn_surf = app.combat_ui_font.render("令行禁止", True, pg.Color("white"))
        app._morale_lv3_btn_surf = app.combat_ui_font.render("老乡指路", True, pg.Color("white"))
        app._morale_lv4_btn_surf = app.combat_ui_font.render("军容严整", True, pg.Color("white"))
        app._combat_table_btn_surf = app.combat_ui_font.render("战斗判定表", True, pg.Color("white"))
        app._pp_btn_surf = app.combat_ui_font.render("使用政治点数", True, pg.Color("white"))
        app._pp_end_btn_surf = app.combat_ui_font.render("结束行动", True, pg.Color("white"))

        tooltip_size = max(12, int(app.screen_height * 0.018))
        app.tooltip_font = app._font("msyh.ttc", tooltip_size)
        app.tooltip_bold_font = app._font("msyhbd.ttc", tooltip_size)
        morale_tt_size = max(10, int(app.screen_height * 0.014))
        app.morale_tt_font = app._font("msyh.ttc", morale_tt_size)
        console_font_size = max(14, int(app.screen_height * 0.022))
        app.console_font = app._font("msyh.ttc", console_font_size)

        app._build_loading_assets()
        app._build_mode_select_assets()
        app._build_choosing_assets()
        app._build_play_assets()
        app._cached_tooltip_surface = None
        app._last_tooltip_data = None

    def present_frame(self, app) -> None:
        if not app.display_surface:
            return

        if app._direct_render:
            pg.display.flip()
            return

        app.display_surface.fill(pg.Color("white"))
        scaled = pg.transform.smoothscale(
            app.window, (app.viewport_rect.width, app.viewport_rect.height)
        )
        app.display_surface.blit(scaled, app.viewport_rect.topleft)
        pg.display.flip()

    def to_logical_pos(self, app, pos):
        x, y = pos
        if app._direct_render:
            return (x, y)
        if not app.viewport_rect.collidepoint((x, y)):
            return (-10_000, -10_000)

        lx = int((x - app.viewport_rect.x) * app.screen_width / app.viewport_rect.width)
        ly = int((y - app.viewport_rect.y) * app.screen_height / app.viewport_rect.height)
        lx = max(0, min(app.screen_width - 1, lx))
        ly = max(0, min(app.screen_height - 1, ly))
        return (lx, ly)

    def get_logical_mouse_pos(self, app):
        return app._to_logical_pos(pg.mouse.get_pos())

    def adapt_event_to_logical(self, app, event: pg.event.Event) -> pg.event.Event:
        if hasattr(event, "pos"):
            data = dict(event.dict)
            data["pos"] = app._to_logical_pos(event.pos)
            return pg.event.Event(event.type, data)
        return event

    def resize_windowed(self, app, width: int, height: int) -> None:
        width = max(app.min_window_width, width)
        height = max(app.min_window_height, height)
        app.display_surface = pg.display.set_mode((width, height), pg.RESIZABLE)
        app._windowed_size = (width, height)
        app.is_fullscreen = False
        app._direct_render = False
        app._reflow_after_window_change()

    def toggle_fullscreen_mode(self, app) -> None:
        if not app.is_fullscreen:
            app._windowed_size = app.display_surface.get_size()
            app.display_surface = pg.display.set_mode((0, 0), pg.FULLSCREEN)
            app.is_fullscreen = True
            app._direct_render = True
            app.window = app.display_surface
            app.screen_width, app.screen_height = app.display_surface.get_size()
            app._rebuild_layout_for_screen_size()
        else:
            app.display_surface = pg.display.set_mode(app._windowed_size, pg.RESIZABLE)
            app.is_fullscreen = False
            app._direct_render = False
            app.window = pg.Surface((app._base_screen_width, app._base_screen_height)).convert()
        app._reflow_after_window_change()

    def draw_global_fullscreen_btn(self, app) -> None:
        font_size = max(10, int(app.screen_height * 0.018))
        hint_font = app._font("msyh.ttc", font_size)
        hint_surf = hint_font.render("按 F11 切换全屏/窗口模式", True, pg.Color("#888888"))
        x = (app.screen_width - hint_surf.get_width()) // 2
        y = app.screen_height - hint_surf.get_height() - 8
        app.window.blit(hint_surf, (x, y))
