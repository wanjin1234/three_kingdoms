import unittest
from unittest.mock import patch

from src.core.app_contexts import (
    EventConfirmContext,
    EventDrawPhaseContext,
    EventTargetApplyContext,
)
from src.core.event_card_service import EventCardService


class _Card:
    def __init__(self, name="事件", needs_target=False, effect_value=1):
        self.name = name
        self.needs_target = needs_target
        self.effect_value = effect_value


class _Unit:
    def __init__(self):
        self.major_mp_bonus = 0
        self.mp = 0
        self.temp_dice_bonus = 0
        self.defense_bonus = 0
        self.attack_bonus = 0
        self.unit_type = "infantry"


class _Prov:
    def __init__(self):
        self.units = [_Unit()]
        self.name = "测试地块"


class EventCardServiceMinimalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = EventCardService()

    def test_confirm_event_card_with_context_schedules_ai_turn(self):
        state = {
            "overlay": {
                "card": _Card(name="测试事件", needs_target=False),
                "drawer": "WEI",
            },
            "selecting": False,
            "pending_id": None,
            "pending_drawer": None,
            "ai_timer": None,
            "evt_draw_phase": False,
            "human": "SHU",
            "player": "WEI",
            "finished": False,
            "applied": 0,
            "enter": 0,
            "exit": 0,
        }

        context = EventConfirmContext(
            get_event_card_overlay=lambda: state["overlay"],
            clear_event_card_overlay=lambda: state.__setitem__("overlay", None),
            apply_event_card=lambda _card, _drawer: state.__setitem__("applied", state["applied"] + 1),
            is_event_card_overlay_active=lambda: bool(state["overlay"]),
            is_evt_draw_phase_active=lambda: state["evt_draw_phase"],
            get_player_country=lambda: state["player"],
            get_country_total_pp=lambda _c: 1,
            enter_evt_draw_phase_if_needed=lambda: state.__setitem__("enter", state["enter"] + 1),
            exit_evt_draw_phase=lambda: state.__setitem__("exit", state["exit"] + 1),
            get_human_country=lambda: state["human"],
            is_selecting_evt_target=lambda: state["selecting"],
            get_pending_evt_card_id=lambda: state["pending_id"],
            get_pending_evt_drawer=lambda: state["pending_drawer"],
            ai_auto_select_evt_target=lambda _d: None,
            get_ai_turn_timer=lambda: state["ai_timer"],
            is_turn_game_finished=lambda: state["finished"],
            set_ai_turn_timer=lambda v: state.__setitem__("ai_timer", v),
        )

        with patch("src.core.event_card_service.pg.time.get_ticks", return_value=1000):
            self.service.confirm_event_card_with_context(context)

        self.assertEqual(state["applied"], 1)
        self.assertEqual(state["ai_timer"], 1400)

    def test_apply_evt_target_unit_with_context_updates_unit(self):
        state = {"pending": "evt_wangshen", "ai_timer": None, "finished": False, "messages": []}
        prov = _Prov()

        context = EventTargetApplyContext(
            get_pending_evt_card_id=lambda: state["pending"],
            clear_pending_evt_target_state=lambda: state.__setitem__("pending", None),
            get_province_by_id=lambda _pid: prov,
            get_event_card_definition=lambda _cid: _Card(name="望神", effect_value=2),
            show_message=lambda msg, **_kwargs: state["messages"].append(str(msg)),
            check_evt_draw_phase_pp=lambda: None,
            get_player_country=lambda: "WEI",
            get_human_country=lambda: "SHU",
            get_ai_turn_timer=lambda: state["ai_timer"],
            is_turn_game_finished=lambda: state["finished"],
            set_ai_turn_timer=lambda v: state.__setitem__("ai_timer", v),
        )

        with patch("src.core.event_card_service.pg.time.get_ticks", return_value=2000):
            self.service.apply_evt_target_unit_with_context(context, prov_id=1, slot=0)

        unit = prov.units[0]
        self.assertEqual(unit.major_mp_bonus, 2)
        self.assertEqual(unit.mp, 2)
        self.assertEqual(state["ai_timer"], 2400)

    def test_draw_phase_context_entry_and_check(self):
        state = {
            "player": "SHU",
            "human": "SHU",
            "pending": False,
            "pp": 1,
            "evt_draw_phase": False,
            "skip_rect": object(),
            "messages": [],
            "props": [],
        }

        context = EventDrawPhaseContext(
            get_player_country=lambda: state["player"],
            get_human_country=lambda: state["human"],
            is_major_round_choice_pending=lambda: state["pending"],
            get_country_total_pp=lambda _c: state["pp"],
            set_evt_draw_phase=lambda v: state.__setitem__("evt_draw_phase", v),
            get_evt_draw_phase=lambda: state["evt_draw_phase"],
            set_evt_skip_draw_btn_rect=lambda r: state.__setitem__("skip_rect", r),
            show_message=lambda msg, **_kwargs: state["messages"].append(str(msg)),
            show_properties=lambda text: state["props"].append(text),
            get_country_label=lambda _c: "蜀",
        )

        self.service.enter_evt_draw_phase_if_needed_with_context(context)
        self.assertTrue(state["evt_draw_phase"])

        state["pp"] = 0
        self.service.check_evt_draw_phase_pp_with_context(context)
        self.assertFalse(state["evt_draw_phase"])
        self.assertIsNone(state["skip_rect"])


if __name__ == "__main__":
    unittest.main()
