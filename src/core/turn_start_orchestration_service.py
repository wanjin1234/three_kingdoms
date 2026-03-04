from __future__ import annotations

import pygame as pg

from src.core.app_contexts import (
    ApplyMajorRoundChoiceContext,
    EndFullRoundContext,
    StartMajorRoundChoiceContext,
)
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

        app._start_major_round_choice_phase()
        app.clear_selection()
        app._update_card_panel()
        app.state = type(app.state).PLAYING
        if app.music_manager:
            app.music_manager.play_game()

        if app.human_country is not None and app.player_country != app.human_country:
            app._ai_turn_timer = pg.time.get_ticks() + 800

    def start_major_round_choice_phase_with_context(
        self,
        context: StartMajorRoundChoiceContext,
    ) -> None:
        pending, done = context.begin_major_round_choice()
        context.on_set_major_round_choice_state(pending, done)
        context.on_set_country_stat_choice_btns({})

        if context.human_country is not None:
            for country in context.turn_order:
                if country != context.human_country:
                    ai_pp = context.get_total_pp(country)
                    auto_choice = context.choose_major_round_bonus(ai_pp)
                    context.on_apply_major_round_choice(country, auto_choice)

    def apply_major_round_choice_with_context(
        self,
        context: ApplyMajorRoundChoiceContext,
        country: str,
        choice: str,
    ) -> None:
        if not context.major_round_choice_pending:
            return

        applied = context.apply_major_round_choice(
            country_stats=context.country_stats,
            major_round_choice_done=context.major_round_choice_done,
            country=country,
            choice=choice,
        )
        if not applied:
            return

        if choice == "support":
            context.on_check_tianxia_guixin_victory()

        if context.all_major_round_choices_done(context.major_round_choice_done):
            context.on_set_major_round_choice_pending(False)
            if context.on_show_message:
                context.on_show_message(
                    f"第{context.major_round}大回合加点完成：三国均已选择"
                )
            context.on_enter_evt_draw_phase_if_needed()

    def end_full_round_with_context(self, context: EndFullRoundContext) -> None:
        context.on_clear_turn_effects()
        context.on_replenish_action_points()
        context.on_set_gexu_guard_active(False)
        context.on_clear_jingnang_applied()
