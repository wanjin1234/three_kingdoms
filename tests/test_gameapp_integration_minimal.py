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

        def _stub(app, view_model=None):
            called["ok"] = True
            self.assertIsNotNone(view_model)

        self.app.gameplay_render_service.render_gameplay = _stub
        self.app._render_gameplay()
        self.assertTrue(called["ok"])

    def test_asset_build_methods_delegate_to_service(self) -> None:
        called = {"mode": 0, "loading": 0, "choosing": 0, "play": 0}

        self.app.asset_build_service.build_mode_select_assets = (
            lambda app: called.__setitem__("mode", called["mode"] + 1)
        )
        self.app.asset_build_service.build_loading_assets = (
            lambda app: called.__setitem__("loading", called["loading"] + 1)
        )
        self.app.asset_build_service.build_choosing_assets = (
            lambda app: called.__setitem__("choosing", called["choosing"] + 1)
        )
        self.app.asset_build_service.build_play_assets = (
            lambda app, **kwargs: called.__setitem__("play", called["play"] + 1)
        )

        self.app._build_mode_select_assets()
        self.app._build_loading_assets()
        self.app._build_choosing_assets()
        self.app._build_play_assets()

        self.assertEqual(called, {"mode": 1, "loading": 1, "choosing": 1, "play": 1})

    def test_execute_playing_input_commands_delegates_to_service(self) -> None:
        called = {"n": 0}
        self.app.playing_command_service.execute = (
            lambda **kwargs: called.__setitem__("n", called["n"] + 1)
        )

        self.app._execute_playing_input_commands([], on_show_message=None)

        self.assertEqual(called["n"], 1)

    def test_restart_game_delegates_to_service(self) -> None:
        called = {"n": 0}
        self.app.game_reset_service.restart_game = (
            lambda *args, **kwargs: called.__setitem__("n", called["n"] + 1)
        )

        self.app._restart_game()

        self.assertEqual(called["n"], 1)

    def test_handle_playing_event_delegates_to_service(self) -> None:
        called = {"n": 0}
        self.app.playing_event_orchestrator_service.handle_playing_event = (
            lambda *args, **kwargs: called.__setitem__("n", called["n"] + 1)
        )

        self.app._handle_playing_event(pg.event.Event(pg.NOEVENT, {}))

        self.assertEqual(called["n"], 1)

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

    def test_playing_event_command_paths_simulation(self) -> None:
        self.app._start_turn_based_game("SHU")
        self.app.state = GameState.PLAYING

        logs: list[str] = []
        if self.app.info_panel:
            self.app.info_panel.show_message = lambda msg, **kwargs: logs.append(str(msg))

        # 右键路径：未阻断时应分发到 _handle_game_right_click
        called = {"n": 0}
        self.app._handle_game_right_click = lambda _pos: called.__setitem__("n", called["n"] + 1)
        self.app.major_round_choice_pending = False
        self.app.evt_draw_phase = False
        self.app.selecting_evt_target = False
        self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 3, "pos": (100, 100)}))
        self.assertEqual(called["n"], 1)

        # 右键路径：阻断时不应调用 _handle_game_right_click
        self.app.major_round_choice_pending = True
        self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 3, "pos": (100, 100)}))
        self.assertEqual(called["n"], 1)
        self.assertTrue(any("请先完成三国大回合加点选择" in m for m in logs))
        self.app.major_round_choice_pending = False

        # 键盘命令化路径：ESC 关闭帮助
        self.app.help_overlay_visible = True
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, {"key": pg.K_ESCAPE}))
        self.assertFalse(self.app.help_overlay_visible)

        # ESC 取消PP召唤子状态
        self.app.pp_spend_mode = True
        self.app.pp_summon_target_prov = object()
        self.app.pp_summon_btns = [object()]
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, {"key": pg.K_ESCAPE}))
        self.assertIsNone(self.app.pp_summon_target_prov)
        self.assertEqual(self.app.pp_summon_btns, [])
        # 再按一次 ESC 退出 PP 模式（ESC 处理优先级高于卡牌目标模式）
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, {"key": pg.K_ESCAPE}))
        self.assertFalse(self.app.pp_spend_mode)

        # ESC 取消卡牌目标选择
        self.app.selecting_card_target = True
        self.app.selected_card_for_effect = "card_demo"
        self.app.handle_event(pg.event.Event(pg.KEYDOWN, {"key": pg.K_ESCAPE}))
        self.assertFalse(self.app.selecting_card_target)
        self.assertIsNone(self.app.selected_card_for_effect)

    def test_deep_simulated_operation_sequence(self) -> None:
        self.app._start_turn_based_game("SHU")
        self.app.state = GameState.PLAYING

        # 先渲染一帧，确保按钮与覆盖层相关矩形初始化
        self.app._render_gameplay()

        # 模拟帮助按钮点击 -> 打开覆盖层
        help_btn = next(b for b in self.app.control_btns if b["action"] == "HELP")
        self.app.handle_event(
            pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 1, "pos": help_btn["rect"].center})
        )
        self.assertTrue(self.app.help_overlay_visible)

        # 模拟帮助覆盖层翻页与外部点击关闭
        self.app._help_rule_surfaces = [object(), object(), object()]
        self.app.help_current_page = 1
        self.app._help_prev_btn = pg.Rect(10, 10, 40, 40)
        self.app._help_next_btn = pg.Rect(60, 10, 40, 40)
        self.app._help_overlay_content_rect = pg.Rect(0, 0, 200, 200)

        self.app.handle_event(pg.event.Event(pg.MOUSEWHEEL, {"x": 0, "y": -1}))
        self.assertEqual(self.app.help_current_page, 2)

        # 点击覆盖层外部关闭
        self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 1, "pos": (500, 500)}))
        self.assertFalse(self.app.help_overlay_visible)

        # 混合输入序列：鼠标移动、左键、右键，验证主循环关键路径稳定
        self.app.handle_event(pg.event.Event(pg.MOUSEMOTION, {"pos": (120, 120)}))
        self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 1, "pos": (120, 120)}))
        self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 3, "pos": (140, 140)}))

        self.assertEqual(self.app.state, GameState.PLAYING)


if __name__ == "__main__":
    unittest.main()
