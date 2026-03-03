import unittest

from src.core.turn_service import TurnService


class TurnServiceMinimalTests(unittest.TestCase):
    def _service(self) -> TurnService:
        return TurnService(
            turn_order=["SHU", "WU", "WEI"],
            max_major_rounds=5,
            max_minor_rounds=6,
        )

    def test_choose_major_round_bonus(self) -> None:
        svc = self._service()
        self.assertEqual(svc.choose_major_round_bonus(0), "politics")
        self.assertEqual(svc.choose_major_round_bonus(1), "support")

    def test_apply_major_round_choice(self) -> None:
        svc = self._service()
        stats = svc.create_country_stats()
        _, done = svc.begin_major_round_choice()

        ok = svc.apply_major_round_choice(
            country_stats=stats,
            major_round_choice_done=done,
            country="SHU",
            choice="support",
        )

        self.assertTrue(ok)
        self.assertEqual(stats["SHU"]["people_support"], 2)
        self.assertTrue(done["SHU"])

    def test_advance_turn_normal(self) -> None:
        svc = self._service()
        result = svc.advance_turn(turn_index=0, minor_round=1, major_round=1)
        self.assertEqual(result.turn_index, 1)
        self.assertEqual(result.minor_round, 1)
        self.assertEqual(result.major_round, 1)
        self.assertFalse(result.completed_minor_round)
        self.assertFalse(result.started_new_major_round)
        self.assertFalse(result.game_finished)

    def test_advance_turn_wrap_minor_round(self) -> None:
        svc = self._service()
        result = svc.advance_turn(turn_index=2, minor_round=1, major_round=1)
        self.assertEqual(result.turn_index, 0)
        self.assertEqual(result.minor_round, 2)
        self.assertEqual(result.major_round, 1)
        self.assertTrue(result.completed_minor_round)
        self.assertFalse(result.started_new_major_round)
        self.assertFalse(result.game_finished)

    def test_advance_turn_wrap_major_round(self) -> None:
        svc = self._service()
        result = svc.advance_turn(turn_index=2, minor_round=6, major_round=1)
        self.assertEqual(result.turn_index, 0)
        self.assertEqual(result.minor_round, 1)
        self.assertEqual(result.major_round, 2)
        self.assertFalse(result.completed_minor_round)
        self.assertTrue(result.started_new_major_round)
        self.assertFalse(result.game_finished)

    def test_advance_turn_game_finished(self) -> None:
        svc = self._service()
        result = svc.advance_turn(turn_index=2, minor_round=6, major_round=5)
        self.assertTrue(result.game_finished)


if __name__ == "__main__":
    unittest.main()
