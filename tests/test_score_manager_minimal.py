import unittest

from src.core.score_manager import ScoreManager
from src.map.province import Province


class ScoreManagerMinimalTests(unittest.TestCase):
    def _province(self, pid: int, name: str, country: str, point: float) -> Province:
        return Province(
            province_id=pid,
            name=name,
            country=country,
            terrain="plain",
            defense=1.0,
            victory_point=point,
            x_factor=0,
            y_factor=0,
            units=[],
        )

    def test_country_score_uses_victory_point(self) -> None:
        manager = ScoreManager()
        provinces = [
            self._province(1, "A", "SHU", 2.0),
            self._province(2, "B", "SHU", 0.5),
            self._province(3, "C", "WEI", 3.0),
        ]
        scores = manager.calculate_country_score(provinces, {})
        self.assertEqual(scores["SHU"], 2.5)
        self.assertEqual(scores["WEI"], 3.0)
        self.assertEqual(scores["WU"], 0.0)

    def test_net_score_equals_current_minus_initial(self) -> None:
        manager = ScoreManager()
        initial = [
            self._province(1, "A", "SHU", 1.0),
            self._province(2, "B", "WEI", 1.0),
        ]
        manager.record_initial_scores(initial)

        current = [
            self._province(1, "A", "SHU", 2.0),
            self._province(2, "B", "WEI", 0.5),
            self._province(3, "C", "WU", 1.0),
        ]
        net = manager.get_net_scores(current, {})
        self.assertEqual(net["SHU"], 1.0)
        self.assertEqual(net["WEI"], -0.5)
        self.assertEqual(net["WU"], 1.0)


if __name__ == "__main__":
    unittest.main()
