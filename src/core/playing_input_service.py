from __future__ import annotations

import logging
from typing import Callable

import pygame as pg

from src.game_objects.unit import UnitState

MAX_UNIT_STACK = 3

logger = logging.getLogger(__name__)


class PlayingInputService:
    """游戏内输入分支服务（帮助覆盖层、顶部功能按钮）。"""

    def handle_game_right_click(self, app, pos) -> None:
        self = app
        if self.pp_spend_mode and self.pp_summon_target_prov is None:
            _rc_prov = self._get_province_at(pos)
            if _rc_prov and _rc_prov.country == self.player_country:
                if len(_rc_prov.units) >= MAX_UNIT_STACK:
                    if self.info_panel:
                        self.info_panel.show_message("该地块部队已满（最多3支），无法召唤")
                elif self.evt_flag_hu_recruit and self.player_country == "WEI":
                    if self.info_panel:
                        self.info_panel.show_message("胡人袭扰：本回合魏国不能召唤新部队")
                else:
                    self.pp_summon_target_prov = _rc_prov
            else:
                if self.info_panel:
                    self.info_panel.show_message("请右键点击己方地块来召唤部队")
            return

        if not self.selected_units:
            return

        target_province = self._get_province_at(pos)
        if not target_province:
            return

        is_enemy = target_province.country != self.player_country

        if is_enemy:
            target_effect = self.card_effect_manager.get_effect(str(target_province.province_id))
            if target_effect and target_effect.protected:
                self.info_panel.show_message("此格子不能被进攻")
                return

        _danshi_lv = self._get_people_support_level(self.player_country) if self.player_country else 0
        _city_needs_combat = self._is_fort_or_city(target_province) and not (
            _danshi_lv >= 5 and len(target_province.units) == 0
        )
        can_attack = is_enemy and (len(target_province.units) > 0 or _city_needs_combat)

        if can_attack:
            if self.morale_free_move_mode:
                self.info_panel.show_message("令行禁止：只可移动，不可攻击")
                return
            if self.combat_target and self.combat_target == target_province:
                self._cancel_combat_preview()
            else:
                self._handle_combat(target_province)
            return

        if self.pending_post_move_attack:
            if self.info_panel:
                self.info_panel.show_message("请选择攻击单位或不攻击")
            return

        self._handle_movement(target_province)

    def handle_keydown(self, app, event: pg.event.Event) -> bool:
        self = app
        if event.key == pg.K_ESCAPE:
            if self.help_overlay_visible:
                self.help_overlay_visible = False
                return True
            if self.morale_free_move_mode or self.morale_bonus_mp_mode or self.morale_cure_mode:
                self.morale_free_move_mode = False
                self.morale_bonus_mp_mode = False
                self.morale_cure_mode = False
                if self.info_panel:
                    self.info_panel.show_message("已取消民心效果操作")
                return True
            if self.pp_spend_mode:
                if self.pp_summon_target_prov is not None:
                    self.pp_summon_target_prov = None
                    self.pp_summon_btns = []
                    if self.info_panel:
                        self.info_panel.show_message("已取消召唤选择，可继续使用PP")
                else:
                    self.pp_spend_mode = False
                    if self.info_panel:
                        self.info_panel.show_message("已退出PP行动模式（回合未结束，可继续操作）")
                return True
            if self.selecting_card_target:
                self._cancel_card_target_selection()
                return True
            self.clear_selection()
            return True

        if event.key == pg.K_RETURN:
            if self.major_round_choice_pending:
                if self.info_panel:
                    self.info_panel.show_message("请先完成三国大回合加点选择")
                return True
            self._play_selected_card()
            return True

        return False

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

    def handle_unit_selection_click(self, app, pos) -> bool:
        self = app
        target_unit = self._get_unit_slot_at(pos)
        if not target_unit:
            return False

        prov_id, slot_idx = target_unit
        prov = self.map_manager.get_by_id(prov_id)
        if prov and prov.country and prov.country != self.player_country:
            self.info_panel.show_message("不能操作敌方单位")
            return True

        if self.pending_post_move_attack and self.pending_attacker:
            if (prov_id, slot_idx) != self.pending_attacker:
                self.info_panel.show_message("请继续使用刚移动的单位，或右键结束该动作")
                return True

        if (prov_id, slot_idx) in self.selected_units:
            self.remove_selection(prov_id, slot_idx)
        else:
            shift_held = bool(pg.key.get_mods() & pg.KMOD_SHIFT)
            self.add_selection(prov_id, slot_idx, allow_cross_province=shift_held)
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

    def handle_card_panel_click(self, app, pos) -> bool:
        self = app
        if not self.card_panel or not self.card_panel.rect.collidepoint(pos):
            return False

        card_id = self.card_panel.get_card_at(pos)
        if not card_id:
            return False

        self.card_panel.select_card(card_id)

        if (
            card_id == "card_jiangdong_zhiti"
            and self.show_combat_ui
            and self.waiting_defender_response
            and self.allow_jiangdong_selection
        ):
            self._play_selected_card()
            return True

        card_def = self.card_repository.get_definition(card_id)
        if card_def and card_def.category in ("buff", "defensive", "summon"):
            self._play_selected_card()
            return True

        if card_def:
            _desc = card_def.description or ""
            self.info_panel.show_message(f"【{card_def.name}】\n{_desc}\n按 Enter 使用")

        return True

    def handle_info_panel_click(self, app, pos) -> bool:
        self = app
        return bool(self.info_panel and self.info_panel.handle_click(pos))

    def handle_card_target_click(self, app, pos) -> bool:
        self = app
        if not self.selecting_card_target or not self.selected_card_for_effect:
            return False

        target_prov = self._get_province_at(pos)
        if target_prov:
            if self._apply_card_to_province(
                self.selected_card_for_effect,
                target_prov.province_id,
            ):
                self.selecting_card_target = False
                self.selected_card_for_effect = None
            return True

        self.info_panel.show_message("请点击地图上的一个格子", duration=1.0)
        return True

    def handle_combat_ui_click(self, app, pos) -> bool:
        self = app
        if self.show_combat_ui and self.combat_btn_rect and self.combat_btn_rect.collidepoint(pos):
            if self.defender_can_use_jiangdong and not self.defender_jiangdong_decided:
                self.waiting_defender_response = True
                self.allow_jiangdong_selection = True
                wei_manager = self.card_managers.get("WEI")
                if wei_manager:
                    self.card_manager = wei_manager
                self._update_card_panel()
                self.info_panel.show_message("进攻方已投骰，请防守方选择江东止啼（或点击不使用）")
                return True

            if self.defender_can_hold_position and not self.defender_hold_decided:
                self.waiting_defender_response = True
                self.info_panel.show_message("进攻方已投骰，等待防守方即时决策")
                return True

            if self.combat_callback:
                self.combat_callback()
            return True

        if (
            self.show_combat_ui
            and self.defense_hold_btn_rect
            and self.defense_hold_btn_rect.collidepoint(pos)
        ):
            if (
                self.waiting_defender_response
                and self.defender_can_hold_position
                and not self.defender_hold_decided
            ):
                self.defender_use_hold_position = True
                self.defender_hold_decided = True
                self.info_panel.show_message("已选择：防守方选择：DR改D1DG", duration=1.2)
                if (
                    self.defender_jiangdong_decided
                    and self.defender_hold_decided
                    and self.combat_callback
                ):
                    self.waiting_defender_response = False
                    self.combat_callback()
            return True

        if (
            self.show_combat_ui
            and self.defense_hold_skip_btn_rect
            and self.defense_hold_skip_btn_rect.collidepoint(pos)
        ):
            if (
                self.waiting_defender_response
                and self.defender_can_hold_position
                and not self.defender_hold_decided
            ):
                self.defender_use_hold_position = False
                self.defender_hold_decided = True
                self.info_panel.show_message("已选择：保持正常DR", duration=1.2)
                if (
                    self.defender_jiangdong_decided
                    and self.defender_hold_decided
                    and self.combat_callback
                ):
                    self.waiting_defender_response = False
                    self.combat_callback()
            return True

        if (
            self.show_combat_ui
            and self.skip_jiangdong_card_btn_rect
            and self.skip_jiangdong_card_btn_rect.collidepoint(pos)
        ):
            if (
                self.waiting_defender_response
                and self.defender_can_use_jiangdong
                and not self.defender_jiangdong_decided
            ):
                self.defender_use_jiangdong = False
                self.defender_jiangdong_decided = True
                self.allow_jiangdong_selection = False
                if self.player_country and self.player_country in self.card_managers:
                    self.card_manager = self.card_managers[self.player_country]
                self._update_card_panel()
                self.info_panel.show_message("已选择：本次不使用江东止啼", duration=1.2)
                if (
                    self.defender_jiangdong_decided
                    and self.defender_hold_decided
                    and self.combat_callback
                ):
                    self.waiting_defender_response = False
                    self.combat_callback()
            return True

        return False

    def handle_evt_target_click(self, app, pos) -> bool:
        self = app
        if not self.selecting_evt_target or not self.pending_evt_card_id:
            return False

        card_def = self.event_card_deck.get_definition(self.pending_evt_card_id)
        selector = self.pending_evt_drawer or self.player_country
        if card_def and card_def.target_type == "unit":
            target_unit = self._get_unit_slot_at(pos)
            if target_unit:
                prov_id, slot_idx = target_unit
                prov = self.map_manager.get_by_id(prov_id)
                if prov and prov.country == selector:
                    self._apply_evt_target_unit(prov_id, slot_idx)
                else:
                    cn = self.country_labels.get(selector, selector)
                    if self.info_panel:
                        self.info_panel.show_message(f"请点击{cn}的单位")
            else:
                if self.info_panel:
                    cn = self.country_labels.get(selector, selector)
                    self.info_panel.show_message(f"请点击{cn}的单位")
            return True

        if card_def and card_def.target_type == "province":
            prov = self._get_province_at(pos)
            if prov and prov.country == selector:
                self._apply_evt_target_province(prov.province_id)
            else:
                cn = self.country_labels.get(selector, selector)
                if self.info_panel:
                    self.info_panel.show_message(f"请点击{cn}的地块")
            return True

        return False

    def handle_draw_event_button_click(self, app, pos) -> bool:
        self = app
        if not self.draw_event_btn_rect or not self.draw_event_btn_rect.collidepoint(pos):
            return False
        self._trigger_draw_event_card(self.player_country)
        return True

    def handle_pp_click(self, app, pos) -> bool:
        self = app
        if self.pp_btn_rect and self.pp_btn_rect.collidepoint(pos):
            if self._pp_can_use(self.player_country):
                self.pp_spend_mode = True
                if self.info_panel:
                    self.info_panel.show_message(
                        "PP行动：左键点击受伤己方单位回血，右键点击己方地块召唤部队",
                        duration=3.0,
                    )
            else:
                self.info_panel.show_message("政治点数不足（需≥1才可使用）")
            return True

        if not self.pp_spend_mode:
            return False

        if self.pp_spend_end_btn_rect and self.pp_spend_end_btn_rect.collidepoint(pos):
            self.pp_spend_mode = False
            self.pp_summon_target_prov = None
            self.pp_summon_btns = []
            self._finish_country_action("使用政治点数")
            return True

        if self.pp_summon_target_prov is not None:
            for _sbtn in self.pp_summon_btns:
                if not _sbtn["rect"].collidepoint(pos):
                    continue

                if _sbtn["unit_type"] is None:
                    self.pp_summon_target_prov = None
                    self.pp_summon_btns = []
                    if self.info_panel:
                        self.info_panel.show_message("已取消召唤")
                    return True

                if _sbtn["enabled"]:
                    _tprov = self.pp_summon_target_prov
                    _utype = _sbtn["unit_type"]
                    _uhp = _sbtn["hp"]
                    _ucost = _sbtn["cost"]
                    if self.evt_flag_hu_recruit and self.player_country == "WEI":
                        if self.info_panel:
                            self.info_panel.show_message("胡人袭扰：本回合魏国不能召唤新部队")
                    elif len(_tprov.units) >= MAX_UNIT_STACK:
                        if self.info_panel:
                            self.info_panel.show_message("该地块部队已满（最多3支）")
                    elif self._spend_pp(self.player_country, _ucost):
                        try:
                            _udef = self.unit_repository.get_definition(_utype)
                            _nu = UnitState(_utype)
                            _nu.hp = _uhp
                            _nu.mp = _udef.move
                            _tprov.units.append(_nu)
                            self.map_manager.invalidate_cache()
                            self.move_dst_provs[_tprov.province_id] = self.player_country
                            self.move_dst_slots[_tprov.province_id] = [len(_tprov.units) - 1]
                            _remain = self._get_total_pp(self.player_country)
                            _uname = {
                                "infantry": "步兵",
                                "cavalry": "骑兵",
                                "archer": "弓兵",
                            }.get(_utype, _utype)
                            if self.info_panel:
                                self.info_panel.show_message(
                                    f"在{_tprov.name}召唤了{_uname}（{_uhp}血），剩余PP：{_remain}"
                                )
                        except Exception:
                            logger.exception("PP召唤失败")
                            return True
                    else:
                        if self.info_panel:
                            self.info_panel.show_message("政治点数不足")
                else:
                    if self.info_panel:
                        self.info_panel.show_message("政治点数不足以执行此操作")

                self.pp_summon_target_prov = None
                self.pp_summon_btns = []
                return True

            return True

        _unit_hit = self._get_unit_slot_at(pos)
        if _unit_hit:
            _hpid, _hslot = _unit_hit
            _hprov = self.map_manager.get_by_id(_hpid)
            if _hprov and _hprov.country == self.player_country and _hslot < len(_hprov.units):
                _hu = _hprov.units[_hslot]
                if _hu.hp >= 2:
                    if self.info_panel:
                        self.info_panel.show_message("该单位已满血，无需回复")
                else:
                    _hcost = self._get_pp_heal_cost(_hu)
                    if self._get_total_pp(self.player_country) < _hcost:
                        _utp = "特殊" if self._is_special_unit(_hu) else "普通"
                        if self.info_panel:
                            self.info_panel.show_message(f"政治点数不足（{_utp}单位回血需{_hcost}PP）")
                    elif self._spend_pp(self.player_country, _hcost):
                        _hu.hp += 1
                        _remain2 = self._get_total_pp(self.player_country)
                        _utp2 = "特殊" if self._is_special_unit(_hu) else "普通"
                        if self.info_panel:
                            self.info_panel.show_message(
                                f"{_utp2}单位回复1血（消耗{_hcost}PP），剩余PP：{_remain2}"
                            )
            else:
                if self.info_panel:
                    self.info_panel.show_message("请点击己方受伤单位")
        return True

    def handle_morale_click(self, app, pos) -> bool:
        self = app
        if self.morale_lv2_btn_rect and self.morale_lv2_btn_rect.collidepoint(pos):
            self.morale_free_move_mode = True
            if self.info_panel:
                self.info_panel.show_message(
                    "令行禁止：请选中1个单位，再右键点击相邻格", duration=3.0
                )
            return True
        if self.morale_lv3_btn_rect and self.morale_lv3_btn_rect.collidepoint(pos):
            self.morale_bonus_mp_mode = True
            if self.info_panel:
                self.info_panel.show_message(
                    "老乡指路：请点击一个己方单位获得+1行动力", duration=3.0
                )
            return True
        if self.morale_lv4_btn_rect and self.morale_lv4_btn_rect.collidepoint(pos):
            if self._has_confused_units_for_country(self.player_country):
                self.morale_cure_mode = True
                if self.info_panel:
                    self.info_panel.show_message("军容严整：请点击一个混乱的己方单位", duration=3.0)
            else:
                self.morale_lv4_pending.pop(self.player_country, None)
                if self.info_panel:
                    self.info_panel.show_message("军容严整：当前无混乱单位")
            return True

        if self.morale_bonus_mp_mode:
            unit_hit = self._get_unit_slot_at(pos)
            if unit_hit:
                _prov_id, _slot = unit_hit
                _prov = self.map_manager.get_by_id(_prov_id)
                if _prov and _prov.country == self.player_country and _slot < len(_prov.units):
                    _prov.units[_slot].mp += 1
                    self.morale_bonus_mp_mode = False
                    self.morale_lv3_used[self.player_country] = self.major_round
                    if self.info_panel:
                        self.info_panel.show_message("老乡指路：该单位行动力+1")
                else:
                    if self.info_panel:
                        self.info_panel.show_message("请点击己方单位")
            else:
                if self.info_panel:
                    self.info_panel.show_message("请点击己方单位")
            return True

        if self.morale_cure_mode:
            unit_hit = self._get_unit_slot_at(pos)
            if unit_hit:
                _prov_id, _slot = unit_hit
                _prov = self.map_manager.get_by_id(_prov_id)
                if _prov and _prov.country == self.player_country and _slot < len(_prov.units):
                    _u = _prov.units[_slot]
                    if _u.is_confused:
                        _u.is_confused = False
                        self.morale_cure_mode = False
                        self.morale_lv4_pending.pop(self.player_country, None)
                        if self.info_panel:
                            self.info_panel.show_message("军容严整：混乱已解除（大回合结束奖励）")
                    else:
                        if self.info_panel:
                            self.info_panel.show_message("该单位未处于混乱状态，请重新选择")
                else:
                    if self.info_panel:
                        self.info_panel.show_message("请点击己方单位")
            else:
                if self.info_panel:
                    self.info_panel.show_message("请点击混乱状态的己方单位")
            return True

        return False

    def handle_recover_click(self, app, pos) -> bool:
        self = app
        if not self.recover_btn_rect or not self.recover_btn_rect.collidepoint(pos):
            return False

        confused_list = []
        for pid, slot in self.selected_units:
            prov = self.map_manager.get_by_id(pid)
            if prov and slot < len(prov.units):
                u = prov.units[slot]
                if u.is_confused:
                    confused_list.append(u)

        if len(confused_list) == 1:
            confused_list[0].is_confused = False
            self.info_panel.show_message("混乱状态已解除")
            self._update_selection_info()
            self._finish_country_action("解除混乱")
        return True

    def handle_no_attack_click(self, app, pos) -> bool:
        self = app
        if (
            not self.pending_post_move_attack
            or not self.no_attack_btn_rect
            or not self.no_attack_btn_rect.collidepoint(pos)
        ):
            return False

        if self.morale_free_move_mode:
            if self.player_country:
                self.morale_lv2_used[self.player_country] = self.major_round
            self.morale_free_move_mode = False
            self.pending_post_move_attack = False
            self.pending_attacker = None
            self.clear_selection()
            if self.info_panel:
                self.info_panel.show_message("令行禁止：移动完成，继续行动", duration=2.0)
            return True

        if self.info_panel:
            self.info_panel.show_message("已选择不攻击，进入下一步", duration=1.0)
        self._finish_country_action("移动")
        return True

    def handle_major_round_choice_click(self, app, pos) -> bool:
        self = app
        if not self.major_round_choice_pending:
            return False

        for country, btns in self.country_stat_choice_btns.items():
            support_rect = btns.get("support")
            politics_rect = btns.get("politics")
            if support_rect and support_rect.collidepoint(pos):
                self._apply_major_round_choice(country, "support")
                return True
            if politics_rect and politics_rect.collidepoint(pos):
                self._apply_major_round_choice(country, "politics")
                return True

        if self.info_panel:
            self.info_panel.show_message("请在三国面板中完成加点选择")
        return True

    def handle_evt_draw_phase_click(self, app, pos) -> bool:
        self = app
        if not self.evt_draw_phase or self.selecting_evt_target:
            return False

        if self.evt_skip_draw_btn_rect and self.evt_skip_draw_btn_rect.collidepoint(pos):
            self._exit_evt_draw_phase()
            return True

        if self.draw_event_btn_rect and self.draw_event_btn_rect.collidepoint(pos):
            self._trigger_draw_event_card(self.player_country)
            if not self.event_card_overlay:
                self._check_evt_draw_phase_pp()
            return True

        if self.info_panel:
            self.info_panel.show_message("请先完成事件卡阶段（抽取或跳过）")
        return True

    def handle_help_overlay_wheel(self, app, event: pg.event.Event) -> bool:
        self = app
        if event.type != pg.MOUSEWHEEL or not self.help_overlay_visible:
            return False

        total = len(self._help_rule_surfaces)
        if total > 0:
            if event.y > 0 or event.x < 0:
                self.help_current_page = max(0, self.help_current_page - 1)
            elif event.y < 0 or event.x > 0:
                self.help_current_page = min(total - 1, self.help_current_page + 1)
        return True

    def handle_help_overlay_click(self, app, event: pg.event.Event) -> bool:
        self = app
        if (
            event.type != pg.MOUSEBUTTONDOWN
            or event.button != 1
            or not self.help_overlay_visible
        ):
            return False

        total = len(self._help_rule_surfaces)
        if self._help_prev_btn and self._help_prev_btn.collidepoint(event.pos) and total > 0:
            self.help_current_page = max(0, self.help_current_page - 1)
            return True
        if self._help_next_btn and self._help_next_btn.collidepoint(event.pos) and total > 0:
            self.help_current_page = min(total - 1, self.help_current_page + 1)
            return True

        content_rect = self._help_overlay_content_rect
        if content_rect is None or not content_rect.collidepoint(event.pos):
            self.help_overlay_visible = False

        return True

    def handle_control_button_click(self, app, pos) -> bool:
        self = app
        for btn in getattr(self, "control_btns", []):
            if not btn["rect"].collidepoint(pos):
                continue

            action = btn["action"]
            if action == "EXIT":
                self.stop()
            elif action == "RESTART":
                self._restart_game()
            elif action == "SCORE":
                if self.state == type(self.state).PLAYING:
                    self._show_score_screen("wei_turn")
            elif action == "VOLUME":
                self.volume_slider_visible = not self.volume_slider_visible
            elif action == "HELP":
                self.help_overlay_visible = not self.help_overlay_visible
                self.help_current_page = 0
                if self.help_overlay_visible:
                    self._start_help_rule_load()
            return True
        return False
