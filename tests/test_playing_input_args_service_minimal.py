import unittest

from src.core.app_contexts import LeftClickContext, RightClickContext
from src.core.playing_input_args_service import PlayingInputArgsService


class PlayingInputArgsServiceMinimalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PlayingInputArgsService()

    def test_build_right_click_context_contains_expected_bindings(self):
        app = type("A", (), {})()
        app.major_round_choice_pending = False
        app.evt_draw_phase = False
        app.selecting_evt_target = False
        app.pp_spend_mode = True
        app.pp_summon_target_prov = None
        app._get_province_at = lambda _pos: None
        app.player_country = "SHU"
        app.evt_flag_hu_recruit = False
        app._set_pp_summon_target_prov = lambda _prov: None
        app.selected_units = []
        app.card_effect_manager = object()
        app._get_people_support_level = lambda _country: 0
        app._is_fort_or_city = lambda _prov: False
        app.morale_free_move_mode = False
        app.combat_target = None
        app._cancel_combat_preview = lambda: None
        app._handle_combat = lambda _target: None
        app.pending_post_move_attack = False
        app._handle_movement = lambda _target: None
        app.info_panel = None

        context = self.service.build_right_click_context(
            app,
            on_block_message=None,
        )

        self.assertIsInstance(context, RightClickContext)
        self.assertTrue(context.pp_spend_mode)
        self.assertEqual(context.player_country, "SHU")

    def test_build_left_click_context_wraps_payload(self):
        app = object()
        self.service.build_left_click_args = lambda _app, show_msg: {"demo": 1, "msg": show_msg}

        context = self.service.build_left_click_context(app, show_msg=None)

        self.assertIsInstance(context, LeftClickContext)
        self.assertEqual(context.payload["demo"], 1)


if __name__ == "__main__":
    unittest.main()
