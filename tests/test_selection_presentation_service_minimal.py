import unittest

from src.core.selection_presentation_service import SelectionPresentationService


class _Color:
    def __init__(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b


class _Def:
    def __init__(self, country="SHU", move=4, rng=1):
        self.country = country
        self.move = move
        self.range = rng


class _UnitRepo:
    def get_definition(self, _unit_type):
        return _Def(country="SHU", move=4, rng=2)


class _KingdomRepo:
    def get_color(self, _country):
        return _Color(255, 0, 0)


class _UnitState:
    def __init__(self):
        self.unit_type = "infantry"
        self.is_injured = True
        self.is_confused = False
        self.hp = 3
        self.mp = 2


class _Prov:
    def __init__(self, province_id, units):
        self.province_id = province_id
        self.units = units


class _MapManager:
    def __init__(self, provinces):
        self._provinces = {p.province_id: p for p in provinces}

    def get_by_id(self, pid):
        return self._provinces.get(pid)


class _InfoPanel:
    def __init__(self):
        self.last = None

    def show_properties(self, text):
        self.last = text


class SelectionPresentationServiceMinimalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = SelectionPresentationService()

    def test_get_unit_abbr_covers_special_and_generic(self):
        self.assertEqual(self.service.get_unit_abbr("HUBAO_cavalry"), "虎豹")
        self.assertEqual(self.service.get_unit_abbr("foo_infantry"), "步")
        self.assertEqual(self.service.get_unit_abbr("foo_archer"), "弓")

    def test_format_unit_info_contains_status_color_and_attrs(self):
        app = type("A", (), {})()
        app.unit_repository = _UnitRepo()
        app.kingdom_repository = _KingdomRepo()
        app._calculate_unit_powers = lambda _u, _pid: (2.5, 1.5)

        text = self.service.format_unit_info(app, _UnitState(), province_id=1)

        self.assertIn("|#ff0000|步|#000000|", text)
        self.assertIn("(伤)", text)
        self.assertIn("血3", text)
        self.assertIn("攻2.5", text)
        self.assertIn("防1.5", text)
        self.assertIn("动2/4", text)
        self.assertIn("射2", text)

    def test_update_selection_info_handles_empty_and_selected(self):
        app = type("A", (), {})()
        app.info_panel = _InfoPanel()
        app.selected_units = []
        app.map_manager = _MapManager([])
        app.unit_repository = _UnitRepo()
        app.kingdom_repository = _KingdomRepo()
        app._calculate_unit_powers = lambda _u, _pid: (1.0, 1.0)

        self.service.update_selection_info(app)
        # 新行为：空选时不主动清除面板，保留旧信息
        self.assertIsNone(app.info_panel.last)

        unit = _UnitState()
        app.selected_units = [(1, 0)]
        app.map_manager = _MapManager([_Prov(1, [unit])])

        self.service.update_selection_info(app)
        self.assertIsInstance(app.info_panel.last, str)
        self.assertIn("血3", app.info_panel.last)


if __name__ == "__main__":
    unittest.main()
