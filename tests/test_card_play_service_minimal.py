import unittest

from src.core.app_contexts import CardApplyEffectContext, CardCancelSelectionContext
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

    def test_cancel_card_target_selection_from_context(self):
        app = type("A", (), {})()
        app.selecting_card_target = True
        app.selected_card_for_effect = "card_x"
        app.info_panel = _InfoPanel()

        context = CardCancelSelectionContext(
            on_set_selecting_card_target=(
                lambda v: setattr(app, "selecting_card_target", v)
            ),
            on_set_selected_card_for_effect=(
                lambda v: setattr(app, "selected_card_for_effect", v)
            ),
            show_message=app.info_panel.show_message,
        )
        self.service.cancel_card_target_selection_with_context(context)

        self.assertFalse(app.selecting_card_target)
        self.assertIsNone(app.selected_card_for_effect)
        self.assertTrue(any("已取消卡牌选择" in m for m in app.info_panel.messages))

    def test_apply_card_effect_updates_state_from_context(self):
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
        context = CardApplyEffectContext(
            use_card=app.card_manager.use_card,
            player_country=app.player_country,
            append_jingnang_applied=(
                lambda c, n, d: app.jingnang_applied.setdefault(c, []).append((n, d))
            ),
            show_message=app.info_panel.show_message,
            on_update_card_panel=app._update_card_panel,
        )
        self.service.apply_card_effect_with_context(context, "card_demo", card_def)

        self.assertEqual(app.card_manager.used, ["card_demo"])
        self.assertEqual(app._update_card_panel_called, 1)
        self.assertIn("SHU", app.jingnang_applied)
        self.assertEqual(app.jingnang_applied["SHU"][0][0], "测试卡")

    def test_apply_card_effect_with_context(self):
        used = []
        appended = []
        messages = []
        updated = {"n": 0}

        context = CardApplyEffectContext(
            use_card=lambda cid: used.append(cid),
            player_country="WEI",
            append_jingnang_applied=lambda c, n, d: appended.append((c, n, d)),
            show_message=lambda msg, **_kwargs: messages.append(str(msg)),
            on_update_card_panel=lambda: updated.__setitem__("n", updated["n"] + 1),
        )

        card_def = _CardDef("测试卡2", "desc2")
        self.service.apply_card_effect_with_context(context, "card_demo2", card_def)

        self.assertEqual(used, ["card_demo2"])
        self.assertEqual(appended, [("WEI", "测试卡2", "desc2")])
        self.assertTrue(any("已使用锦囊卡" in m for m in messages))
        self.assertEqual(updated["n"], 1)

    def test_cancel_card_target_selection_with_context(self):
        state = {"selecting": True, "selected": "x", "messages": []}
        context = CardCancelSelectionContext(
            on_set_selecting_card_target=lambda v: state.__setitem__("selecting", v),
            on_set_selected_card_for_effect=lambda v: state.__setitem__("selected", v),
            show_message=lambda msg, **_kwargs: state["messages"].append(str(msg)),
        )

        self.service.cancel_card_target_selection_with_context(context)

        self.assertFalse(state["selecting"])
        self.assertIsNone(state["selected"])
        self.assertTrue(any("已取消卡牌选择" in m for m in state["messages"]))


if __name__ == "__main__":
    unittest.main()
