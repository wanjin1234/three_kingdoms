import unittest

import pygame as pg

from src.core.polyline_render_service import PolylineRenderService


class PolylineRenderServiceMinimalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()

    @classmethod
    def tearDownClass(cls):
        pg.quit()

    def setUp(self):
        self.service = PolylineRenderService()

    def test_draw_smooth_polyline_no_crash(self):
        app = type("App", (), {})()
        app.window = pg.Surface((200, 200), pg.SRCALPHA)
        points = [
            pg.math.Vector2(20, 20),
            pg.math.Vector2(100, 40),
            pg.math.Vector2(180, 120),
        ]

        self.service.draw_smooth_polyline(
            window=app.window,
            color=pg.Color("blue"),
            points=points,
            width=12,
        )

        self.assertTrue(True)

    def test_draw_smooth_polyline_ignores_short_input(self):
        app = type("App", (), {})()
        app.window = pg.Surface((100, 100), pg.SRCALPHA)

        self.service.draw_smooth_polyline(
            window=app.window,
            color=pg.Color("blue"),
            points=[pg.math.Vector2(10, 10)],
            width=6,
        )

        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
