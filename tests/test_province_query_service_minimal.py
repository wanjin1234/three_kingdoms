import unittest

import pygame as pg

from src.core.province_query_service import ProvinceQueryService


class _Province:
    def __init__(self, province_id, center, units=None):
        self.province_id = province_id
        self.center_cache = center
        self.units = units or []

    def compute_center(self, _hex_side):
        return self.center_cache


class _Map:
    def __init__(self, provinces):
        self.provinces = provinces


class _UnitRenderer:
    def selection_rects(self, center, count):
        cx, cy = center
        return [pg.Rect(cx - 5 + i * 12, cy - 5, 10, 10) for i in range(count)]


class ProvinceQueryServiceMinimalTest(unittest.TestCase):
    def setUp(self):
        self.service = ProvinceQueryService()

    def test_get_unit_slot_at_hits_unit(self):
        p = _Province(1, (50, 50), [object(), object()])
        app = type("App", (), {})()
        app.map_manager = _Map([p])
        app.unit_renderer = _UnitRenderer()
        app.hex_side = 20

        hit = self.service.get_unit_slot_at(
            provinces=app.map_manager.provinces,
            unit_renderer=app.unit_renderer,
            hex_side=app.hex_side,
            pos=(50, 50),
        )

        self.assertEqual(hit, (1, 0))

    def test_get_province_at_within_threshold(self):
        p1 = _Province(1, (0, 0), [])
        p2 = _Province(2, (100, 0), [])
        app = type("App", (), {})()
        app.map_manager = _Map([p1, p2])
        app.hex_side = 20

        prov = self.service.get_province_at(
            provinces=app.map_manager.provinces,
            hex_side=app.hex_side,
            pos=(5, 0),
        )

        self.assertIs(prov, p1)


if __name__ == "__main__":
    unittest.main()
