"""
战斗流程服务：抽离 `GameApp` 中的战斗主流程编排。
"""

from __future__ import annotations

import logging
import random
import re
from math import dist, sqrt
from typing import Any

from src.core.combat import get_ratio_column, resolve_combat

logger = logging.getLogger(__name__)
SQRT3 = sqrt(3)


class CombatFlowService:
    """战斗流程编排服务。"""

    def handle_combat(self, app: Any, target: object) -> None:
        """处理战斗逻辑。"""
        if not app.combat_utils_service.check_combat_preconditions(app, target):
            return

        unit_stride = SQRT3 * app.hex_side
        total_attack = 0.0
        participating_attackers = []
        defender_types = [u.unit_type for u in target.units]

        for pid, idx in app.selected_units:
            province = app.map_manager.get_by_id(pid)
            if not province:
                continue

            unit_state = province.units[idx]
            definition = app.unit_repository.get_definition(unit_state.unit_type)

            p_center = (
                province.center_cache
                if province.center_cache
                else province.compute_center(app.hex_side)
            )
            t_center = (
                target.center_cache
                if target.center_cache
                else target.compute_center(app.hex_side)
            )

            current_distance = dist(p_center, t_center)
            allowed_range_px = definition.range * unit_stride * 1.1

            if current_distance > allowed_range_px:
                app.clear_selection(clear_ui=False)
                app.info_panel.show_message(f"距离不足:{definition.range}", duration=2.0)
                return

            if unit_state.mp < 1:
                app.clear_selection(clear_ui=False)
                app.info_panel.show_message("行动力不足")
                return

            atk, _ = app._calculate_unit_powers(unit_state, province.province_id)
            atk += app._get_attack_terrain_penalty(province, target, unit_state)
            atk = max(0, atk)

            bonus = app.combat_utils_service.get_counter_bonus(
                unit_state.unit_type, defender_types
            )

            total_attack += atk + bonus
            participating_attackers.append((province, unit_state))

        if total_attack <= 0:
            app.info_panel.show_message("攻击力太低")
            return

        total_defense = app.combat_utils_service.calculate_total_defense(app, target)
        attacker_provinces = {p.province_id for p, _ in participating_attackers}
        is_flanked = app.combat_utils_service.calculate_is_flanked(
            app, target, attacker_provinces
        )

        col_index = get_ratio_column(total_attack, total_defense, is_flanked)
        col_index = app.combat_utils_service.apply_base_column_adjustment(
            app, target, col_index
        )

        if app.card_effect_manager.is_offensive_card_active("card_huoshao_lianying"):
            if len(target.units) > 1:
                col_index = min(5, col_index + 1)

        ratio_val = total_attack / total_defense

        atk_lines = []
        for prov, u_state in participating_attackers:
            atk_lines.append(
                app._format_unit_info(u_state, prefix="攻", province_id=prov.province_id)
            )
        attacker_info = "\n".join(atk_lines)

        def_lines = []
        if target.units:
            for u in target.units:
                def_lines.append(
                    app._format_unit_info(u, prefix="防", province_id=target.province_id)
                )
        elif app._is_fort_or_city(target):
            def_lines.append("守备：防御2（空城）")
        defender_info = "\n".join(def_lines)

        app.show_combat_ui = True
        app.combat_target = target

        wei_manager = app.card_managers.get("WEI")
        app.defender_can_use_jiangdong = (
            target.country == "WEI"
            and wei_manager is not None
            and not wei_manager.is_card_used("card_jiangdong_zhiti")
        )
        app.defender_use_jiangdong = False
        app.defender_jiangdong_decided = not app.defender_can_use_jiangdong
        app.waiting_defender_response = False

        app.allow_jiangdong_selection = False
        if app.player_country and app.player_country in app.card_managers:
            app.card_manager = app.card_managers[app.player_country]
            app._update_card_panel()

        app.defender_can_hold_position = app._is_fort_or_city(target) and bool(target.units)
        app.defender_hold_decided = not app.defender_can_hold_position
        app.defender_use_hold_position = False

        app.combat_result_title = None
        app.combat_result_timer = 0

        app.combat_ratio_val = ratio_val
        app.combat_callback = lambda: self.execute_combat(app, participating_attackers, target)

        app.info_panel.show_combat_details(attacker_info, defender_info)

        if app.human_country is not None and target.country != app.human_country:
            app.defender_jiangdong_decided = True
            app.defender_use_jiangdong = False
            app.defender_hold_decided = True
            app.defender_use_hold_position = False

    def execute_combat(self, app: Any, attackers: list, target_province: object) -> None:
        """执行战斗，每次点击投骰时重新计算攻防比。"""
        total_attack = 0.0
        for prov, u_state in attackers:
            atk, _ = app._calculate_unit_powers(u_state, prov.province_id)
            atk += app._get_attack_terrain_penalty(prov, target_province, u_state)
            atk = max(0, atk)

            defender_types = [u.unit_type for u in target_province.units]
            bonus = app.combat_utils_service.get_counter_bonus(
                u_state.unit_type, defender_types
            )
            total_attack += atk + bonus

        total_defense = app.combat_utils_service.calculate_total_defense(app, target_province)
        attacker_provinces = {p.province_id for p, _ in attackers}
        is_flanked = app.combat_utils_service.calculate_is_flanked(
            app, target_province, attacker_provinces
        )

        col_index = get_ratio_column(total_attack, total_defense, is_flanked)
        col_index = app.combat_utils_service.apply_base_column_adjustment(
            app, target_province, col_index
        )

        self.resolve_combat(app, col_index, attackers, target_province)

    def resolve_combat(
        self, app: Any, col_index: int, attackers: list, target_province: object
    ) -> None:
        """投骰后的回调结算。"""
        use_jiangdong = app.defender_use_jiangdong
        use_hold_position = app.defender_use_hold_position

        app.clear_selection(clear_ui=False)

        defenders_snapshot = list(target_province.units)
        has_garrison_only = (not target_province.units) and app._is_fort_or_city(target_province)

        raw_dice = random.randint(1, 6)
        dice = raw_dice

        attacker_dice_bonus = 0
        for prov, _ in attackers:
            effect = app.card_effect_manager.get_effect(str(prov.province_id))
            if effect and effect.dice_bonus > 0:
                attacker_dice_bonus = max(attacker_dice_bonus, effect.dice_bonus)
        for _, u in attackers:
            attacker_dice_bonus = max(attacker_dice_bonus, getattr(u, "temp_dice_bonus", 0))

        defender_dice_bonus = 0
        target_effect = app.card_effect_manager.get_effect(str(target_province.province_id))
        if target_effect and target_effect.dice_bonus > 0:
            defender_dice_bonus = target_effect.dice_bonus
        for u in target_province.units:
            defender_dice_bonus = max(defender_dice_bonus, getattr(u, "temp_dice_bonus", 0))

        atk_country = app.player_country
        def_country = target_province.country

        if app.evt_flag_all_attack:
            attacker_dice_bonus += 1

        if atk_country == "WEI" and app.evt_wuzi_bonus > 0 and app.evt_wuzi_rounds > 0:
            attacker_dice_bonus += app.evt_wuzi_bonus

        if atk_country == "WU" and def_country == "WEI" and app.evt_flag_hefei:
            attacker_dice_bonus -= 1

        if atk_country == "SHU" and def_country == "WU" and app.evt_lonzhong_skill > 0:
            attacker_dice_bonus += 1
            app.evt_lonzhong_skill -= 1
            app._refresh_session_skill_display()
            if app.info_panel:
                remaining = (
                    f"，剩余 {app.evt_lonzhong_skill} 次" if app.evt_lonzhong_skill > 0 else ""
                )
                app.info_panel.show_message(
                    f"蜀汉使用「隆中定计」：进攻骰点+1！{remaining}", duration=2.0
                )

        if atk_country == "WU" and def_country == "SHU" and app.evt_jingzhu_skill > 0:
            attacker_dice_bonus += app.evt_jingzhu_skill

        if def_country == "SHU" and app.evt_yishen_skill > 0 and col_index > 1:
            col_index = 1
            app.evt_yishen_skill -= 1
            app._refresh_session_skill_display()
            if app.info_panel:
                remaining = (
                    f"，剩余 {app.evt_yishen_skill} 次" if app.evt_yishen_skill > 0 else ""
                )
                app.info_panel.show_message(
                    f"蜀汉使用「一身是胆」：按1:1档位计算！{remaining}", duration=2.0
                )

        if use_jiangdong and target_province.country == "WEI":
            attacker_dice_bonus -= 2

        dice = max(1, min(6, raw_dice + attacker_dice_bonus + defender_dice_bonus))
        logger.debug(
            "DICE: raw=%d atk_bonus=%d def_bonus=%d use_jd=%s => final=%d | atk_units=%s",
            raw_dice,
            attacker_dice_bonus,
            defender_dice_bonus,
            use_jiangdong,
            dice,
            [(u.unit_type, getattr(u, "temp_dice_bonus", 0)) for _, u in attackers],
        )

        result_code = resolve_combat(dice, col_index)

        dmg_attacker = 0
        dmg_defender = 0
        confused_defender = False
        retreat_defender = False

        if "A2" in result_code:
            dmg_attacker = 2
        elif "A1" in result_code:
            dmg_attacker = 1

        if "D1" in result_code:
            dmg_defender = 1

        if "AG" in result_code:
            app._apply_confusion(attackers)

        if "DG" in result_code:
            if target_province.units:
                app._apply_confusion([(None, u) for u in target_province.units])
            confused_defender = True

        if "DR" in result_code or "R" in result_code and "D" in result_code:
            retreat_defender = True

        pre_def_hp = {id(u): u.hp for u in target_province.units}
        attacker_groups: dict[int, list] = {}
        for prov, unit in attackers:
            attacker_groups.setdefault(prov.province_id, []).append(unit)
        pre_atk_hp_by_prov = {
            pid: {id(u): u.hp for u in units} for pid, units in attacker_groups.items()
        }

        if dmg_attacker > 0:
            app._apply_damage([u for _, u in attackers], dmg_attacker)

        if dmg_defender > 0 and target_province.units:
            app._apply_damage(target_province.units, dmg_defender)

        app._try_apply_gexu_guard(target_province, target_province.units, pre_def_hp)
        for pid, units in attacker_groups.items():
            prov = app.map_manager.get_by_id(pid)
            if prov:
                app._try_apply_gexu_guard(prov, units, pre_atk_hp_by_prov.get(pid, {}))
        app.gexu_guard_active = False

        if retreat_defender:
            if app._is_fort_or_city(target_province) and target_province.units and use_hold_position:
                for defender in target_province.units:
                    defender.is_confused = True
                    defender.confusion_count = max(1, defender.confusion_count)
                    defender.hp -= 1
                retreat_defender = False
                confused_defender = True
                result_code = result_code.replace("DR", "D1DG")
            elif not has_garrison_only:
                app._handle_retreat(target_province)
            else:
                retreat_defender = False

        app._cleanup_dead_units(attackers, target_province)

        can_occupy = not target_province.units
        if has_garrison_only:
            can_occupy = ("DR" in result_code) or ("DG" in result_code)

        if can_occupy:
            app._advance_after_combat(attackers, target_province)

        ratio_strs = ["1:2", "1:1", "2:1", "3:1", "4:1", "5:1"]
        r_idx = max(0, min(5, col_index))
        ratio_str = ratio_strs[r_idx]

        bonus_total = attacker_dice_bonus + defender_dice_bonus
        if bonus_total != 0:
            sign = "+" if bonus_total > 0 else ""
            dice_str = f"骰{raw_dice}{sign}{bonus_total}={dice}"
        else:
            dice_str = f"骰{dice}"
        title_line = " · ".join([ratio_str, dice_str, result_code])

        summary_parts = [f"攻损{dmg_attacker}", f"防损{dmg_defender}"]
        summary_line = " · ".join(summary_parts)

        status_msgs = []
        if confused_defender:
            status_msgs.append("防乱")
        if retreat_defender:
            status_msgs.append("防退")
        status_line = " · ".join(status_msgs) if status_msgs else None

        title_lines = [title_line, summary_line]
        if status_line:
            title_lines.append(status_line)
        full_title_str = " · ".join(title_lines)

        logs = []
        logs.append("--- 进攻方 ---")
        for prov, u_state in attackers:
            logs.append(app._format_unit_info(u_state, prefix="攻", province_id=prov.province_id))

        if defenders_snapshot:
            logs.append("--- 防守方 ---")
            for u_state in defenders_snapshot:
                logs.append(
                    app._format_unit_info(
                        u_state, prefix="防", province_id=target_province.province_id
                    )
                )
        elif has_garrison_only:
            logs.append("--- 防守方 ---")
            logs.append("守备：防御2（空城）")
        else:
            logs.append("防守方全灭或撤离")

        app.combat_result_title = full_title_str
        app.combat_result_timer = -1

        app.info_panel.show_combat_result(None, None, "\n".join(logs))

        action_name = "移动后攻击" if app.pending_post_move_attack else "攻击"
        app._finish_country_action(action_name, keep_info_message=True)
