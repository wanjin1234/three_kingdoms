import unittest

from src.core.app_contexts import RefreshSessionSkillDisplayContext, RemoveMajorRoundContext
from src.core.major_round_status_service import MajorRoundStatusService


class MajorRoundStatusServiceMinimalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MajorRoundStatusService()

    def test_remove_from_major_round_filters_target(self):
        app = type("A", (), {})()
        app.evt_applied_major_round = {
            "SHU": [("隆中定计", "x"), ("其他", "y")],
            "WEI": [("隆中定计", "z")],
        }

        context = RemoveMajorRoundContext(
            get_major_round_countries=lambda: list(app.evt_applied_major_round.keys()),
            filter_out_card_for_country=(
                lambda c, card_name: app.evt_applied_major_round.__setitem__(
                    c,
                    [
                        (n, d)
                        for n, d in app.evt_applied_major_round.get(c, [])
                        if n != card_name
                    ],
                )
            ),
        )

        self.service.remove_from_major_round_with_context(context, "隆中定计", "SHU")

        self.assertEqual(app.evt_applied_major_round["SHU"], [("其他", "y")])
        self.assertEqual(app.evt_applied_major_round["WEI"], [("隆中定计", "z")])

    def test_refresh_session_skill_display_rebuilds_shu_entries(self):
        app = type("A", (), {})()
        app.evt_applied_major_round = {"SHU": [("隆中定计", "old")]}
        app.evt_lonzhong_skill = 2
        app.evt_yishen_skill = 1
        app.evt_xingluo_active = True

        remove_context = RemoveMajorRoundContext(
            get_major_round_countries=lambda: list(app.evt_applied_major_round.keys()),
            filter_out_card_for_country=(
                lambda c, card_name: app.evt_applied_major_round.__setitem__(
                    c,
                    [
                        (n, d)
                        for n, d in app.evt_applied_major_round.get(c, [])
                        if n != card_name
                    ],
                )
            ),
        )
        context = RefreshSessionSkillDisplayContext(
            on_remove_from_major_round=(
                lambda card_name, country=None: self.service.remove_from_major_round_with_context(
                    remove_context,
                    card_name,
                    country,
                )
            ),
            get_evt_lonzhong_skill=lambda: app.evt_lonzhong_skill,
            get_evt_yishen_skill=lambda: app.evt_yishen_skill,
            is_evt_xingluo_active=lambda: bool(app.evt_xingluo_active),
            append_major_round_record=(
                lambda c, n, d: app.evt_applied_major_round.setdefault(c, []).append((n, d))
            ),
        )

        self.service.refresh_session_skill_display_with_context(context)

        names = [n for n, _d in app.evt_applied_major_round["SHU"]]
        self.assertIn("隆中定计", names)
        self.assertIn("一身是胆", names)
        self.assertIn("星落秋风", names)


if __name__ == "__main__":
    unittest.main()
