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


if __name__ == "__main__":
    unittest.main()
