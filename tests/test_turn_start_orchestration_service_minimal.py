import unittest
from unittest.mock import patch

from src.core.turn_start_orchestration_service import TurnStartOrchestrationService


class TurnStartOrchestrationServiceMinimalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TurnStartOrchestrationService()

    def test_end_full_round_clears_turn_effect_flags(self):
        app = type("A", (), {})()
        app.card_effect_manager = type("CE", (), {"clear_turn_effects": lambda _self: None})()
        app._replenish_action_points_called = 0
        app._replenish_action_points = lambda: setattr(
            app,
            "_replenish_action_points_called",
            app._replenish_action_points_called + 1,
        )
        app.gexu_guard_active = True
        app.jingnang_applied = {"SHU": [("x", "y")]}

        self.service.end_full_round(app)

        self.assertFalse(app.gexu_guard_active)
        self.assertEqual(app.jingnang_applied, {})
        self.assertEqual(app._replenish_action_points_called, 1)

    def test_apply_major_round_choice_done_triggers_evt_draw(self):
        app = type("A", (), {})()
        app.major_round_choice_pending = True
        app.country_stats = {"SHU": {"people_support": 0, "politics_points": 0}}
        app.major_round_choice_done = {"SHU": False}
        app.major_round = 1
        app._check_tianxia_guixin_victory_called = 0
        app._check_tianxia_guixin_victory = lambda: setattr(
            app,
            "_check_tianxia_guixin_victory_called",
            app._check_tianxia_guixin_victory_called + 1,
        )
        app._enter_evt_draw_phase_if_needed_called = 0
        app._enter_evt_draw_phase_if_needed = lambda: setattr(
            app,
            "_enter_evt_draw_phase_if_needed_called",
            app._enter_evt_draw_phase_if_needed_called + 1,
        )
        app.info_panel = type("I", (), {"show_message": lambda _self, _msg: None})()

        app.turn_service = type(
            "T",
            (),
            {
                "apply_major_round_choice": lambda _self, **_kwargs: True,
                "all_major_round_choices_done": lambda _self, _done: True,
            },
        )()

        self.service.apply_major_round_choice(app, "SHU", "support")

        self.assertFalse(app.major_round_choice_pending)
        self.assertEqual(app._check_tianxia_guixin_victory_called, 1)
        self.assertEqual(app._enter_evt_draw_phase_if_needed_called, 1)


if __name__ == "__main__":
    unittest.main()
