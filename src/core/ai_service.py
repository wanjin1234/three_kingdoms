"""
AI 服务：抽离 `GameApp` 中的 AI 决策与行动流程。

该模块保留现有规则与行为，`GameApp` 仅做委托调用。
"""

from __future__ import annotations

import logging
from math import dist, sqrt
from typing import Any

import pygame as pg

from src.core.app_contexts import (
    AIAutoSelectEventTargetContext,
    AIBorderProvincesContext,
    AIRunTurnContext,
)
from src.game_objects.unit import UnitState

logger = logging.getLogger(__name__)

SQRT3 = sqrt(3)
MAX_UNIT_STACK = 3


class AIService:
    """AI 决策与执行服务。"""

    def _calc_border_provinces(self, map_manager: Any, hex_side: int | float, country: str):
        """返回己方边境省列表，按到最近相邻敌省中心距离升序。"""
        border = []
        for prov in map_manager.provinces:
            if prov.country != country:
                continue
            p_center = prov.center_cache or prov.compute_center(hex_side)
            min_d = float("inf")
            for nbr_id in map_manager._adjacency.get(prov.province_id, []):
                nbr = map_manager.get_by_id(nbr_id)
                if nbr is None or nbr.country == country or not nbr.country:
                    continue
                e_center = nbr.center_cache or nbr.compute_center(hex_side)
                d = dist(p_center, e_center)
                if d < min_d:
                    min_d = d
            if min_d < float("inf"):
                border.append((min_d, prov))
        border.sort(key=lambda x: x[0])
        return [p for _, p in border]

    def get_border_provinces_with_context(
        self,
        context: AIBorderProvincesContext,
        country: str,
    ):
        """基于契约计算边境省列表。"""
        return self._calc_border_provinces(
            context.map_manager,
            context.hex_side,
            country,
        )

    def get_main_threat_country(self, app: Any, country: str) -> str | None:
        """返回在AI边境线对面（邻接图直接相邻可通行网格）兵力最多的敌国。"""
        own_prov_ids = {
            p.province_id for p in app.map_manager.provinces if p.country == country
        }
        threat: dict[str, int] = {}
        counted: set[int] = set()
        for prov_id in own_prov_ids:
            for nbr_id in app.map_manager._adjacency.get(prov_id, []):
                if nbr_id in counted:
                    continue
                nbr = app.map_manager.get_by_id(nbr_id)
                if nbr is None or not nbr.country or nbr.country == country:
                    continue
                counted.add(nbr_id)
                threat[nbr.country] = threat.get(nbr.country, 0) + len(nbr.units)

        if not threat:
            return None
        return max(threat.items(), key=lambda kv: kv[1])[0]

    def use_summon_card(self, app: Any, country: str, card_id: str, target_prov) -> bool:
        cm = app.card_managers.get(country)
        if cm is None:
            return False

        if card_id == "card_qilin_qishu":
            entry = ("MOUNTAIN_archer", "SHU", "无当飞军")
        elif card_id == "card_guanmu_xiangkan":
            entry = ("CAV_archer", "WU", "解烦兵")
        else:
            return False

        unit_type, required_country, unit_name = entry
        if target_prov.country != required_country:
            return False

        try:
            unit_def = app.unit_repository.get_definition(unit_type)
            new_unit = UnitState(unit_type)
            new_unit.mp = unit_def.move
            target_prov.units.append(new_unit)
            app.map_manager.invalidate_cache()
            app.move_dst_provs[target_prov.province_id] = country
            app.move_dst_slots[target_prov.province_id] = [len(target_prov.units) - 1]
        except Exception:
            logger.exception("AI 召唤 %s 失败", unit_name)
            return False

        cm.use_card(card_id)
        app.info_panel.show_message(f"AI召唤了{unit_name}（地图高亮格子）", duration=2.0)
        # 在地图上临时高亮目标省份
        if hasattr(app, "_highlight_province_temp"):
            app._highlight_province_temp(target_prov.province_id)
        logger.info(
            "AI [%s] 使用 %s，在 %s 召唤了 %s",
            country,
            card_id,
            target_prov.name,
            unit_name,
        )
        return True

    def execute_combat(self, app: Any, province, slot_idx: int, target) -> bool:
        """AI 直接执行战斗（跳过 UI 交互）。返回是否成功发起。"""
        app.selected_units = [(province.province_id, slot_idx)]
        app._handle_combat(target)
        if app.combat_callback and app.show_combat_ui:
            app.defender_jiangdong_decided = True
            app.defender_use_jiangdong = False
            app.defender_hold_decided = True
            app.defender_use_hold_position = False
            cb = app.combat_callback
            app.combat_callback = None
            app.show_combat_ui = False
            cb()
            return True
        return False

    def pick_attack_target(self, app: Any, province, unit_state):
        """AI 选择攻击目标：优先进攻主要威胁国，其次选血量最少的相邻敌省。"""
        definition = app.unit_repository.get_definition(unit_state.unit_type)
        unit_stride = SQRT3 * app.hex_side
        allowed_range_px = definition.range * unit_stride * 1.1
        p_center = (
            province.center_cache if province.center_cache else province.compute_center(app.hex_side)
        )
        atk_c = province.country
        main_threat = self.get_main_threat_country(app, atk_c)

        best = None
        best_score = (2, float("inf"))
        for target in app.map_manager.provinces:
            if target.country == province.country:
                continue
            if not target.units and not app._is_fort_or_city(target):
                continue
            def_c = target.country
            if app.evt_flag_liukang:
                if (atk_c == "SHU" and def_c == "WU") or (atk_c == "WU" and def_c == "SHU"):
                    continue
            if app.evt_flag_wuwei and atk_c == "WU" and def_c == "WEI":
                continue
            t_center = target.center_cache if target.center_cache else target.compute_center(app.hex_side)
            if dist(p_center, t_center) <= allowed_range_px:
                _t_eff = app.card_effect_manager.get_effect(str(target.province_id))
                if _t_eff and _t_eff.protected:
                    continue
                priority = 0 if (main_threat and def_c == main_threat) else 1
                score = (priority, len(target.units))
                if score < best_score:
                    best_score = score
                    best = target
        return best

    def border_defense_score(self, app: Any, prov) -> float:
        """计算边境省的防御驻守优先级评分（分值越高越值得驻守）。"""
        terrain = (prov.terrain or "").lower()
        if terrain == "city":
            score = 4.0
        elif terrain in ("hill", "mountain", "hills", "mountains"):
            score = 3.0
        else:
            score = 1.0

        for nbr_id in app.map_manager._adjacency.get(prov.province_id, []):
            if app.map_manager._river_crossing_edges.get((prov.province_id, nbr_id), False) or app.map_manager._river_crossing_edges.get((nbr_id, prov.province_id), False):
                score += 1.0
                break

        score -= len(prov.units) * 2.0
        if len(prov.units) == 0:
            score += 3.0
        return score

    def pick_move_target(self, app: Any, province, unit_state, border_provs=None):
        """AI 选择移动目标。"""
        ap = unit_state.mp
        if ap <= 0:
            return None

        p_center = province.center_cache or province.compute_center(app.hex_side)

        if border_provs:
            best_bp = None
            best_score = float("-inf")
            best_path_cost = float("inf")
            for bp in border_provs:
                if bp.province_id == province.province_id:
                    continue
                if len(bp.units) >= MAX_UNIT_STACK:
                    continue
                pc = app.map_manager.find_path_cost(province.province_id, bp.province_id)
                if pc > ap or pc > 100:
                    continue
                sc = self.border_defense_score(app, bp)
                if sc > best_score or (sc == best_score and pc < best_path_cost):
                    best_score = sc
                    best_path_cost = pc
                    best_bp = bp
            if best_bp is not None:
                return best_bp

            best_d_any = float("inf")
            anchor_center = None
            for bp in border_provs:
                if bp.province_id == province.province_id:
                    continue
                bc = bp.center_cache or bp.compute_center(app.hex_side)
                d = dist(p_center, bc)
                if d < best_d_any:
                    best_d_any = d
                    anchor_center = bc
            if anchor_center is not None:
                best_dest = None
                best_dist_to_anchor = float("inf")
                for candidate in app.map_manager.provinces:
                    if candidate.province_id == province.province_id:
                        continue
                    if candidate.country not in (province.country, None, ""):
                        continue
                    pc2 = app.map_manager.find_path_cost(province.province_id, candidate.province_id)
                    if pc2 > ap or pc2 > 100:
                        continue
                    c_center = candidate.center_cache or candidate.compute_center(app.hex_side)
                    d2 = dist(c_center, anchor_center)
                    if d2 < best_dist_to_anchor:
                        best_dist_to_anchor = d2
                        best_dest = candidate
                return best_dest
            return None

        main_threat = self.get_main_threat_country(app, province.country)
        best_d = float("inf")
        best_d_fallback = float("inf")
        anchor_center_threat = None
        anchor_center_fallback = None
        for target in app.map_manager.provinces:
            if target.country == province.country or not target.country:
                continue
            if app.map_manager.find_path_cost(province.province_id, target.province_id) >= 9999:
                continue
            tc = target.center_cache or target.compute_center(app.hex_side)
            d = dist(p_center, tc)
            if main_threat and target.country == main_threat:
                if d < best_d:
                    best_d = d
                    anchor_center_threat = tc
            else:
                if d < best_d_fallback:
                    best_d_fallback = d
                    anchor_center_fallback = tc
        anchor_center = anchor_center_threat or anchor_center_fallback

        if anchor_center is None:
            return None

        unit_stride = max(1.0, SQRT3 * app.hex_side)
        best_dest = None
        best_combined = float("-inf")
        for candidate in app.map_manager.provinces:
            if candidate.province_id == province.province_id:
                continue
            if candidate.country not in (province.country, None, ""):
                continue
            path_cost = app.map_manager.find_path_cost(province.province_id, candidate.province_id)
            if path_cost > ap or path_cost > 100:
                continue
            c_center = candidate.center_cache or candidate.compute_center(app.hex_side)
            d_to_anchor = dist(c_center, anchor_center)
            defense_sc = self.border_defense_score(app, candidate)
            combined = defense_sc - d_to_anchor / unit_stride
            if combined > best_combined:
                best_combined = combined
                best_dest = candidate

        return best_dest

    def auto_select_evt_target_with_context(
        self,
        context: AIAutoSelectEventTargetContext,
        selector_country: str,
    ) -> None:
        """AI 立即为 needs_target 事件卡自动选择目标（契约化）。"""
        pending_evt_card_id = context.get_pending_evt_card_id()
        if not pending_evt_card_id:
            return
        card_def = context.get_event_card_definition(pending_evt_card_id)
        if not card_def:
            context.clear_pending_evt_target_state()
            return

        if card_def.target_type == "unit":
            border_provs = context.get_border_provinces(selector_country)
            border_ids = {p.province_id for p in border_provs}
            chosen_prov = None
            for prov in context.get_provinces():
                if prov.country == selector_country and prov.units:
                    if prov.province_id in border_ids:
                        chosen_prov = prov
                        break
            if chosen_prov is None:
                for prov in context.get_provinces():
                    if prov.country == selector_country and prov.units:
                        chosen_prov = prov
                        break
            if chosen_prov:
                context.apply_evt_target_unit(chosen_prov.province_id, 0)
            else:
                context.clear_pending_evt_target_state()
                context.check_evt_draw_phase_pp()

        elif card_def.target_type == "province":
            chosen_prov = max(
                (
                    p
                    for p in context.get_provinces()
                    if p.country == selector_country and p.units
                ),
                key=lambda p: len(p.units),
                default=None,
            )
            if chosen_prov:
                context.apply_evt_target_province(chosen_prov.province_id)
            else:
                context.clear_pending_evt_target_state()
                context.check_evt_draw_phase_pp()

    def run_turn_with_context(self, context: AIRunTurnContext) -> None:
        """AI 行动：自动完成大回合加点选择 + 移动/攻击，然后结束本国回合。"""
        app = context.app
        border_context = AIBorderProvincesContext(
            map_manager=app.map_manager,
            hex_side=app.hex_side,
        )

        def _get_border_provinces(country: str):
            return self.get_border_provinces_with_context(border_context, country)

        if app.turn_game_finished:
            return
        country = app.player_country
        if country is None or country == app.human_country:
            return

        if app.event_card_overlay:
            _tmp_drawer = app.event_card_overlay.get("drawer", "")
            if app.human_country is None and _tmp_drawer != app.human_country:
                app._confirm_event_card()
            if app.event_card_overlay or app.selecting_evt_target:
                app._ai_turn_timer = pg.time.get_ticks() + 300
                return

        _ai_support = app._get_people_support_level(country)

        if _ai_support >= 2 and app.morale_lv2_used.get(country, 0) != app.major_round:
            border_provs_lv2 = _get_border_provinces(country)
            for _bp in border_provs_lv2:
                if not _bp.units:
                    continue
                _dest = self.pick_move_target(app, _bp, _bp.units[0], border_provs_lv2)
                if _dest and _dest.country == country and app.map_manager.find_path_cost(_bp.province_id, _dest.province_id) == 1:
                    app.morale_free_move_mode = True
                    app.selected_units = [(_bp.province_id, 0)]
                    app._handle_movement(_dest)
                    break
            app.morale_lv2_used[country] = app.major_round
            app.morale_free_move_mode = False

        if _ai_support >= 3 and app.morale_lv3_used.get(country, 0) != app.major_round:
            _border_p3 = _get_border_provinces(country)
            for _bp3 in _border_p3:
                if _bp3.units:
                    _bp3.units[0].mp += 1
                    app.morale_lv3_used[country] = app.major_round
                    break
            else:
                app.morale_lv3_used[country] = app.major_round

        if app.selecting_evt_target and app.pending_evt_card_id:
            if app.human_country is not None and app.pending_evt_drawer == app.human_country:
                return
            app._ai_auto_select_evt_target(app.pending_evt_drawer or country)
            return

        if app.major_round_choice_pending:
            for c in list(app.turn_order):
                if c == app.human_country:
                    continue
                if not app.major_round_choice_done.get(c, False):
                    _ai_pp_now = app._get_total_pp(c)
                    _choice = "politics" if _ai_pp_now == 0 else "support"
                    app._apply_major_round_choice(c, _choice)
            if app.major_round_choice_pending:
                app._ai_turn_timer = pg.time.get_ticks() + 300
                return

        if not app.evt_ai_drawn_this_turn.get(country) and app._can_draw_event_card(country):
            app.evt_ai_drawn_this_turn[country] = True
            app._trigger_draw_event_card(country)
            if app.selecting_evt_target and app.pending_evt_card_id:
                if app.human_country is None or app.pending_evt_drawer != app.human_country:
                    app._ai_auto_select_evt_target(app.pending_evt_drawer or country)
            if app.event_card_overlay or app.selecting_evt_target:
                app._ai_turn_timer = pg.time.get_ticks() + 200
                return

        if app._pp_can_use(country):
            _healed_unit_ids: set = set()
            for _prov in app.map_manager.provinces:
                if _prov.country != country:
                    continue
                for _u in _prov.units:
                    if id(_u) in _healed_unit_ids:
                        continue
                    if _u.hp < 2:
                        _cost = app._get_pp_heal_cost(_u)
                        if app._get_total_pp(country) >= _cost:
                            app._spend_pp(country, _cost)
                            _u.hp += 1
                            _healed_unit_ids.add(id(_u))

        border_provs = _get_border_provinces(country)
        border_ids = {p.province_id for p in border_provs}

        inland_by_prov: dict = {}
        border_by_prov: dict = {}

        for province in app.map_manager.provinces:
            if province.country != country:
                continue
            for slot_idx, unit_state in enumerate(province.units):
                if unit_state.mp <= 0:
                    continue
                key = province.province_id
                if key in border_ids:
                    if key not in border_by_prov:
                        border_by_prov[key] = (province, [])
                    border_by_prov[key][1].append((slot_idx, unit_state))
                else:
                    if key not in inland_by_prov:
                        inland_by_prov[key] = (province, [])
                    inland_by_prov[key][1].append((slot_idx, unit_state))

        border_units = [
            (prov, slot_idx, unit_state)
            for prov, slots in border_by_prov.values()
            for slot_idx, unit_state in slots
        ]

        action_taken = False
        _main_threat = self.get_main_threat_country(app, country)

        def _border_threat_key(item):
            prov, _, _ = item
            for nbr_id in app.map_manager._adjacency.get(prov.province_id, []):
                nbr = app.map_manager.get_by_id(nbr_id)
                if nbr is not None and nbr.country == _main_threat:
                    return 0
            return 1

        border_units.sort(key=_border_threat_key)

        def _calc_path_cost(src_prov, tgt_prov, lead_unit):
            src_eff = app.card_effect_manager.get_effect(str(src_prov.province_id))
            ign = bool(getattr(lead_unit, "temp_terrain_immunity", False))
            if src_eff and src_eff.terrain_immunity:
                ign = True
            if getattr(lead_unit, "unit_type", "") == "WUDANG_archer":
                ign = True
            if ign:
                return app._find_path_cost_ignore_mountain(src_prov.province_id, tgt_prov.province_id)
            return app.map_manager.find_path_cost(src_prov.province_id, tgt_prov.province_id)

        if inland_by_prov:
            def _inland_prov_priority(item):
                province, _ = item
                p_c = province.center_cache or province.compute_center(app.hex_side)
                if not border_provs:
                    return float("inf")
                return min(dist(p_c, bp.center_cache or bp.compute_center(app.hex_side)) for bp in border_provs)

            sorted_inland = sorted(inland_by_prov.values(), key=_inland_prov_priority)

            for province, slots in sorted_inland:
                lead_unit = slots[0][1]
                dest = self.pick_move_target(app, province, lead_unit, border_provs)
                if dest is None:
                    continue
                pc = _calc_path_cost(province, dest, lead_unit)
                if pc > 100:
                    continue
                valid_slots = [(idx, u) for idx, u in slots if u.mp >= pc]
                if not valid_slots:
                    continue
                app.selected_units = [(province.province_id, idx) for idx, _ in valid_slots]
                app._handle_movement(dest)
                if app.player_country != country:
                    return

        border_provs = _get_border_provinces(country)
        border_ids = {p.province_id for p in border_provs}
        empty_border = sorted([p for p in border_provs if len(p.units) == 0], key=lambda p: self.border_defense_score(app, p), reverse=True)
        for empty_prov in empty_border:
            filled = False
            surplus_border = sorted([p for p in border_provs if p.province_id != empty_prov.province_id and len(p.units) >= 2], key=lambda p: len(p.units), reverse=True)
            for src_prov in surplus_border:
                pc = _calc_path_cost(src_prov, empty_prov, src_prov.units[0])
                if pc > 100:
                    continue
                movable = [(idx, u) for idx, u in enumerate(src_prov.units) if u.mp >= pc]
                if not movable:
                    continue
                app.selected_units = [(src_prov.province_id, movable[0][0])]
                app._handle_movement(empty_prov)
                if app.player_country != country:
                    return
                filled = True
                break
            if not filled:
                for src_prov_id, (src_prov2, slots2) in list(inland_by_prov.items()):
                    pc2 = _calc_path_cost(src_prov2, empty_prov, slots2[0][1])
                    if pc2 > 100:
                        continue
                    mv2 = [(idx, u) for idx, u in slots2 if u.mp >= pc2]
                    if not mv2:
                        continue
                    app.selected_units = [(src_prov2.province_id, mv2[0][0])]
                    app._handle_movement(empty_prov)
                    if app.player_country != country:
                        return
                    break
            border_provs = _get_border_provinces(country)
            border_ids = {p.province_id for p in border_provs}

        border_provs = _get_border_provinces(country)
        border_ids = {p.province_id for p in border_provs}
        border_by_prov = {}
        for _prov in app.map_manager.provinces:
            if _prov.country != country:
                continue
            for _slot_idx, _unit_state in enumerate(_prov.units):
                if _unit_state.mp <= 0:
                    continue
                if _prov.province_id in border_ids:
                    if _prov.province_id not in border_by_prov:
                        border_by_prov[_prov.province_id] = (_prov, [])
                    border_by_prov[_prov.province_id][1].append((_slot_idx, _unit_state))
        border_units = [
            (prov, slot_idx, unit_state)
            for prov, slots in border_by_prov.values()
            for slot_idx, unit_state in slots
        ]
        border_units.sort(key=_border_threat_key)

        _cm = app.card_managers.get(country)
        if _cm:
            for _card in list(_cm.get_available_cards()):
                if _card.category == "offensive" and _card.id in (
                    "card_zhenjing_huaxia_shu",
                    "card_huoshao_lianying",
                ):
                    if app.card_effect_manager.activate_offensive_card(_card.id):
                        _cm.use_card(_card.id)
                        action_taken = True
                elif _card.category == "summon" and _card.id in (
                    "card_qilin_qishu",
                    "card_guanmu_xiangkan",
                ):
                    _summon_tgt = None
                    for _rp in app.map_manager.provinces:
                        if (
                            _rp.country == country
                            and _rp.units
                            and len(_rp.units) < MAX_UNIT_STACK
                            and _rp.province_id in border_ids
                        ):
                            _summon_tgt = _rp
                            break
                    if _summon_tgt is None:
                        for _rp in app.map_manager.provinces:
                            if _rp.country == country and len(_rp.units) < MAX_UNIT_STACK:
                                _summon_tgt = _rp
                                break
                    if _summon_tgt is not None:
                        if self.use_summon_card(app, country, _card.id, _summon_tgt):
                            action_taken = True

        _danshi_morale = app._get_people_support_level(country)
        for province, slot_idx, unit_state in border_units:
            if app._has_attackable_target_for_unit(province, unit_state):
                target = self.pick_attack_target(app, province, unit_state)
                if target is not None:
                    if _danshi_morale >= 5 and not target.units and app._is_fort_or_city(target):
                        _danshi_pc = app.map_manager.find_path_cost(province.province_id, target.province_id)
                        if 0 < _danshi_pc <= unit_state.mp:
                            app.selected_units = [(province.province_id, slot_idx)]
                            app._handle_movement(target)
                            if app.player_country != country:
                                return
                            continue
                    if self.execute_combat(app, province, slot_idx, target):
                        return

        for prov_id, (province, slots) in border_by_prov.items():
            lead_unit = slots[0][1]
            dest = self.pick_move_target(app, province, lead_unit, None)
            if dest is None:
                continue
            pc = _calc_path_cost(province, dest, lead_unit)
            if pc > 100:
                continue
            valid_slots = [(idx, u) for idx, u in slots if u.mp >= pc]
            if not valid_slots:
                continue
            app.selected_units = [(province.province_id, idx) for idx, _ in valid_slots]
            app._handle_movement(dest)
            if app.player_country != country:
                return

        if _cm:
            _border_ids_set = {p.province_id for p in _get_border_provinces(country)}
            for _card in list(_cm.get_available_cards()):
                if _card.category == "buff":
                    _tgt = None
                    for _rp in app.map_manager.provinces:
                        if (
                            _rp.country == country
                            and _rp.units
                            and len(_rp.units) < MAX_UNIT_STACK
                            and _rp.province_id in _border_ids_set
                        ):
                            _tgt = _rp
                            break
                    if _tgt is None:
                        for _rp in app.map_manager.provinces:
                            if _rp.country == country and _rp.units:
                                _tgt = _rp
                                break
                    if _tgt is not None:
                        if app._apply_card_to_province(_card.id, _tgt.province_id):
                            action_taken = True

        _ai_pp_used = False
        if app._pp_can_use(country):
            _can_recruit = not (getattr(app, "evt_flag_hu_recruit", False) and country == "WEI")
            if _can_recruit and app._get_total_pp(country) >= 1:
                _recruit_target = None
                _border_pset = {p.province_id for p in _get_border_provinces(country)}
                for _rp in app.map_manager.provinces:
                    if _rp.country == country and len(_rp.units) < app.MAX_UNIT_STACK:
                        if _rp.province_id in _border_pset:
                            _recruit_target = _rp
                            break
                if _recruit_target is None:
                    for _rp in app.map_manager.provinces:
                        if _rp.country == country and len(_rp.units) < app.MAX_UNIT_STACK:
                            _recruit_target = _rp
                            break
                if _recruit_target is not None:
                    _pp_left = app._get_total_pp(country)
                    if _pp_left >= 2:
                        new_u = UnitState("infantry")
                        new_u.hp = 2
                        app._spend_pp(country, 2)
                    else:
                        new_u = UnitState("infantry")
                        new_u.hp = 1
                        app._spend_pp(country, 1)
                    _recruit_target.units.append(new_u)
                    app.map_manager.invalidate_cache()
                    app.move_dst_provs[_recruit_target.province_id] = country
                    app.move_dst_slots[_recruit_target.province_id] = [len(_recruit_target.units) - 1]
                    _ai_pp_used = True
                    # 显示招募通知
                    _country_label = app.country_labels.get(country, country)
                    _unit_quality = "精锐" if new_u.hp >= 2 else ""
                    if app.info_panel:
                        app.info_panel.show_properties(
                            f"{_country_label}：在{_recruit_target.name}招募了{_unit_quality}步兵"
                        )
            if _ai_pp_used:
                action_taken = True

        if app._has_confused_units_for_country(country):
            for _prov in app.map_manager.provinces:
                if _prov.country != country:
                    continue
                for _u in _prov.units:
                    if _u.is_confused:
                        _u.is_confused = False
                        app._finish_country_action(f"AI({country})解除混乱", keep_info_message=True)
                        return

        app._finish_country_action(f"AI({country})行动", keep_info_message=action_taken)

