import unittest
from enum import Enum, auto
from types import SimpleNamespace
from unittest.mock import patch

import pygame as pg

from src.core.console_service import ConsoleService


class _GameState(Enum):
    PLAYING = auto()
    LOADING = auto()


class _InfoPanel:
    def __init__(self):
        self.messages = []

    def show_message(self, msg, duration=None):
        self.messages.append((msg, duration))


class ConsoleServiceMinimalTest(unittest.TestCase):
    def setUp(self):
        self.service = ConsoleService()
        self.app = SimpleNamespace(
            state=_GameState.PLAYING,
            console_visible=False,
            console_input="abc",
            console_message="old",
            human_country="SHU",
            player_country="WU",
            turn_game_finished=False,
            _ai_turn_timer=None,
            country_labels={"SHU": "蜀", "WU": "吴", "WEI": "魏"},
            info_panel=_InfoPanel(),
        )

    def test_toggle_console_resets_buffers_when_opening(self):
        self.service.toggle_console(self.app)
        self.assertTrue(self.app.console_visible)
        self.assertEqual(self.app.console_input, "")
        self.assertEqual(self.app.console_message, "")

    def test_observe_command_enables_observe_mode(self):
        with patch("src.core.console_service.pg.time.get_ticks", return_value=1000):
            self.service.process_console_command(self.app, "observe")
        self.assertEqual(self.app.human_country, "OBSERVE")
        self.assertEqual(self.app._ai_turn_timer, 1600)

    def test_tag_command_switches_human_country(self):
        self.app.player_country = "SHU"
        self.app._ai_turn_timer = 1234
        self.service.process_console_command(self.app, "tag shu")
        self.assertEqual(self.app.human_country, "SHU")
        self.assertIsNone(self.app._ai_turn_timer)


if __name__ == "__main__":
    unittest.main()
