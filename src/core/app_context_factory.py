from __future__ import annotations

from typing import Any

from src.core.app_contexts import (
    AIAutoSelectEventTargetContext,
    AIBorderProvincesContext,
    AIRunTurnContext,
    ApplyMajorRoundChoiceContext,
    AdvanceCountryTurnContext,
    CardApplyEffectContext,
    CardCancelSelectionContext,
    CheckTianxiaVictoryContext,
    ClearForTurnSwitchContext,
    EndFullRoundContext,
    EventConfirmContext,
    EventDrawPhaseContext,
    EventTargetApplyContext,
    FinishCountryActionContext,
    RefreshSessionSkillDisplayContext,
    RemoveMajorRoundContext,
    StartMajorRoundChoiceContext,
)


def build_card_apply_effect_context(app: Any) -> CardApplyEffectContext:
    return CardApplyEffectContext(
        use_card=app.card_manager.use_card,
        player_country=app.player_country,
        append_jingnang_applied=(
            lambda country, name, desc: app.jingnang_applied.setdefault(
                country,
                [],
            ).append((name, desc))
        ),
        show_message=app.info_panel.show_message,
        on_update_card_panel=app._update_card_panel,
    )


def build_cancel_card_target_selection_context(app: Any) -> CardCancelSelectionContext:
    return CardCancelSelectionContext(
        on_set_selecting_card_target=(lambda v: setattr(app, "selecting_card_target", v)),
        on_set_selected_card_for_effect=(
            lambda v: setattr(app, "selected_card_for_effect", v)
        ),
        show_message=app.info_panel.show_message,
    )


def build_start_major_round_choice_context(app: Any) -> StartMajorRoundChoiceContext:
    return StartMajorRoundChoiceContext(
        turn_order=list(app.turn_order),
        human_country=app.human_country,
        begin_major_round_choice=app.turn_service.begin_major_round_choice,
        choose_major_round_bonus=app.turn_service.choose_major_round_bonus,
        get_total_pp=app._get_total_pp,
        on_apply_major_round_choice=app._apply_major_round_choice,
        on_set_major_round_choice_state=(
            lambda pending, done: (
                setattr(app, "major_round_choice_pending", pending),
                setattr(app, "major_round_choice_done", done),
            )
        ),
        on_set_country_stat_choice_btns=(
            lambda v: setattr(app, "country_stat_choice_btns", v)
        ),
    )


def build_apply_major_round_choice_context(app: Any) -> ApplyMajorRoundChoiceContext:
    return ApplyMajorRoundChoiceContext(
        major_round_choice_pending=app.major_round_choice_pending,
        country_stats=app.country_stats,
        major_round_choice_done=app.major_round_choice_done,
        major_round=app.major_round,
        apply_major_round_choice=app.turn_service.apply_major_round_choice,
        all_major_round_choices_done=app.turn_service.all_major_round_choices_done,
        on_set_major_round_choice_pending=(
            lambda v: setattr(app, "major_round_choice_pending", v)
        ),
        on_check_tianxia_guixin_victory=app._check_tianxia_guixin_victory,
        on_show_message=(app.info_panel.show_message if app.info_panel else None),
        on_enter_evt_draw_phase_if_needed=app._enter_evt_draw_phase_if_needed,
    )


def build_end_full_round_context(app: Any) -> EndFullRoundContext:
    return EndFullRoundContext(
        on_clear_turn_effects=app.card_effect_manager.clear_turn_effects,
        on_replenish_action_points=app._replenish_action_points,
        on_set_gexu_guard_active=(lambda v: setattr(app, "gexu_guard_active", v)),
        on_clear_jingnang_applied=app.jingnang_applied.clear,
    )


def build_remove_major_round_context(app: Any) -> RemoveMajorRoundContext:
    return RemoveMajorRoundContext(
        get_major_round_countries=lambda: list(app.evt_applied_major_round.keys()),
        filter_out_card_for_country=(
            lambda c, card_name: app.evt_applied_major_round.__setitem__(
                c,
                [
                    (n, d)
                    for n, d in app.evt_applied_major_round.get(c, [])
                    if n != card_name
                ],
            )
        ),
    )


def build_refresh_session_skill_display_context(
    app: Any,
) -> RefreshSessionSkillDisplayContext:
    return RefreshSessionSkillDisplayContext(
        on_remove_from_major_round=app._remove_from_major_round,
        get_evt_lonzhong_skill=lambda: app.evt_lonzhong_skill,
        get_evt_yishen_skill=lambda: app.evt_yishen_skill,
        is_evt_xingluo_active=lambda: bool(app.evt_xingluo_active),
        append_major_round_record=(
            lambda c, name, desc: app.evt_applied_major_round.setdefault(c, []).append(
                (name, desc)
            )
        ),
    )


