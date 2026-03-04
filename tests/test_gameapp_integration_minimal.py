import unittest
from unittest.mock import patch

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

    def test_card_play_methods_delegate_to_service(self) -> None:
        called = {"play": 0, "effect": 0, "apply": 0, "cancel": 0}
        self.app.card_manager = type("_CardMgr", (), {"use_card": lambda self, _cid: None})()
        self.app.player_country = "SHU"

        self.app.card_play_service.play_selected_card = (
            lambda app: called.__setitem__("play", called["play"] + 1)
        )
        self.app.card_play_service.apply_card_effect_with_context = (
            lambda _ctx, _cid, _def: called.__setitem__("effect", called["effect"] + 1)
        )
        self.app.card_play_service.apply_card_to_province = (
            lambda app, _cid, _pid: called.__setitem__("apply", called["apply"] + 1) or True
        )
        self.app.card_play_service.cancel_card_target_selection_with_context = (
            lambda _ctx: called.__setitem__("cancel", called["cancel"] + 1)
        )

        self.app._play_selected_card()
        self.app._apply_card_effect("x", object())
        self.app._apply_card_to_province("x", 1)
        self.app._cancel_card_target_selection()

        self.assertEqual(called, {"play": 1, "effect": 1, "apply": 1, "cancel": 1})

    def test_event_card_methods_delegate_to_service(self) -> None:
        called = {
            "trigger": 0,
            "confirm": 0,
            "unit": 0,
            "prov": 0,
            "enter": 0,
            "exit": 0,
            "check": 0,
        }

        self.app.event_card_service.trigger_draw_event_card = (
            lambda _app, _country: called.__setitem__("trigger", called["trigger"] + 1)
        )
        self.app.event_card_service.confirm_event_card_with_context = (
            lambda _ctx: called.__setitem__("confirm", called["confirm"] + 1)
        )
        self.app.event_card_service.apply_evt_target_unit_with_context = (
            lambda _ctx, _pid, _slot: called.__setitem__("unit", called["unit"] + 1)
        )
        self.app.event_card_service.apply_evt_target_province_with_context = (
            lambda _ctx, _pid: called.__setitem__("prov", called["prov"] + 1)
        )
        self.app.event_card_service.enter_evt_draw_phase_if_needed_with_context = (
            lambda _ctx: called.__setitem__("enter", called["enter"] + 1)
        )
        self.app.event_card_service.exit_evt_draw_phase_with_context = (
            lambda _ctx: called.__setitem__("exit", called["exit"] + 1)
        )
        self.app.event_card_service.check_evt_draw_phase_pp_with_context = (
            lambda _ctx: called.__setitem__("check", called["check"] + 1)
        )

        self.app._trigger_draw_event_card("SHU")
        self.app._confirm_event_card()
        self.app._apply_evt_target_unit(1, 0)
        self.app._apply_evt_target_province(1)
        self.app._enter_evt_draw_phase_if_needed()
        self.app._exit_evt_draw_phase()
        self.app._check_evt_draw_phase_pp()

        self.assertEqual(
            called,
            {
                "trigger": 1,
                "confirm": 1,
                "unit": 1,
                "prov": 1,
                "enter": 1,
                "exit": 1,
                "check": 1,
            },
        )

    def test_turn_start_and_major_round_status_methods_delegate_to_service(self) -> None:
        called = {
            "start": 0,
            "major_start": 0,
            "major_apply": 0,
            "end_round": 0,
            "remove": 0,
            "refresh": 0,
        }

        self.app.turn_start_orchestration_service.start_turn_based_game = (
            lambda app, _human: called.__setitem__("start", called["start"] + 1)
        )
        self.app.turn_start_orchestration_service.start_major_round_choice_phase_with_context = (
            lambda _ctx: called.__setitem__("major_start", called["major_start"] + 1)
        )
        self.app.turn_start_orchestration_service.apply_major_round_choice_with_context = (
            lambda _ctx, _c, _k: called.__setitem__("major_apply", called["major_apply"] + 1)
        )
        self.app.turn_start_orchestration_service.end_full_round_with_context = (
            lambda _ctx: called.__setitem__("end_round", called["end_round"] + 1)
        )
        self.app.major_round_status_service.remove_from_major_round_with_context = (
            lambda _ctx, _name, _country=None: called.__setitem__("remove", called["remove"] + 1)
        )
        self.app.major_round_status_service.refresh_session_skill_display_with_context = (
            lambda _ctx: called.__setitem__("refresh", called["refresh"] + 1)
        )

        self.app._start_turn_based_game("SHU")
        self.app._start_major_round_choice_phase()
        self.app._apply_major_round_choice("SHU", "support")
        self.app._end_full_round()
        self.app._remove_from_major_round("隆中定计", "SHU")
        self.app._refresh_session_skill_display()

        self.assertEqual(
            called,
            {
                "start": 1,
                "major_start": 1,
                "major_apply": 1,
                "end_round": 1,
                "remove": 1,
                "refresh": 1,
            },
        )

    def test_turn_orchestration_methods_delegate_to_service(self) -> None:
        called = {"clear": 0, "advance": 0, "finish": 0, "victory": 0}

        self.app.turn_orchestration_service.clear_for_turn_switch_with_context = (
            lambda _ctx, **_kwargs: called.__setitem__("clear", called["clear"] + 1)
        )
        self.app.turn_orchestration_service.advance_country_turn_with_context = (
            lambda _ctx, **_kwargs: called.__setitem__("advance", called["advance"] + 1)
        )
        self.app.turn_orchestration_service.finish_country_action_with_context = (
            lambda _ctx, _name, **_kwargs: called.__setitem__("finish", called["finish"] + 1)
        )
        self.app.turn_orchestration_service.check_tianxia_guixin_victory_with_context = (
            lambda _ctx: called.__setitem__("victory", called["victory"] + 1)
        )

        self.app._clear_for_turn_switch()
        self.app._advance_country_turn()
        self.app._finish_country_action("移动")
        self.app._check_tianxia_guixin_victory()

        self.assertEqual(called, {"clear": 1, "advance": 1, "finish": 1, "victory": 1})

    def test_ai_event_target_method_delegates_to_service_context(self) -> None:
        called = {"auto": 0}

        self.app.ai_service.auto_select_evt_target_with_context = (
            lambda _ctx, _country: called.__setitem__("auto", called["auto"] + 1)
        )

        self.app._ai_auto_select_evt_target("SHU")

        self.assertEqual(called, {"auto": 1})

    def test_run_ai_turn_method_delegates_to_service_context(self) -> None:
        called = {"run": 0}

        self.app.ai_service.run_turn_with_context = (
            lambda _ctx: called.__setitem__("run", called["run"] + 1)
        )

        self.app._run_ai_turn()

        self.assertEqual(called, {"run": 1})

    def test_selection_presentation_methods_delegate_to_service(self) -> None:
        called = {"abbr": 0, "format": 0, "update": 0}

        self.app.selection_presentation_service.get_unit_abbr = (
            lambda _unit_type: called.__setitem__("abbr", called["abbr"] + 1) or "步"
        )
        self.app.selection_presentation_service.format_unit_info = (
            lambda app, _u, prefix="", province_id=None: (
                called.__setitem__("format", called["format"] + 1) or "ok"
            )
        )
        self.app.selection_presentation_service.update_selection_info = (
            lambda app: called.__setitem__("update", called["update"] + 1)
        )

        abbr = self.app._get_unit_abbr("infantry")
        info = self.app._format_unit_info(object(), province_id=1)
        self.app._update_selection_info()

        self.assertEqual(abbr, "步")
        self.assertEqual(info, "ok")
        self.assertEqual(called, {"abbr": 1, "format": 1, "update": 1})

    def test_turn_resource_methods_delegate_to_service(self) -> None:
        called = {
            "support": 0,
            "confused": 0,
            "special": 0,
            "heal_cost": 0,
            "total_pp": 0,
            "can_use": 0,
            "ai_cure": 0,
            "replenish": 0,
        }

        self.app.turn_resource_service.get_people_support_level = (
            lambda _stats, _country: called.__setitem__("support", called["support"] + 1)
            or 7
        )
        self.app.turn_resource_service.has_confused_units_for_country = (
            lambda _provinces, _country: called.__setitem__("confused", called["confused"] + 1)
            or True
        )
        self.app.turn_resource_service.is_special_unit = (
            lambda _unit: called.__setitem__("special", called["special"] + 1) or True
        )
        self.app.turn_resource_service.get_pp_heal_cost = (
            lambda _unit: called.__setitem__("heal_cost", called["heal_cost"] + 1)
            or 2
        )
        self.app.turn_resource_service.get_total_pp = (
            lambda _stats, _temp_pp, _country: called.__setitem__("total_pp", called["total_pp"] + 1)
            or 3
        )
        self.app.turn_resource_service.pp_can_use = (
            lambda _stats, _temp_pp, _country: called.__setitem__("can_use", called["can_use"] + 1)
            or True
        )
        self.app.turn_resource_service.ai_cure_confused_unit = (
            lambda _provinces, _country: called.__setitem__("ai_cure", called["ai_cure"] + 1)
            or True
        )
        self.app.turn_resource_service.replenish_action_points = (
            lambda _provinces, _unit_repo: called.__setitem__("replenish", called["replenish"] + 1)
        )

        self.assertEqual(self.app._get_people_support_level("SHU"), 7)
        self.assertTrue(self.app._has_confused_units_for_country("SHU"))
        self.assertTrue(self.app._is_special_unit(object()))
        self.assertEqual(self.app._get_pp_heal_cost(object()), 2)
        self.assertEqual(self.app._get_total_pp("SHU"), 3)
        self.assertTrue(self.app._pp_can_use("SHU"))
        self.assertTrue(self.app._ai_cure_confused_unit("SHU"))
        self.app._replenish_action_points()

        self.assertEqual(
            called,
            {
                "support": 1,
                "confused": 1,
                "special": 1,
                "heal_cost": 1,
                "total_pp": 1,
                "can_use": 1,
                "ai_cure": 1,
                "replenish": 1,
            },
        )

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

        # 右键路径：未阻断时应分发到输入服务右键上下文入口
        called = {"n": 0}
        self.app.playing_input_service.handle_right_click_with_context = (
            lambda **_kwargs: called.__setitem__("n", called["n"] + 1) or True
        )
        self.app.major_round_choice_pending = False
        self.app.evt_draw_phase = False
        self.app.selecting_evt_target = False
        self.app.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 3, "pos": (100, 100)}))
        self.assertEqual(called["n"], 1)

        # 右键路径：阻断时不应调用右键处理入口
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

    def test_render_gameplay_uses_single_logical_mouse_query_per_frame(self) -> None:
        self.app._start_turn_based_game("SHU")
        self.app.state = GameState.PLAYING

        # 隔离与本优化无关的末端tooltip路径，避免额外读取鼠标坐标
        self.app._render_volume_slider = lambda: None
        self.app._draw_country_stats_overlay = lambda: None
        self.app._render_draw_event_btn = lambda: None
        self.app._render_pp_summon_panel = lambda: None
        self.app._render_event_card_overlay = lambda: None
        self.app._draw_hover_tooltip = lambda: None
        self.app._draw_evt_info_tooltip = lambda: None
        self.app._render_help_overlay = lambda: None
        if self.app.card_panel:
            self.app.card_panel.draw = lambda _surface: None
            self.app.card_panel.draw_tooltip = lambda _surface: None

        original = self.app._get_logical_mouse_pos
        called = {"n": 0}

        def _counted_mouse_pos():
            called["n"] += 1
            return original()

        self.app._get_logical_mouse_pos = _counted_mouse_pos
        self.app._render_gameplay()

        self.assertEqual(called["n"], 1)

    def test_render_gameplay_caches_river_ban_layer_between_frames(self) -> None:
        self.app._start_turn_based_game("SHU")
        self.app.state = GameState.PLAYING

        called = {"n": 0}
        original = self.app.polyline_render_service.draw_smooth_polyline

        def _counted_draw(**kwargs):
            called["n"] += 1
            return original(**kwargs)

        self.app.polyline_render_service.draw_smooth_polyline = _counted_draw

        self.app._render_gameplay()
        first_frame_calls = called["n"]
        self.assertGreater(first_frame_calls, 0)

        self.app._render_gameplay()
        self.assertEqual(called["n"], first_frame_calls)

    def test_help_overlay_mask_cache_hit(self) -> None:
        self.app.help_overlay_visible = True
        self.app._help_rule_surfaces = [pg.Surface((320, 200), pg.SRCALPHA)]
        self.app.help_current_page = 0

        self.app._render_help_overlay()
        first_mask = self.app._help_mask_cache_surface
        self.assertIsNotNone(first_mask)

        self.app._render_help_overlay()
        self.assertIs(first_mask, self.app._help_mask_cache_surface)

    def test_help_overlay_scaled_slide_cache_hit_and_resize_invalidate(self) -> None:
        self.app.help_overlay_visible = True
        self.app._help_rule_surfaces = [pg.Surface((320, 200), pg.SRCALPHA)]
        self.app.help_current_page = 0

        smoothscale_calls = {"n": 0}
        original = pg.transform.smoothscale

        def _counted_smoothscale(*args, **kwargs):
            smoothscale_calls["n"] += 1
            return original(*args, **kwargs)

        with patch(
            "src.core.help_overlay_render_service.pg.transform.smoothscale",
            side_effect=_counted_smoothscale,
        ):
            self.app._render_help_overlay()
            first_calls = smoothscale_calls["n"]
            self.assertGreater(first_calls, 0)

            self.app._render_help_overlay()
            self.assertEqual(smoothscale_calls["n"], first_calls)

            # 逻辑分辨率变化 -> 目标尺寸变化 -> 缩放缓存应失效重建
            self.app.screen_width += 37
            self.app.screen_height += 19
            self.app.window = pg.Surface((self.app.screen_width, self.app.screen_height)).convert()
            self.app._render_help_overlay()
            self.assertGreater(smoothscale_calls["n"], first_calls)

    def test_score_screen_cache_hit(self) -> None:
        self.app._start_turn_based_game("SHU")
        self.app._show_score_screen("wei_turn")

        original_font = self.app._font
        font_calls = {"n": 0}

        def _counted_font(*args, **kwargs):
            font_calls["n"] += 1
            return original_font(*args, **kwargs)

        self.app._font = _counted_font
        self.app._render_score_screen()
        first_calls = font_calls["n"]
        self.assertGreater(first_calls, 0)

        self.app._render_score_screen()
        self.assertEqual(font_calls["n"], first_calls)

    def test_score_screen_cache_invalidate_on_content_change(self) -> None:
        self.app._start_turn_based_game("SHU")
        self.app._show_score_screen("wei_turn")
        self.app._render_score_screen()
        first_cache = self.app._score_screen_cache_surface
        self.assertIsNotNone(first_cache)

        self.app.show_score_screen["net_scores"]["SHU"] += 1
        self.app._render_score_screen()
        self.assertIsNot(first_cache, self.app._score_screen_cache_surface)

    def test_score_screen_cache_invalidate_on_resize(self) -> None:
        self.app._start_turn_based_game("SHU")
        self.app._show_score_screen("wei_turn")
        self.app._render_score_screen()
        first_cache = self.app._score_screen_cache_surface
        self.assertIsNotNone(first_cache)

        self.app.screen_width += 64
        self.app.screen_height += 32
        self.app.window = pg.Surface((self.app.screen_width, self.app.screen_height)).convert()
        self.app._render_score_screen()
        self.assertIsNot(first_cache, self.app._score_screen_cache_surface)


if __name__ == "__main__":
    unittest.main()
