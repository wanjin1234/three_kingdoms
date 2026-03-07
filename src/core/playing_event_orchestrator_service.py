from __future__ import annotations

import pygame as pg


class PlayingEventOrchestratorService:
    """PLAYING 状态事件总路由，将键鼠事件分发到各专项处理器。"""

    def handle_playing_event(self, app, event: pg.event.Event) -> None:
        show_msg = app.info_panel.show_message if app.info_panel else None

        if app.playing_input_service.handle_help_overlay_wheel(
            event=event,
            help_overlay_visible=app.help_overlay_visible,
            help_rule_surfaces=app._help_rule_surfaces,
            help_current_page=app.help_current_page,
            help_zoom_factor=getattr(app, "help_zoom_factor", 1.0),
            on_set_help_current_page=lambda page: setattr(app, "help_current_page", page),
            on_set_help_zoom_factor=lambda z: setattr(app, "help_zoom_factor", z),
        ):
            return

        if app.playing_input_service.handle_help_overlay_click(
            event=event,
            help_overlay_visible=app.help_overlay_visible,
            help_rule_surfaces=app._help_rule_surfaces,
            help_current_page=app.help_current_page,
            help_prev_btn=app._help_prev_btn,
            help_next_btn=app._help_next_btn,
            help_overlay_content_rect=app._help_overlay_content_rect,
            on_set_help_current_page=lambda page: setattr(app, "help_current_page", page),
            on_set_help_overlay_visible=lambda v: setattr(app, "help_overlay_visible", v),
        ):
            return

        if event.type == pg.KEYDOWN:
            keyboard_commands = app.playing_input_service.build_keydown_commands(
                key=event.key,
                help_overlay_visible=app.help_overlay_visible,
                morale_free_move_mode=app.morale_free_move_mode,
                morale_bonus_mp_mode=app.morale_bonus_mp_mode,
                morale_cure_mode=app.morale_cure_mode,
                pp_spend_mode=app.pp_spend_mode,
                pp_summon_target_prov=app.pp_summon_target_prov,
                selecting_card_target=app.selecting_card_target,
                major_round_choice_pending=app.major_round_choice_pending,
            )
            if keyboard_commands:
                app._execute_playing_input_commands(
                    keyboard_commands,
                    on_show_message=show_msg,
                )
                return
        elif event.type == pg.MOUSEBUTTONDOWN:
            if event.button == 1:
                if app.event_card_overlay:
                    if app.evt_overlay_ok_btn and app.evt_overlay_ok_btn.collidepoint(
                        event.pos
                    ):
                        app._confirm_event_card()
                    return

                left_click_context = app.playing_input_args_service.build_left_click_context(
                    app,
                    show_msg=show_msg,
                )

                if app.playing_input_service.handle_left_click_with_context(
                    pos=event.pos,
                    context=left_click_context,
                ):
                    return

            elif event.button == 3:
                right_click_commands = app.playing_input_service.build_right_click_commands(
                    pos=event.pos,
                    major_round_choice_pending=app.major_round_choice_pending,
                    evt_draw_phase=app.evt_draw_phase,
                    selecting_evt_target=app.selecting_evt_target,
                )
                if right_click_commands:
                    app._execute_playing_input_commands(
                        right_click_commands,
                        on_show_message=show_msg,
                    )
                    return
        elif event.type == pg.MOUSEMOTION:
            app.playing_input_service.handle_mouse_motion(
                vol_dragging=app._vol_dragging,
                volume_slider_visible=app.volume_slider_visible,
                slider_rect=app._vol_slider_rect,
                pos=event.pos,
                on_update_volume=app._update_volume_from_y,
                card_panel=app.card_panel,
            )
        elif event.type == pg.MOUSEBUTTONUP:
            if event.button == 1:
                app.playing_input_service.handle_left_button_up(
                    on_stop_drag=lambda: setattr(app, "_vol_dragging", False)
                )
