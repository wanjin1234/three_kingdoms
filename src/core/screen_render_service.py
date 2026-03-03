"""
界面渲染服务：抽离 `GameApp` 中的部分界面渲染逻辑。
"""

from __future__ import annotations

from typing import Any

import pygame as pg

from src.core.view_models import MainSceneViewModel


class ScreenRenderService:
    """加载/模式选择/势力选择/控制台渲染服务。"""

    def render_main_scene(
        self,
        app: Any,
        view_model: MainSceneViewModel | None = None,
    ) -> None:
        """根据当前状态渲染主场景内容。"""
        vm = view_model or MainSceneViewModel(
            show_score_screen=bool(app.show_score_screen),
            state=app.state,
        )

        if vm.show_score_screen:
            app._render_score_screen()
            return

        state_type = type(vm.state)
        if vm.state == getattr(state_type, "LOADING", None):
            app._render_loading_screen()
        elif vm.state == getattr(state_type, "MODE_SELECT", None):
            app._render_mode_select_screen()
        elif vm.state == getattr(state_type, "CHOOSING", None):
            app._render_choosing_screen()
        else:
            app._render_gameplay()

    def render_top_overlays(self, app: Any) -> None:
        """渲染顶层覆盖：全屏按钮 + 控制台。"""
        app._draw_global_fullscreen_btn()
        app._render_console()

    def should_render_console(self, app: Any) -> bool:
        return bool(app.console_visible)

    def calc_console_bar_height(self, screen_height: int) -> int:
        return max(32, int(screen_height * 0.048))

    def render_console(self, app: Any) -> None:
        """渲染控制台浮层。"""
        if not self.should_render_console(app):
            return
        w = app.screen_width
        bar_h = self.calc_console_bar_height(app.screen_height)
        y = app.screen_height - bar_h - 2

        overlay = pg.Surface((w, bar_h), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        app.window.blit(overlay, (0, y))

        prompt = "> " + app.console_input + "_"
        text_surf = app.console_font.render(prompt, True, pg.Color("#e8e8e8"))
        app.window.blit(text_surf, (12, y + (bar_h - text_surf.get_height()) // 2))

        if app.console_message:
            hint_surf = app.console_font.render(
                app.console_message, True, pg.Color("#aaffaa")
            )
            app.window.blit(
                hint_surf,
                (
                    w - hint_surf.get_width() - 12,
                    y + (bar_h - hint_surf.get_height()) // 2,
                ),
            )

    def render_loading_screen(self, app: Any) -> None:
        """渲染加载界面。"""
        app.window.fill(pg.Color("white"))
        app.window.blit(app.loading_image_right, app.loading_image_right_pos)
        app.window.blit(app.loading_image_left, app.loading_image_left_pos)
        app.window.blit(app.loading_title_surface, app.loading_title_pos)
        pg.draw.rect(app.window, pg.Color("yellow"), app.start_button_rect)
        app.window.blit(app.loading_button_surface, app.loading_button_pos)

    def render_mode_select_screen(self, app: Any) -> None:
        """渲染模式选择界面。"""
        app.window.fill(pg.Color("white"))
        app.window.blit(app.loading_image_right, app.loading_image_right_pos)
        app.window.blit(app.loading_image_left, app.loading_image_left_pos)
        app.window.blit(app.mode_select_title_surface, app.mode_select_title_pos)
        pg.draw.rect(
            app.window, pg.Color("#f0c040"), app.mode_single_rect, border_radius=12
        )
        app.window.blit(app.mode_single_surface, app.mode_single_text_pos)
        pg.draw.rect(
            app.window, pg.Color("#80c0f0"), app.mode_multi_rect, border_radius=12
        )
        app.window.blit(app.mode_multi_surface, app.mode_multi_text_pos)

    def render_choosing_screen(self, app: Any) -> None:
        """渲染势力选择界面。"""
        app.window.fill(pg.Color("white"))
        for surface, position in app.choosing_portraits:
            app.window.blit(surface, position)
        app.window.blit(app.choosing_title_surface, app.choosing_title_pos)
        for _, button in app.faction_buttons.items():
            pg.draw.circle(
                app.window,
                button["color"],
                button["center"],
                app.faction_button_radius,
            )
            app.window.blit(button["label_surface"], button["label_pos"])
