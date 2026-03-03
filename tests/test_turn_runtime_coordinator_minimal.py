import unittest

from src.core.turn_runtime_coordinator import TurnRuntimeCoordinator


class _Unit:
    def __init__(self) -> None:
        self.major_mp_bonus = 1
        self.temp_river_immunity = True
        self.temp_terrain_immunity = True
        self.temp_dice_bonus = 2


class _Province:
    def __init__(self) -> None:
        self.units = [_Unit()]


class _MapManager:
    def __init__(self) -> None:
        self.provinces = [_Province()]


class _CardEffectManager:
    def __init__(self) -> None:
        self.cleared = False

    def clear_all_effects(self) -> None:
        self.cleared = True


class _FakeApp:
    def __init__(self) -> None:
        self.pending_post_move_attack = True
        self.pending_attacker = (1, 0)
        self.selecting_card_target = True
        self.selected_card_for_effect = "x"
        self.evt_temp_pp = {"SHU": 1}
        self.evt_applied_this_round = {"SHU": [("a", "b")]}
        self.evt_ai_drawn_this_turn = {"SHU": True}
        self.selecting_evt_target = True
        self.pending_evt_card_id = "evt"
        self.pending_evt_drawer = "SHU"
        self.evt_wuzi_rounds = 1
        self.evt_wuzi_bonus = 3

        self._clear_called = False
        self._clear_keep_info = None

        self.turn_order = ["SHU", "WU", "WEI"]
        self.human_country = "SHU"
        self.morale_lv4_pending = {}
        self._ai_cured = []
        self.map_manager = _MapManager()
        self.evt_flag_hefei = True
        self.evt_flag_she_hushu = True
        self.evt_flag_hu_recruit = True
        self.evt_jingzhu_skill = 3
        self.evt_laomaikuai_active = True
        self.evt_applied_major_round = {"SHU": [("x", "y")]}
        self.jingnang_applied_major = {"SHU": [("x", "y")]}
        self._refresh_called = False
        self.card_effect_manager = _CardEffectManager()
        self._end_full_round_called = False
        self._start_choice_called = False

        self.evt_flag_liukang = True
        self.evt_flag_liukang_drawer = "WEI"
        self.evt_flag_wuwei = True
        self.evt_flag_wuwei_drawer = "WEI"
        self.gexu_guard_active = True
        self.evt_flag_all_attack = True
        self.evt_all_attack_drawer = "WEI"
        self._removed = []
        self.move_src_provs = {1: "WEI", 2: "SHU"}
        self.move_dst_provs = {3: "WEI", 4: "WU"}
        self.move_src_slots = {1: [0], 99: [2]}
        self.move_dst_slots = {3: [1], 100: [1]}

    def _clear_for_turn_switch(self, keep_info_message: bool = False) -> None:
        self._clear_called = True
        self._clear_keep_info = keep_info_message

    def _get_people_support_level(self, country: str) -> int:
        return 4 if country in ("SHU", "WU") else 0

    def _ai_cure_confused_unit(self, country: str) -> None:
        self._ai_cured.append(country)

    def _refresh_session_skill_display(self) -> None:
        self._refresh_called = True

    def _end_full_round(self) -> None:
        self._end_full_round_called = True

    def _start_major_round_choice_phase(self) -> None:
        self._start_choice_called = True

    def _remove_from_major_round(self, card_name: str, country: str | None = None) -> None:
        self._removed.append((card_name, country))


class TurnRuntimeCoordinatorMinimalTests(unittest.TestCase):
    def test_prepare_turn_switch(self) -> None:
        app = _FakeApp()
        coord = TurnRuntimeCoordinator()

        coord.prepare_turn_switch(app, keep_info_message=True)

        self.assertFalse(app.pending_post_move_attack)
        self.assertIsNone(app.pending_attacker)
        self.assertFalse(app.selecting_card_target)
        self.assertIsNone(app.selected_card_for_effect)
        self.assertEqual(app.evt_temp_pp, {})
        self.assertEqual(app.evt_applied_this_round, {})
        self.assertEqual(app.evt_ai_drawn_this_turn, {})
        self.assertFalse(app.selecting_evt_target)
        self.assertIsNone(app.pending_evt_card_id)
        self.assertIsNone(app.pending_evt_drawer)
        self.assertEqual(app.evt_wuzi_rounds, 0)
        self.assertEqual(app.evt_wuzi_bonus, 0)
        self.assertTrue(app._clear_called)
        self.assertTrue(app._clear_keep_info)

    def test_apply_major_round_rollover(self) -> None:
        app = _FakeApp()
        coord = TurnRuntimeCoordinator()

        coord.apply_major_round_rollover(app)

        self.assertTrue(app.morale_lv4_pending.get("SHU", False))
        self.assertIn("WU", app._ai_cured)
        unit = app.map_manager.provinces[0].units[0]
        self.assertEqual(unit.major_mp_bonus, 0)
        self.assertFalse(unit.temp_river_immunity)
        self.assertFalse(unit.temp_terrain_immunity)
        self.assertEqual(unit.temp_dice_bonus, 0)
        self.assertFalse(app.evt_flag_hefei)
        self.assertFalse(app.evt_flag_she_hushu)
        self.assertFalse(app.evt_flag_hu_recruit)
        self.assertEqual(app.evt_jingzhu_skill, 0)
        self.assertFalse(app.evt_laomaikuai_active)
        self.assertEqual(app.evt_applied_major_round, {})
        self.assertEqual(app.jingnang_applied_major, {})
        self.assertTrue(app._refresh_called)
        self.assertTrue(app.card_effect_manager.cleared)
        self.assertTrue(app._end_full_round_called)
        self.assertTrue(app._start_choice_called)

    def test_on_country_turn_start(self) -> None:
        app = _FakeApp()
        coord = TurnRuntimeCoordinator()

        coord.on_country_turn_start(app, new_country="WEI")

        self.assertFalse(app.evt_flag_liukang)
        self.assertEqual(app.evt_flag_liukang_drawer, "")
        self.assertFalse(app.evt_flag_wuwei)
        self.assertEqual(app.evt_flag_wuwei_drawer, "")
        self.assertFalse(app.gexu_guard_active)
        self.assertFalse(app.evt_flag_all_attack)
        self.assertEqual(app.evt_all_attack_drawer, "")
        self.assertIn(("联刘抗曹", None), app._removed)
        self.assertIn(("吴魏媾和", None), app._removed)
        self.assertIn(("奖率三军", None), app._removed)
        self.assertEqual(app.move_src_provs, {2: "SHU"})
        self.assertEqual(app.move_dst_provs, {4: "WU"})
        self.assertEqual(app.move_src_slots, {})
        self.assertEqual(app.move_dst_slots, {})


if __name__ == "__main__":
    unittest.main()
