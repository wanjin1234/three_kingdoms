import unittest

import pygame as pg

from src.core.overlay_ui_service import OverlayUIService


class OverlayUIServiceMinimalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()
        pg.font.init()

    @classmethod
    def tearDownClass(cls):
        pg.font.quit()
        pg.quit()

    def setUp(self):
        self.service = OverlayUIService()

    def test_get_display_name_known_key(self):
        self.assertEqual(self.service.get_display_name("city"), "城市")
        self.assertEqual(self.service.get_display_name("HUBAO_cavalry"), "虎豹骑")

    def test_get_display_name_suffix_match(self):
        self.assertEqual(self.service.get_display_name("elite_infantry_t2"), "步兵")
        self.assertEqual(self.service.get_display_name("my_cavalry_variant"), "骑兵")
        self.assertEqual(self.service.get_display_name("fast_archer"), "弓兵")

    def test_get_display_name_unknown(self):
        self.assertIsNone(self.service.get_display_name("unknown_type"))

    def test_draw_hover_tooltip_without_app_get_display_name(self):
        app = type("App", (), {})()
        _state = type("State", (), {})()
        type(_state).PLAYING = _state
        app.state = _state
        app.window = pg.Surface((320, 240))
        app.screen_width = 320
        app.screen_height = 240
        app.tooltip_font = pg.font.Font(None, 18)
        app.tooltip_bold_font = pg.font.Font(None, 18)
        app._last_tooltip_data = None
        app._cached_tooltip_surface = None
        app.country_labels = {}
        app.country_button_colors = {}
        app.kingdom_repository = type("KR", (), {"get_color": lambda *_: None})()
        app._get_logical_mouse_pos = lambda: (50, 50)
        app._get_unit_slot_at = lambda _pos: None
        app._is_hovering_ban_line = lambda _pos: False
        app._is_hovering_river = lambda _pos: False

        province = type(
            "Province",
            (),
            {"name": "Tile_1", "terrain": "plain", "country": None},
        )()
        app._get_province_at = lambda _pos: province

        self.service.draw_hover_tooltip(app)


if __name__ == "__main__":
    unittest.main()
