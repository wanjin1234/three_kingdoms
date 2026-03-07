from __future__ import annotations

import pygame as pg


class GameEventRouterService:
    """游戏事件总路由，按游戏状态将 pygame 事件分发到对应处理流程。"""

    def handle_event(self, app, event: pg.event.Event, *, music_end_event: int, game_state) -> None:
        # 背景音乐：曲目结束时自动播放下一首
        if event.type == music_end_event:
            if app.music_manager:
                app.music_manager.on_track_end()
            return

        if event.type == pg.QUIT:
            app.stop()
            return

        if event.type in (pg.VIDEORESIZE, pg.WINDOWSIZECHANGED):
            if not app.is_fullscreen:
                if event.type == pg.VIDEORESIZE:
                    new_w, new_h = event.w, event.h
                else:
                    new_w = getattr(event, "x", app.display_width)
                    new_h = getattr(event, "y", app.display_height)

                if (new_w, new_h) != (app.display_width, app.display_height):
                    app._resize_windowed(new_w, new_h)
            return

        event = app._adapt_event_to_logical(event)

        # F11 全局切换全屏
        if event.type == pg.KEYDOWN and event.key == pg.K_F11:
            app._toggle_fullscreen_mode()
            return

        # ` 键（反引号）切换控制台显示/隐藏
        if event.type == pg.KEYDOWN and event.key == pg.K_BACKQUOTE:
            app._toggle_console()
            return

        # 控制台打开时，所有后续事件交由控制台处理，不传递给游戏逻辑
        if app.console_visible:
            app._handle_console_event(event)
            return

        # 如果正在显示分数屏，优先处理
        if app.show_score_screen:
            app._handle_score_screen_event(event)
            return

        if app.state == game_state.LOADING:
            app._handle_loading_event(event)
        elif app.state == game_state.MODE_SELECT:
            app._handle_mode_select_event(event)
        elif app.state == game_state.CHOOSING:
            app._handle_choosing_event(event)
        elif app.state == game_state.PLAYING:
            app._handle_playing_event(event)

    def handle_loading_event(self, app, event: pg.event.Event, *, game_state) -> None:
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if app.start_button_rect.collidepoint(event.pos):
                app.state = game_state.MODE_SELECT

    def handle_mode_select_event(self, app, event: pg.event.Event, *, game_state) -> None:
        if event.type != pg.MOUSEBUTTONDOWN or event.button != 1:
            return
        if app.mode_single_rect.collidepoint(event.pos):
            app.state = game_state.CHOOSING
        elif app.mode_multi_rect.collidepoint(event.pos):
            app._start_turn_based_game(human_country=None)

    def handle_choosing_event(self, app, event: pg.event.Event) -> None:
        if event.type != pg.MOUSEBUTTONDOWN or event.button != 1:
            return
        for country, button in app.faction_buttons.items():
            cx, cy = button["center"]
            dx = event.pos[0] - cx
            dy = event.pos[1] - cy
            if (dx * dx + dy * dy) <= app.faction_button_radius**2:
                app._start_turn_based_game(human_country=country)
                return

    def handle_score_screen_event(self, app, event: pg.event.Event, *, game_state) -> None:
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                app.show_score_screen = None
                if app.state == game_state.PLAYING and app.turn_game_finished:
                    app._restart_game()
