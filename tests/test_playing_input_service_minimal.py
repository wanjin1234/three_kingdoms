import unittest

import pygame as pg

from src.core.app_contexts import LeftClickContext, RightClickContext
from src.core.playing_input_service import PlayingInputService


class PlayingInputServiceMinimalTest(unittest.TestCase):
    def setUp(self):
        self.service = PlayingInputService()

    def test_handle_help_overlay_wheel_consumes_and_turns_page(self):
        app = type("App", (), {})()
        app.help_overlay_visible = True
        app._help_rule_surfaces = [object(), object(), object()]
        app.help_current_page = 1

        event = pg.event.Event(pg.MOUSEWHEEL, {"x": 0, "y": 1})
        consumed = self.service.handle_help_overlay_wheel(
            event=event,
            help_overlay_visible=app.help_overlay_visible,
            help_rule_surfaces=app._help_rule_surfaces,
            help_current_page=app.help_current_page,
            ctrl_held=False,
            on_set_help_current_page=lambda page: setattr(app, "help_current_page", page),
        )

        self.assertTrue(consumed)
        self.assertEqual(app.help_current_page, 0)

    def test_handle_help_overlay_wheel_ctrl_zooms(self):
        app = type("App", (), {})()
        app.help_overlay_visible = True
        app._help_rule_surfaces = [object()]
        app.help_current_page = 0
        app.help_zoom_factor = 1.0

        event = pg.event.Event(pg.MOUSEWHEEL, {"x": 0, "y": 1})
        self.service.handle_help_overlay_wheel(
            event=event,
            help_overlay_visible=app.help_overlay_visible,
            help_rule_surfaces=app._help_rule_surfaces,
            help_current_page=app.help_current_page,
            help_zoom_factor=app.help_zoom_factor,
            ctrl_held=True,
            on_set_help_current_page=lambda page: setattr(app, "help_current_page", page),
            on_set_help_zoom_factor=lambda z: setattr(app, "help_zoom_factor", z),
        )

        # 页码不应变，缩放应增加
        self.assertEqual(app.help_current_page, 0)
        self.assertGreater(app.help_zoom_factor, 1.0)

    def test_handle_help_overlay_click_outside_closes(self):
        app = type("App", (), {})()
        app.help_overlay_visible = True
        app._help_rule_surfaces = [object()]
        app.help_current_page = 0
        app._help_prev_btn = None
        app._help_next_btn = None
        app._help_overlay_content_rect = pg.Rect(100, 100, 50, 50)

        event = pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 1, "pos": (10, 10)})
        consumed = self.service.handle_help_overlay_click(
            event=event,
            help_overlay_visible=app.help_overlay_visible,
            help_rule_surfaces=app._help_rule_surfaces,
            help_current_page=app.help_current_page,
            help_prev_btn=app._help_prev_btn,
            help_next_btn=app._help_next_btn,
            help_overlay_content_rect=app._help_overlay_content_rect,
            on_set_help_current_page=lambda page: setattr(app, "help_current_page", page),
            on_set_help_overlay_visible=lambda v: setattr(app, "help_overlay_visible", v),
        )

        self.assertTrue(consumed)
        self.assertFalse(app.help_overlay_visible)

    def test_handle_control_button_click_help_toggle(self):
        app = type("App", (), {})()
        app.control_btns = [{"rect": pg.Rect(0, 0, 20, 20), "action": "HELP"}]
        app.help_overlay_visible = False
        app.help_current_page = 3
        called = {"load": 0}
        app._start_help_rule_load = lambda: called.__setitem__("load", called["load"] + 1)

        consumed = self.service.handle_control_button_click(
            control_btns=app.control_btns,
            pos=(10, 10),
            state=type("S", (), {"PLAYING": "PLAYING"})().PLAYING,
            on_stop=lambda: None,
            on_restart_game=lambda: None,
            on_show_score_screen=lambda _t: None,
            volume_slider_visible=False,
            on_set_volume_slider_visible=lambda v: setattr(app, "volume_slider_visible", v),
            help_overlay_visible=app.help_overlay_visible,
            on_set_help_overlay_visible=lambda v: setattr(app, "help_overlay_visible", v),
            on_set_help_current_page=lambda page: setattr(app, "help_current_page", page),
            on_start_help_rule_load=app._start_help_rule_load,
        )

        self.assertTrue(consumed)
        self.assertTrue(app.help_overlay_visible)
        self.assertEqual(app.help_current_page, 0)
        self.assertEqual(called["load"], 1)

    def test_handle_major_round_choice_click_support(self):
        app = type("App", (), {})()
        app.major_round_choice_pending = True
        app.country_stat_choice_btns = {
            "SHU": {
                "support": pg.Rect(0, 0, 20, 20),
                "politics": pg.Rect(30, 0, 20, 20),
            }
        }
        called = []
        app._apply_major_round_choice = lambda c, k: called.append((c, k))
        app.info_panel = None

        consumed = self.service.handle_major_round_choice_click(
            major_round_choice_pending=app.major_round_choice_pending,
            country_stat_choice_btns=app.country_stat_choice_btns,
            pos=(10, 10),
            on_apply_major_round_choice=app._apply_major_round_choice,
            on_show_message=(
                lambda msg: app.info_panel.show_message(msg) if app.info_panel else None
            ),
        )

        self.assertTrue(consumed)
        self.assertEqual(called, [("SHU", "support")])

    def test_handle_evt_draw_phase_click_draw_then_check(self):
        app = type("App", (), {})()
        app.evt_draw_phase = True
        app.selecting_evt_target = False
        app.evt_skip_draw_btn_rect = pg.Rect(0, 0, 20, 20)
        app.draw_event_btn_rect = pg.Rect(30, 0, 20, 20)
        app.player_country = "SHU"
        app.event_card_overlay = None
        called = {"draw": 0, "check": 0}
        app._trigger_draw_event_card = (
            lambda country: called.__setitem__("draw", called["draw"] + 1)
        )
        app._check_evt_draw_phase_pp = (
            lambda: called.__setitem__("check", called["check"] + 1)
        )
        app._exit_evt_draw_phase = lambda: None
        app.info_panel = None

        consumed = self.service.handle_evt_draw_phase_click(
            evt_draw_phase=app.evt_draw_phase,
            selecting_evt_target=app.selecting_evt_target,
            evt_skip_draw_btn_rect=app.evt_skip_draw_btn_rect,
            draw_event_btn_rect=app.draw_event_btn_rect,
            pos=(35, 10),
            player_country=app.player_country,
            on_exit_evt_draw_phase=app._exit_evt_draw_phase,
            on_trigger_draw_event_card=app._trigger_draw_event_card,
            has_event_card_overlay=bool(app.event_card_overlay),
            on_check_evt_draw_phase_pp=app._check_evt_draw_phase_pp,
            on_show_message=(
                lambda msg: app.info_panel.show_message(msg) if app.info_panel else None
            ),
        )

        self.assertTrue(consumed)
        self.assertEqual(called["draw"], 1)
        self.assertEqual(called["check"], 1)

    def test_handle_pp_click_entry_enable_mode(self):
        app = type("App", (), {})()
        app.pp_btn_rect = pg.Rect(0, 0, 20, 20)
        app.player_country = "SHU"
        app.pp_spend_mode = False
        app._pp_can_use = lambda _country: True
        app.info_panel = type("Info", (), {"show_message": lambda *args, **kwargs: None})()

        consumed = self.service.handle_pp_click(
            pos=(10, 10),
            pp_btn_rect=app.pp_btn_rect,
            player_country=app.player_country,
            can_use_pp=app._pp_can_use,
            pp_spend_mode=app.pp_spend_mode,
            pp_spend_end_btn_rect=None,
            pp_summon_target_prov=None,
            pp_summon_btns=[],
            evt_flag_hu_recruit=False,
            spend_pp=lambda _c, _a: True,
            unit_repository=type("Repo", (), {"get_definition": lambda *_args: None})(),
            on_invalidate_map_cache=lambda: None,
            on_record_move_dst=lambda _pid, _c, _slot: None,
            get_total_pp=lambda _c: 0,
            get_unit_slot_at=lambda _pos: None,
            get_province_by_id=lambda _pid: None,
            get_pp_heal_cost=lambda _u: 1,
            is_special_unit=lambda _u: False,
            on_finish_country_action=lambda _a: None,
            on_set_pp_spend_mode=lambda v: setattr(app, "pp_spend_mode", v),
            on_set_pp_summon_target_prov=lambda v: setattr(app, "pp_summon_target_prov", v),
            on_set_pp_summon_btns=lambda v: setattr(app, "pp_summon_btns", v),
            on_show_message=app.info_panel.show_message,
        )

        self.assertTrue(consumed)
        self.assertTrue(app.pp_spend_mode)

    def test_handle_morale_click_lv3_enable_bonus_mode(self):
        app = type("App", (), {})()
        app.morale_lv2_btn_rect = None
        app.morale_lv3_btn_rect = pg.Rect(0, 0, 20, 20)
        app.morale_lv4_btn_rect = None
        app.morale_bonus_mp_mode = False
        app.morale_cure_mode = False
        app.player_country = "SHU"
        app.major_round = 1
        app._get_unit_slot_at = lambda _pos: None
        app.map_manager = type("Map", (), {"get_by_id": lambda *_args: None})()
        app._has_confused_units_for_country = lambda _country: False
        app.morale_lv4_pending = {}
        app.morale_lv3_used = {}
        app.info_panel = type("Info", (), {"show_message": lambda *args, **kwargs: None})()

        consumed = self.service.handle_morale_click(
            pos=(10, 10),
            morale_lv2_btn_rect=app.morale_lv2_btn_rect,
            morale_lv3_btn_rect=app.morale_lv3_btn_rect,
            morale_lv4_btn_rect=app.morale_lv4_btn_rect,
            morale_bonus_mp_mode=app.morale_bonus_mp_mode,
            morale_cure_mode=app.morale_cure_mode,
            player_country=app.player_country,
            major_round=app.major_round,
            get_unit_slot_at=app._get_unit_slot_at,
            get_province_by_id=app.map_manager.get_by_id,
            has_confused_units_for_country=app._has_confused_units_for_country,
            on_set_morale_free_move_mode=lambda v: setattr(app, "morale_free_move_mode", v),
            on_set_morale_bonus_mp_mode=lambda v: setattr(app, "morale_bonus_mp_mode", v),
            on_set_morale_cure_mode=lambda v: setattr(app, "morale_cure_mode", v),
            on_clear_morale_lv4_pending=lambda country: app.morale_lv4_pending.pop(country, None),
            on_mark_morale_lv3_used=lambda country, rnd: app.morale_lv3_used.__setitem__(country, rnd),
            on_show_message=app.info_panel.show_message,
        )

        self.assertTrue(consumed)
        self.assertTrue(app.morale_bonus_mp_mode)

    def test_handle_no_attack_click_finish_action(self):
        app = type("App", (), {})()
        app.pending_post_move_attack = True
        app.no_attack_btn_rect = pg.Rect(0, 0, 20, 20)
        app.morale_free_move_mode = False
        app.info_panel = type("Info", (), {"show_message": lambda *args, **kwargs: None})()
        called = []
        app._finish_country_action = lambda action: called.append(action)

        consumed = self.service.handle_no_attack_click(
            pending_post_move_attack=app.pending_post_move_attack,
            no_attack_btn_rect=app.no_attack_btn_rect,
            pos=(10, 10),
            morale_free_move_mode=app.morale_free_move_mode,
            player_country=None,
            major_round=1,
            on_mark_morale_lv2_used=lambda _c, _r: None,
            on_set_morale_free_move_mode=lambda v: setattr(app, "morale_free_move_mode", v),
            on_set_pending_post_move_attack=lambda v: setattr(app, "pending_post_move_attack", v),
            on_set_pending_attacker=lambda a: setattr(app, "pending_attacker", a),
            on_clear_selection=lambda: None,
            on_show_message=app.info_panel.show_message,
            on_finish_country_action=app._finish_country_action,
        )

        self.assertTrue(consumed)
        self.assertEqual(called, ["移动"])

    def test_handle_combat_ui_click_combat_button(self):
        app = type("App", (), {})()
        app.show_combat_ui = True
        app.combat_btn_rect = pg.Rect(0, 0, 20, 20)
        app.defender_can_use_jiangdong = False
        app.defender_jiangdong_decided = True
        app.defender_can_hold_position = False
        app.defender_hold_decided = True
        called = []
        app.combat_callback = lambda: called.append("combat")
        app.info_panel = type("Info", (), {"show_message": lambda *args, **kwargs: None})()

        consumed = self.service.handle_combat_ui_click(
            pos=(10, 10),
            show_combat_ui=app.show_combat_ui,
            combat_btn_rect=app.combat_btn_rect,
            defender_can_use_jiangdong=app.defender_can_use_jiangdong,
            defender_jiangdong_decided=app.defender_jiangdong_decided,
            defender_can_hold_position=app.defender_can_hold_position,
            defender_hold_decided=app.defender_hold_decided,
            waiting_defender_response=False,
            defense_hold_btn_rect=None,
            defense_hold_skip_btn_rect=None,
            skip_jiangdong_card_btn_rect=None,
            player_country="SHU",
            card_managers={},
            on_set_waiting_defender_response=lambda _v: None,
            on_set_allow_jiangdong_selection=lambda _v: None,
            on_set_card_manager=lambda _m: None,
            on_update_card_panel=lambda: None,
            on_show_message=app.info_panel.show_message,
            on_set_defender_use_hold_position=lambda _v: None,
            on_set_defender_hold_decided=lambda _v: None,
            on_set_defender_use_jiangdong=lambda _v: None,
            on_set_defender_jiangdong_decided=lambda _v: None,
            combat_callback=app.combat_callback,
        )

        self.assertTrue(consumed)
        self.assertEqual(called, ["combat"])

    def test_handle_evt_target_click_unit_success(self):
        app = type("App", (), {})()
        app.selecting_evt_target = True
        app.pending_evt_card_id = "evt1"
        card_def = type("CardDef", (), {"target_type": "unit"})()
        app.event_card_deck = type(
            "Deck", (), {"get_definition": lambda _self, _cid: card_def}
        )()
        app.pending_evt_drawer = "SHU"
        app.player_country = "SHU"
        app._get_unit_slot_at = lambda _pos: (1, 0)
        app.map_manager = type(
            "Map", (), {"get_by_id": lambda _self, _pid: type("P", (), {"country": "SHU"})()}
        )()
        called = []
        app._apply_evt_target_unit = lambda pid, slot: called.append((pid, slot))
        app.country_labels = {"SHU": "蜀"}
        app.info_panel = type("Info", (), {"show_message": lambda *args, **kwargs: None})()

        consumed = self.service.handle_evt_target_click(
            selecting_evt_target=app.selecting_evt_target,
            pending_evt_card_id=app.pending_evt_card_id,
            event_card_deck=app.event_card_deck,
            pending_evt_drawer=app.pending_evt_drawer,
            player_country=app.player_country,
            pos=(10, 10),
            get_unit_slot_at=app._get_unit_slot_at,
            get_province_by_id=app.map_manager.get_by_id,
            get_province_at=lambda _pos: None,
            on_apply_evt_target_unit=app._apply_evt_target_unit,
            on_apply_evt_target_province=lambda _pid: None,
            country_labels=app.country_labels,
            on_show_message=(
                app.info_panel.show_message if app.info_panel else None
            ),
        )

        self.assertTrue(consumed)
        self.assertEqual(called, [(1, 0)])

    def test_handle_draw_event_button_click(self):
        app = type("App", (), {})()
        app.draw_event_btn_rect = pg.Rect(0, 0, 20, 20)
        app.player_country = "WEI"
        called = []
        app._trigger_draw_event_card = lambda c: called.append(c)

        consumed = self.service.handle_draw_event_button_click(
            draw_event_btn_rect=app.draw_event_btn_rect,
            pos=(10, 10),
            player_country=app.player_country,
            on_trigger_draw_event_card=app._trigger_draw_event_card,
        )

        self.assertTrue(consumed)
        self.assertEqual(called, ["WEI"])

    def test_handle_card_panel_click_offensive_shows_desc(self):
        app = type("App", (), {})()
        app.card_panel = type(
            "CardPanel",
            (),
            {
                "rect": pg.Rect(0, 0, 50, 50),
                "get_card_at": lambda _self, _pos: "card_x",
                "select_card": lambda _self, _cid: None,
            },
        )()
        app.show_combat_ui = False
        app.waiting_defender_response = False
        app.allow_jiangdong_selection = False
        app.card_repository = type(
            "Repo",
            (),
            {
                "get_definition": lambda _self, _cid: type(
                    "Def", (), {"category": "offensive", "name": "测试", "description": "描述"}
                )()
            },
        )()
        logs = []
        app.info_panel = type("Info", (), {"show_message": lambda _self, msg, **kwargs: logs.append(msg)})()
        app._play_selected_card = lambda: None

        consumed = self.service.handle_card_panel_click(
            pos=(10, 10),
            card_panel=app.card_panel,
            show_combat_ui=app.show_combat_ui,
            waiting_defender_response=app.waiting_defender_response,
            allow_jiangdong_selection=app.allow_jiangdong_selection,
            card_repository=app.card_repository,
            on_play_selected_card=app._play_selected_card,
            on_show_message=(
                lambda msg: app.info_panel.show_message(msg) if app.info_panel else None
            ),
        )

        self.assertTrue(consumed)
        self.assertTrue(any("按 Enter 使用" in msg for msg in logs))

    def test_handle_info_panel_click_true(self):
        app = type("App", (), {})()
        app.info_panel = type("Info", (), {"handle_click": lambda _self, _pos: True})()

        consumed = self.service.handle_info_panel_click(
            info_panel=app.info_panel,
            pos=(10, 10),
        )

        self.assertTrue(consumed)

    def test_handle_card_target_click_success_clears_state(self):
        app = type("App", (), {})()
        app.selecting_card_target = True
        app.selected_card_for_effect = "card_abc"
        app._get_province_at = lambda _pos: type("P", (), {"province_id": 7})()
        app._apply_card_to_province = lambda cid, pid: cid == "card_abc" and pid == 7
        app.info_panel = type("Info", (), {"show_message": lambda *args, **kwargs: None})()

        consumed = self.service.handle_card_target_click(
            pos=(10, 10),
            selecting_card_target=app.selecting_card_target,
            selected_card_for_effect=app.selected_card_for_effect,
            get_province_at=app._get_province_at,
            apply_card_to_province=app._apply_card_to_province,
            on_clear_card_target_selection=lambda: (
                setattr(app, "selecting_card_target", False),
                setattr(app, "selected_card_for_effect", None),
            ),
            on_show_message=app.info_panel.show_message,
        )

        self.assertTrue(consumed)
        self.assertFalse(app.selecting_card_target)
        self.assertIsNone(app.selected_card_for_effect)

    def test_handle_keydown_escape_closes_help_overlay(self):
        app = type("App", (), {})()
        app.help_overlay_visible = True
        app.morale_free_move_mode = False
        app.morale_bonus_mp_mode = False
        app.morale_cure_mode = False
        app.pp_spend_mode = False
        app.selecting_card_target = False
        app.clear_selection = lambda: None
        event = pg.event.Event(pg.KEYDOWN, {"key": pg.K_ESCAPE})

        consumed = self.service.handle_keydown(
            key=event.key,
            help_overlay_visible=app.help_overlay_visible,
            morale_free_move_mode=app.morale_free_move_mode,
            morale_bonus_mp_mode=app.morale_bonus_mp_mode,
            morale_cure_mode=app.morale_cure_mode,
            pp_spend_mode=app.pp_spend_mode,
            pp_summon_target_prov=None,
            selecting_card_target=app.selecting_card_target,
            major_round_choice_pending=False,
            on_set_help_overlay_visible=lambda v: setattr(app, "help_overlay_visible", v),
            on_reset_morale_modes=lambda: (
                setattr(app, "morale_free_move_mode", False),
                setattr(app, "morale_bonus_mp_mode", False),
                setattr(app, "morale_cure_mode", False),
            ),
            on_show_message=None,
            on_set_pp_summon_target_prov=lambda v: setattr(app, "pp_summon_target_prov", v),
            on_clear_pp_summon_btns=lambda: setattr(app, "pp_summon_btns", []),
            on_set_pp_spend_mode=lambda v: setattr(app, "pp_spend_mode", v),
            on_cancel_card_target_selection=lambda: None,
            on_clear_selection=app.clear_selection,
            on_play_selected_card=lambda: None,
        )

        self.assertTrue(consumed)
        self.assertFalse(app.help_overlay_visible)

    def test_handle_unit_selection_click_enemy_blocked(self):
        app = type("App", (), {})()
        app._get_unit_slot_at = lambda _pos: (1, 0)
        app.map_manager = type(
            "Map",
            (),
            {"get_by_id": lambda _self, _pid: type("P", (), {"country": "WEI"})()},
        )()
        app.player_country = "SHU"
        app.info_panel = type("Info", (), {"show_message": lambda *args, **kwargs: None})()
        app.pending_post_move_attack = False
        app.pending_attacker = None
        app.selected_units = []
        app.remove_selection = lambda *_args, **_kwargs: None
        app.add_selection = lambda *_args, **_kwargs: None

        consumed = self.service.handle_unit_selection_click(
            pos=(10, 10),
            get_unit_slot_at=app._get_unit_slot_at,
            get_province_by_id=app.map_manager.get_by_id,
            player_country=app.player_country,
            pending_post_move_attack=app.pending_post_move_attack,
            pending_attacker=app.pending_attacker,
            selected_units=app.selected_units,
            on_remove_selection=app.remove_selection,
            on_add_selection=lambda pid, idx, shift: app.add_selection(
                pid, idx, allow_cross_province=shift
            ),
            on_show_message=(
                lambda msg: app.info_panel.show_message(msg) if app.info_panel else None
            ),
            shift_held=False,
        )

        self.assertTrue(consumed)

    def test_should_block_right_click_major_round(self):
        app = type("App", (), {})()
        app.major_round_choice_pending = True
        app.evt_draw_phase = False
        app.selecting_evt_target = False
        app.info_panel = type("Info", (), {"show_message": lambda *args, **kwargs: None})()

        blocked = self.service.should_block_right_click(
            major_round_choice_pending=app.major_round_choice_pending,
            evt_draw_phase=app.evt_draw_phase,
            selecting_evt_target=app.selecting_evt_target,
            on_block_message=(
                lambda msg: app.info_panel.show_message(msg) if app.info_panel else None
            ),
        )

        self.assertTrue(blocked)

    def test_handle_volume_slider_click_inside(self):
        app = type("App", (), {})()
        app.volume_slider_visible = True
        app._vol_slider_rect = pg.Rect(0, 0, 40, 100)
        app._vol_dragging = False
        called = []
        app._update_volume_from_y = lambda y: called.append(y)

        consumed = self.service.handle_volume_slider_click(
            volume_slider_visible=app.volume_slider_visible,
            slider_rect=app._vol_slider_rect,
            pos=(10, 20),
            on_start_drag=lambda: setattr(app, "_vol_dragging", True),
            on_update_volume=app._update_volume_from_y,
            on_hide_slider=lambda: setattr(app, "volume_slider_visible", False),
        )

        self.assertTrue(consumed)
        self.assertTrue(app._vol_dragging)
        self.assertEqual(called, [20])

    def test_handle_mouse_motion_updates_volume_when_dragging(self):
        app = type("App", (), {})()
        app._vol_dragging = True
        app.volume_slider_visible = True
        app._vol_slider_rect = pg.Rect(0, 0, 40, 100)
        calls = []
        card_panel = type("CardPanel", (), {"handle_mouse_motion": lambda _self, pos: calls.append(("card", pos))})()

        self.service.handle_mouse_motion(
            vol_dragging=app._vol_dragging,
            volume_slider_visible=app.volume_slider_visible,
            slider_rect=app._vol_slider_rect,
            pos=(5, 30),
            on_update_volume=lambda y: calls.append(("vol", y)),
            card_panel=card_panel,
        )

        self.assertIn(("vol", 30), calls)
        self.assertIn(("card", (5, 30)), calls)

    def test_handle_left_button_up_stops_drag(self):
        app = type("App", (), {})()
        app._vol_dragging = True

        self.service.handle_left_button_up(
            on_stop_drag=lambda: setattr(app, "_vol_dragging", False)
        )

        self.assertFalse(app._vol_dragging)

    def test_handle_game_right_click_pp_sets_target(self):
        app = type("App", (), {})()
        app.pp_spend_mode = True
        app.pp_summon_target_prov = None
        app.player_country = "SHU"
        province = type("P", (), {"country": "SHU", "units": []})()
        app._get_province_at = lambda _pos: province
        app.evt_flag_hu_recruit = False
        app.info_panel = type("Info", (), {"show_message": lambda *args, **kwargs: None})()
        app.selected_units = []

        self.service.handle_game_right_click(
            pos=(10, 10),
            pp_spend_mode=app.pp_spend_mode,
            pp_summon_target_prov=app.pp_summon_target_prov,
            get_province_at=app._get_province_at,
            player_country=app.player_country,
            evt_flag_hu_recruit=app.evt_flag_hu_recruit,
            on_set_pp_summon_target_prov=(
                lambda prov: setattr(app, "pp_summon_target_prov", prov)
            ),
            selected_units=app.selected_units,
            card_effect_manager=type("CE", (), {"get_effect": lambda *_args: None})(),
            on_get_people_support_level=lambda _country: 0,
            is_fort_or_city=lambda _prov: False,
            morale_free_move_mode=False,
            combat_target=None,
            on_cancel_combat_preview=lambda: None,
            on_handle_combat=lambda _target: None,
            pending_post_move_attack=False,
            on_handle_movement=lambda _target: None,
            on_show_message=(
                app.info_panel.show_message if app.info_panel else None
            ),
        )

        self.assertIs(app.pp_summon_target_prov, province)

    def test_handle_recover_click_single_confused_unit(self):
        app = type("App", (), {})()
        app.recover_btn_rect = pg.Rect(0, 0, 20, 20)
        confused = type("U", (), {"is_confused": True})()
        app.selected_units = [(1, 0)]
        app.map_manager = type(
            "Map", (), {"get_by_id": lambda _self, _pid: type("P", (), {"units": [confused]})()}
        )()
        logs = []
        app.info_panel = type("Info", (), {"show_message": lambda _self, msg, **kwargs: logs.append(msg)})()
        called = {"update": 0, "finish": 0}

        consumed = self.service.handle_recover_click(
            recover_btn_rect=app.recover_btn_rect,
            pos=(10, 10),
            selected_units=app.selected_units,
            get_province_by_id=app.map_manager.get_by_id,
            on_show_message=app.info_panel.show_message,
            on_update_selection_info=lambda: called.__setitem__("update", called["update"] + 1),
            on_finish_country_action=lambda _a: called.__setitem__("finish", called["finish"] + 1),
        )

        self.assertTrue(consumed)
        self.assertFalse(confused.is_confused)
        self.assertEqual(called["update"], 1)
        self.assertEqual(called["finish"], 1)

    def test_handle_keyboard_input_delegates_keydown(self):
        called = {"n": 0}

        def _fake_handle_keydown(**kwargs):
            called["n"] += 1
            self.assertEqual(kwargs["key"], pg.K_RETURN)
            return True

        self.service.handle_keydown = _fake_handle_keydown

        consumed = self.service.handle_keyboard_input(
            key=pg.K_RETURN,
            help_overlay_visible=False,
            morale_free_move_mode=False,
            morale_bonus_mp_mode=False,
            morale_cure_mode=False,
            pp_spend_mode=False,
            pp_summon_target_prov=None,
            selecting_card_target=False,
            major_round_choice_pending=False,
            on_set_help_overlay_visible=lambda _v: None,
            on_reset_morale_modes=lambda: None,
            on_show_message=None,
            on_set_pp_summon_target_prov=lambda _v: None,
            on_clear_pp_summon_btns=lambda: None,
            on_set_pp_spend_mode=lambda _v: None,
            on_cancel_card_target_selection=lambda: None,
            on_clear_selection=lambda: None,
            on_play_selected_card=lambda: None,
        )

        self.assertTrue(consumed)
        self.assertEqual(called["n"], 1)

    def test_build_keydown_commands_escape_pp_summon(self):
        commands = self.service.build_keydown_commands(
            key=pg.K_ESCAPE,
            help_overlay_visible=False,
            morale_free_move_mode=False,
            morale_bonus_mp_mode=False,
            morale_cure_mode=False,
            pp_spend_mode=True,
            pp_summon_target_prov=object(),
            selecting_card_target=False,
            major_round_choice_pending=False,
        )

        self.assertEqual(commands[0]["name"], "set_pp_summon_target_prov")
        self.assertEqual(commands[1]["name"], "clear_pp_summon_btns")

    def test_build_keydown_commands_return_blocked_by_major_round(self):
        commands = self.service.build_keydown_commands(
            key=pg.K_RETURN,
            help_overlay_visible=False,
            morale_free_move_mode=False,
            morale_bonus_mp_mode=False,
            morale_cure_mode=False,
            pp_spend_mode=False,
            pp_summon_target_prov=None,
            selecting_card_target=False,
            major_round_choice_pending=True,
        )

        self.assertEqual(commands, [{"name": "show_message", "payload": "请先完成三国大回合加点选择"}])

    def test_build_right_click_commands_blocked(self):
        commands = self.service.build_right_click_commands(
            pos=(10, 10),
            major_round_choice_pending=True,
            evt_draw_phase=False,
            selecting_evt_target=False,
        )

        self.assertTrue(any(cmd.get("name") == "show_message" for cmd in commands))
        self.assertEqual(commands[-1]["name"], "consume_event")

    def test_build_right_click_commands_dispatch(self):
        commands = self.service.build_right_click_commands(
            pos=(11, 22),
            major_round_choice_pending=False,
            evt_draw_phase=False,
            selecting_evt_target=False,
        )

        self.assertEqual(commands, [{"name": "handle_game_right_click", "payload": (11, 22)}])

    def test_handle_right_click_blocked(self):
        consumed = self.service.handle_right_click(
            pos=(1, 1),
            major_round_choice_pending=True,
            evt_draw_phase=False,
            selecting_evt_target=False,
            on_block_message=lambda _msg: None,
            pp_spend_mode=False,
            pp_summon_target_prov=None,
            get_province_at=lambda _pos: None,
            player_country="SHU",
            evt_flag_hu_recruit=False,
            on_set_pp_summon_target_prov=lambda _v: None,
            selected_units=[],
            card_effect_manager=type("CE", (), {"get_effect": lambda *_args: None})(),
            on_get_people_support_level=lambda _country: 0,
            is_fort_or_city=lambda _p: False,
            morale_free_move_mode=False,
            combat_target=None,
            on_cancel_combat_preview=lambda: None,
            on_handle_combat=lambda _p: None,
            pending_post_move_attack=False,
            on_handle_movement=lambda _p: None,
            on_show_message=None,
        )

        self.assertTrue(consumed)

    def test_handle_right_click_with_context_delegates(self):
        called = {"n": 0}

        self.service.handle_right_click = lambda **_kwargs: called.__setitem__("n", called["n"] + 1) or True

        context = RightClickContext(
            major_round_choice_pending=False,
            evt_draw_phase=False,
            selecting_evt_target=False,
            on_block_message=None,
            pp_spend_mode=False,
            pp_summon_target_prov=None,
            get_province_at=lambda _pos: None,
            player_country="SHU",
            evt_flag_hu_recruit=False,
            on_set_pp_summon_target_prov=lambda _v: None,
            selected_units=[],
            card_effect_manager=type("CE", (), {"get_effect": lambda *_args: None})(),
            on_get_people_support_level=lambda _country: 0,
            is_fort_or_city=lambda _prov: False,
            morale_free_move_mode=False,
            combat_target=None,
            on_cancel_combat_preview=lambda: None,
            on_handle_combat=lambda _target: None,
            pending_post_move_attack=False,
            on_handle_movement=lambda _target: None,
            on_show_message=None,
        )

        consumed = self.service.handle_right_click_with_context(
            pos=(1, 2),
            context=context,
        )

        self.assertTrue(consumed)
        self.assertEqual(called["n"], 1)

    def test_handle_left_click_pipeline(self):
        called = []
        self.service._handle_left_click_global_ui = lambda **_kwargs: called.append("g") or False
        self.service._handle_left_click_combat_and_event = lambda **_kwargs: called.append("c") or False
        self.service._handle_left_click_panels_and_selection = lambda **_kwargs: called.append("p") or True

        consumed = self.service.handle_left_click(pos=(1, 1), args={})

        self.assertTrue(consumed)
        self.assertEqual(called, ["g", "c", "p"])

    def test_handle_left_click_with_context_delegates(self):
        called = {"n": 0}

        def _fake_handle_left_click(*, pos, args):
            called["n"] += 1
            self.assertEqual(pos, (3, 4))
            self.assertEqual(args, {"k": "v"})
            return True

        self.service.handle_left_click = _fake_handle_left_click

        consumed = self.service.handle_left_click_with_context(
            pos=(3, 4),
            context=LeftClickContext(payload={"k": "v"}),
        )

        self.assertTrue(consumed)
        self.assertEqual(called["n"], 1)


if __name__ == "__main__":
    unittest.main()
