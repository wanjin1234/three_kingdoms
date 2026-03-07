import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
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

    def test_load_help_rule_surfaces_reads_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            pdf_path = Path(td) / "rules.pdf"
            # 用 fitz 创建一个包含 2 页的最简 PDF
            doc = fitz.open()
            for _ in range(2):
                doc.new_page(width=200, height=200)
            doc.save(str(pdf_path))
            doc.close()

            surfaces, failed = self.service.load_help_rule_surfaces(pdf_path=pdf_path)

            self.assertFalse(failed)
            self.assertEqual(len(surfaces), 2)
            self.assertIsInstance(surfaces[0], pg.Surface)

    def test_load_help_rule_surfaces_missing_pdf_returns_failed(self):
        surfaces, failed = self.service.load_help_rule_surfaces(
            pdf_path=Path("/nonexistent/rules.pdf")
        )
        self.assertTrue(failed)
        self.assertEqual(surfaces, [])


if __name__ == "__main__":
    unittest.main()