def build_clear_for_turn_switch_context(app: Any) -> ClearForTurnSwitchContext:
    return ClearForTurnSwitchContext(
        clear_selected_units=app.selected_units.clear,
        reset_combat_interaction_state=(
            lambda: (
                setattr(app, "show_combat_ui", False),
                setattr(app, "combat_target", None),
                setattr(app, "combat_callback", None),
                setattr(app, "defense_jiangdong_btn_rect", None),
                setattr(app, "defense_jiangdong_skip_btn_rect", None),
                setattr(app, "defense_hold_btn_rect", None),
                setattr(app, "defense_hold_skip_btn_rect", None),
                setattr(app, "defender_can_use_jiangdong", False),
                setattr(app, "defender_jiangdong_decided", True),
                setattr(app, "defender_use_jiangdong", False),
                setattr(app, "defender_can_hold_position", False),
                setattr(app, "defender_hold_decided", True),
                setattr(app, "defender_use_hold_position", False),
                setattr(app, "waiting_defender_response", False),
                setattr(app, "allow_jiangdong_selection", False),
                setattr(app, "no_attack_btn_rect", None),
                setattr(app, "skip_jiangdong_card_btn_rect", None),
            )
        ),
        reset_morale_and_pp_modes=(
            lambda: (
                setattr(app, "morale_free_move_mode", False),
                setattr(app, "morale_bonus_mp_mode", False),
                setattr(app, "morale_cure_mode", False),
                setattr(app, "pp_spend_mode", False),
                setattr(app, "pp_summon_target_prov", None),
                setattr(app, "pp_summon_btns", []),
            )
        ),
        on_clear_combat_result_ui=(
            lambda: (
                setattr(app, "combat_result_title", None),
                setattr(app, "combat_result_timer", 0),
            )
        ),
        show_properties=(app.info_panel.show_properties if app.info_panel else None),
    )


def build_advance_country_turn_context(app: Any) -> AdvanceCountryTurnContext:
    return AdvanceCountryTurnContext(
        turn_game_finished=bool(app.turn_game_finished),
        prepare_turn_switch=(
            lambda keep_info_message: app.turn_runtime.prepare_turn_switch(
                app,
                keep_info_message=keep_info_message,
            )
        ),
        advance_turn=(
            lambda: app.turn_service.advance_turn(
                turn_index=app.turn_index,
                minor_round=app.minor_round,
                major_round=app.major_round,
            )
        ),
        on_set_turn_progression=(
            lambda turn_index, minor_round, major_round: (
                setattr(app, "turn_index", turn_index),
                setattr(app, "minor_round", minor_round),
                setattr(app, "major_round", major_round),
            )
        ),
        on_handle_game_finished=(lambda: app.turn_presentation.handle_game_finished(app)),
        on_end_full_round=app._end_full_round,
        on_apply_major_round_rollover=(
            lambda: app.turn_runtime.apply_major_round_rollover(app)
        ),
        get_turn_order=lambda: list(app.turn_order),
        on_set_player_country=(lambda c: setattr(app, "player_country", c)),
        on_country_turn_start=(
            lambda c: app.turn_runtime.on_country_turn_start(app, new_country=c)
        ),
        on_country_activated=(lambda: app.turn_presentation.on_country_activated(app)),
    )


def build_finish_country_action_context(app: Any) -> FinishCountryActionContext:
    return FinishCountryActionContext(
        on_advance_country_turn=(
            lambda keep_info_message: app._advance_country_turn(
                keep_info_message=keep_info_message
            )
        )
    )


def build_ai_run_turn_context(app: Any) -> AIRunTurnContext:
    return AIRunTurnContext(app=app)


def build_ai_border_provinces_context(app: Any) -> AIBorderProvincesContext:
    return AIBorderProvincesContext(
        map_manager=app.map_manager,
        hex_side=app.hex_side,
    )


def build_ai_auto_select_event_target_context(app: Any) -> AIAutoSelectEventTargetContext:
    border_ctx = build_ai_border_provinces_context(app)
    return AIAutoSelectEventTargetContext(
        get_pending_evt_card_id=lambda: app.pending_evt_card_id,
        get_event_card_definition=app.event_card_deck.get_definition,
        clear_pending_evt_target_state=lambda: (
            setattr(app, "selecting_evt_target", False),
            setattr(app, "pending_evt_card_id", None),
            setattr(app, "pending_evt_drawer", None),
        ),
        get_border_provinces=(
            lambda country: app.ai_service.get_border_provinces_with_context(
                border_ctx,
                country,
            )
        ),
        get_provinces=lambda: list(app.map_manager.provinces),
        apply_evt_target_unit=app._apply_evt_target_unit,
        apply_evt_target_province=app._apply_evt_target_province,
        check_evt_draw_phase_pp=app._check_evt_draw_phase_pp,
    )


