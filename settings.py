"""Centralized, file-based configuration for the Three Kingdoms game."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).parent.resolve()
ASSET_ROOT = BASE_DIR / "assets"


@dataclass(frozen=True)
class Settings:
    """Immutable bundle of runtime configuration knobs."""

    fps: int
    asset_root: Path
    map_definition_file: Path
    kingdoms_file: Path
    units_file: Path
    fonts_dir: Path
    graphics_dir: Path
    window_title: str = "Three Kingdoms"
    borderless: bool = True
    icon_slot_size_factor: float = 0.6

    @property
    def map_graphics_dir(self) -> Path:
        return self.graphics_dir / "map"

    @property
    def ui_graphics_dir(self) -> Path:
        return self.graphics_dir / "ui"

    @property
    def unit_graphics_dir(self) -> Path:
        return self.graphics_dir / "units"


SETTINGS = Settings(
    fps=60,
    asset_root=ASSET_ROOT,
    map_definition_file=ASSET_ROOT / "map" / "definitions.csv",
    kingdoms_file=ASSET_ROOT / "data" / "kingdoms.json",
    units_file=ASSET_ROOT / "data" / "units.json",
    fonts_dir=ASSET_ROOT / "fonts",
    graphics_dir=ASSET_ROOT / "graphics",
)
