import unittest

import pygame as pg

from src.core.country_stats_overlay_service import CountryStatsOverlayService


class CountryStatsOverlayServiceMinimalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()
        pg.font.init()

    @classmethod
    def tearDownClass(cls):
        pg.font.quit()
        pg.quit()

    def setUp(self):
        self.service = CountryStatsOverlayService()

    def _build_app(self, major_round_choice_pending=False):
        app = type("App", (), {})()
        app.screen_width = 960
        app.screen_height = 540
        app.window = pg.Surface((app.screen_width, app.screen_height))
        app.turn_order = ["SHU", "WU", "WEI"]
        app.country_stats = {
            "SHU": {"people_support": 3, "political_points": 2},
            "WU": {"people_support": 4, "political_points": 1},
            "WEI": {"people_support": 5, "political_points": 3},
        }
        app.evt_temp_pp = {"SHU": 0, "WU": 1, "WEI": 0}
        app.country_labels = {"SHU": "蜀", "WU": "吴", "WEI": "魏"}
        app.country_button_colors = {
            "SHU": pg.Color("red"),
            "WU": pg.Color("green"),
            "WEI": pg.Color("blue"),
        }
        app.country_stat_title_font = pg.font.Font(None, 20)
        app.country_stat_font = pg.font.Font(None, 18)
        app.control_btns = []
        app.info_panel = None
        app.card_panel = None
        app.evt_applied_this_round = {}
        app.jingnang_applied = {}
        app.evt_applied_major_round = {}
        app.jingnang_applied_major = {}
        app.major_round_choice_pending = major_round_choice_pending
        app.major_round_choice_done = {"SHU": False, "WU": True, "WEI": False}
        app.country_stat_choice_btns = {}
        app.evt_info_btns = {}
        app._get_map_bounds_rect = lambda: pg.Rect(180, 60, 500, 360)
        app._get_logical_mouse_pos = lambda: (-1, -1)
        return app

    def test_draw_country_stats_overlay_builds_info_buttons(self):
        app = self._build_app(major_round_choice_pending=False)

        self.service.draw_country_stats_overlay(app)

        self.assertEqual(set(app.evt_info_btns.keys()), {"SHU", "WU", "WEI"})
        self.assertEqual(app.country_stat_choice_btns, {})

    def test_draw_country_stats_overlay_builds_choice_buttons_when_pending(self):
        app = self._build_app(major_round_choice_pending=True)

        self.service.draw_country_stats_overlay(app)

        self.assertIn("SHU", app.country_stat_choice_btns)
        self.assertIn("WEI", app.country_stat_choice_btns)
        self.assertNotIn("WU", app.country_stat_choice_btns)

    # ── O2 缓存行为测试 ────────────────────────────────────────────────

    def test_cache_populated_after_first_call(self):
        """首次调用后 _cs_overlay_cache 应被填充。"""
        app = self._build_app()
        self.assertIsNone(getattr(app, "_cs_overlay_cache", None))

        self.service.draw_country_stats_overlay(app)

        self.assertIsNotNone(app._cs_overlay_cache)
        self.assertIn("key", app._cs_overlay_cache)
        self.assertIn("content_specs", app._cs_overlay_cache)
        self.assertIn("excl_surf", app._cs_overlay_cache)

    def test_cache_hit_reuses_same_dict_on_identical_data(self):
        """数据不变时连续两次调用应命中缓存，返回同一个 dict 对象。"""
        app = self._build_app()
        self.service.draw_country_stats_overlay(app)
        cache_after_first = app._cs_overlay_cache

        self.service.draw_country_stats_overlay(app)

        self.assertIs(
            app._cs_overlay_cache,
            cache_after_first,
            "数据未变时应命中缓存，不应创建新 dict",
        )

    def test_cache_excl_surf_identity_preserved_on_hit(self):
        """缓存命中时 excl_surf 对象身份不变（未重新 font.render）。"""
        app = self._build_app()
        self.service.draw_country_stats_overlay(app)
        excl_id = id(app._cs_overlay_cache["excl_surf"])

        self.service.draw_country_stats_overlay(app)

        self.assertEqual(
            id(app._cs_overlay_cache["excl_surf"]),
            excl_id,
            "缓存命中时 excl_surf 不应重新渲染",
        )

    def test_cache_miss_on_stats_change(self):
        """country_stats 数值变化时应触发缓存失效重建。"""
        app = self._build_app()
        self.service.draw_country_stats_overlay(app)
        cache_before = app._cs_overlay_cache

        app.country_stats["SHU"]["people_support"] = 99
        self.service.draw_country_stats_overlay(app)

        self.assertIsNot(
            app._cs_overlay_cache,
            cache_before,
            "country_stats 变化后应重建缓存",
        )

    def test_cache_miss_on_temp_pp_change(self):
        """evt_temp_pp 变化（临时政治点数）应触发缓存失效。"""
        app = self._build_app()
        self.service.draw_country_stats_overlay(app)
        cache_before = app._cs_overlay_cache

        app.evt_temp_pp["SHU"] = 5
        self.service.draw_country_stats_overlay(app)

        self.assertIsNot(app._cs_overlay_cache, cache_before)

    def test_cache_miss_on_choice_done_change(self):
        """major_round_choice_done 变化应触发缓存失效。"""
        app = self._build_app(major_round_choice_pending=True)
        self.service.draw_country_stats_overlay(app)
        cache_before = app._cs_overlay_cache

        app.major_round_choice_done["SHU"] = True
        self.service.draw_country_stats_overlay(app)

        self.assertIsNot(app._cs_overlay_cache, cache_before)

    def test_cache_miss_on_screen_size_change(self):
        """屏幕尺寸变化应触发缓存失效（字体大小随之改变）。"""
        app = self._build_app()
        self.service.draw_country_stats_overlay(app)
        cache_before = app._cs_overlay_cache

        app.screen_width = 1280
        app.screen_height = 720
        self.service.draw_country_stats_overlay(app)

        self.assertIsNot(app._cs_overlay_cache, cache_before)

    def test_mouse_pos_called_exactly_once_per_frame(self):
        """O2：每帧只调用一次 _get_logical_mouse_pos（原最多 9 次）。"""
        app = self._build_app()
        call_count = [0]

        def _counted_mouse():
            call_count[0] += 1
            return (-1, -1)

        app._get_logical_mouse_pos = _counted_mouse

        # 第 1 帧（冷启动，触发缓存构建）
        self.service.draw_country_stats_overlay(app)
        self.assertEqual(call_count[0], 1, "冷启动帧也应只调用一次鼠标坐标")

        # 第 2 帧（缓存命中）
        self.service.draw_country_stats_overlay(app)
        self.assertEqual(call_count[0], 2, "缓存命中帧应只调用一次鼠标坐标")

    def test_mouse_pos_called_once_in_choice_phase(self):
        """选择阶段（choice_pending=True）每帧同样只调一次鼠标坐标。"""
        app = self._build_app(major_round_choice_pending=True)
        call_count = [0]

        def _counted_mouse():
            call_count[0] += 1
            return (-1, -1)

        app._get_logical_mouse_pos = _counted_mouse

        self.service.draw_country_stats_overlay(app)
        self.assertEqual(call_count[0], 1)

        self.service.draw_country_stats_overlay(app)
        self.assertEqual(call_count[0], 2)

    def test_evt_info_btns_rebuilt_every_frame(self):
        """evt_info_btns 每帧都需要重建，供输入系统碰撞检测使用。"""
        app = self._build_app()
        self.service.draw_country_stats_overlay(app)
        self.assertEqual(set(app.evt_info_btns.keys()), {"SHU", "WU", "WEI"})

        # 第二帧（缓存命中），注册表仍应完整
        app.evt_info_btns = {}
        self.service.draw_country_stats_overlay(app)
        self.assertEqual(set(app.evt_info_btns.keys()), {"SHU", "WU", "WEI"})

    def test_cache_none_reset_clears_stale_cache(self):
        """外部将 _cs_overlay_cache 置 None（模拟 rebuild_layout）后应强制重建。"""
        app = self._build_app()
        self.service.draw_country_stats_overlay(app)
        excl_id_before = id(app._cs_overlay_cache["excl_surf"])

        # 模拟 rebuild_layout_for_screen_size 重置缓存
        app._cs_overlay_cache = None

        self.service.draw_country_stats_overlay(app)
        excl_id_after = id(app._cs_overlay_cache["excl_surf"])

        # 重建后 excl_surf 是新对象
        self.assertIsNotNone(app._cs_overlay_cache)
        # 注：新旧 excl_surf 内容相同，但对象可能不同（取决于 Python 内存复用）
        # 关键是 cache 被重建，而不是沿用旧的
        self.assertIn("excl_surf", app._cs_overlay_cache)


if __name__ == "__main__":
    unittest.main()
