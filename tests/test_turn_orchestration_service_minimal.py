import unittest

from src.core.app_contexts import (
    AdvanceCountryTurnContext,
    CheckTianxiaVictoryContext,
    ClearForTurnSwitchContext,
    FinishCountryActionContext,
)
from src.core.turn_orchestration_service import TurnOrchestrationService


class _Advance:
    def __init__(
        self,
        *,
        turn_index: int,
        minor_round: int,
        major_round: int,
        game_finished: bool,
        completed_minor_round: bool,
        started_new_major_round: bool,
    ):
        self.turn_index = turn_index
        self.minor_round = minor_round
        self.major_round = major_round
        self.game_finished = game_finished
        self.completed_minor_round = completed_minor_round
        self.started_new_major_round = started_new_major_round


class TurnOrchestrationServiceMinimalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TurnOrchestrationService()

    def test_clear_for_turn_switch_with_context(self):
        called = {"sel": 0, "combat": 0, "mode": 0, "ui": 0, "prop": []}
        context = ClearForTurnSwitchContext(
            clear_selected_units=lambda: called.__setitem__("sel", called["sel"] + 1),
            reset_combat_interaction_state=lambda: called.__setitem__(
                "combat", called["combat"] + 1
            ),
            reset_morale_and_pp_modes=lambda: called.__setitem__("mode", called["mode"] + 1),
            on_clear_combat_result_ui=lambda: called.__setitem__("ui", called["ui"] + 1),
            show_properties=lambda text: called["prop"].append(text),
        )

        self.service.clear_for_turn_switch_with_context(context, keep_info_message=False)

        self.assertEqual(called["sel"], 1)
        self.assertEqual(called["combat"], 1)
        self.assertEqual(called["mode"], 1)
        self.assertEqual(called["ui"], 1)
        # 新行为：切回合时不再主动清除 info panel 内容，保留旧信息
        self.assertEqual(called["prop"], [])

    def test_advance_country_turn_with_context(self):
        called = {
            "prepare": 0,
            "set_prog": [],
            "end": 0,
            "roll": 0,
            "set_country": [],
            "start": [],
            "act": 0,
        }
        context = AdvanceCountryTurnContext(
            turn_game_finished=False,
            prepare_turn_switch=lambda _keep: called.__setitem__(
                "prepare", called["prepare"] + 1
            ),
            advance_turn=lambda: _Advance(
                turn_index=1,
                minor_round=2,
                major_round=3,
                game_finished=False,
                completed_minor_round=True,
                started_new_major_round=False,
            ),
            on_set_turn_progression=lambda i, n, m: called["set_prog"].append((i, n, m)),
            on_handle_game_finished=lambda: None,
            on_end_full_round=lambda: called.__setitem__("end", called["end"] + 1),
            on_apply_major_round_rollover=lambda: called.__setitem__("roll", called["roll"] + 1),
            get_turn_order=lambda: ["SHU", "WEI", "WU"],
            on_set_player_country=lambda c: called["set_country"].append(c),
            on_country_turn_start=lambda c: called["start"].append(c),
            on_country_activated=lambda: called.__setitem__("act", called["act"] + 1),
        )

        self.service.advance_country_turn_with_context(context, keep_info_message=True)

        self.assertEqual(called["prepare"], 1)
        self.assertEqual(called["set_prog"], [(1, 2, 3)])
        self.assertEqual(called["end"], 1)
        self.assertEqual(called["roll"], 0)
        self.assertEqual(called["set_country"], ["WEI"])
        self.assertEqual(called["start"], ["WEI"])
        self.assertEqual(called["act"], 1)

    def test_finish_country_action_with_context(self):
        called = []
        context = FinishCountryActionContext(
            on_advance_country_turn=lambda keep: called.append(bool(keep))
        )

        self.service.finish_country_action_with_context(
            context,
            "移动",
            keep_info_message=True,
        )

        self.assertEqual(called, [True])

    def test_check_tianxia_guixin_victory_with_context(self):
        state = {
            "finished": False,
            "player": "SHU",
            "card_mgr": object(),
            "panel_cleared": 0,
            "recorded": False,
            "initial": 0,
            "show": None,
            "msg": [],
        }
        record = type(
            "R",
            (),
            {
                "shu_score": 10,
                "shu_initial": 8,
                "wei_score": 11,
                "wei_initial": 9,
                "wu_score": 9,
                "wu_initial": 8,
            },
        )()

        context = CheckTianxiaVictoryContext(
            check_tianxia_guixin=lambda: "WEI",
            on_set_turn_game_finished=lambda v: state.__setitem__("finished", v),
            on_set_player_country=lambda v: state.__setitem__("player", v),
            on_set_card_manager=lambda v: state.__setitem__("card_mgr", v),
            on_clear_card_panel_available=lambda: state.__setitem__(
                "panel_cleared", state["panel_cleared"] + 1
            ),
            score_manager_initial_recorded=state["recorded"],
            on_record_initial_scores=lambda: state.__setitem__("initial", state["initial"] + 1),
            on_set_score_manager_initial_recorded=lambda v: state.__setitem__("recorded", v),
            get_detailed_scores=lambda: record,
            on_set_show_score_screen=lambda d: state.__setitem__("show", d),
            on_show_message=lambda m: state["msg"].append(m),
        )

        self.service.check_tianxia_guixin_victory_with_context(context)

        self.assertTrue(state["finished"])
        self.assertIsNone(state["player"])
        self.assertIsNone(state["card_mgr"])
        self.assertEqual(state["panel_cleared"], 1)
        self.assertEqual(state["initial"], 1)
        self.assertTrue(state["recorded"])
        self.assertEqual(state["show"]["tianxia_winner"], "WEI")
        self.assertTrue(any("天下归心" in m for m in state["msg"]))


if __name__ == "__main__":
    unittest.main()
