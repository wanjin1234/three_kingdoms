import unittest

from src.core.state_models import CombatState, EventCardState, TurnState, UIState


class StateModelsMinimalTest(unittest.TestCase):
    def setUp(self):
        self.app = type("App", (), {})()
        self.app.player_country = "SHU"
        self.app.human_country = "SHU"
        self.app.turn_order = ["SHU", "WU", "WEI"]
        self.app.turn_index = 0
        self.app.major_round = 1
        self.app.minor_round = 1
        self.app.turn_game_finished = False
        self.app.country_stats = {"SHU": {"people_support": 3, "political_points": 2}}
        self.app.major_round_choice_pending = False
        self.app.major_round_choice_done = {"SHU": False, "WU": False, "WEI": False}

        self.app.selected_units = []
        self.app.country_stat_choice_btns = {}
        self.app.evt_info_btns = {}
        self.app.help_overlay_visible = False
        self.app.volume_slider_visible = False
        self.app.volume_level = 1.0
        self.app.pp_summon_btns = []

        self.app.show_combat_ui = False
        self.app.combat_target = None
        self.app.combat_ratio_val = 0.0
        self.app.waiting_defender_response = False
        self.app.combat_result_title = None
        self.app.combat_result_timer = 0.0

        self.app.event_card_overlay = None
        self.app.selecting_evt_target = False
        self.app.pending_evt_card_id = None
        self.app.pending_evt_drawer = None
        self.app.evt_temp_pp = {}
        self.app.evt_draw_phase = False
        self.app.evt_applied_this_round = {}
        self.app.evt_applied_major_round = {}
        self.app.jingnang_applied = {}
        self.app.jingnang_applied_major = {}

    def test_turn_state_proxy_read_write(self):
        model = TurnState(self.app)

        self.assertEqual(model.player_country, "SHU")
        model.turn_index = 2
        model.major_round = 3

        self.assertEqual(self.app.turn_index, 2)
        self.assertEqual(self.app.major_round, 3)

    def test_ui_combat_event_models_proxy(self):
        ui_model = UIState(self.app)
        combat_model = CombatState(self.app)
        evt_model = EventCardState(self.app)

        ui_model.volume_level = 0.35
        combat_model.show_combat_ui = True
        evt_model.evt_draw_phase = True

        self.assertEqual(self.app.volume_level, 0.35)
        self.assertTrue(self.app.show_combat_ui)
        self.assertTrue(self.app.evt_draw_phase)


if __name__ == "__main__":
    unittest.main()
