import unittest
from types import SimpleNamespace

from src.core.combat_utils_service import CombatUtilsService


class _DummyProv:
    def __init__(self, province_id: int, terrain: str = "plain"):
        self.province_id = province_id
        self.terrain = terrain
        self.country = "WU"
        self.units = []
        self.center_cache = (0.0, 0.0)

    def compute_center(self, _hex_side):
        return self.center_cache


class _DummyEffects:
    @staticmethod
    def get_effect(_key: str):
        return None

    @staticmethod
    def is_offensive_card_active(_card_id: str) -> bool:
        return False


class _DummyUnit:
    def __init__(self, unit_type: str):
        self.unit_type = unit_type


class CombatUtilsServiceMinimalTest(unittest.TestCase):
    def setUp(self):
        self.service = CombatUtilsService()
        p1 = _DummyProv(1, "plain")
        p2 = _DummyProv(2, "plain")
        p3 = _DummyProv(3, "city")
        p1.center_cache = (0.0, 0.0)
        p2.center_cache = (15.0, 0.0)
        p3.center_cache = (30.0, 0.0)
        prov_map = {1: p1, 2: p2, 3: p3}
        self.app = SimpleNamespace(
            map_manager=SimpleNamespace(
                _river_crossing_edges={(1, 2): True},
                _adjacency={1: [2], 2: [1, 3], 3: [2]},
                get_by_id=lambda pid: prov_map.get(pid),
            ),
            card_effect_manager=_DummyEffects(),
            unit_repository=SimpleNamespace(
                get_definition=lambda _t: SimpleNamespace(defense=2)
            ),
            hex_side=10,
            gexu_guard_active=False,
            player_country="WU",
            evt_flag_liukang=False,
            evt_flag_wuwei=False,
            evt_flag_she_hushu=False,
            pending_post_move_attack=False,
            pending_attacker=None,
            selected_units=[],
            info_panel=SimpleNamespace(show_message=lambda *_args, **_kwargs: None),
            _calculate_unit_powers=lambda _u, _pid: (2, 3),
            _province_has_river_neighbor=lambda _pid: False,
        )

    def test_get_unit_relationship(self):
        self.assertEqual(self.service.get_unit_relationship("infantry", "archer"), 1)
        self.assertEqual(self.service.get_unit_relationship("archer", "infantry"), -1)
        self.assertEqual(self.service.get_unit_relationship("cavalry", "archer"), -1)

    def test_attack_terrain_penalty_for_river_crossing(self):
        atk = _DummyProv(1, "plain")
        deff = _DummyProv(2, "plain")
        unit = _DummyUnit("infantry")
        penalty = self.service.get_attack_terrain_penalty(self.app, atk, deff, unit)
        self.assertEqual(penalty, -1)

    def test_find_path_cost_ignore_mountain(self):
        cost = self.service.find_path_cost_ignore_mountain(self.app, 1, 3)
        # 1->2 跨河消耗 2，2->3 普通消耗 1，总计 3
        self.assertEqual(cost, 3)

    def test_counter_bonus(self):
        bonus = self.service.get_counter_bonus("infantry", ["archer"])
        self.assertEqual(bonus, 0.5)

    def test_check_combat_preconditions_blocked_by_wuwei(self):
        self.app.evt_flag_wuwei = True
        target = _DummyProv(2, "plain")
        target.country = "WEI"
        ok = self.service.check_combat_preconditions(self.app, target)
        self.assertFalse(ok)

    def test_calculate_total_defense_for_empty_city(self):
        target = _DummyProv(3, "city")
        target.units = []
        total_def = self.service.calculate_total_defense(self.app, target)
        self.assertEqual(total_def, 2.0)

    def test_calculate_is_flanked_true(self):
        target = _DummyProv(2, "plain")
        target.center_cache = (15.0, 0.0)
        # 1 和 3 都在阈值内，形成夹击
        is_flanked = self.service.calculate_is_flanked(self.app, target, {1, 3})
        self.assertTrue(is_flanked)

    def test_apply_base_column_adjustment_no_cards(self):
        target = _DummyProv(2, "plain")
        self.assertEqual(
            self.service.apply_base_column_adjustment(self.app, target, 2),
            2,
        )


if __name__ == "__main__":
    unittest.main()
