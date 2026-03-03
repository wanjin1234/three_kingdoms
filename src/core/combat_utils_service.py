"""
战斗通用工具服务：抽离 `GameApp` 中的战斗辅助计算方法。
"""

from __future__ import annotations

from math import dist, sqrt
from typing import Any

from src.game_objects.unit import UnitState

SQRT3 = sqrt(3)


class CombatUtilsService:
    """战斗辅助计算服务。"""

    def is_mountain_terrain(self, province: object) -> bool:
        terrain = (province.terrain or "").lower()
        return terrain in ("hill", "mountain", "hills", "mountains")

    def is_fort_or_city(self, province: object) -> bool:
        terrain = (province.terrain or "").lower()
        return terrain == "city"

    def is_river_crossing(self, app: Any, from_id: int, to_id: int) -> bool:
        return app.map_manager._river_crossing_edges.get(
            (from_id, to_id), False
        ) or app.map_manager._river_crossing_edges.get((to_id, from_id), False)

    def get_attack_terrain_penalty(
        self, app: Any, attacker_prov: object, target_prov: object, unit_state
    ) -> int:
        """跨河/攻山地惩罚：满足任一条件时攻击力-1（无当飞军除外）。"""
        unit_type_lower = (unit_state.unit_type or "").lower()
        if "wudang" in unit_type_lower:
            return 0

        effect = app.card_effect_manager.get_effect(str(attacker_prov.province_id))
        river_immune = bool(effect and effect.river_immunity) or bool(
            getattr(unit_state, "temp_river_immunity", False)
        )
        terrain_immune = bool(effect and effect.terrain_immunity) or bool(
            getattr(unit_state, "temp_terrain_immunity", False)
        )

        is_river = self.is_river_crossing(
            app, attacker_prov.province_id, target_prov.province_id
        )
        is_mountain = self.is_mountain_terrain(target_prov)

        if (is_river and not river_immune) or (is_mountain and not terrain_immune):
            return -1
        return 0

    def find_path_cost_ignore_mountain(self, app: Any, start_id: int, target_id: int) -> int:
        """计算移动消耗：忽略山地额外消耗，但保留基础步耗和跨河消耗。"""
        if start_id == target_id:
            return 0

        import heapq

        queue = [(0, start_id)]
        min_costs = {start_id: 0}

        while queue:
            curr_total, curr_id = heapq.heappop(queue)

            if curr_total > min_costs.get(curr_id, float("inf")):
                continue

            if curr_id == target_id:
                return curr_total

            for next_id in app.map_manager._adjacency.get(curr_id, []):
                step_cost = 1
                if self.is_river_crossing(app, curr_id, next_id):
                    step_cost += 1

                new_total = curr_total + step_cost
                if new_total < min_costs.get(next_id, float("inf")):
                    min_costs[next_id] = new_total
                    heapq.heappush(queue, (new_total, next_id))

        return 9999

    def find_path_ignore_mountain(self, app: Any, start_id: int, target_id: int) -> list:
        """返回忽略山地消耗的最短路径（省ID列表，含首尾）。"""
        if start_id == target_id:
            return [start_id]

        import heapq

        queue = [(0, start_id, [start_id])]
        min_costs: dict = {start_id: 0}

        while queue:
            curr_total, curr_id, path = heapq.heappop(queue)

            if curr_total > min_costs.get(curr_id, float("inf")):
                continue

            if curr_id == target_id:
                return path

            for next_id in app.map_manager._adjacency.get(curr_id, []):
                step_cost = 1
                if self.is_river_crossing(app, curr_id, next_id):
                    step_cost += 1
                new_total = curr_total + step_cost
                if new_total < min_costs.get(next_id, float("inf")):
                    min_costs[next_id] = new_total
                    heapq.heappush(queue, (new_total, next_id, path + [next_id]))

        return []

    def try_apply_gexu_guard(
        self, app: Any, province: object, units: list[UnitState], pre_hp_map: dict[int, int]
    ) -> bool:
        """割须弃袍：本小回合内，魏方防御最高单位受伤时免除一次伤害（全局标志）。"""
        if not app.gexu_guard_active or not units:
            return False

        highest_def_unit = max(
            units,
            key=lambda u: app._calculate_unit_powers(u, province.province_id)[1],
        )

        before_hp = pre_hp_map.get(id(highest_def_unit), highest_def_unit.hp)
        if highest_def_unit.hp < before_hp:
            highest_def_unit.hp += 1
            app.gexu_guard_active = False
            return True

        return False

    def has_attackable_target_for_unit(self, app: Any, province: object, unit_state) -> bool:
        """判断某单位在当前位置是否存在可攻击目标。"""
        definition = app.unit_repository.get_definition(unit_state.unit_type)
        unit_stride = SQRT3 * app.hex_side
        allowed_range_px = definition.range * unit_stride * 1.1

        p_center = (
            province.center_cache
            if province.center_cache
            else province.compute_center(app.hex_side)
        )

        for target in app.map_manager.provinces:
            if target.country == app.player_country:
                continue
            if not target.units and not self.is_fort_or_city(target):
                continue

            t_center = (
                target.center_cache if target.center_cache else target.compute_center(app.hex_side)
            )
            if dist(p_center, t_center) <= allowed_range_px:
                target_eff = app.card_effect_manager.get_effect(str(target.province_id))
                if target_eff and target_eff.protected:
                    continue
                return True

        return False

    def get_base_unit_type(self, unit_type: str) -> str:
        """提取兵种基础类型 (infantry/cavalry/archer)。"""
        unit_lower = unit_type.lower()
        if "infantry" in unit_lower:
            return "infantry"
        if "cavalry" in unit_lower:
            return "cavalry"
        if "archer" in unit_lower:
            return "archer"
        return ""

    def get_target_selection_key(self, app: Any, unit_state) -> tuple[int, int]:
        """计算单位目标选择优先级: (是否受伤, 防御力)。"""
        is_inj = 1 if unit_state.is_injured else 0
        defense = app.unit_repository.get_definition(unit_state.unit_type).defense
        return (is_inj, defense)

    def get_unit_relationship(self, attacker_type: str, defender_type: str) -> int:
        """判断兵种克制关系，返回 1 / -1 / 0。"""
        a_base = self.get_base_unit_type(attacker_type)
        d_base = self.get_base_unit_type(defender_type)

        if not a_base or not d_base:
            return 0

        if a_base == "infantry":
            if d_base == "archer":
                return 1
            if d_base == "cavalry":
                return -1
        elif a_base == "archer":
            if d_base == "cavalry":
                return 1
            if d_base == "infantry":
                return -1
        elif a_base == "cavalry":
            if d_base == "infantry":
                return 1
            if d_base == "archer":
                return -1

        return 0

    def get_counter_bonus(self, attacker_type: str, defender_types: list[str]) -> float:
        """计算兵种克制加成。"""
        bonus = 0.0
        has_adv = False
        has_dis = False
        for d_type in defender_types:
            rel = self.get_unit_relationship(attacker_type, d_type)
            if rel == 1:
                has_adv = True
            if rel == -1:
                has_dis = True
        if has_adv:
            bonus += 0.5
        if has_dis:
            bonus -= 0.5
        return bonus

    def calculate_total_defense(self, app: Any, target_province: object) -> float:
        """计算防守总值（含舍身护主与空城守备规则）。"""
        total_defense = 0.0
        if target_province.units:
            for unit in target_province.units:
                _, dfs = app._calculate_unit_powers(unit, target_province.province_id)
                if target_province.country == "WU" and app.evt_flag_she_hushu:
                    dfs += 1
                total_defense += dfs
        elif self.is_fort_or_city(target_province):
            total_defense = 2.0

        if total_defense <= 0.1:
            total_defense = 0.1
        return total_defense

    def calculate_is_flanked(
        self, app: Any, target_province: object, attacker_provinces: set[int]
    ) -> bool:
        """判断防守方是否被夹击（相邻进攻来源省份数 >= 2）。"""
        unit_stride = SQRT3 * app.hex_side
        neighbor_count = 0
        target_center = (
            target_province.center_cache
            if target_province.center_cache
            else target_province.compute_center(app.hex_side)
        )
        neighbor_threshold = unit_stride * 1.1

        for p_id in attacker_provinces:
            prov = app.map_manager.get_by_id(p_id)
            if not prov:
                continue
            p_center = (
                prov.center_cache if prov.center_cache else prov.compute_center(app.hex_side)
            )
            if dist(p_center, target_center) < neighbor_threshold:
                neighbor_count += 1

        return neighbor_count >= 2

    def apply_base_column_adjustment(
        self, app: Any, target_province: object, col_index: int
    ) -> int:
        """应用基础列修正（城市-1、威震华夏+河流+1）。"""
        col_adj = 0
        if self.is_fort_or_city(target_province):
            col_adj -= 1
        if app.card_effect_manager.is_offensive_card_active("card_zhenjing_huaxia_shu"):
            if app._province_has_river_neighbor(target_province.province_id):
                col_adj += 1
        return max(0, min(5, col_index + col_adj))

    def check_combat_preconditions(self, app: Any, target: object) -> bool:
        """战斗前置校验。返回 True 表示可继续发起战斗。"""
        atk_c = app.player_country
        def_c = target.country

        if app.evt_flag_liukang:
            if (atk_c == "SHU" and def_c == "WU") or (atk_c == "WU" and def_c == "SHU"):
                if app.info_panel:
                    app.info_panel.show_message("「联刘抗曹」：本回合蜀汉与东吴不能互相攻击")
                return False

        if app.evt_flag_wuwei and atk_c == "WU" and def_c == "WEI":
            if app.info_panel:
                app.info_panel.show_message("「吴魏媾和」：本回合东吴不能进攻曹魏")
            return False

        target_effect = app.card_effect_manager.get_effect(str(target.province_id))
        if target_effect and target_effect.protected:
            if app.info_panel:
                app.info_panel.show_message("此格子不能被进攻")
            return False

        if app.pending_post_move_attack and app.pending_attacker:
            if len(app.selected_units) != 1 or app.selected_units[0] != app.pending_attacker:
                if app.info_panel:
                    app.info_panel.show_message("当前仅可由移动后的单位发起攻击")
                return False

        return True
