import unittest

from src.core.screen_render_service import ScreenRenderService


class ScreenRenderServiceMinimalTest(unittest.TestCase):
    def setUp(self):
        self.service = ScreenRenderService()

    def test_calc_console_bar_height(self):
        self.assertEqual(self.service.calc_console_bar_height(200), 32)
        self.assertEqual(self.service.calc_console_bar_height(1000), 48)

    def test_should_render_console(self):
        app = type("App", (), {"console_visible": True})()
        self.assertTrue(self.service.should_render_console(app))

    def test_render_main_scene_routes_by_state(self):
        app = type("App", (), {})()
        app.show_score_screen = False
        state = type("State", (), {})()
        type(state).LOADING = state
        type(state).MODE_SELECT = object()
        type(state).CHOOSING = object()
        app.state = state
        calls = {"loading": 0, "mode": 0, "choosing": 0, "gameplay": 0, "score": 0}
        app._render_loading_screen = lambda: calls.__setitem__("loading", calls["loading"] + 1)
        app._render_mode_select_screen = lambda: calls.__setitem__("mode", calls["mode"] + 1)
        app._render_choosing_screen = lambda: calls.__setitem__("choosing", calls["choosing"] + 1)
        app._render_gameplay = lambda: calls.__setitem__("gameplay", calls["gameplay"] + 1)
        app._render_score_screen = lambda: calls.__setitem__("score", calls["score"] + 1)

        self.service.render_main_scene(app)

        self.assertEqual(calls["loading"], 1)
        self.assertEqual(calls["score"], 0)

    def test_render_main_scene_prefers_score_screen(self):
        app = type("App", (), {})()
        app.show_score_screen = True
        app.state = object()
        calls = {"score": 0, "gameplay": 0}
        app._render_score_screen = lambda: calls.__setitem__("score", calls["score"] + 1)
        app._render_loading_screen = lambda: None
        app._render_mode_select_screen = lambda: None
        app._render_choosing_screen = lambda: None
        app._render_gameplay = lambda: calls.__setitem__("gameplay", calls["gameplay"] + 1)

        self.service.render_main_scene(app)

        self.assertEqual(calls["score"], 1)
        self.assertEqual(calls["gameplay"], 0)

    def test_render_top_overlays_calls_fullscreen_and_console(self):
        app = type("App", (), {})()
        calls = {"full": 0, "console": 0}
        app._draw_global_fullscreen_btn = lambda: calls.__setitem__("full", calls["full"] + 1)
        app._render_console = lambda: calls.__setitem__("console", calls["console"] + 1)

        self.service.render_top_overlays(app)

        self.assertEqual(calls["full"], 1)
        self.assertEqual(calls["console"], 1)


if __name__ == "__main__":
    unittest.main()
