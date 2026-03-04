import unittest

import pygame as pg

from src.core.score_screen_service import ScoreScreenService


class _Record:
    def __init__(self):
        self.shu_score = 10.0
        self.shu_initial = 8.0
        self.shu_people_support = 2
        self.shu_special = ["Hanzhong"]
        self.shu_normal = 3

        self.wei_score = 12.0
        self.wei_initial = 10.0
        self.wei_people_support = 3
        self.wei_special = []
        self.wei_normal = 4

        self.wu_score = 9.0
        self.wu_initial = 8.0
        self.wu_people_support = 1
        self.wu_special = []
        self.wu_normal = 2


class _ScoreManager:
    def get_detailed_scores(self, _provinces, _country_stats):
        return _Record()

    def check_tianxia_guixin(self, _provinces, _country_stats):
        return None

    def get_winner_by_score(self, _provinces, _country_stats):
        return "WEI", {"SHU": 1.0, "WEI": 2.0, "WU": 1.0}


class _Music:
    def __init__(self):
        self.called = 0

    def play_score(self):
        self.called += 1


class ScoreScreenServiceMinimalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()
        pg.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pg.quit()

    def setUp(self) -> None:
        self.service = ScoreScreenService()

    def _make_app(self):
        class _MapManager:
            provinces = []

        class _App:
            pass

        app = _App()
        app.map_manager = _MapManager()
        app.country_stats = {}
        app.score_manager = _ScoreManager()
        app.music_manager = _Music()
        app.show_score_screen = None
        app._score_screen_cache_key = None
        app._score_screen_cache_surface = None
        app.screen_width = 800
        app.screen_height = 600
        app.window = pg.Surface((800, 600))
        app._font = lambda _filename, size: pg.font.Font(None, size)
        return app

    def test_show_score_screen_sets_state_and_cache_reset(self):
        app = self._make_app()
        app._score_screen_cache_key = (1,)
        app._score_screen_cache_surface = pg.Surface((10, 10))

        self.service.show_score_screen(app, "wei_turn")

        self.assertIsNotNone(app.show_score_screen)
        self.assertEqual(app.show_score_screen["type"], "wei_turn")
        self.assertIsNone(app._score_screen_cache_key)
        self.assertIsNone(app._score_screen_cache_surface)

    def test_render_score_screen_cache_hit(self):
        app = self._make_app()
        self.service.show_score_screen(app, "wei_turn")

        self.service.render_score_screen(app)
        first = app._score_screen_cache_surface
        self.assertIsNotNone(first)

        self.service.render_score_screen(app)
        self.assertIs(first, app._score_screen_cache_surface)


if __name__ == "__main__":
    unittest.main()
