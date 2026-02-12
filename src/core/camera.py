"""Minimal camera stub to future-proof panning and zooming."""
from __future__ import annotations

from pygame import Vector2


class Camera:
    def __init__(self) -> None:
        self.offset = Vector2(0, 0)

    def apply(self, position: tuple[int, int]) -> tuple[int, int]:
        return int(position[0] + self.offset.x), int(position[1] + self.offset.y)

    def handle_input(self) -> None:
        """Placeholder for future WASD/drag camera controls."""
        return
