import unittest

import pygame as pg

from src.core.map_bounds_service import MapBoundsService


class _Province:
    def __init__(self, center):
        self.center_cache = center

    def compute_center(self, _hex_side):
        return self.center_cache


class _Map:
    def __init__(self, provinces):
        self.provinces = provinces


class MapBoundsServiceMinimalTest(unittest.TestCase):
    def setUp(self):
        self.service = MapBoundsService()

    def test_get_map_bounds_rect_empty(self):
        app = type("App", (), {})()
        app.map_manager = _Map([])
        app.screen_width = 300
        app.screen_height = 200

        rect = self.service.get_map_bounds_rect(
            provinces=app.map_manager.provinces,
            hex_side=20,
            screen_width=app.screen_width,
            screen_height=app.screen_height,
        )

        self.assertEqual(rect, pg.Rect(0, 0, 300, 200))

    def test_get_map_bounds_rect_from_provinces(self):
        app = type("App", (), {})()
        app.map_manager = _Map([_Province((100, 80)), _Province((180, 140))])
        app.screen_width = 400
        app.screen_height = 300
        app.hex_side = 20

        rect = self.service.get_map_bounds_rect(
            provinces=app.map_manager.provinces,
            hex_side=app.hex_side,
            screen_width=app.screen_width,
            screen_height=app.screen_height,
        )

        self.assertGreater(rect.width, 0)
        self.assertGreater(rect.height, 0)
        self.assertLessEqual(rect.right, app.screen_width)
        self.assertLessEqual(rect.bottom, app.screen_height)


if __name__ == "__main__":
    unittest.main()
