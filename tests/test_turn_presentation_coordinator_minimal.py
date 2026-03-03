import unittest
from unittest.mock import patch

from src.core.turn_presentation_coordinator import TurnPresentationCoordinator


class _CardPanel:
    def __init__(self) -> None:
        self.last_cards = None

    def set_available_cards(self, cards):
        self.last_cards = cards


class _InfoPanel:
    def __init__(self) -> None:
        self.last_message = None

    def show_message(self, message: str) -> None:
        self.last_message = message


class _FakeApp:
    def __init__(self) -> None:
        self.turn_game_finished = False
        self.player_country = "SHU"
        self.card_manager = object()
        self.card_panel = _CardPanel()
        self.info_panel = _InfoPanel()
        self.show_score_screen_called = None

        self.card_managers = {"SHU": "shu_mgr", "WEI": "wei_mgr", "WU": "wu_mgr"}
        self.updated_panel = False
        self.entered_evt_phase = False
        self.human_country = "SHU"
        self._ai_turn_timer = 123

    def _show_score_screen(self, screen_type: str) -> None:
        self.show_score_screen_called = screen_type

    def _update_card_panel(self) -> None:
        self.updated_panel = True

    def _enter_evt_draw_phase_if_needed(self) -> None:
        self.entered_evt_phase = True


class TurnPresentationCoordinatorMinimalTests(unittest.TestCase):
    def test_handle_game_finished(self) -> None:
        app = _FakeApp()
        coord = TurnPresentationCoordinator()

        coord.handle_game_finished(app)

        self.assertTrue(app.turn_game_finished)
        self.assertIsNone(app.player_country)
        self.assertIsNone(app.card_manager)
        self.assertEqual(app.card_panel.last_cards, [])
        self.assertEqual(app.show_score_screen_called, "game_over")
        self.assertIn("对局结束", app.info_panel.last_message)

    def test_on_country_activated_human_turn(self) -> None:
        app = _FakeApp()
        app.player_country = "SHU"
        app.human_country = "SHU"
        coord = TurnPresentationCoordinator()

        coord.on_country_activated(app)

        self.assertEqual(app.card_manager, "shu_mgr")
        self.assertTrue(app.updated_panel)
        self.assertTrue(app.entered_evt_phase)
        self.assertIsNone(app._ai_turn_timer)

    def test_on_country_activated_ai_turn(self) -> None:
        app = _FakeApp()
        app.player_country = "WEI"
        app.human_country = "SHU"
        coord = TurnPresentationCoordinator()

        with patch("src.core.turn_presentation_coordinator.pg.time.get_ticks", return_value=1000):
            coord.on_country_activated(app)

        self.assertEqual(app.card_manager, "wei_mgr")
        self.assertTrue(app.updated_panel)
        self.assertTrue(app.entered_evt_phase)
        self.assertEqual(app._ai_turn_timer, 1600)


if __name__ == "__main__":
    unittest.main()
