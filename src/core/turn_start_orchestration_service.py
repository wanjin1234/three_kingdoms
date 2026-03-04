from __future__ import annotations

import pygame as pg

from src.game_objects.card import CardManager


class TurnStartOrchestrationService:
    """开局与大回合加点编排服务。"""

    def start_turn_based_game(self, app, human_country: str = "SHU") -> None:
        app.human_country = human_country
        app.turn_index = 0
        app.major_round = 1
        app.minor_round = 1
        app.turn_game_finished = False
        app.player_country = app.turn_order[app.turn_index]

        app.card_managers = {
            country: CardManager(app.card_repository, country)
            for country in app.turn_order
        }
        app.card_manager = app.card_managers[app.player_country]

        app.card_effect_manager.clear_all_effects()
        app._replenish_action_points()

        app.move_src_provs = {}
        app.move_dst_provs = {}
        app.move_src_slots = {}
        app.move_dst_slots = {}

        app.score_manager.record_initial_scores(app.map_manager.provinces)
        app.score_manager_initial_recorded = True

        self.start_major_round_choice_phase(app)
        app.clear_selection()
        app._update_card_panel()
        app.state = type(app.state).PLAYING
        if app.music_manager:
            app.music_manager.play_game()

        if app.human_country is not None and app.player_country != app.human_country:
            app._ai_turn_timer = pg.time.get_ticks() + 800

    def start_major_round_choice_phase(self, app) -> None:
        (
            app.major_round_choice_pending,
            app.major_round_choice_done,
        ) = app.turn_service.begin_major_round_choice()
        app.country_stat_choice_btns = {}

        if app.human_country is not None:
            for c in list(app.turn_order):
                if c != app.human_country:
                    ai_pp = app._get_total_pp(c)
                    auto_choice = app.turn_service.choose_major_round_bonus(ai_pp)
                    self.apply_major_round_choice(app, c, auto_choice)

    def apply_major_round_choice(self, app, country: str, choice: str) -> None:
        if not app.major_round_choice_pending:
            return

        applied = app.turn_service.apply_major_round_choice(
            country_stats=app.country_stats,
            major_round_choice_done=app.major_round_choice_done,
            country=country,
            choice=choice,
        )
        if not applied:
            return

        if choice == "support":
            app._check_tianxia_guixin_victory()

        if app.turn_service.all_major_round_choices_done(app.major_round_choice_done):
            app.major_round_choice_pending = False
            if app.info_panel:
                app.info_panel.show_message(
                    f"第{app.major_round}大回合加点完成：三国均已选择"
                )
            app._enter_evt_draw_phase_if_needed()

    def end_full_round(self, app) -> None:
        app.card_effect_manager.clear_turn_effects()
        app._replenish_action_points()
        app.gexu_guard_active = False
        app.jingnang_applied.clear()
