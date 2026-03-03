import unittest

import pygame as pg

from src.core.selection_service import SelectionService


class _Province:
    def __init__(self, province_id, country, units, center=(50, 50)):
        self.province_id = province_id
        self.country = country
        self.units = units
        self.center_cache = center

    def compute_center(self, _hex_side):
        return self.center_cache


class _MapManager:
    def __init__(self, provinces):
        self.provinces = provinces


class _UnitRenderer:
    def selection_rects(self, center, count):
        cx, cy = center
        return [pg.Rect(cx - 5 + i * 12, cy - 5, 10, 10) for i in range(count)]


class SelectionServiceMinimalTest(unittest.TestCase):
    def setUp(self):
        self.service = SelectionService()

    def test_handle_selection_click_adds_player_unit(self):
        province = _Province(1, "SHU", [object(), object()])
        app = type("App", (), {})()
        app.player_country = "SHU"
        app.map_manager = _MapManager([province])
        app.unit_renderer = _UnitRenderer()
        app.hex_side = 10
        calls = []
        app.add_selection = lambda pid, idx: calls.append((pid, idx))

        self.service.handle_selection_click(
            player_country=app.player_country,
            provinces=app.map_manager.provinces,
            unit_renderer=app.unit_renderer,
            hex_side=app.hex_side,
            mouse_pos=(50, 50),
            on_add_selection=app.add_selection,
        )

        self.assertEqual(calls, [(1, 0)])

    def test_handle_selection_click_ignores_enemy_unit(self):
        province = _Province(2, "WEI", [object()])
        app = type("App", (), {})()
        app.player_country = "SHU"
        app.map_manager = _MapManager([province])
        app.unit_renderer = _UnitRenderer()
        app.hex_side = 10
        calls = []
        app.add_selection = lambda pid, idx: calls.append((pid, idx))

        self.service.handle_selection_click(
            player_country=app.player_country,
            provinces=app.map_manager.provinces,
            unit_renderer=app.unit_renderer,
            hex_side=app.hex_side,
            mouse_pos=(50, 50),
            on_add_selection=app.add_selection,
        )

        self.assertEqual(calls, [])

    def test_handle_selection_click_without_player_country(self):
        province = _Province(3, "SHU", [object()])
        app = type("App", (), {})()
        app.player_country = None
        app.map_manager = _MapManager([province])
        app.unit_renderer = _UnitRenderer()
        app.hex_side = 10
        calls = []
        app.add_selection = lambda pid, idx: calls.append((pid, idx))

        self.service.handle_selection_click(
            player_country=app.player_country,
            provinces=app.map_manager.provinces,
            unit_renderer=app.unit_renderer,
            hex_side=app.hex_side,
            mouse_pos=(50, 50),
            on_add_selection=app.add_selection,
        )

        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
