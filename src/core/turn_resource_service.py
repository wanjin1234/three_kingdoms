from __future__ import annotations


class TurnResourceService:
    """回合资源/状态相关服务。"""

    def get_people_support_level(self, app, country: str) -> int:
        """获取国家当前民心等级（点数即等级，支持负数）。"""
        return app.turn_state.country_stats.get(country, {}).get("people_support", 0)

    def has_confused_units_for_country(self, app, country: str) -> bool:
        """检查该国是否有任何混乱状态的单位。"""
        for prov in app.map_manager.provinces:
            if prov.country == country:
                for unit in prov.units:
                    if unit.is_confused:
                        return True
        return False

    def is_special_unit(self, unit_state) -> bool:
        """判断是否为特殊兵种（虎豹骑/无当飞军/解烦兵）。"""
        t = (unit_state.unit_type or "").lower()
        return "hubao" in t or "wudang" in t or "jiefan" in t

    def get_pp_heal_cost(self, app, unit_state) -> int:
        """获取回复该单位1点血量的PP消耗：普通1PP，特殊2PP。"""
        return 2 if self.is_special_unit(unit_state) else 1

    def get_total_pp(self, app, country: str) -> int:
        """获取国家当前可用PP总量（普通+临时）。"""
        pp = app.turn_state.country_stats.get(country, {}).get("political_points", 0)
        temp = app.event_card_state.evt_temp_pp.get(country, 0)
        return pp + temp

    def pp_can_use(self, app, country: str) -> bool:
        """PP是否满足最低使用门槛（≥1）。"""
        return self.get_total_pp(app, country) >= 1

    def ai_cure_confused_unit(self, app, country: str) -> bool:
        """AI自动解除该国第一个混乱单位的混乱状态。"""
        for prov in app.map_manager.provinces:
            if prov.country == country:
                for unit in prov.units:
                    if unit.is_confused:
                        unit.is_confused = False
                        return True
        return False

    def replenish_action_points(self, app) -> None:
        """重置所有单位行动力（MP），不清除混乱状态。"""
        for prov in app.map_manager.provinces:
            for unit in prov.units:
                defn = app.unit_repository.get_definition(unit.unit_type)
                max_mp = defn.move
                unit.mp = max_mp + getattr(unit, "major_mp_bonus", 0)
