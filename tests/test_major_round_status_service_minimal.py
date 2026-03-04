import unittest

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

        self.service.remove_from_major_round(app, "隆中定计", "SHU")

        self.assertEqual(app.evt_applied_major_round["SHU"], [("其他", "y")])
        self.assertEqual(app.evt_applied_major_round["WEI"], [("隆中定计", "z")])

    def test_refresh_session_skill_display_rebuilds_shu_entries(self):
        app = type("A", (), {})()
        app.evt_applied_major_round = {"SHU": [("隆中定计", "old")]}
        app.evt_lonzhong_skill = 2
        app.evt_yishen_skill = 1
        app.evt_xingluo_active = True

        self.service.refresh_session_skill_display(app)

        names = [n for n, _d in app.evt_applied_major_round["SHU"]]
        self.assertIn("隆中定计", names)
        self.assertIn("一身是胆", names)
        self.assertIn("星落秋风", names)


if __name__ == "__main__":
    unittest.main()
