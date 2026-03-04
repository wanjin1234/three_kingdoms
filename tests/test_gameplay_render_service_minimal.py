import unittest

import pygame as pg

from src.core.gameplay_render_service import GameplayRenderService


class GameplayRenderServiceMinimalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()

    @classmethod
    def tearDownClass(cls):
        pg.quit()

    def setUp(self):
        self.service = GameplayRenderService()

    def test_build_round_text_without_country(self):
        self.assertEqual(self.service.build_round_text(1, 2, ""), "回合 1-2")

    def test_build_round_text_with_country(self):
        self.assertEqual(self.service.build_round_text(3, 5, "蜀"), "回合 3-5 · 蜀")

    def test_get_bg_alpha_surface_cache_hit_and_invalidate(self):
        class _App:
            pass

        app = _App()
        app.bg_image = pg.Surface((16, 16), pg.SRCALPHA)

        s1 = self.service._get_bg_alpha_surface(app, alpha=128)
        s2 = self.service._get_bg_alpha_surface(app, alpha=128)
        self.assertIs(s1, s2)  # 缓存命中
        self.assertEqual(s1.get_alpha(), 128)

        app.bg_image = pg.Surface((32, 32), pg.SRCALPHA)
        s3 = self.service._get_bg_alpha_surface(app, alpha=128)
        self.assertIsNot(s2, s3)  # 资源变化后失效重建
        self.assertEqual(s3.get_alpha(), 128)

    def test_get_river_ban_layer_cache_hit_and_invalidate(self):
        class _PolylineStub:
            def __init__(self):
                self.calls = 0

            def draw_smooth_polyline(self, **kwargs):
                self.calls += 1

        class _App:
            pass

        app = _App()
        app.window = pg.Surface((120, 80), pg.SRCALPHA)
        app.polyline_render_service = _PolylineStub()

        app.yangtze_polylines = [
            [pg.math.Vector2(10, 10), pg.math.Vector2(30, 30)],
            [pg.math.Vector2(30, 10), pg.math.Vector2(60, 30)],
        ]
        app.yellow_river_polyline = [pg.math.Vector2(5, 40), pg.math.Vector2(50, 40)]
        app.ban_line_polyline = [pg.math.Vector2(15, 60), pg.math.Vector2(75, 60)]

        layer1 = self.service._get_river_ban_layer(app)
        first_calls = app.polyline_render_service.calls
        self.assertGreater(first_calls, 0)

        layer2 = self.service._get_river_ban_layer(app)
        self.assertIs(layer1, layer2)  # 缓存命中
        self.assertEqual(app.polyline_render_service.calls, first_calls)

        # 尺寸变化 -> 缓存失效
        app.window = pg.Surface((140, 90), pg.SRCALPHA)
        layer3 = self.service._get_river_ban_layer(app)
        self.assertIsNot(layer2, layer3)
        self.assertGreater(app.polyline_render_service.calls, first_calls)

        calls_after_resize = app.polyline_render_service.calls
        # 几何变更（替换折线对象） -> 缓存失效
        app.yellow_river_polyline = [pg.math.Vector2(5, 45), pg.math.Vector2(55, 45)]
        layer4 = self.service._get_river_ban_layer(app)
        self.assertIsNot(layer3, layer4)
        self.assertGreater(app.polyline_render_service.calls, calls_after_resize)


if __name__ == "__main__":
    unittest.main()
