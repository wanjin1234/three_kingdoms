import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pygame as pg

from src.core.help_rule_load_service import HelpRuleLoadService


class HelpRuleLoadServiceMinimalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pg.init()

    @classmethod
    def tearDownClass(cls):
        pg.quit()

    def setUp(self):
        self.service = HelpRuleLoadService()

    def test_start_help_rule_load_skip_when_already_loaded(self):
        with patch("src.core.help_rule_load_service.threading.Thread") as mock_thread:
            started = self.service.start_help_rule_load(
                has_surfaces=True,
                is_loading=False,
                load_target=lambda: None,
            )

        mock_thread.assert_not_called()
        self.assertFalse(started)

    def test_load_help_rule_thread_reads_images(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rule_dir = root / "rule"
            rule_dir.mkdir(parents=True, exist_ok=True)

            surf = pg.Surface((8, 8))
            pg.image.save(surf, str(rule_dir / "rule_1.png"))

            surfaces, failed = self.service.load_help_rule_surfaces(graphics_dir=root)

            self.assertFalse(failed)
            self.assertGreaterEqual(len(surfaces), 1)


if __name__ == "__main__":
    unittest.main()
