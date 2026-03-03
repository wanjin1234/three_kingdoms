import unittest

import pygame as pg

from settings import SETTINGS
from src.core.app import GameApp, GameState


class ArchPhase0SmokeMinimalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = GameApp(settings=SETTINGS, debug=False)

    def tearDown(self) -> None:
        try:
            self.app.stop()
        except Exception:
            pass

    def test_playing_runtime_smoke_path(self) -> None:
        # 进入对局
        self.app._start_turn_based_game("SHU")
        self.app.state = GameState.PLAYING

        # 渲染主战场
        self.app._render_gameplay()

        # 高频交互：鼠标移动 + 左键 + 右键
        self.app.handle_event(pg.event.Event(pg.MOUSEMOTION, {"pos": (120, 120)}))
        self.app.handle_event(
            pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 1, "pos": (120, 120)})
        )
        self.app.handle_event(
            pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 3, "pos": (120, 120)})
        )

        # 帮助覆盖层路径
        self.app.help_overlay_visible = True
        self.app._render_help_overlay()

        # 新抽离能力路径
        _ = self.app._get_map_bounds_rect()
        self.app._draw_smooth_polyline(
            pg.Color("blue"),
            [pg.math.Vector2(10, 10), pg.math.Vector2(20, 20)],
            4,
        )

        self.assertEqual(self.app.state, GameState.PLAYING)


if __name__ == "__main__":
    unittest.main()
