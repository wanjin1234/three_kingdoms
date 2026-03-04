import unittest
from unittest.mock import patch

from src.core.app_contexts import (
    ApplyMajorRoundChoiceContext,
    EndFullRoundContext,
    StartMajorRoundChoiceContext,
)
from src.core.turn_start_orchestration_service import TurnStartOrchestrationService


class TurnStartOrchestrationServiceMinimalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TurnStartOrchestrationService()

    def test_end_full_round_clears_turn_effect_flags(self):
        called = {"clear": 0, "replenish": 0, "flag": None, "jingnang": 0}
        context = EndFullRoundContext(
            on_clear_turn_effects=lambda: called.__setitem__("clear", called["clear"] + 1),
            on_replenish_action_points=lambda: called.__setitem__(
                "replenish", called["replenish"] + 1
            ),
            on_set_gexu_guard_active=lambda v: called.__setitem__("flag", v),
            on_clear_jingnang_applied=lambda: called.__setitem__(
                "jingnang", called["jingnang"] + 1
            ),
        )

        self.service.end_full_round_with_context(context)

        self.assertEqual(called["clear"], 1)
        self.assertEqual(called["replenish"], 1)
        self.assertFalse(called["flag"])
        self.assertEqual(called["jingnang"], 1)

    def test_apply_major_round_choice_done_triggers_evt_draw(self):
        state = {"pending": True, "victory": 0, "enter": 0}
        context = ApplyMajorRoundChoiceContext(
            major_round_choice_pending=True,
            country_stats={"SHU": {"people_support": 0, "political_points": 0}},
            major_round_choice_done={"SHU": False},
            major_round=1,
            apply_major_round_choice=lambda **_kwargs: True,
            all_major_round_choices_done=lambda _done: True,
            on_set_major_round_choice_pending=lambda v: state.__setitem__("pending", v),
            on_check_tianxia_guixin_victory=lambda: state.__setitem__(
                "victory", state["victory"] + 1
            ),
            on_show_message=lambda _msg: None,
            on_enter_evt_draw_phase_if_needed=lambda: state.__setitem__(
                "enter", state["enter"] + 1
            ),
        )

        self.service.apply_major_round_choice_with_context(context, "SHU", "support")

        self.assertFalse(state["pending"])
        self.assertEqual(state["victory"], 1)
        self.assertEqual(state["enter"], 1)

    def test_start_major_round_choice_phase_with_context_auto_applies_ai(self):
        called = {"set_state": 0, "set_btns": 0, "apply": []}

        context = StartMajorRoundChoiceContext(
            turn_order=["SHU", "WU", "WEI"],
            human_country="SHU",
            begin_major_round_choice=lambda: (True, {"SHU": False, "WU": False, "WEI": False}),
            choose_major_round_bonus=lambda _pp: "support",
            get_total_pp=lambda _country: 2,
            on_apply_major_round_choice=lambda c, k: called["apply"].append((c, k)),
            on_set_major_round_choice_state=lambda _pending, _done: called.__setitem__(
                "set_state", called["set_state"] + 1
            ),
            on_set_country_stat_choice_btns=lambda _v: called.__setitem__(
                "set_btns", called["set_btns"] + 1
            ),
        )

        self.service.start_major_round_choice_phase_with_context(context)

        self.assertEqual(called["set_state"], 1)
        self.assertEqual(called["set_btns"], 1)
        self.assertEqual(called["apply"], [("WU", "support"), ("WEI", "support")])

    def test_end_full_round_with_context_executes_all_callbacks(self):
        called = {"clear": 0, "replenish": 0, "flag": 0, "jingnang": 0}
        context = EndFullRoundContext(
            on_clear_turn_effects=lambda: called.__setitem__("clear", called["clear"] + 1),
            on_replenish_action_points=lambda: called.__setitem__(
                "replenish", called["replenish"] + 1
            ),
            on_set_gexu_guard_active=lambda _v: called.__setitem__("flag", called["flag"] + 1),
            on_clear_jingnang_applied=lambda: called.__setitem__(
                "jingnang", called["jingnang"] + 1
            ),
        )

        self.service.end_full_round_with_context(context)

        self.assertEqual(called, {"clear": 1, "replenish": 1, "flag": 1, "jingnang": 1})

    def test_apply_major_round_choice_with_context_noop_when_not_pending(self):
        called = {"apply": 0, "victory": 0, "enter": 0}
        context = ApplyMajorRoundChoiceContext(
            major_round_choice_pending=False,
            country_stats={},
            major_round_choice_done={},
            major_round=1,
            apply_major_round_choice=lambda **_kwargs: called.__setitem__("apply", called["apply"] + 1)
            or True,
            all_major_round_choices_done=lambda _done: True,
            on_set_major_round_choice_pending=lambda _v: None,
            on_check_tianxia_guixin_victory=lambda: called.__setitem__(
                "victory", called["victory"] + 1
            ),
            on_show_message=None,
            on_enter_evt_draw_phase_if_needed=lambda: called.__setitem__(
                "enter", called["enter"] + 1
            ),
        )

        self.service.apply_major_round_choice_with_context(context, "SHU", "support")

        self.assertEqual(called, {"apply": 0, "victory": 0, "enter": 0})


if __name__ == "__main__":
    unittest.main()
