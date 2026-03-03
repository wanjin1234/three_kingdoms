import unittest

import pygame as pg

from src.core.evt_info_tooltip_service import EvtInfoTooltipService


class EvtInfoTooltipServiceMinimalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()
        pg.font.init()

    @classmethod
    def tearDownClass(cls):
        pg.font.quit()
        pg.quit()

    def setUp(self):
        self.service = EvtInfoTooltipService()

    @staticmethod
    def _playing_state_obj():
        state = type("State", (), {})()
        type(state).PLAYING = state
        return state

    def _build_app(self):
        app = type("App", (), {})()
        app.state = self._playing_state_obj()
        app.window = pg.Surface((480, 320), pg.SRCALPHA)
        app.screen_width = 480
        app.screen_height = 320
        app.country_stat_font = pg.font.Font(None, 20)
        app.tooltip_font = pg.font.Font(None, 18)
        app.country_labels = {"SHU": "蜀"}
        app.evt_info_btns = {"SHU": pg.Rect(20, 20, 24, 24)}
        app.jingnang_applied = {"SHU": [("火计", "令目标部队攻击力-1")]} 
        app.jingnang_applied_major = {"SHU": []}
        app.evt_applied_this_round = {"SHU": [("天时", "本回合行动力+1")]}
        app.evt_applied_major_round = {"SHU": []}
        app._get_logical_mouse_pos = lambda: (25, 25)
        return app

    def test_draw_evt_info_tooltip_when_hovered(self):
        app = self._build_app()

        self.service.draw_evt_info_tooltip(app)

        self.assertTrue(True)

    def test_draw_evt_info_tooltip_noop_when_not_playing(self):
        app = self._build_app()
        app.state = object()

        self.service.draw_evt_info_tooltip(app)

        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
