"""
战斗结算服务：抽离 `GameApp` 中的伤害、混乱、撤退与战后处理。
"""

from __future__ import annotations

import logging
import random
from typing import Any

logger = logging.getLogger(__name__)
MAX_UNIT_STACK = 3


class CombatResolutionService:
    """战斗结算辅助服务。"""

    def apply_damage(self, app: Any, units: list, amount: int) -> None:
        """分配伤害。"""
        for _ in range(amount):
            living_units = [u for u in units if u.hp > 0]
            if not living_units:
                break

            candidates = sorted(living_units, key=app._get_target_selection_key)
            target = candidates[0]
            target.hp -= 1

    def apply_confusion(self, app: Any, unit_tuples: list, amount: int = 1) -> None:
        """应用混乱。"""
        units = [u for _, u in unit_tuples]

        for _ in range(amount):
            living_units = [u for u in units if u.hp > 0]
            if not living_units:
                break

            candidates = sorted(living_units, key=app._get_target_selection_key)
            target = candidates[0]

            if target.is_confused:
                target.confusion_count += 1
                target.hp -= 1
                target.is_confused = True
            else:
                target.is_confused = True
                target.confusion_count = 1

    def handle_retreat(self, app: Any, province: object) -> None:
        """处理撤退。"""
        if not province.units:
            return

        start_id = province.province_id
        valid_destinations = []
        neighbor_ids = app.map_manager._adjacency.get(start_id, [])

        for nid in neighbor_ids:
            dest_prov = app.map_manager.get_by_id(nid)
            if not dest_prov:
                continue

            if dest_prov.country and dest_prov.country != province.country:
                continue

            if len(dest_prov.units) + len(province.units) > MAX_UNIT_STACK:
                continue

            step_cost = 1
            t_terrain = dest_prov.terrain.lower() if dest_prov.terrain else ""
            if t_terrain in ("hill", "mountain", "hills", "mountains"):
                step_cost += 1

            if step_cost <= 1:
                valid_destinations.append(dest_prov)

        if valid_destinations:
            dest = random.choice(valid_destinations)
            dest.units.extend(u for u in province.units if u.hp > 0)
            province.units.clear()
            logger.info("Defenders retreated to %s", getattr(dest, "name", "?"))
        else:
            self.apply_damage(app, province.units, 1)

    def cleanup_dead_units(self, attackers: list, target: object) -> None:
        """清理战场。"""
        any_dead = False
        for _, u in attackers:
            if u.hp <= 0:
                any_dead = True
                break

        if any_dead:
            seen_prov_ids = set()
            unique_provs = []
            for p, _ in attackers:
                if p.province_id not in seen_prov_ids:
                    seen_prov_ids.add(p.province_id)
                    unique_provs.append(p)

            for p in unique_provs:
                p.units = [u for u in p.units if u.hp > 0]

        target.units = [u for u in target.units if u.hp > 0]

    def advance_after_combat(self, app: Any, attackers: list, target: object) -> None:
        """进占：按顺序派出至多2个相邻进攻单位。"""
        movers = 0
        limit = 2
        adjacent_ids: set = set(app.map_manager._adjacency.get(target.province_id, []))

        for prov, unit in attackers:
            if movers >= limit:
                break
            if unit.hp <= 0 or unit not in prov.units:
                continue
            if prov.province_id not in adjacent_ids:
                continue
            prov.units.remove(unit)
            target.units.append(unit)
            target.country = app.player_country
            movers += 1

        if movers > 0:
            app.map_manager.invalidate_cache()
            app._check_tianxia_guixin_victory()
