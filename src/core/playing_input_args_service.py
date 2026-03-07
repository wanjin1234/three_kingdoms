from __future__ import annotations

import pygame as pg

from src.core.app_contexts import LeftClickContext, RightClickContext


class PlayingInputArgsService:
    """构建 PLAYING 状态下左/右键点击所需的输入参数包。"""

    def build_left_click_context(self, app, *, show_msg) -> LeftClickContext:
        return LeftClickContext(payload=self.build_left_click_args(app, show_msg=show_msg))

    def build_right_click_context(
        self,
        app,
        *,
        on_block_message,
    ) -> RightClickContext:
        return RightClickContext(
            major_round_choice_pending=app.major_round_choice_pending,
            evt_draw_phase=app.evt_draw_phase,
            selecting_evt_target=app.selecting_evt_target,
            on_block_message=on_block_message,
            pp_spend_mode=app.pp_spend_mode,
            pp_summon_target_prov=app.pp_summon_target_prov,
            get_province_at=app._get_province_at,
            player_country=app.player_country,
            evt_flag_hu_recruit=app.evt_flag_hu_recruit,
            on_set_pp_summon_target_prov=app._set_pp_summon_target_prov,
            selected_units=app.selected_units,
            card_effect_manager=app.card_effect_manager,
            on_get_people_support_level=app._get_people_support_level,
            is_fort_or_city=app._is_fort_or_city,
            morale_free_move_mode=app.morale_free_move_mode,
            combat_target=app.combat_target,
            on_cancel_combat_preview=app._cancel_combat_preview,
            on_handle_combat=app._handle_combat,
            pending_post_move_attack=app.pending_post_move_attack,
            on_handle_movement=app._handle_movement,
            on_show_message=(app.info_panel.show_message if app.info_panel else None),
        )

    def build_left_click_args(self, app, *, show_msg):
        return {
            "control_btns": getattr(app, "control_btns", []),
            "state": app.state,
            "on_stop": app.stop,
            "on_restart_game": app._restart_game,
            "on_show_score_screen": app._show_score_screen,
            "volume_slider_visible": app.volume_slider_visible,
            "on_set_volume_slider_visible": (
                lambda v: setattr(app, "volume_slider_visible", v)
            ),
            "help_overlay_visible": app.help_overlay_visible,
            "on_set_help_overlay_visible": (
                lambda v: setattr(app, "help_overlay_visible", v)
            ),
            "on_set_help_current_page": (
                lambda page: setattr(app, "help_current_page", page)
            ),
            "on_start_help_rule_load": app._start_help_rule_load,
            "slider_rect": app._vol_slider_rect,
            "on_start_drag": lambda: setattr(app, "_vol_dragging", True),
            "on_update_volume": app._update_volume_from_y,
            "on_hide_slider": lambda: setattr(app, "volume_slider_visible", False),
            "major_round_choice_pending": app.major_round_choice_pending,
            "country_stat_choice_btns": app.country_stat_choice_btns,
            "on_apply_major_round_choice": app._apply_major_round_choice,
            "evt_draw_phase": app.evt_draw_phase,
            "selecting_evt_target": app.selecting_evt_target,
            "evt_skip_draw_btn_rect": app.evt_skip_draw_btn_rect,
            "draw_event_btn_rect": app.draw_event_btn_rect,
            "player_country": app.player_country,
            "on_exit_evt_draw_phase": app._exit_evt_draw_phase,
            "on_trigger_draw_event_card": app._trigger_draw_event_card,
            "has_event_card_overlay": bool(app.event_card_overlay),
            "on_check_evt_draw_phase_pp": app._check_evt_draw_phase_pp,
            "show_combat_ui": app.show_combat_ui,
            "combat_btn_rect": app.combat_btn_rect,
            "defender_can_use_jiangdong": app.defender_can_use_jiangdong,
            "defender_jiangdong_decided": app.defender_jiangdong_decided,
            "defender_can_hold_position": app.defender_can_hold_position,
            "defender_hold_decided": app.defender_hold_decided,
            "waiting_defender_response": app.waiting_defender_response,
            "defense_hold_btn_rect": app.defense_hold_btn_rect,
            "defense_hold_skip_btn_rect": app.defense_hold_skip_btn_rect,
            "skip_jiangdong_card_btn_rect": app.skip_jiangdong_card_btn_rect,
            "card_managers": app.card_managers,
            "on_set_waiting_defender_response": (
                lambda v: setattr(app, "waiting_defender_response", v)
            ),
            "on_set_allow_jiangdong_selection": (
                lambda v: setattr(app, "allow_jiangdong_selection", v)
            ),
            "on_set_card_manager": (
                lambda manager: setattr(app, "card_manager", manager)
            ),
            "on_update_card_panel": app._update_card_panel,
            "on_set_defender_use_hold_position": (
                lambda v: setattr(app, "defender_use_hold_position", v)
            ),
            "on_set_defender_hold_decided": (
                lambda v: setattr(app, "defender_hold_decided", v)
            ),
            "on_set_defender_use_jiangdong": (
                lambda v: setattr(app, "defender_use_jiangdong", v)
            ),
            "on_set_defender_jiangdong_decided": (
                lambda v: setattr(app, "defender_jiangdong_decided", v)
            ),
            "combat_callback": app.combat_callback,
            "pending_evt_card_id": app.pending_evt_card_id,
            "event_card_deck": app.event_card_deck,
            "pending_evt_drawer": app.pending_evt_drawer,
            "get_unit_slot_at": app._get_unit_slot_at,
            "get_province_by_id": app.map_manager.get_by_id,
            "get_province_at": app._get_province_at,
            "on_apply_evt_target_unit": app._apply_evt_target_unit,
            "on_apply_evt_target_province": app._apply_evt_target_province,
            "country_labels": app.country_labels,
            "pp_btn_rect": app.pp_btn_rect,
            "can_use_pp": app._pp_can_use,
            "pp_spend_mode": app.pp_spend_mode,
            "pp_spend_end_btn_rect": app.pp_spend_end_btn_rect,
            "pp_summon_target_prov": app.pp_summon_target_prov,
            "pp_summon_btns": app.pp_summon_btns,
            "evt_flag_hu_recruit": app.evt_flag_hu_recruit,
            "spend_pp": app._spend_pp,
            "unit_repository": app.unit_repository,
            "on_invalidate_map_cache": app.map_manager.invalidate_cache,
            "on_record_move_dst": (
                lambda prov_id, country, slot_idx: (
                    app.move_dst_provs.__setitem__(prov_id, country),
                    app.move_dst_slots.__setitem__(prov_id, [slot_idx]),
                )
            ),
            "get_total_pp": app._get_total_pp,
            "get_pp_heal_cost": app._get_pp_heal_cost,
            "is_special_unit": app._is_special_unit,
            "on_finish_country_action": app._finish_country_action,
            "on_set_pp_spend_mode": (
                lambda v: setattr(app, "pp_spend_mode", v)
            ),
            "on_set_pp_summon_target_prov": (
                lambda prov: setattr(app, "pp_summon_target_prov", prov)
            ),
            "on_set_pp_summon_btns": (
                lambda buttons: setattr(app, "pp_summon_btns", buttons)
            ),
            "morale_lv2_btn_rect": app.morale_lv2_btn_rect,
            "morale_lv3_btn_rect": app.morale_lv3_btn_rect,
            "morale_lv4_btn_rect": app.morale_lv4_btn_rect,
            "morale_bonus_mp_mode": app.morale_bonus_mp_mode,
            "morale_cure_mode": app.morale_cure_mode,
            "major_round": app.major_round,
            "has_confused_units_for_country": app._has_confused_units_for_country,
            "on_set_morale_free_move_mode": (
                lambda v: setattr(app, "morale_free_move_mode", v)
            ),
            "on_set_morale_bonus_mp_mode": (
                lambda v: setattr(app, "morale_bonus_mp_mode", v)
            ),
            "on_set_morale_cure_mode": (
                lambda v: setattr(app, "morale_cure_mode", v)
            ),
            "on_clear_morale_lv4_pending": (
                lambda country: app.morale_lv4_pending.pop(country, None)
            ),
            "on_mark_morale_lv3_used": (
                lambda country, rnd: app.morale_lv3_used.__setitem__(country, rnd)
            ),
            "recover_btn_rect": app.recover_btn_rect,
            "selected_units": app.selected_units,
            "on_update_selection_info": app._update_selection_info,
            "pending_post_move_attack": app.pending_post_move_attack,
            "no_attack_btn_rect": app.no_attack_btn_rect,
            "morale_free_move_mode": app.morale_free_move_mode,
            "on_mark_morale_lv2_used": (
                lambda country, rnd: app.morale_lv2_used.__setitem__(country, rnd)
            ),
            "on_set_pending_post_move_attack": (
                lambda v: setattr(app, "pending_post_move_attack", v)
            ),
            "on_set_pending_attacker": (
                lambda attacker: setattr(app, "pending_attacker", attacker)
            ),
            "on_clear_selection": app.clear_selection,
            "card_panel": app.card_panel,
            "allow_jiangdong_selection": app.allow_jiangdong_selection,
            "card_repository": app.card_repository,
            "on_play_selected_card": app._play_selected_card,
            "info_panel": app.info_panel,
            "selecting_card_target": app.selecting_card_target,
            "selected_card_for_effect": app.selected_card_for_effect,
            "apply_card_to_province": app._apply_card_to_province,
            "on_clear_card_target_selection": (
                lambda: (
                    setattr(app, "selecting_card_target", False),
                    setattr(app, "selected_card_for_effect", None),
                )
            ),
            "pending_attacker": app.pending_attacker,
            "on_remove_selection": app.remove_selection,
            "on_add_selection": (
                lambda pid, idx, shift: app.add_selection(
                    pid,
                    idx,
                    allow_cross_province=shift,
                )
            ),
            "shift_held": bool(pg.key.get_mods() & pg.KMOD_SHIFT),
            "on_show_message": show_msg,
        }
