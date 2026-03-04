import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.ui_render_helper_service import UIRenderHelperService


class UIRenderHelperServiceMinimalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = UIRenderHelperService()

    def _make_app(self):
        class _Settings:
            fonts_dir = Path(".")

        class _App:
            settings = _Settings()

        return _App()

    def test_font_cache_hit_same_key(self) -> None:
        app = self._make_app()
        created = []

        class _DummyFont:
            pass

        def _factory(path, size):
            created.append((str(path), size))
            return _DummyFont()

        with patch("src.core.ui_render_helper_service.pg.font.Font", side_effect=_factory):
            f1 = self.service.font(app, "msyh.ttc", 18)
            f2 = self.service.font(app, "msyh.ttc", 18)

        self.assertIs(f1, f2)
        self.assertEqual(len(created), 1)

    def test_font_cache_miss_when_size_changes(self) -> None:
        app = self._make_app()
        created = []

        class _DummyFont:
            pass

        def _factory(path, size):
            created.append((str(path), size))
            return _DummyFont()

        with patch("src.core.ui_render_helper_service.pg.font.Font", side_effect=_factory):
            f1 = self.service.font(app, "msyh.ttc", 16)
            f2 = self.service.font(app, "msyh.ttc", 20)

        self.assertIsNot(f1, f2)
        self.assertEqual(len(created), 2)


if __name__ == "__main__":
    unittest.main()
