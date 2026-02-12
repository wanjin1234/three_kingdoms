"""Kingdom metadata utilities."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import pygame as pg


@dataclass(frozen=True)
class Kingdom:
    kingdom_id: str
    name: str
    color: pg.Color


class KingdomRepository:
    """Loads kingdom definitions and exposes convenience lookups."""

    def __init__(self, json_file: Path) -> None:
        with json_file.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        self._kingdoms: Dict[str, Kingdom] = {}
        for entry in payload:
            color = pg.Color(entry["color"])
            kingdom = Kingdom(
                kingdom_id=entry["id"],
                name=entry["name"],
                color=color,
            )
            self._kingdoms[kingdom.kingdom_id] = kingdom

    def get_color(self, kingdom_id: str) -> pg.Color:
        kingdom = self._kingdoms.get(kingdom_id)
        if kingdom:
            return kingdom.color
        return pg.Color("gray50")

    def get(self, kingdom_id: str) -> Kingdom | None:
        return self._kingdoms.get(kingdom_id)
