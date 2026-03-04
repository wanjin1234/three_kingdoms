import unittest

from src.core.card_play_service import CardPlayService


class _InfoPanel:
    def __init__(self):
        self.messages = []

    def show_message(self, msg, **_kwargs):
        self.messages.append(str(msg))


class _CardManager:
    def __init__(self):
        self.used = []

    def use_card(self, cid):
        self.used.append(cid)


class _CardDef:
    def __init__(self, name, desc=""):
        self.name = name
        self.description = desc


class CardPlayServiceMinimalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = CardPlayService()

    def test_cancel_card_target_selection(self):
        app = type("A", (), {})()
        app.selecting_card_target = True
        app.selected_card_for_effect = "card_x"
        app.info_panel = _InfoPanel()

        self.service.cancel_card_target_selection(app)

        self.assertFalse(app.selecting_card_target)
        self.assertIsNone(app.selected_card_for_effect)
        self.assertTrue(any("已取消卡牌选择" in m for m in app.info_panel.messages))

    def test_apply_card_effect_updates_state(self):
        app = type("A", (), {})()
        app.card_manager = _CardManager()
        app.player_country = "SHU"
        app.jingnang_applied = {}
        app.info_panel = _InfoPanel()
        app._update_card_panel_called = 0
        app._update_card_panel = lambda: setattr(
            app,
            "_update_card_panel_called",
            app._update_card_panel_called + 1,
        )

        card_def = _CardDef("测试卡", "desc")
        self.service.apply_card_effect(app, "card_demo", card_def)

        self.assertEqual(app.card_manager.used, ["card_demo"])
        self.assertEqual(app._update_card_panel_called, 1)
        self.assertIn("SHU", app.jingnang_applied)
        self.assertEqual(app.jingnang_applied["SHU"][0][0], "测试卡")


if __name__ == "__main__":
    unittest.main()
