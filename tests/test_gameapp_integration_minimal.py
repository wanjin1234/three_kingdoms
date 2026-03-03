import unittest

import pygame as pg

from settings import SETTINGS
from src.core.app import GameApp, GameState


class GameAppIntegrationMinimalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = GameApp(settings=SETTINGS, debug=False)

    def tearDown(self) -> None:
        try:
            self.app.stop()
        except Exception:
            pass

    def test_init_has_critical_runtime_fields(self) -> None:
        # 防止再次出现 clear_selection 时缺字段崩溃
        self.assertTrue(hasattr(self.app, "selected_units"))
        self.assertIsInstance(self.app.selected_units, list)
        # 重构后关键服务字段也应存在
        self.assertTrue(hasattr(self.app, "combat_flow_service"))
        self.assertTrue(hasattr(self.app, "combat_resolution_service"))
        self.assertTrue(hasattr(self.app, "gameplay_render_service"))
        # 阶段1状态模型字段
        self.assertTrue(hasattr(self.app, "turn_state"))
        self.assertTrue(hasattr(self.app, "ui_state"))
        self.assertTrue(hasattr(self.app, "combat_state"))
        self.assertTrue(hasattr(self.app, "event_card_state"))

    def test_state_models_proxy_same_underlying_fields(self) -> None:
        self.app.turn_state.major_round = 3
        self.app.ui_state.volume_level = 0.4
        self.app.combat_state.show_combat_ui = True
        self.app.event_card_state.evt_draw_phase = True

        self.assertEqual(self.app.major_round, 3)
        self.assertEqual(self.app.volume_level, 0.4)
        self.assertTrue(self.app.show_combat_ui)
        self.assertTrue(self.app.evt_draw_phase)

    def test_choosing_click_enters_playing_without_attribute_error(self) -> None:
        self.app.state = GameState.CHOOSING
        pos = self.app.faction_buttons["SHU"]["center"]
        ev = pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 1, "pos": pos})

        self.app.handle_event(ev)

        self.assertEqual(self.app.state, GameState.PLAYING)
        self.assertTrue(hasattr(self.app, "selected_units"))

    def test_render_gameplay_delegates_to_service(self) -> None:
        called = {"ok": False}

        def _stub(app):
            called["ok"] = True

        self.app.gameplay_render_service.render_gameplay = _stub
        self.app._render_gameplay()
        self.assertTrue(called["ok"])

    def test_playing_interactions_smoke_no_attribute_error(self) -> None:
        self.app._start_turn_based_game("SHU")
        self.app.state = GameState.PLAYING

        # 覆盖真实渲染路径（包含 hover tooltip/事件信息 tooltip 调用链）
        self.app._render_gameplay()

        # 模拟玩家常见操作：移动鼠标、左键、右键
        self.app.handle_event(pg.event.Event(pg.MOUSEMOTION, {"pos": (100, 100)}))
        self.app.handle_event(
            pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 1, "pos": (100, 100)})
        )
        self.app.handle_event(
            pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 3, "pos": (100, 100)})
        )

        # 只要没抛异常就算通过；补一条状态断言确保对象仍有效
        self.assertEqual(self.app.state, GameState.PLAYING)


if __name__ == "__main__":
    unittest.main()
