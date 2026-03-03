import unittest

from src.core.gameplay_render_service import GameplayRenderService


class GameplayRenderServiceMinimalTest(unittest.TestCase):
    def setUp(self):
        self.service = GameplayRenderService()

    def test_build_round_text_without_country(self):
        self.assertEqual(self.service.build_round_text(1, 2, ""), "回合 1-2")

    def test_build_round_text_with_country(self):
        self.assertEqual(self.service.build_round_text(3, 5, "蜀"), "回合 3-5 · 蜀")


if __name__ == "__main__":
    unittest.main()
