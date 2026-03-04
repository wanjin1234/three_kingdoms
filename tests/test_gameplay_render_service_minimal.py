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

    # ── O3: 战斗判定表预渲染 ──────────────────────────────────────────

    def test_build_combat_table_surf_returns_surface(self):
        """`_build_combat_table_surf` 应返回非空 SRCALPHA Surface。"""
        font = pg.font.Font(None, 14)
        surf = GameplayRenderService._build_combat_table_surf(font)
        self.assertIsInstance(surf, pg.Surface)
        w, h = surf.get_size()
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_build_combat_table_surf_size_proportional_to_font(self):
        """较大字体应产生较大的表格 Surface。"""
        small_font = pg.font.Font(None, 12)
        large_font = pg.font.Font(None, 24)
        small_surf = GameplayRenderService._build_combat_table_surf(small_font)
        large_surf = GameplayRenderService._build_combat_table_surf(large_font)
        self.assertGreater(large_surf.get_width(), small_surf.get_width())
        self.assertGreater(large_surf.get_height(), small_surf.get_height())

    def test_get_combat_table_surf_caches_by_font_id(self):
        """相同字体对象连续两次调用应返回同一 Surface 对象。"""
        class _App:
            pass
        app = _App()
        app.morale_tt_font = pg.font.Font(None, 14)

        surf1 = GameplayRenderService._get_combat_table_surf(app)
        surf2 = GameplayRenderService._get_combat_table_surf(app)
        self.assertIs(surf1, surf2, "字体未变时应命中缓存，返回同一对象")

    def test_get_combat_table_surf_invalidates_on_font_change(self):
        """字体对象变更后应重建 Surface。"""
        class _App:
            pass
        app = _App()
        app.morale_tt_font = pg.font.Font(None, 14)
        surf1 = GameplayRenderService._get_combat_table_surf(app)

        app.morale_tt_font = pg.font.Font(None, 20)  # 新字体对象，id 不同
        surf2 = GameplayRenderService._get_combat_table_surf(app)
        self.assertIsNot(surf1, surf2, "字体变化后应重建 Surface")

    def test_get_combat_table_surf_respects_forced_reset(self):
        """外部将 _combat_table_cache_key 置 None 后应强制重建。"""
        class _App:
            pass
        app = _App()
        app.morale_tt_font = pg.font.Font(None, 14)
        surf1 = GameplayRenderService._get_combat_table_surf(app)

        app._combat_table_cache_key = None  # 模拟 rebuild_layout 重置
        surf2 = GameplayRenderService._get_combat_table_surf(app)
        self.assertIsNotNone(surf2)
        # 重建后缓存键应与当前字体对象 id 一致
        self.assertEqual(app._combat_table_cache_key, id(app.morale_tt_font))


if __name__ == "__main__":
    unittest.main()
