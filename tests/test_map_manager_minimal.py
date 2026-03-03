import csv
import tempfile
import unittest
from pathlib import Path

import pygame as pg

from src.map.map_manager import MapManager


class MapManagerMinimalTests(unittest.TestCase):
    def _write_csv(self, rows: list[dict]) -> Path:
        tmp_dir = Path(tempfile.mkdtemp(prefix="tk_map_test_"))
        csv_path = tmp_dir / "definitions.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "id",
                    "name",
                    "country",
                    "terrain",
                    "defense",
                    "point",
                    "x_factor",
                    "y_factor",
                    "units",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
        return csv_path

    def test_same_start_target_cost_is_zero(self) -> None:
        csv_path = self._write_csv(
            [
                {
                    "id": 1,
                    "name": "A",
                    "country": "SHU",
                    "terrain": "plain",
                    "defense": 1,
                    "point": 0.5,
                    "x_factor": 0,
                    "y_factor": 0,
                    "units": "",
                }
            ]
        )
        mm = MapManager(
            definition_file=csv_path,
            terrain_graphics_dir=Path("."),
            color_resolver=lambda _: pg.Color("white"),
        )
        mm.set_hex_side(40)
        self.assertEqual(mm.find_path_cost(1, 1), 0)

    def test_unreachable_returns_large_cost(self) -> None:
        csv_path = self._write_csv(
            [
                {
                    "id": 1,
                    "name": "A",
                    "country": "SHU",
                    "terrain": "plain",
                    "defense": 1,
                    "point": 0.5,
                    "x_factor": 0,
                    "y_factor": 0,
                    "units": "",
                },
                {
                    "id": 2,
                    "name": "B",
                    "country": "WEI",
                    "terrain": "plain",
                    "defense": 1,
                    "point": 0.5,
                    "x_factor": 10,
                    "y_factor": 0,
                    "units": "",
                },
            ]
        )
        mm = MapManager(
            definition_file=csv_path,
            terrain_graphics_dir=Path("."),
            color_resolver=lambda _: pg.Color("white"),
        )
        mm.set_hex_side(40)
        self.assertEqual(mm.find_path_cost(1, 2), 9999)

    def test_ignore_mountain_reduces_cost(self) -> None:
        csv_path = self._write_csv(
            [
                {
                    "id": 1,
                    "name": "A",
                    "country": "SHU",
                    "terrain": "plain",
                    "defense": 1,
                    "point": 0.5,
                    "x_factor": 1,
                    "y_factor": 1,
                    "units": "",
                },
                {
                    "id": 2,
                    "name": "B",
                    "country": "SHU",
                    "terrain": "mountain",
                    "defense": 1,
                    "point": 0.5,
                    "x_factor": 2,
                    "y_factor": 1,
                    "units": "",
                },
            ]
        )
        mm = MapManager(
            definition_file=csv_path,
            terrain_graphics_dir=Path("."),
            color_resolver=lambda _: pg.Color("white"),
        )
        mm.set_hex_side(40)

        normal = mm.find_path_cost(1, 2)
        ignore_mtn = mm.find_path_cost_ignore_mountain(1, 2)

        self.assertEqual(normal, 2)
        self.assertEqual(ignore_mtn, 1)


if __name__ == "__main__":
    unittest.main()
