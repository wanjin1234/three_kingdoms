from __future__ import annotations


class TurnOrchestrationService:
    """回合编排壳服务（阶段5-B：从 GameApp 继续下沉）。"""

    def clear_for_turn_switch(self, app, *, keep_info_message: bool = False) -> None:
        app.selected_units.clear()
        app.show_combat_ui = False
        app.combat_target = None
        app.combat_callback = None
        app.defense_jiangdong_btn_rect = None
        app.defense_jiangdong_skip_btn_rect = None
        app.defense_hold_btn_rect = None
        app.defense_hold_skip_btn_rect = None
        app.defender_can_use_jiangdong = False
        app.defender_jiangdong_decided = True
        app.defender_use_jiangdong = False
        app.defender_can_hold_position = False
        app.defender_hold_decided = True
        app.defender_use_hold_position = False
        app.waiting_defender_response = False
        app.allow_jiangdong_selection = False
        app.no_attack_btn_rect = None
        app.skip_jiangdong_card_btn_rect = None
        app.morale_free_move_mode = False
        app.morale_bonus_mp_mode = False
        app.morale_cure_mode = False
        app.pp_spend_mode = False
        app.pp_summon_target_prov = None
        app.pp_summon_btns = []

        if not keep_info_message:
            app.combat_result_title = None
            app.combat_result_timer = 0
            if app.info_panel:
                app.info_panel.show_properties("")

    def advance_country_turn(self, app, *, keep_info_message: bool = False) -> None:
        if app.turn_game_finished:
            return

        app.turn_runtime.prepare_turn_switch(app, keep_info_message=keep_info_message)

        advance = app.turn_service.advance_turn(
            turn_index=app.turn_index,
            minor_round=app.minor_round,
            major_round=app.major_round,
        )
        app.turn_index = advance.turn_index
        app.minor_round = advance.minor_round
        app.major_round = advance.major_round

        if advance.game_finished:
            app.turn_presentation.handle_game_finished(app)
            return

        if advance.completed_minor_round:
            app._end_full_round()
        elif advance.started_new_major_round:
            app.turn_runtime.apply_major_round_rollover(app)

        app.player_country = app.turn_order[app.turn_index]
        new_country = app.player_country
        app.turn_runtime.on_country_turn_start(app, new_country=new_country)
        app.turn_presentation.on_country_activated(app)

    def finish_country_action(
        self,
        app,
        action_name: str,
        *,
        keep_info_message: bool = False,
    ) -> None:
        _ = action_name
        self.advance_country_turn(app, keep_info_message=keep_info_message)

    def check_tianxia_guixin_victory(self, app) -> None:
        winner = app.score_manager.check_tianxia_guixin(
            app.map_manager.provinces,
            app.country_stats,
        )

        if winner:
            app.turn_game_finished = True
            app.player_country = None
            app.card_manager = None
            if app.card_panel:
                app.card_panel.set_available_cards([])

            if not app.score_manager_initial_recorded:
                app.score_manager.record_initial_scores(app.map_manager.provinces)
                app.score_manager_initial_recorded = True

            record = app.score_manager.get_detailed_scores(
                app.map_manager.provinces,
                app.country_stats,
            )

            net_scores = {
                "SHU": record.shu_score - record.shu_initial,
                "WEI": record.wei_score - record.wei_initial,
                "WU": record.wu_score - record.wu_initial,
            }

            app.show_score_screen = {
                "type": "game_over",
                "record": record,
                "net_scores": net_scores,
                "tianxia_winner": winner,
            }

            winner_names = {"SHU": "蜀汉", "WEI": "曹魏", "WU": "孙吴"}
            if app.info_panel:
                app.info_panel.show_message(
                    f"{winner_names.get(winner, winner)} 达成「天下归心」胜利！"
                )
