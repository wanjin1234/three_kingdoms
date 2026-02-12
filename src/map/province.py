"""Province (hex tile) domain model."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import List


@dataclass
class Province:
    province_id: int
    name: str
    country: str
    terrain: str
    defense: float
    victory_point: float
    x_factor: float
    y_factor: float
    units: List[str] = field(default_factory=list)

    def compute_center(self, hex_side: float) -> tuple[int, int]:
        """Convert normalized coordinates back to screen space."""
        x = int(self.x_factor * hex_side)
        y = int(self.y_factor * sqrt(3) * hex_side)
        return x, y