def build_check_tianxia_victory_context(app: Any) -> CheckTianxiaVictoryContext:
    return CheckTianxiaVictoryContext(
        check_tianxia_guixin=(
            lambda: app.score_manager.check_tianxia_guixin(
                app.map_manager.provinces,
                app.country_stats,
            )
        ),
        on_set_turn_game_finished=(lambda v: setattr(app, "turn_game_finished", v)),
        on_set_player_country=(lambda v: setattr(app, "player_country", v)),
        on_set_card_manager=(lambda v: setattr(app, "card_manager", v)),
        on_clear_card_panel_available=(
            lambda: app.card_panel.set_available_cards([]) if app.card_panel else None
        ),
        score_manager_initial_recorded=bool(app.score_manager_initial_recorded),
        on_record_initial_scores=(
            lambda: app.score_manager.record_initial_scores(app.map_manager.provinces)
        ),
        on_set_score_manager_initial_recorded=(
            lambda v: setattr(app, "score_manager_initial_recorded", v)
        ),
        get_detailed_scores=(
            lambda: app.score_manager.get_detailed_scores(
                app.map_manager.provinces,
                app.country_stats,
            )
        ),
        on_set_show_score_screen=(lambda v: setattr(app, "show_score_screen", v)),
        on_show_message=(app.info_panel.show_message if app.info_panel else None),
    )


def build_event_confirm_context(app: Any) -> EventConfirmContext:
    return EventConfirmContext(
        get_event_card_overlay=lambda: app.event_card_overlay,
        clear_event_card_overlay=lambda: (
            setattr(app, "event_card_overlay", None),
            setattr(app, "evt_overlay_ok_btn", None),
        ),
        apply_event_card=app._apply_event_card,
        is_event_card_overlay_active=lambda: bool(app.event_card_overlay),
        is_evt_draw_phase_active=lambda: bool(app.evt_draw_phase),
        get_player_country=lambda: app.player_country,
        get_country_total_pp=app._get_total_pp,
        enter_evt_draw_phase_if_needed=app._enter_evt_draw_phase_if_needed,
        exit_evt_draw_phase=app._exit_evt_draw_phase,
        get_human_country=lambda: app.human_country,
        is_selecting_evt_target=lambda: bool(app.selecting_evt_target),
        get_pending_evt_card_id=lambda: app.pending_evt_card_id,
        get_pending_evt_drawer=lambda: app.pending_evt_drawer,
        ai_auto_select_evt_target=app._ai_auto_select_evt_target,
        get_ai_turn_timer=lambda: app._ai_turn_timer,
        is_turn_game_finished=lambda: bool(app.turn_game_finished),
        set_ai_turn_timer=lambda v: setattr(app, "_ai_turn_timer", v),
    )


def build_event_target_apply_context(app: Any) -> EventTargetApplyContext:
    return EventTargetApplyContext(
        get_pending_evt_card_id=lambda: app.pending_evt_card_id,
        clear_pending_evt_target_state=lambda: (
            setattr(app, "selecting_evt_target", False),
            setattr(app, "pending_evt_card_id", None),
            setattr(app, "pending_evt_drawer", None),
        ),
        get_province_by_id=app.map_manager.get_by_id,
        get_event_card_definition=app.event_card_deck.get_definition,
        show_message=(app.info_panel.show_message if app.info_panel else None),
        check_evt_draw_phase_pp=app._check_evt_draw_phase_pp,
        get_player_country=lambda: app.player_country,
        get_human_country=lambda: app.human_country,
        get_ai_turn_timer=lambda: app._ai_turn_timer,
        is_turn_game_finished=lambda: bool(app.turn_game_finished),
        set_ai_turn_timer=lambda v: setattr(app, "_ai_turn_timer", v),
    )


def build_event_draw_phase_context(app: Any) -> EventDrawPhaseContext:
    return EventDrawPhaseContext(
        get_player_country=lambda: app.player_country,
        get_human_country=lambda: app.human_country,
        is_major_round_choice_pending=lambda: bool(app.major_round_choice_pending),
        get_country_total_pp=app._get_total_pp,
        set_evt_draw_phase=lambda v: setattr(app, "evt_draw_phase", v),
        get_evt_draw_phase=lambda: bool(app.evt_draw_phase),
        set_evt_skip_draw_btn_rect=lambda r: setattr(app, "evt_skip_draw_btn_rect", r),
        show_message=(app.info_panel.show_message if app.info_panel else None),
        show_properties=(app.info_panel.show_properties if app.info_panel else None),
        get_country_label=lambda c: app.country_labels.get(c, c),
    )
