"""Load map definitions and render the hex board."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence

import pygame as pg

from .geometry import hex_vertices
from .province import Province

ColorResolver = Callable[[str], pg.Color]


class MapManager:
    """Handles province loading and drawing."""

    def __init__(
        self,
        *,
        definition_file: Path,
        terrain_graphics_dir: Path,
        color_resolver: ColorResolver,
    ) -> None:
        self._definition_file = definition_file
        self._terrain_graphics_dir = terrain_graphics_dir
        self._color_resolver = color_resolver
        self._provinces = self._load_provinces(definition_file)
        self._hex_side = 0.0
        self._terrain_cache: Dict[str, pg.Surface | None] = {}
        self._border_width = 10

    @staticmethod
    def _load_provinces(definition_file: Path) -> List[Province]:
        provinces: List[Province] = []
        with definition_file.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                units_raw = row.get("units", "").strip()
                units = [token for token in units_raw.split(";") if token]
                provinces.append(
                    Province(
                        province_id=int(row["id"]),
                        name=row["name"],
                        country=row["country"],
                        terrain=row["terrain"],
                        defense=float(row["defense"]),
                        victory_point=float(row["point"]),
                        x_factor=float(row["x_factor"]),
                        y_factor=float(row["y_factor"]),
                        units=units,
                    )
                )
        return provinces

    def set_hex_side(self, side_length: float) -> None:
        self._hex_side = side_length

    @property
    def provinces(self) -> Sequence[Province]:
        return self._provinces

    def get_by_id(self, province_id: int) -> Province | None:
        return next((p for p in self._provinces if p.province_id == province_id), None)

    def draw(self, surface: pg.Surface) -> None:
        if not self._hex_side:
            raise RuntimeError("Hex side length has not been initialized")

        for province in self._provinces:
            center = province.compute_center(self._hex_side)
            color = self._color_resolver(province.country)
            vertices = hex_vertices(center, self._hex_side)
            pg.draw.polygon(surface, pg.Color("white"), vertices)
            pg.draw.polygon(surface, color, vertices, self._border_width)
            self._draw_terrain_icon(surface, province.terrain, center)

    def _draw_terrain_icon(self, surface: pg.Surface, terrain: str, center: tuple[int, int]) -> None:
        icon = self._get_terrain_icon(terrain)
        if icon is None:
            return
        rect = icon.get_rect(center=center)
        surface.blit(icon, rect)

    def _get_terrain_icon(self, terrain: str) -> pg.Surface | None:
        key = terrain.lower()
        if key == "plain":
            return None
        if key not in self._terrain_cache:
            filename = {
                "city": "city_icon.jpg",
                "hill": "hill_icon.jpg",
            }.get(key)
            if filename is None:
                self._terrain_cache[key] = None
                return None
            surface = pg.image.load(self._terrain_graphics_dir / filename).convert_alpha()
            scale = int(0.5 * self._hex_side)
            self._terrain_cache[key] = pg.transform.smoothscale(surface, (scale, scale))
        return self._terrain_cache[key]
