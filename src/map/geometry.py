"""Hex geometry helpers reused across the map layer."""
from __future__ import annotations

from math import sqrt
from typing import Iterable, Tuple

Point = Tuple[int, int]


def hex_vertices(center: Point, side_length: float) -> Tuple[Point, ...]:
    """Return vertices for a flat-topped hexagon."""
    cx, cy = center
    half = 0.5 * side_length
    vertical = 0.5 * sqrt(3) * side_length
    return (
        (int(cx + side_length), int(cy)),
        (int(cx + half), int(cy + vertical)),
        (int(cx - half), int(cy + vertical)),
        (int(cx - side_length), int(cy)),
        (int(cx - half), int(cy - vertical)),
        (int(cx + half), int(cy - vertical)),
    )
