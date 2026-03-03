import unittest

import pygame as pg

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
        consumed = self.service.handle_help_overlay_wheel(app, event)

        self.assertTrue(consumed)
        self.assertEqual(app.help_current_page, 0)

    def test_handle_help_overlay_click_outside_closes(self):
        app = type("App", (), {})()
        app.help_overlay_visible = True
        app._help_rule_surfaces = [object()]
        app.help_current_page = 0
        app._help_prev_btn = None
        app._help_next_btn = None
        app._help_overlay_content_rect = pg.Rect(100, 100, 50, 50)

        event = pg.event.Event(pg.MOUSEBUTTONDOWN, {"button": 1, "pos": (10, 10)})
        consumed = self.service.handle_help_overlay_click(app, event)

        self.assertTrue(consumed)
        self.assertFalse(app.help_overlay_visible)

    def test_handle_control_button_click_help_toggle(self):
        app = type("App", (), {})()
        app.control_btns = [{"rect": pg.Rect(0, 0, 20, 20), "action": "HELP"}]
        app.help_overlay_visible = False
        app.help_current_page = 3
        called = {"load": 0}
        app._start_help_rule_load = lambda: called.__setitem__("load", called["load"] + 1)

        consumed = self.service.handle_control_button_click(app, (10, 10))

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

        consumed = self.service.handle_major_round_choice_click(app, (10, 10))

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

        consumed = self.service.handle_evt_draw_phase_click(app, (35, 10))

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

        consumed = self.service.handle_pp_click(app, (10, 10))

        self.assertTrue(consumed)
        self.assertTrue(app.pp_spend_mode)

    def test_handle_morale_click_lv3_enable_bonus_mode(self):
        app = type("App", (), {})()
        app.morale_lv2_btn_rect = None
        app.morale_lv3_btn_rect = pg.Rect(0, 0, 20, 20)
        app.morale_lv4_btn_rect = None
        app.morale_bonus_mp_mode = False
        app.info_panel = type("Info", (), {"show_message": lambda *args, **kwargs: None})()

        consumed = self.service.handle_morale_click(app, (10, 10))

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

        consumed = self.service.handle_no_attack_click(app, (10, 10))

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

        consumed = self.service.handle_combat_ui_click(app, (10, 10))

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

        consumed = self.service.handle_evt_target_click(app, (10, 10))

        self.assertTrue(consumed)
        self.assertEqual(called, [(1, 0)])

    def test_handle_draw_event_button_click(self):
        app = type("App", (), {})()
        app.draw_event_btn_rect = pg.Rect(0, 0, 20, 20)
        app.player_country = "WEI"
        called = []
        app._trigger_draw_event_card = lambda c: called.append(c)

        consumed = self.service.handle_draw_event_button_click(app, (10, 10))

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

        consumed = self.service.handle_card_panel_click(app, (10, 10))

        self.assertTrue(consumed)
        self.assertTrue(any("按 Enter 使用" in msg for msg in logs))

    def test_handle_info_panel_click_true(self):
        app = type("App", (), {})()
        app.info_panel = type("Info", (), {"handle_click": lambda _self, _pos: True})()

        consumed = self.service.handle_info_panel_click(app, (10, 10))

        self.assertTrue(consumed)

    def test_handle_card_target_click_success_clears_state(self):
        app = type("App", (), {})()
        app.selecting_card_target = True
        app.selected_card_for_effect = "card_abc"
        app._get_province_at = lambda _pos: type("P", (), {"province_id": 7})()
        app._apply_card_to_province = lambda cid, pid: cid == "card_abc" and pid == 7
        app.info_panel = type("Info", (), {"show_message": lambda *args, **kwargs: None})()

        consumed = self.service.handle_card_target_click(app, (10, 10))

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

        consumed = self.service.handle_keydown(app, event)

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

        consumed = self.service.handle_unit_selection_click(app, (10, 10))

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

        self.service.handle_game_right_click(app, (10, 10))

        self.assertIs(app.pp_summon_target_prov, province)


if __name__ == "__main__":
    unittest.main()
