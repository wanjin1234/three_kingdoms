from __future__ import annotations

from src.core.app_contexts import (
    AdvanceCountryTurnContext,
    CheckTianxiaVictoryContext,
    ClearForTurnSwitchContext,
    FinishCountryActionContext,
)


class TurnOrchestrationService:
    """回合编排壳服务（阶段5-B：从 GameApp 继续下沉）。"""

    def clear_for_turn_switch_with_context(
        self,
        context: ClearForTurnSwitchContext,
        *,
        keep_info_message: bool = False,
    ) -> None:
        context.clear_selected_units()
        context.reset_combat_interaction_state()
        context.reset_morale_and_pp_modes()

        if not keep_info_message:
            context.on_clear_combat_result_ui()
            if context.show_properties:
                context.show_properties("")

    def advance_country_turn_with_context(
        self,
        context: AdvanceCountryTurnContext,
        *,
        keep_info_message: bool = False,
    ) -> None:
        if context.turn_game_finished:
            return

        context.prepare_turn_switch(keep_info_message)

        advance = context.advance_turn()
        context.on_set_turn_progression(
            advance.turn_index,
            advance.minor_round,
            advance.major_round,
        )

        if advance.game_finished:
            context.on_handle_game_finished()
            return

        if advance.completed_minor_round:
            context.on_end_full_round()
        elif advance.started_new_major_round:
            context.on_apply_major_round_rollover()

        turn_order = context.get_turn_order()
        new_country = turn_order[advance.turn_index]
        context.on_set_player_country(new_country)
        context.on_country_turn_start(new_country)
        context.on_country_activated()

    def finish_country_action_with_context(
        self,
        context: FinishCountryActionContext,
        action_name: str,
        *,
        keep_info_message: bool = False,
    ) -> None:
        _ = action_name
        context.on_advance_country_turn(keep_info_message)

    def check_tianxia_guixin_victory_with_context(
        self,
        context: CheckTianxiaVictoryContext,
    ) -> None:
        winner = context.check_tianxia_guixin()

        if winner:
            context.on_set_turn_game_finished(True)
            context.on_set_player_country(None)
            context.on_set_card_manager(None)
            context.on_clear_card_panel_available()

            if not context.score_manager_initial_recorded:
                context.on_record_initial_scores()
                context.on_set_score_manager_initial_recorded(True)

            record = context.get_detailed_scores()

            net_scores = {
                "SHU": record.shu_score - record.shu_initial,
                "WEI": record.wei_score - record.wei_initial,
                "WU": record.wu_score - record.wu_initial,
            }

            context.on_set_show_score_screen(
                {
                    "type": "game_over",
                    "record": record,
                    "net_scores": net_scores,
                    "tianxia_winner": winner,
                }
            )

            winner_names = {"SHU": "蜀汉", "WEI": "曹魏", "WU": "孙吴"}
            if context.on_show_message:
                context.on_show_message(
                    f"{winner_names.get(winner, winner)} 达成「天下归心」胜利！"
                )
