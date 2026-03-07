from __future__ import annotations

import logging
from typing import Callable

import pygame as pg

from src.core.app_contexts import LeftClickContext, RightClickContext
from src.game_objects.unit import UnitState

MAX_UNIT_STACK = 3

logger = logging.getLogger(__name__)


class PlayingInputService:
    """游戏内输入分支服务（帮助覆盖层、顶部功能按钮）。"""

    # ====================================================================
    # 归并入口（键盘 / 左键 / 右键）
    # ====================================================================

    def handle_keyboard_input(
        self,
        *,
        key: int,
        help_overlay_visible: bool,
        morale_free_move_mode: bool,
        morale_bonus_mp_mode: bool,
        morale_cure_mode: bool,
        pp_spend_mode: bool,
        pp_summon_target_prov,
        selecting_card_target: bool,
        major_round_choice_pending: bool,
        on_set_help_overlay_visible: Callable[[bool], None],
        on_reset_morale_modes: Callable[[], None],
        on_show_message: Callable[[str], None] | None,
        on_set_pp_summon_target_prov: Callable[[object | None], None],
        on_clear_pp_summon_btns: Callable[[], None],
        on_set_pp_spend_mode: Callable[[bool], None],
        on_cancel_card_target_selection: Callable[[], None],
        on_clear_selection: Callable[[], None],
        on_play_selected_card: Callable[[], None],
    ) -> bool:
        return self.handle_keydown(
            key=key,
            help_overlay_visible=help_overlay_visible,
            morale_free_move_mode=morale_free_move_mode,
            morale_bonus_mp_mode=morale_bonus_mp_mode,
            morale_cure_mode=morale_cure_mode,
            pp_spend_mode=pp_spend_mode,
            pp_summon_target_prov=pp_summon_target_prov,
            selecting_card_target=selecting_card_target,
            major_round_choice_pending=major_round_choice_pending,
            on_set_help_overlay_visible=on_set_help_overlay_visible,
            on_reset_morale_modes=on_reset_morale_modes,
            on_show_message=on_show_message,
            on_set_pp_summon_target_prov=on_set_pp_summon_target_prov,
            on_clear_pp_summon_btns=on_clear_pp_summon_btns,
            on_set_pp_spend_mode=on_set_pp_spend_mode,
            on_cancel_card_target_selection=on_cancel_card_target_selection,
            on_clear_selection=on_clear_selection,
            on_play_selected_card=on_play_selected_card,
        )

    def handle_right_click(
        self,
        *,
        pos,
        major_round_choice_pending: bool,
        evt_draw_phase: bool,
        selecting_evt_target: bool,
        on_block_message: Callable[[str], None] | None,
        pp_spend_mode: bool,
        pp_summon_target_prov,
        get_province_at: Callable,
        player_country: str | None,
        evt_flag_hu_recruit: bool,
        on_set_pp_summon_target_prov: Callable[[object | None], None],
        selected_units,
        card_effect_manager,
        on_get_people_support_level: Callable[[str], int],
        is_fort_or_city: Callable[[object], bool],
        morale_free_move_mode: bool,
        combat_target,
        on_cancel_combat_preview: Callable[[], None],
        on_handle_combat: Callable[[object], None],
        pending_post_move_attack: bool,
        on_handle_movement: Callable[[object], None],
        on_show_message: Callable[[str], None] | None,
    ) -> bool:
        if self.should_block_right_click(
            major_round_choice_pending=major_round_choice_pending,
            evt_draw_phase=evt_draw_phase,
            selecting_evt_target=selecting_evt_target,
            on_block_message=on_block_message,
        ):
            return True

        self.handle_game_right_click(
            pos=pos,
            pp_spend_mode=pp_spend_mode,
            pp_summon_target_prov=pp_summon_target_prov,
            get_province_at=get_province_at,
            player_country=player_country,
            evt_flag_hu_recruit=evt_flag_hu_recruit,
            on_set_pp_summon_target_prov=on_set_pp_summon_target_prov,
            selected_units=selected_units,
            card_effect_manager=card_effect_manager,
            on_get_people_support_level=on_get_people_support_level,
            is_fort_or_city=is_fort_or_city,
            morale_free_move_mode=morale_free_move_mode,
            combat_target=combat_target,
            on_cancel_combat_preview=on_cancel_combat_preview,
            on_handle_combat=on_handle_combat,
            pending_post_move_attack=pending_post_move_attack,
            on_handle_movement=on_handle_movement,
            on_show_message=on_show_message,
        )
        return True

    def handle_right_click_with_context(
        self,
        *,
        pos,
        context: RightClickContext,
    ) -> bool:
        return self.handle_right_click(
            pos=pos,
            major_round_choice_pending=context.major_round_choice_pending,
            evt_draw_phase=context.evt_draw_phase,
            selecting_evt_target=context.selecting_evt_target,
            on_block_message=context.on_block_message,
            pp_spend_mode=context.pp_spend_mode,
            pp_summon_target_prov=context.pp_summon_target_prov,
            get_province_at=context.get_province_at,
            player_country=context.player_country,
            evt_flag_hu_recruit=context.evt_flag_hu_recruit,
            on_set_pp_summon_target_prov=context.on_set_pp_summon_target_prov,
            selected_units=context.selected_units,
            card_effect_manager=context.card_effect_manager,
            on_get_people_support_level=context.on_get_people_support_level,
            is_fort_or_city=context.is_fort_or_city,
            morale_free_move_mode=context.morale_free_move_mode,
            combat_target=context.combat_target,
            on_cancel_combat_preview=context.on_cancel_combat_preview,
            on_handle_combat=context.on_handle_combat,
            pending_post_move_attack=context.pending_post_move_attack,
            on_handle_movement=context.on_handle_movement,
            on_show_message=context.on_show_message,
        )

    def handle_left_click_with_context(
        self,
        *,
        pos,
        context: LeftClickContext,
    ) -> bool:
        return self.handle_left_click(
            pos=pos,
            args=context.payload,
        )

    def _handle_left_click_global_ui(self, *, pos, args: dict) -> bool:
        if self.handle_control_button_click(
            control_btns=args["control_btns"],
            pos=pos,
            state=args["state"],
            on_stop=args["on_stop"],
            on_restart_game=args["on_restart_game"],
            on_show_score_screen=args["on_show_score_screen"],
            volume_slider_visible=args["volume_slider_visible"],
            on_set_volume_slider_visible=args["on_set_volume_slider_visible"],
            help_overlay_visible=args["help_overlay_visible"],
            on_set_help_overlay_visible=args["on_set_help_overlay_visible"],
            on_set_help_current_page=args["on_set_help_current_page"],
            on_start_help_rule_load=args["on_start_help_rule_load"],
        ):
            return True

        if self.handle_volume_slider_click(
            volume_slider_visible=args["volume_slider_visible"],
            slider_rect=args["slider_rect"],
            pos=pos,
            on_start_drag=args["on_start_drag"],
            on_update_volume=args["on_update_volume"],
            on_hide_slider=args["on_hide_slider"],
        ):
            return True

        if self.handle_major_round_choice_click(
            major_round_choice_pending=args["major_round_choice_pending"],
            country_stat_choice_btns=args["country_stat_choice_btns"],
            pos=pos,
            on_apply_major_round_choice=args["on_apply_major_round_choice"],
            on_show_message=args["on_show_message"],
        ):
            return True

        if self.handle_evt_draw_phase_click(
            evt_draw_phase=args["evt_draw_phase"],
            selecting_evt_target=args["selecting_evt_target"],
            evt_skip_draw_btn_rect=args["evt_skip_draw_btn_rect"],
            draw_event_btn_rect=args["draw_event_btn_rect"],
            pos=pos,
            player_country=args["player_country"],
            on_exit_evt_draw_phase=args["on_exit_evt_draw_phase"],
            on_trigger_draw_event_card=args["on_trigger_draw_event_card"],
            has_event_card_overlay=args["has_event_card_overlay"],
            on_check_evt_draw_phase_pp=args["on_check_evt_draw_phase_pp"],
            on_show_message=args["on_show_message"],
        ):
            return True

        return False

    def _handle_left_click_combat_and_event(self, *, pos, args: dict) -> bool:
        if self.handle_combat_ui_click(
            pos=pos,
            show_combat_ui=args["show_combat_ui"],
            combat_btn_rect=args["combat_btn_rect"],
            defender_can_use_jiangdong=args["defender_can_use_jiangdong"],
            defender_jiangdong_decided=args["defender_jiangdong_decided"],
            defender_can_hold_position=args["defender_can_hold_position"],
            defender_hold_decided=args["defender_hold_decided"],
            waiting_defender_response=args["waiting_defender_response"],
            defense_hold_btn_rect=args["defense_hold_btn_rect"],
            defense_hold_skip_btn_rect=args["defense_hold_skip_btn_rect"],
            skip_jiangdong_card_btn_rect=args["skip_jiangdong_card_btn_rect"],
            player_country=args["player_country"],
            card_managers=args["card_managers"],
            on_set_waiting_defender_response=args["on_set_waiting_defender_response"],
            on_set_allow_jiangdong_selection=args["on_set_allow_jiangdong_selection"],
            on_set_card_manager=args["on_set_card_manager"],
            on_update_card_panel=args["on_update_card_panel"],
            on_show_message=args["on_show_message"],
            on_set_defender_use_hold_position=args["on_set_defender_use_hold_position"],
            on_set_defender_hold_decided=args["on_set_defender_hold_decided"],
            on_set_defender_use_jiangdong=args["on_set_defender_use_jiangdong"],
            on_set_defender_jiangdong_decided=args["on_set_defender_jiangdong_decided"],
            combat_callback=args["combat_callback"],
        ):
            return True

        if self.handle_evt_target_click(
            selecting_evt_target=args["selecting_evt_target"],
            pending_evt_card_id=args["pending_evt_card_id"],
            event_card_deck=args["event_card_deck"],
            pending_evt_drawer=args["pending_evt_drawer"],
            player_country=args["player_country"],
            pos=pos,
            get_unit_slot_at=args["get_unit_slot_at"],
            get_province_by_id=args["get_province_by_id"],
            get_province_at=args["get_province_at"],
            on_apply_evt_target_unit=args["on_apply_evt_target_unit"],
            on_apply_evt_target_province=args["on_apply_evt_target_province"],
            country_labels=args["country_labels"],
            on_show_message=args["on_show_message"],
        ):
            return True

        if self.handle_draw_event_button_click(
            draw_event_btn_rect=args["draw_event_btn_rect"],
            pos=pos,
            player_country=args["player_country"],
            on_trigger_draw_event_card=args["on_trigger_draw_event_card"],
        ):
            return True

        if self.handle_pp_click(
            pos=pos,
            pp_btn_rect=args["pp_btn_rect"],
            player_country=args["player_country"],
            can_use_pp=args["can_use_pp"],
            pp_spend_mode=args["pp_spend_mode"],
            pp_spend_end_btn_rect=args["pp_spend_end_btn_rect"],
            pp_summon_target_prov=args["pp_summon_target_prov"],
            pp_summon_btns=args["pp_summon_btns"],
            evt_flag_hu_recruit=args["evt_flag_hu_recruit"],
            spend_pp=args["spend_pp"],
            unit_repository=args["unit_repository"],
            on_invalidate_map_cache=args["on_invalidate_map_cache"],
            on_record_move_dst=args["on_record_move_dst"],
            get_total_pp=args["get_total_pp"],
            get_unit_slot_at=args["get_unit_slot_at"],
            get_province_by_id=args["get_province_by_id"],
            get_pp_heal_cost=args["get_pp_heal_cost"],
            is_special_unit=args["is_special_unit"],
            on_finish_country_action=args["on_finish_country_action"],
            on_set_pp_spend_mode=args["on_set_pp_spend_mode"],
            on_set_pp_summon_target_prov=args["on_set_pp_summon_target_prov"],
            on_set_pp_summon_btns=args["on_set_pp_summon_btns"],
            on_show_message=args["on_show_message"],
        ):
            return True

        if self.handle_morale_click(
            pos=pos,
            morale_lv2_btn_rect=args["morale_lv2_btn_rect"],
            morale_lv3_btn_rect=args["morale_lv3_btn_rect"],
            morale_lv4_btn_rect=args["morale_lv4_btn_rect"],
            morale_bonus_mp_mode=args["morale_bonus_mp_mode"],
            morale_cure_mode=args["morale_cure_mode"],
            player_country=args["player_country"],
            major_round=args["major_round"],
            get_unit_slot_at=args["get_unit_slot_at"],
            get_province_by_id=args["get_province_by_id"],
            has_confused_units_for_country=args["has_confused_units_for_country"],
            on_set_morale_free_move_mode=args["on_set_morale_free_move_mode"],
            on_set_morale_bonus_mp_mode=args["on_set_morale_bonus_mp_mode"],
            on_set_morale_cure_mode=args["on_set_morale_cure_mode"],
            on_clear_morale_lv4_pending=args["on_clear_morale_lv4_pending"],
            on_mark_morale_lv3_used=args["on_mark_morale_lv3_used"],
            on_show_message=args["on_show_message"],
        ):
            return True

        if self.handle_recover_click(
            recover_btn_rect=args["recover_btn_rect"],
            pos=pos,
            selected_units=args["selected_units"],
            get_province_by_id=args["get_province_by_id"],
            on_show_message=args["on_show_message"],
            on_update_selection_info=args["on_update_selection_info"],
            on_finish_country_action=args["on_finish_country_action"],
        ):
            return True

        if self.handle_no_attack_click(
            pending_post_move_attack=args["pending_post_move_attack"],
            no_attack_btn_rect=args["no_attack_btn_rect"],
            pos=pos,
            morale_free_move_mode=args["morale_free_move_mode"],
            player_country=args["player_country"],
            major_round=args["major_round"],
            on_mark_morale_lv2_used=args["on_mark_morale_lv2_used"],
            on_set_morale_free_move_mode=args["on_set_morale_free_move_mode"],
            on_set_pending_post_move_attack=args["on_set_pending_post_move_attack"],
            on_set_pending_attacker=args["on_set_pending_attacker"],
            on_clear_selection=args["on_clear_selection"],
            on_show_message=args["on_show_message"],
            on_finish_country_action=args["on_finish_country_action"],
        ):
            return True

        return False

    def _handle_left_click_panels_and_selection(self, *, pos, args: dict) -> bool:
        if self.handle_card_panel_click(
            pos=pos,
            card_panel=args["card_panel"],
            show_combat_ui=args["show_combat_ui"],
            waiting_defender_response=args["waiting_defender_response"],
            allow_jiangdong_selection=args["allow_jiangdong_selection"],
            card_repository=args["card_repository"],
            on_play_selected_card=args["on_play_selected_card"],
            on_show_message=args["on_show_message"],
        ):
            return True

        if self.handle_info_panel_click(
            info_panel=args["info_panel"],
            pos=pos,
        ):
            return True

        if self.handle_card_target_click(
            pos=pos,
            selecting_card_target=args["selecting_card_target"],
            selected_card_for_effect=args["selected_card_for_effect"],
            get_province_at=args["get_province_at"],
            apply_card_to_province=args["apply_card_to_province"],
            on_clear_card_target_selection=args["on_clear_card_target_selection"],
            on_show_message=args["on_show_message"],
        ):
            return True

        if self.handle_unit_selection_click(
            pos=pos,
            get_unit_slot_at=args["get_unit_slot_at"],
            get_province_by_id=args["get_province_by_id"],
            player_country=args["player_country"],
            pending_post_move_attack=args["pending_post_move_attack"],
            pending_attacker=args["pending_attacker"],
            selected_units=args["selected_units"],
            on_remove_selection=args["on_remove_selection"],
            on_add_selection=args["on_add_selection"],
            on_show_message=args["on_show_message"],
            shift_held=args["shift_held"],
        ):
            return True

        return False

    def handle_left_click(self, *, pos, args: dict) -> bool:
        if self._handle_left_click_global_ui(pos=pos, args=args):
            return True
        if self._handle_left_click_combat_and_event(pos=pos, args=args):
            return True
        if self._handle_left_click_panels_and_selection(pos=pos, args=args):
            return True
        return False

    def handle_game_right_click(
        self,
        *,
        pos,
        pp_spend_mode: bool,
        pp_summon_target_prov,
        get_province_at: Callable,
        player_country: str | None,
        evt_flag_hu_recruit: bool,
        on_set_pp_summon_target_prov: Callable[[object | None], None],
        selected_units,
        card_effect_manager,
        on_get_people_support_level: Callable[[str], int],
        is_fort_or_city: Callable[[object], bool],
        morale_free_move_mode: bool,
        combat_target,
        on_cancel_combat_preview: Callable[[], None],
        on_handle_combat: Callable[[object], None],
        pending_post_move_attack: bool,
        on_handle_movement: Callable[[object], None],
        on_show_message: Callable[[str], None] | None = None,
    ) -> None:
        if pp_spend_mode and pp_summon_target_prov is None:
            _rc_prov = get_province_at(pos)
            if _rc_prov and _rc_prov.country == player_country:
                if len(_rc_prov.units) >= MAX_UNIT_STACK:
                    if on_show_message:
                        on_show_message("该地块部队已满（最多3支），无法召唤")
                elif evt_flag_hu_recruit and player_country == "WEI":
                    if on_show_message:
                        on_show_message("胡人袭扰：本回合魏国不能召唤新部队")
                else:
                    on_set_pp_summon_target_prov(_rc_prov)
            else:
                if on_show_message:
                    on_show_message("请右键点击己方地块来召唤部队")
            return

        if not selected_units:
            return

        target_province = get_province_at(pos)
        if not target_province:
            return

        is_enemy = target_province.country != player_country

        if is_enemy:
            target_effect = card_effect_manager.get_effect(str(target_province.province_id))
            if target_effect and target_effect.protected:
                if on_show_message:
                    on_show_message("此格子不能被进攻")
                return

        _danshi_lv = on_get_people_support_level(player_country) if player_country else 0
        _city_needs_combat = is_fort_or_city(target_province) and not (
            _danshi_lv >= 5 and len(target_province.units) == 0
        )
        can_attack = is_enemy and (len(target_province.units) > 0 or _city_needs_combat)

        if can_attack:
            if morale_free_move_mode:
                if on_show_message:
                    on_show_message("令行禁止：只可移动，不可攻击")
                return
            if combat_target and combat_target == target_province:
                on_cancel_combat_preview()
            else:
                on_handle_combat(target_province)
            return

        if pending_post_move_attack:
            if on_show_message:
                on_show_message("请选择攻击单位或不攻击")
            return

        on_handle_movement(target_province)

    def handle_keydown(
        self,
        *,
        key: int,
        help_overlay_visible: bool,
        morale_free_move_mode: bool,
        morale_bonus_mp_mode: bool,
        morale_cure_mode: bool,
        pp_spend_mode: bool,
        pp_summon_target_prov,
        selecting_card_target: bool,
        major_round_choice_pending: bool,
        on_set_help_overlay_visible: Callable[[bool], None],
        on_reset_morale_modes: Callable[[], None],
        on_show_message: Callable[[str], None] | None,
        on_set_pp_summon_target_prov: Callable[[object | None], None],
        on_clear_pp_summon_btns: Callable[[], None],
        on_set_pp_spend_mode: Callable[[bool], None],
        on_cancel_card_target_selection: Callable[[], None],
        on_clear_selection: Callable[[], None],
        on_play_selected_card: Callable[[], None],
    ) -> bool:
        commands = self.build_keydown_commands(
            key=key,
            help_overlay_visible=help_overlay_visible,
            morale_free_move_mode=morale_free_move_mode,
            morale_bonus_mp_mode=morale_bonus_mp_mode,
            morale_cure_mode=morale_cure_mode,
            pp_spend_mode=pp_spend_mode,
            pp_summon_target_prov=pp_summon_target_prov,
            selecting_card_target=selecting_card_target,
            major_round_choice_pending=major_round_choice_pending,
        )
        if not commands:
            return False

        for command in commands:
            name = command["name"]
            payload = command.get("payload")

            if name == "set_help_overlay_visible":
                on_set_help_overlay_visible(bool(payload))
            elif name == "reset_morale_modes":
                on_reset_morale_modes()
            elif name == "show_message":
                if on_show_message:
                    on_show_message(str(payload))
            elif name == "set_pp_summon_target_prov":
                on_set_pp_summon_target_prov(payload)
            elif name == "clear_pp_summon_btns":
                on_clear_pp_summon_btns()
            elif name == "set_pp_spend_mode":
                on_set_pp_spend_mode(bool(payload))
            elif name == "cancel_card_target_selection":
                on_cancel_card_target_selection()
            elif name == "clear_selection":
                on_clear_selection()
            elif name == "play_selected_card":
                on_play_selected_card()

        return True

    def build_keydown_commands(
        self,
        *,
        key: int,
        help_overlay_visible: bool,
        morale_free_move_mode: bool,
        morale_bonus_mp_mode: bool,
        morale_cure_mode: bool,
        pp_spend_mode: bool,
        pp_summon_target_prov,
        selecting_card_target: bool,
        major_round_choice_pending: bool,
    ) -> list[dict]:
        """构建键盘输入命令（命令由编排层执行）。"""
        commands: list[dict] = []

        if key == pg.K_ESCAPE:
            if help_overlay_visible:
                return [{"name": "set_help_overlay_visible", "payload": False}]

            if morale_free_move_mode or morale_bonus_mp_mode or morale_cure_mode:
                return [
                    {"name": "reset_morale_modes"},
                    {"name": "show_message", "payload": "已取消民心效果操作"},
                ]

            if pp_spend_mode:
                if pp_summon_target_prov is not None:
                    return [
                        {"name": "set_pp_summon_target_prov", "payload": None},
                        {"name": "clear_pp_summon_btns"},
                        {"name": "show_message", "payload": "已取消召唤选择，可继续使用PP"},
                    ]
                return [
                    {"name": "set_pp_spend_mode", "payload": False},
                    {
                        "name": "show_message",
                        "payload": "已退出PP行动模式（回合未结束，可继续操作）",
                    },
                ]

            if selecting_card_target:
                return [{"name": "cancel_card_target_selection"}]

            return [{"name": "clear_selection"}]

        if key == pg.K_RETURN:
            if major_round_choice_pending:
                return [{"name": "show_message", "payload": "请先完成三国大回合加点选择"}]
            return [{"name": "play_selected_card"}]

        return commands

    def build_right_click_commands(
        self,
        *,
        pos,
        major_round_choice_pending: bool,
        evt_draw_phase: bool,
        selecting_evt_target: bool,
    ) -> list[dict]:
        """构建右键输入命令（命令由编排层执行）。"""
        _messages: list[str] = []
        blocked = self.should_block_right_click(
            major_round_choice_pending=major_round_choice_pending,
            evt_draw_phase=evt_draw_phase,
            selecting_evt_target=selecting_evt_target,
            on_block_message=lambda msg: _messages.append(msg),
        )
        if blocked:
            commands = [{"name": "show_message", "payload": msg} for msg in _messages]
            commands.append({"name": "consume_event"})
            return commands
        return [{"name": "handle_game_right_click", "payload": pos}]

    def handle_volume_slider_click(
        self,
        *,
        volume_slider_visible: bool,
        slider_rect: pg.Rect | None,
        pos,
        on_start_drag: Callable[[], None],
        on_update_volume: Callable[[int], None],
        on_hide_slider: Callable[[], None],
    ) -> bool:
        if not volume_slider_visible or not slider_rect:
            return False
        if slider_rect.collidepoint(pos):
            on_start_drag()
            on_update_volume(pos[1])
            return True
        on_hide_slider()
        return False

    def handle_unit_selection_click(
        self,
        *,
        pos,
        get_unit_slot_at: Callable,
        get_province_by_id: Callable,
        player_country: str | None,
        pending_post_move_attack: bool,
        pending_attacker,
        selected_units,
        on_remove_selection: Callable[[int, int], None],
        on_add_selection: Callable[[int, int, bool], None],
        on_show_message: Callable[[str], None] | None = None,
        shift_held: bool = False,
    ) -> bool:
        target_unit = get_unit_slot_at(pos)
        if not target_unit:
            return False

        prov_id, slot_idx = target_unit
        prov = get_province_by_id(prov_id)
        if prov and prov.country and prov.country != player_country:
            if on_show_message:
                on_show_message("不能操作敌方单位")
            return True

        if pending_post_move_attack and pending_attacker:
            if (prov_id, slot_idx) != pending_attacker:
                if on_show_message:
                    on_show_message("请继续使用刚移动的单位，或右键结束该动作")
                return True

        if (prov_id, slot_idx) in selected_units:
            on_remove_selection(prov_id, slot_idx)
        else:
            on_add_selection(prov_id, slot_idx, shift_held)
        return True

    def should_block_right_click(
        self,
        *,
        major_round_choice_pending: bool,
        evt_draw_phase: bool,
        selecting_evt_target: bool,
        on_block_message: Callable[[str], None] | None = None,
    ) -> bool:
        if major_round_choice_pending:
            if on_block_message:
                on_block_message("请先完成三国大回合加点选择")
            return True
        if evt_draw_phase or selecting_evt_target:
            return True
        return False

    def handle_mouse_motion(
        self,
        *,
        vol_dragging: bool,
        volume_slider_visible: bool,
        slider_rect: pg.Rect | None,
        pos,
        on_update_volume: Callable[[int], None],
        card_panel=None,
    ) -> None:
        if vol_dragging and volume_slider_visible and slider_rect:
            on_update_volume(pos[1])
        if card_panel:
            card_panel.handle_mouse_motion(pos)

    def handle_left_button_up(self, *, on_stop_drag: Callable[[], None]) -> None:
        on_stop_drag()

    def handle_card_panel_click(
        self,
        *,
        pos,
        card_panel,
        show_combat_ui: bool,
        waiting_defender_response: bool,
        allow_jiangdong_selection: bool,
        card_repository,
        on_play_selected_card: Callable[[], None],
        on_show_message: Callable[[str], None] | None = None,
    ) -> bool:
        if not card_panel or not card_panel.rect.collidepoint(pos):
            return False

        card_id = card_panel.get_card_at(pos)
        if not card_id:
            return False

        card_panel.select_card(card_id)

        if (
            card_id == "card_jiangdong_zhiti"
            and show_combat_ui
            and waiting_defender_response
            and allow_jiangdong_selection
        ):
            on_play_selected_card()
            return True

        card_def = card_repository.get_definition(card_id)
        if card_def and card_def.category in ("buff", "defensive", "summon"):
            on_play_selected_card()
            return True

        if card_def and on_show_message:
            _desc = card_def.description or ""
            on_show_message(f"【{card_def.name}】\n{_desc}\n按 Enter 使用")

        return True

    def handle_info_panel_click(self, *, info_panel, pos) -> bool:
        return bool(info_panel and info_panel.handle_click(pos))

    def handle_card_target_click(
        self,
        *,
        pos,
        selecting_card_target: bool,
        selected_card_for_effect: str | None,
        get_province_at: Callable,
        apply_card_to_province: Callable[[str, int], bool],
        on_clear_card_target_selection: Callable[[], None],
        on_show_message: Callable[..., None] | None = None,
    ) -> bool:
        if not selecting_card_target or not selected_card_for_effect:
            return False

        target_prov = get_province_at(pos)
        if target_prov:
            if apply_card_to_province(
                selected_card_for_effect,
                target_prov.province_id,
            ):
                on_clear_card_target_selection()
            return True

        if on_show_message:
            on_show_message("请点击地图上的一个格子", duration=1.0)
        return True

    def handle_combat_ui_click(
        self,
        *,
        pos,
        show_combat_ui: bool,
        combat_btn_rect: pg.Rect | None,
        defender_can_use_jiangdong: bool,
        defender_jiangdong_decided: bool,
        defender_can_hold_position: bool,
        defender_hold_decided: bool,
        waiting_defender_response: bool,
        defense_hold_btn_rect: pg.Rect | None,
        defense_hold_skip_btn_rect: pg.Rect | None,
        skip_jiangdong_card_btn_rect: pg.Rect | None,
        player_country: str | None,
        card_managers,
        on_set_waiting_defender_response: Callable[[bool], None],
        on_set_allow_jiangdong_selection: Callable[[bool], None],
        on_set_card_manager: Callable[[object], None],
        on_update_card_panel: Callable[[], None],
        on_show_message: Callable[..., None] | None,
        on_set_defender_use_hold_position: Callable[[bool], None],
        on_set_defender_hold_decided: Callable[[bool], None],
        on_set_defender_use_jiangdong: Callable[[bool], None],
        on_set_defender_jiangdong_decided: Callable[[bool], None],
        combat_callback: Callable[[], None] | None,
    ) -> bool:
        if show_combat_ui and combat_btn_rect and combat_btn_rect.collidepoint(pos):
            if defender_can_use_jiangdong and not defender_jiangdong_decided:
                on_set_waiting_defender_response(True)
                on_set_allow_jiangdong_selection(True)
                wei_manager = card_managers.get("WEI")
                if wei_manager:
                    on_set_card_manager(wei_manager)
                on_update_card_panel()
                if on_show_message:
                    on_show_message("进攻方已投骰，请防守方选择江东止啼（或点击不使用）")
                return True

            if defender_can_hold_position and not defender_hold_decided:
                on_set_waiting_defender_response(True)
                if on_show_message:
                    on_show_message("进攻方已投骰，等待防守方即时决策")
                return True

            if combat_callback:
                combat_callback()
            return True

        if show_combat_ui and defense_hold_btn_rect and defense_hold_btn_rect.collidepoint(pos):
            if waiting_defender_response and defender_can_hold_position and not defender_hold_decided:
                on_set_defender_use_hold_position(True)
                on_set_defender_hold_decided(True)
                if on_show_message:
                    on_show_message("已选择：防守方选择：DR改D1DG", duration=1.2)
                if defender_jiangdong_decided and combat_callback:
                    on_set_waiting_defender_response(False)
                    combat_callback()
            return True

        if (
            show_combat_ui
            and defense_hold_skip_btn_rect
            and defense_hold_skip_btn_rect.collidepoint(pos)
        ):
            if waiting_defender_response and defender_can_hold_position and not defender_hold_decided:
                on_set_defender_use_hold_position(False)
                on_set_defender_hold_decided(True)
                if on_show_message:
                    on_show_message("已选择：保持正常DR", duration=1.2)
                if defender_jiangdong_decided and combat_callback:
                    on_set_waiting_defender_response(False)
                    combat_callback()
            return True

        if (
            show_combat_ui
            and skip_jiangdong_card_btn_rect
            and skip_jiangdong_card_btn_rect.collidepoint(pos)
        ):
            if waiting_defender_response and defender_can_use_jiangdong and not defender_jiangdong_decided:
                on_set_defender_use_jiangdong(False)
                on_set_defender_jiangdong_decided(True)
                on_set_allow_jiangdong_selection(False)
                if player_country and player_country in card_managers:
                    on_set_card_manager(card_managers[player_country])
                on_update_card_panel()
                if on_show_message:
                    on_show_message("已选择：本次不使用江东止啼", duration=1.2)
                if defender_hold_decided and combat_callback:
                    on_set_waiting_defender_response(False)
                    combat_callback()
            return True

        return False

    def handle_evt_target_click(
        self,
        *,
        selecting_evt_target: bool,
        pending_evt_card_id: str | None,
        event_card_deck,
        pending_evt_drawer: str | None,
        player_country: str | None,
        pos,
        get_unit_slot_at: Callable,
        get_province_by_id: Callable,
        get_province_at: Callable,
        on_apply_evt_target_unit: Callable[[int, int], None],
        on_apply_evt_target_province: Callable[[int], None],
        country_labels,
        on_show_message: Callable[[str], None] | None = None,
    ) -> bool:
        if not selecting_evt_target or not pending_evt_card_id:
            return False

        card_def = event_card_deck.get_definition(pending_evt_card_id)
        selector = pending_evt_drawer or player_country
        if card_def and card_def.target_type == "unit":
            target_unit = get_unit_slot_at(pos)
            if target_unit:
                prov_id, slot_idx = target_unit
                prov = get_province_by_id(prov_id)
                if prov and prov.country == selector:
                    on_apply_evt_target_unit(prov_id, slot_idx)
                else:
                    cn = country_labels.get(selector, selector)
                    if on_show_message:
                        on_show_message(f"请点击{cn}的单位")
            else:
                if on_show_message:
                    cn = country_labels.get(selector, selector)
                    on_show_message(f"请点击{cn}的单位")
            return True

        if card_def and card_def.target_type == "province":
            prov = get_province_at(pos)
            if prov and prov.country == selector:
                on_apply_evt_target_province(prov.province_id)
            else:
                cn = country_labels.get(selector, selector)
                if on_show_message:
                    on_show_message(f"请点击{cn}的地块")
            return True

        return False

    def handle_draw_event_button_click(
        self,
        *,
        draw_event_btn_rect: pg.Rect | None,
        pos,
        player_country: str | None,
        on_trigger_draw_event_card: Callable[[str | None], None],
    ) -> bool:
        if not draw_event_btn_rect or not draw_event_btn_rect.collidepoint(pos):
            return False
        on_trigger_draw_event_card(player_country)
        return True

    def handle_pp_click(
        self,
        *,
        pos,
        pp_btn_rect: pg.Rect | None,
        player_country: str | None,
        can_use_pp: Callable[[str | None], bool],
        pp_spend_mode: bool,
        pp_spend_end_btn_rect: pg.Rect | None,
        pp_summon_target_prov,
        pp_summon_btns,
        evt_flag_hu_recruit: bool,
        spend_pp: Callable[[str | None, int], bool],
        unit_repository,
        on_invalidate_map_cache: Callable[[], None],
        on_record_move_dst: Callable[[int, str | None, int], None],
        get_total_pp: Callable[[str | None], int],
        get_unit_slot_at: Callable,
        get_province_by_id: Callable,
        get_pp_heal_cost: Callable,
        is_special_unit: Callable,
        on_finish_country_action: Callable[[str], None],
        on_set_pp_spend_mode: Callable[[bool], None],
        on_set_pp_summon_target_prov: Callable[[object | None], None],
        on_set_pp_summon_btns: Callable[[list], None],
        on_show_message: Callable[..., None] | None,
    ) -> bool:
        if pp_btn_rect and pp_btn_rect.collidepoint(pos):
            if can_use_pp(player_country):
                on_set_pp_spend_mode(True)
                if on_show_message:
                    on_show_message(
                        "PP行动：左键点击受伤己方单位回血，右键点击己方地块召唤部队",
                        duration=3.0,
                    )
            else:
                if on_show_message:
                    on_show_message("政治点数不足（需≥1才可使用）")
            return True

        if not pp_spend_mode:
            return False

        if pp_spend_end_btn_rect and pp_spend_end_btn_rect.collidepoint(pos):
            on_set_pp_spend_mode(False)
            on_set_pp_summon_target_prov(None)
            on_set_pp_summon_btns([])
            on_finish_country_action("使用政治点数")
            return True

        if pp_summon_target_prov is not None:
            for _sbtn in pp_summon_btns:
                if not _sbtn["rect"].collidepoint(pos):
                    continue

                if _sbtn["unit_type"] is None:
                    on_set_pp_summon_target_prov(None)
                    on_set_pp_summon_btns([])
                    if on_show_message:
                        on_show_message("已取消召唤")
                    return True

                if _sbtn["enabled"]:
                    _tprov = pp_summon_target_prov
                    _utype = _sbtn["unit_type"]
                    _uhp = _sbtn["hp"]
                    _ucost = _sbtn["cost"]
                    if evt_flag_hu_recruit and player_country == "WEI":
                        if on_show_message:
                            on_show_message("胡人袭扰：本回合魏国不能召唤新部队")
                    elif len(_tprov.units) >= MAX_UNIT_STACK:
                        if on_show_message:
                            on_show_message("该地块部队已满（最多3支）")
                    elif spend_pp(player_country, _ucost):
                        try:
                            _udef = unit_repository.get_definition(_utype)
                            _nu = UnitState(_utype)
                            _nu.hp = _uhp
                            _nu.mp = _udef.move
                            _tprov.units.append(_nu)
                            on_invalidate_map_cache()
                            on_record_move_dst(
                                _tprov.province_id,
                                player_country,
                                len(_tprov.units) - 1,
                            )
                            _remain = get_total_pp(player_country)
                            _uname = {
                                "infantry": "步兵",
                                "cavalry": "骑兵",
                                "archer": "弓兵",
                            }.get(_utype, _utype)
                            if on_show_message:
                                on_show_message(
                                    f"在{_tprov.name}召唤了{_uname}（{_uhp}血），剩余PP：{_remain}"
                                )
                        except Exception:
                            logger.exception("PP召唤失败")
                            return True
                    else:
                        if on_show_message:
                            on_show_message("政治点数不足")
                else:
                    if on_show_message:
                        on_show_message("政治点数不足以执行此操作")

                on_set_pp_summon_target_prov(None)
                on_set_pp_summon_btns([])
                return True

            return True

        _unit_hit = get_unit_slot_at(pos)
        if _unit_hit:
            _hpid, _hslot = _unit_hit
            _hprov = get_province_by_id(_hpid)
            if _hprov and _hprov.country == player_country and _hslot < len(_hprov.units):
                _hu = _hprov.units[_hslot]
                if _hu.hp >= 2:
                    if on_show_message:
                        on_show_message("该单位已满血，无需回复")
                else:
                    _hcost = get_pp_heal_cost(_hu)
                    if get_total_pp(player_country) < _hcost:
                        _utp = "特殊" if is_special_unit(_hu) else "普通"
                        if on_show_message:
                            on_show_message(f"政治点数不足（{_utp}单位回血需{_hcost}PP）")
                    elif spend_pp(player_country, _hcost):
                        _hu.hp += 1
                        _remain2 = get_total_pp(player_country)
                        _utp2 = "特殊" if is_special_unit(_hu) else "普通"
                        if on_show_message:
                            on_show_message(
                                f"{_utp2}单位回复1血（消耗{_hcost}PP），剩余PP：{_remain2}"
                            )
            else:
                if on_show_message:
                    on_show_message("请点击己方受伤单位")
        return True

    def handle_morale_click(
        self,
        *,
        pos,
        morale_lv2_btn_rect: pg.Rect | None,
        morale_lv3_btn_rect: pg.Rect | None,
        morale_lv4_btn_rect: pg.Rect | None,
        morale_bonus_mp_mode: bool,
        morale_cure_mode: bool,
        player_country: str | None,
        major_round: int,
        get_unit_slot_at: Callable,
        get_province_by_id: Callable,
        has_confused_units_for_country: Callable[[str], bool],
        on_set_morale_free_move_mode: Callable[[bool], None],
        on_set_morale_bonus_mp_mode: Callable[[bool], None],
        on_set_morale_cure_mode: Callable[[bool], None],
        on_clear_morale_lv4_pending: Callable[[str], None],
        on_mark_morale_lv3_used: Callable[[str, int], None],
        on_show_message: Callable[..., None] | None = None,
    ) -> bool:
        if morale_lv2_btn_rect and morale_lv2_btn_rect.collidepoint(pos):
            on_set_morale_free_move_mode(True)
            if on_show_message:
                on_show_message(
                    "令行禁止：请选中1个单位，再右键点击相邻格", duration=3.0
                )
            return True
        if morale_lv3_btn_rect and morale_lv3_btn_rect.collidepoint(pos):
            on_set_morale_bonus_mp_mode(True)
            if on_show_message:
                on_show_message(
                    "老乡指路：请点击一个己方单位获得+1行动力", duration=3.0
                )
            return True
        if morale_lv4_btn_rect and morale_lv4_btn_rect.collidepoint(pos):
            if player_country and has_confused_units_for_country(player_country):
                on_set_morale_cure_mode(True)
                if on_show_message:
                    on_show_message("军容严整：请点击一个混乱的己方单位", duration=3.0)
            else:
                if player_country:
                    on_clear_morale_lv4_pending(player_country)
                if on_show_message:
                    on_show_message("军容严整：当前无混乱单位")
            return True

        if morale_bonus_mp_mode:
            unit_hit = get_unit_slot_at(pos)
            if unit_hit:
                _prov_id, _slot = unit_hit
                _prov = get_province_by_id(_prov_id)
                if _prov and _prov.country == player_country and _slot < len(_prov.units):
                    _prov.units[_slot].mp += 1
                    on_set_morale_bonus_mp_mode(False)
                    if player_country:
                        on_mark_morale_lv3_used(player_country, major_round)
                    if on_show_message:
                        on_show_message("老乡指路：该单位行动力+1")
                else:
                    if on_show_message:
                        on_show_message("请点击己方单位")
            else:
                if on_show_message:
                    on_show_message("请点击己方单位")
            return True

        if morale_cure_mode:
            unit_hit = get_unit_slot_at(pos)
            if unit_hit:
                _prov_id, _slot = unit_hit
                _prov = get_province_by_id(_prov_id)
                if _prov and _prov.country == player_country and _slot < len(_prov.units):
                    _u = _prov.units[_slot]
                    if _u.is_confused:
                        _u.is_confused = False
                        on_set_morale_cure_mode(False)
                        if player_country:
                            on_clear_morale_lv4_pending(player_country)
                        if on_show_message:
                            on_show_message("军容严整：混乱已解除（大回合结束奖励）")
                    else:
                        if on_show_message:
                            on_show_message("该单位未处于混乱状态，请重新选择")
                else:
                    if on_show_message:
                        on_show_message("请点击己方单位")
            else:
                if on_show_message:
                    on_show_message("请点击混乱状态的己方单位")
            return True

        return False

    def handle_recover_click(
        self,
        *,
        recover_btn_rect: pg.Rect | None,
        pos,
        selected_units,
        get_province_by_id: Callable,
        on_show_message: Callable[[str], None] | None,
        on_update_selection_info: Callable[[], None],
        on_finish_country_action: Callable[[str], None],
    ) -> bool:
        if not recover_btn_rect or not recover_btn_rect.collidepoint(pos):
            return False

        confused_list = []
        for pid, slot in selected_units:
            prov = get_province_by_id(pid)
            if prov and slot < len(prov.units):
                u = prov.units[slot]
                if u.is_confused:
                    confused_list.append(u)

        if len(confused_list) == 1:
            confused_list[0].is_confused = False
            if on_show_message:
                on_show_message("混乱状态已解除")
            on_update_selection_info()
            on_finish_country_action("解除混乱")
        return True

    def handle_no_attack_click(
        self,
        *,
        pending_post_move_attack: bool,
        no_attack_btn_rect: pg.Rect | None,
        pos,
        morale_free_move_mode: bool,
        player_country: str | None,
        major_round: int,
        on_mark_morale_lv2_used: Callable[[str, int], None],
        on_set_morale_free_move_mode: Callable[[bool], None],
        on_set_pending_post_move_attack: Callable[[bool], None],
        on_set_pending_attacker,
        on_clear_selection: Callable[[], None],
        on_show_message: Callable[..., None] | None,
        on_finish_country_action: Callable[[str], None],
    ) -> bool:
        if (
            not pending_post_move_attack
            or not no_attack_btn_rect
            or not no_attack_btn_rect.collidepoint(pos)
        ):
            return False

        if morale_free_move_mode:
            if player_country:
                on_mark_morale_lv2_used(player_country, major_round)
            on_set_morale_free_move_mode(False)
            on_set_pending_post_move_attack(False)
            on_set_pending_attacker(None)
            on_clear_selection()
            if on_show_message:
                on_show_message("令行禁止：移动完成，继续行动", duration=2.0)
            return True

        if on_show_message:
            on_show_message("已选择不攻击，进入下一步", duration=1.0)
        on_finish_country_action("移动")
        return True

    def handle_major_round_choice_click(
        self,
        *,
        major_round_choice_pending: bool,
        country_stat_choice_btns,
        pos,
        on_apply_major_round_choice: Callable[[str, str], None],
        on_show_message: Callable[[str], None] | None = None,
    ) -> bool:
        if not major_round_choice_pending:
            return False

        for country, btns in country_stat_choice_btns.items():
            support_rect = btns.get("support")
            politics_rect = btns.get("politics")
            if support_rect and support_rect.collidepoint(pos):
                on_apply_major_round_choice(country, "support")
                return True
            if politics_rect and politics_rect.collidepoint(pos):
                on_apply_major_round_choice(country, "politics")
                return True

        if on_show_message:
            on_show_message("请在三国面板中完成加点选择")
        return True

    def handle_evt_draw_phase_click(
        self,
        *,
        evt_draw_phase: bool,
        selecting_evt_target: bool,
        evt_skip_draw_btn_rect: pg.Rect | None,
        draw_event_btn_rect: pg.Rect | None,
        pos,
        player_country: str | None,
        on_exit_evt_draw_phase: Callable[[], None],
        on_trigger_draw_event_card: Callable[[str | None], None],
        has_event_card_overlay: bool,
        on_check_evt_draw_phase_pp: Callable[[], None],
        on_show_message: Callable[[str], None] | None = None,
    ) -> bool:
        if not evt_draw_phase or selecting_evt_target:
            return False

        if evt_skip_draw_btn_rect and evt_skip_draw_btn_rect.collidepoint(pos):
            on_exit_evt_draw_phase()
            return True

        if draw_event_btn_rect and draw_event_btn_rect.collidepoint(pos):
            on_trigger_draw_event_card(player_country)
            if not has_event_card_overlay:
                on_check_evt_draw_phase_pp()
            return True

        if on_show_message:
            on_show_message("请先完成事件卡阶段（抽取或跳过）")
        return True

    def handle_help_overlay_wheel(
        self,
        *,
        event: pg.event.Event,
        help_overlay_visible: bool,
        help_rule_surfaces,
        help_current_page: int,
        help_zoom_factor: float = 1.0,
        ctrl_held: bool | None = None,
        on_set_help_current_page: Callable[[int], None],
        on_set_help_zoom_factor: Callable[[float], None] | None = None,
    ) -> bool:
        if event.type != pg.MOUSEWHEEL or not help_overlay_visible:
            return False

        if ctrl_held is None:
            try:
                ctrl_held = bool(pg.key.get_mods() & pg.KMOD_CTRL)
            except Exception:
                ctrl_held = False

        if ctrl_held:
            # Ctrl+滚轮：缩放
            delta = 0.15 if (event.y > 0 or event.x < 0) else -0.15
            raw = help_zoom_factor + delta
            # 跨过 100% 时吸附到 100%档位
            if (help_zoom_factor < 1.0 < raw) or (raw < 1.0 < help_zoom_factor):
                new_zoom = 1.0
            else:
                new_zoom = max(0.5, min(3.0, round(raw, 2)))
            if on_set_help_zoom_factor is not None:
                on_set_help_zoom_factor(new_zoom)
        else:
            total = len(help_rule_surfaces)
            if total > 0:
                if event.y > 0 or event.x < 0:
                    on_set_help_current_page(max(0, help_current_page - 1))
                elif event.y < 0 or event.x > 0:
                    on_set_help_current_page(min(total - 1, help_current_page + 1))
        return True

    def handle_help_overlay_click(
        self,
        *,
        event: pg.event.Event,
        help_overlay_visible: bool,
        help_rule_surfaces,
        help_current_page: int,
        help_prev_btn: pg.Rect | None,
        help_next_btn: pg.Rect | None,
        help_overlay_content_rect: pg.Rect | None,
        on_set_help_current_page: Callable[[int], None],
        on_set_help_overlay_visible: Callable[[bool], None],
    ) -> bool:
        if (
            event.type != pg.MOUSEBUTTONDOWN
            or event.button != 1
            or not help_overlay_visible
        ):
            return False

        total = len(help_rule_surfaces)
        if help_prev_btn and help_prev_btn.collidepoint(event.pos) and total > 0:
            on_set_help_current_page(max(0, help_current_page - 1))
            return True
        if help_next_btn and help_next_btn.collidepoint(event.pos) and total > 0:
            on_set_help_current_page(min(total - 1, help_current_page + 1))
            return True

        content_rect = help_overlay_content_rect
        if content_rect is None or not content_rect.collidepoint(event.pos):
            on_set_help_overlay_visible(False)

        return True

    def handle_control_button_click(
        self,
        *,
        control_btns,
        pos,
        state,
        on_stop: Callable[[], None],
        on_restart_game: Callable[[], None],
        on_show_score_screen: Callable[[str], None],
        volume_slider_visible: bool,
        on_set_volume_slider_visible: Callable[[bool], None],
        help_overlay_visible: bool,
        on_set_help_overlay_visible: Callable[[bool], None],
        on_set_help_current_page: Callable[[int], None],
        on_start_help_rule_load: Callable[[], None],
    ) -> bool:
        for btn in control_btns:
            if not btn["rect"].collidepoint(pos):
                continue

            action = btn["action"]
            if action == "EXIT":
                on_stop()
            elif action == "RESTART":
                on_restart_game()
            elif action == "SCORE":
                if state == type(state).PLAYING:
                    on_show_score_screen("wei_turn")
            elif action == "VOLUME":
                on_set_volume_slider_visible(not volume_slider_visible)
            elif action == "HELP":
                next_visible = not help_overlay_visible
                on_set_help_overlay_visible(next_visible)
                on_set_help_current_page(0)
                if next_visible:
                    on_start_help_rule_load()
            return True
        return False
