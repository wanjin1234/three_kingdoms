"""Centralized pygame event handling."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame as pg

if TYPE_CHECKING:  # pragma: no cover
    from .app import GameApp


class EventManager:
    def __init__(self, app: "GameApp") -> None:
        self._app = app

    def process(self) -> None:
        for event in pg.event.get():
            self._app.handle_event(event)
