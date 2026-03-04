import unittest

import pygame as pg

from src.core.help_overlay_render_service import HelpOverlayRenderService


class HelpOverlayRenderServiceMinimalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()

    @classmethod
    def tearDownClass(cls):
        pg.quit()

    def setUp(self) -> None:
        self.service = HelpOverlayRenderService()

    def _make_app(self):
        class _LoadService:
            def __init__(self):
                self.started = False

            def load_help_rule_surfaces(self, **_kwargs):
                return ([pg.Surface((64, 64), pg.SRCALPHA)], False)

            def start_help_rule_load(self, *, has_surfaces, is_loading, load_target):
                self.started = (not has_surfaces) and (not is_loading)
                if self.started:
                    load_target()
                return self.started

        class _App:
            pass

        app = _App()
        app.window = pg.Surface((800, 600), pg.SRCALPHA)
        app.screen_width = 800
        app.screen_height = 600
        app.help_overlay_visible = True
        app.help_current_page = 0
        app._help_rule_surfaces = [pg.Surface((320, 200), pg.SRCALPHA)]
        app._help_overlay_content_rect = None
        app._help_prev_btn = None
        app._help_next_btn = None
        app._help_load_anim_frame = 0
        app._help_rule_loading = False
        app._help_rule_load_failed = False
        app._help_mask_cache_key = None
        app._help_mask_cache_surface = None
        app._help_scaled_slide_cache_key = None
        app._help_scaled_slide_cache_surface = None
        app._font = lambda _filename, size: pg.font.Font(None, size)
        app.help_rule_load_service = _LoadService()
        app.settings = type("S", (), {"graphics_dir": "."})
        return app

    def test_render_help_overlay_builds_cache_and_nav_rects(self) -> None:
        app = self._make_app()

        self.service.render_help_overlay(app)
        first_scaled = app._help_scaled_slide_cache_surface
        self.assertIsNotNone(first_scaled)
        self.assertIsNotNone(app._help_prev_btn)
        self.assertIsNotNone(app._help_next_btn)

        self.service.render_help_overlay(app)
        self.assertIs(first_scaled, app._help_scaled_slide_cache_surface)

    def test_start_help_rule_load_delegates_and_sets_loading_state(self) -> None:
        app = self._make_app()
        app._help_rule_surfaces = []

        self.service.start_help_rule_load(app)

        self.assertTrue(app._help_rule_loading)
        self.assertTrue(bool(app._help_rule_surfaces))


if __name__ == "__main__":
    unittest.main()
