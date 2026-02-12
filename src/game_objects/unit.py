"""Unit templates and rendering helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pygame as pg

Slot = Tuple[int, int]


@dataclass(frozen=True)
class UnitDefinition:
    unit_type: str
    move: int
    attack: int
    defense: int
    range: int
    country: str | None
    icon_path: Path


class UnitRepository:
    """Loads unit definitions and their icon surfaces."""

    def __init__(self, json_file: Path, asset_root: Path) -> None:
        with json_file.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        self._definitions: Dict[str, UnitDefinition] = {}
        self._raw_icons: Dict[str, pg.Surface] = {}
        for entry in payload:
            unit_type = entry["type"]
            definition = UnitDefinition(
                unit_type=unit_type,
                move=entry["move"],
                attack=entry["attack"],
                defense=entry["defense"],
                range=entry["range"],
                country=entry["country"],
                icon_path=asset_root / entry["icon"],
            )
            self._definitions[unit_type] = definition
            self._raw_icons[unit_type] = pg.image.load(definition.icon_path).convert_alpha()

    def get_definition(self, unit_type: str) -> UnitDefinition:
        return self._definitions[unit_type]

    def get_icon_surface(self, unit_type: str) -> pg.Surface:
        return self._raw_icons[unit_type]

    def iter_icon_surfaces(self) -> Sequence[tuple[str, pg.Surface]]:
        return tuple(self._raw_icons.items())


class UnitRenderer:
    """Handles icon placement and drawing for map provinces."""

    def __init__(self, *, repository: UnitRepository, slot_factor: float) -> None:
        self._repository = repository
        self._slot_factor = slot_factor
        self._icon_size = 0
        self._scaled_icons: Dict[str, pg.Surface] = {}

    def on_hex_side_changed(self, hex_side: float) -> None:
        self._icon_size = max(1, int(hex_side * self._slot_factor))
        self._scaled_icons.clear()
        for unit_type, surface in self._repository.iter_icon_surfaces():
            self._scaled_icons[unit_type] = pg.transform.smoothscale(
                surface, (self._icon_size, self._icon_size)
            )

    def draw_units(self, surface: pg.Surface, center: Tuple[int, int], units: Sequence[str]) -> None:
        if not units or not self._icon_size:
            return
        for idx, unit_type in enumerate(units):
            icon = self._scaled_icons.get(unit_type)
            if icon is None:
                continue
            pos = self._slot_position(center, idx)
            surface.blit(icon, pos)

    def selection_rects(self, center: Tuple[int, int], unit_count: int) -> List[pg.Rect]:
        rects: List[pg.Rect] = []
        if not self._icon_size:
            return rects
        for idx in range(unit_count):
            pos = self._slot_position(center, idx)
            rects.append(pg.Rect(pos[0], pos[1], self._icon_size, self._icon_size))
        return rects

    def _slot_position(self, center: Tuple[int, int], slot_index: int) -> Slot:
        cx, cy = center
        offset = int(self._icon_size)
        slots = (
            (cx, cy - offset),
            (cx, cy),
            (cx - offset, cy),
        )
        clamped_index = min(slot_index, len(slots) - 1)
        return slots[clamped_index]
