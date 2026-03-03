import unittest

from src.core.combat import (
    RESULT_A2,
    RESULT_D1R,
    get_ratio_column,
    resolve_combat,
)


class CombatMinimalTests(unittest.TestCase):
    def test_get_ratio_column_boundaries(self) -> None:
        self.assertEqual(get_ratio_column(1, 4), 0)  # 0.25 -> 1:2
        self.assertEqual(get_ratio_column(1, 1), 1)  # 1.0  -> 1:1
        self.assertEqual(get_ratio_column(2, 1), 2)  # 2.0  -> 2:1
        self.assertEqual(get_ratio_column(3, 1), 3)  # 3.0  -> 3:1
        self.assertEqual(get_ratio_column(4, 1), 4)  # 4.0  -> 4:1
        self.assertEqual(get_ratio_column(5, 1), 5)  # 5.0  -> 5:1

    def test_get_ratio_column_with_flank_bonus(self) -> None:
        base = get_ratio_column(2, 1, is_flanked=False)
        flanked = get_ratio_column(2, 1, is_flanked=True)
        self.assertEqual(base, 2)
        self.assertEqual(flanked, 3)

    def test_resolve_combat_table_lookup(self) -> None:
        self.assertEqual(resolve_combat(1, 0), RESULT_A2)
        self.assertEqual(resolve_combat(6, 5), RESULT_D1R)

    def test_resolve_combat_column_clamp(self) -> None:
        self.assertEqual(resolve_combat(6, -100), resolve_combat(6, 0))
        self.assertEqual(resolve_combat(6, 100), resolve_combat(6, 5))


if __name__ == "__main__":
    unittest.main()
