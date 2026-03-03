import unittest

from src.core.movement_service import MovementService


class MovementServiceMinimalTest(unittest.TestCase):
    def setUp(self):
        self.service = MovementService()

    def test_handle_movement_no_selection_returns(self):
        app = type("App", (), {})()
        app.selected_units = []

        target = type("P", (), {"province_id": 1})()
        self.service.handle_movement(app, target)

        self.assertEqual(app.selected_units, [])

    def test_handle_movement_multi_source_blocked(self):
        logs = []
        app = type("App", (), {})()
        app.selected_units = [(1, 0), (2, 0)]
        app.info_panel = type("Info", (), {"show_message": lambda _self, msg: logs.append(msg)})()

        target = type("P", (), {"province_id": 3})()
        self.service.handle_movement(app, target)

        self.assertTrue(any("只能移动同一格子上的部队" in msg for msg in logs))


if __name__ == "__main__":
    unittest.main()
