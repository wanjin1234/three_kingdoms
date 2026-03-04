import unittest

from src.core.turn_resource_service import TurnResourceService


class _Unit:
    def __init__(self, unit_type="infantry", mp=0, confused=False, bonus=0):
        self.unit_type = unit_type
        self.mp = mp
        self.is_confused = confused
        self.major_mp_bonus = bonus


class _Prov:
    def __init__(self, province_id, country, units):
        self.province_id = province_id
        self.country = country
        self.units = units


class _Def:
    def __init__(self, move=4):
        self.move = move


class _UnitRepo:
    def get_definition(self, _unit_type):
        return _Def(move=4)


class TurnResourceServiceMinimalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TurnResourceService()

    def _make_app(self):
        app = type("A", (), {})()
        app.turn_state = type("TS", (), {"country_stats": {"SHU": {"people_support": -1, "political_points": 2}}})()
        app.event_card_state = type("ES", (), {"evt_temp_pp": {"SHU": 1}})()
        app.map_manager = type("MM", (), {"provinces": []})()
        app.unit_repository = _UnitRepo()
        return app

    def test_people_support_and_pp_related_queries(self):
        app = self._make_app()

        self.assertEqual(
            self.service.get_people_support_level(app.turn_state.country_stats, "SHU"),
            -1,
        )
        self.assertEqual(
            self.service.get_total_pp(
                app.turn_state.country_stats,
                app.event_card_state.evt_temp_pp,
                "SHU",
            ),
            3,
        )
        self.assertTrue(
            self.service.pp_can_use(
                app.turn_state.country_stats,
                app.event_card_state.evt_temp_pp,
                "SHU",
            )
        )

    def test_special_unit_and_heal_cost(self):
        normal = _Unit(unit_type="infantry")
        special = _Unit(unit_type="HUBAO_cavalry")

        self.assertFalse(self.service.is_special_unit(normal))
        self.assertTrue(self.service.is_special_unit(special))

        self.assertEqual(self.service.get_pp_heal_cost(normal), 1)
        self.assertEqual(self.service.get_pp_heal_cost(special), 2)

    def test_confused_queries_and_ai_cure(self):
        app = self._make_app()
        app.map_manager.provinces = [
            _Prov(1, "SHU", [_Unit(confused=False), _Unit(confused=True)]),
            _Prov(2, "WEI", [_Unit(confused=True)]),
        ]

        self.assertTrue(
            self.service.has_confused_units_for_country(app.map_manager.provinces, "SHU")
        )
        self.assertTrue(
            self.service.ai_cure_confused_unit(app.map_manager.provinces, "SHU")
        )
        self.assertFalse(app.map_manager.provinces[0].units[1].is_confused)

    def test_replenish_action_points_keeps_confusion(self):
        app = self._make_app()
        unit = _Unit(unit_type="infantry", mp=0, confused=True, bonus=1)
        app.map_manager.provinces = [_Prov(1, "SHU", [unit])]

        self.service.replenish_action_points(
            app.map_manager.provinces,
            app.unit_repository,
        )

        self.assertEqual(unit.mp, 5)
        self.assertTrue(unit.is_confused)


if __name__ == "__main__":
    unittest.main()
