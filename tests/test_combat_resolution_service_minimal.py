import unittest
from types import SimpleNamespace

from src.core.combat_resolution_service import CombatResolutionService


class _Unit:
    def __init__(self, hp=2):
        self.hp = hp
        self.is_confused = False
        self.confusion_count = 0


class _Prov:
    def __init__(self, pid, country="SHU", terrain="plain", units=None, name="P"):
        self.province_id = pid
        self.country = country
        self.terrain = terrain
        self.units = units or []
        self.name = name


class CombatResolutionServiceMinimalTest(unittest.TestCase):
    def setUp(self):
        self.service = CombatResolutionService()

    def test_apply_damage_reduces_hp(self):
        app = SimpleNamespace(_get_target_selection_key=lambda u: (0, 1))
        units = [_Unit(hp=2), _Unit(hp=2)]
        self.service.apply_damage(app, units, 1)
        self.assertEqual(sum(u.hp for u in units), 3)

    def test_apply_confusion_marks_unit(self):
        app = SimpleNamespace(_get_target_selection_key=lambda u: (0, 1))
        u = _Unit(hp=2)
        self.service.apply_confusion(app, [(None, u)], 1)
        self.assertTrue(u.is_confused)
        self.assertEqual(u.confusion_count, 1)

    def test_advance_after_combat_moves_adjacent_units(self):
        u1 = _Unit(hp=2)
        u2 = _Unit(hp=2)
        src = _Prov(1, country="SHU", units=[u1, u2])
        dst = _Prov(2, country="WEI", units=[])

        app = SimpleNamespace(
            map_manager=SimpleNamespace(
                _adjacency={2: [1]},
                invalidate_cache=lambda: None,
            ),
            player_country="SHU",
            _check_tianxia_guixin_victory=lambda: None,
        )

        self.service.advance_after_combat(app, [(src, u1), (src, u2)], dst)
        self.assertEqual(len(dst.units), 2)
        self.assertEqual(dst.country, "SHU")


if __name__ == "__main__":
    unittest.main()
