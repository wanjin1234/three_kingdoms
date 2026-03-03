import unittest

import pygame as pg

from src.core.volume_ui_service import VolumeUIService


class VolumeUIServiceMinimalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()
        pg.font.init()

    @classmethod
    def tearDownClass(cls):
        pg.font.quit()
        pg.quit()

    def setUp(self):
        self.service = VolumeUIService()

    def _build_app(self):
        app = type("App", (), {})()
        app.window = pg.Surface((240, 240), pg.SRCALPHA)
        app._vol_track_top = 20
        app._vol_track_bottom = 180
        app._vol_track_x = 50
        app._vol_slider_rect = pg.Rect(20, 10, 72, 200)
        app.volume_level = 0.5
        app.tooltip_font = pg.font.Font(None, 18)
        app.combat_ui_font = pg.font.Font(None, 18)
        app._font = lambda *_args, **_kwargs: pg.font.Font(None, 14)
        return app

    def test_update_volume_from_y_clamps(self):
        app = self._build_app()

        vol_top = self.service.calculate_volume_from_y(
            y=-999,
            ty_top=app._vol_track_top,
            ty_bot=app._vol_track_bottom,
        )
        self.assertEqual(vol_top, 1.0)

        vol_bottom = self.service.calculate_volume_from_y(
            y=999,
            ty_top=app._vol_track_top,
            ty_bot=app._vol_track_bottom,
        )
        self.assertEqual(vol_bottom, 0.0)

    def test_draw_and_render_no_crash(self):
        app = self._build_app()

        self.service.draw_speaker_icon(app.window, cx=100, cy=100, radius=14)
        self.service.render_volume_slider(
            window=app.window,
            slider_rect=app._vol_slider_rect,
            track_x=app._vol_track_x,
            track_top=app._vol_track_top,
            track_bottom=app._vol_track_bottom,
            volume_level=app.volume_level,
            font_loader=app._font,
            tooltip_font=app.tooltip_font,
            combat_ui_font=app.combat_ui_font,
        )

        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
