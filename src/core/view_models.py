from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class MainSceneViewModel:
    """主场景只读视图模型。"""

    show_score_screen: bool
    state: object


@dataclass(frozen=True)
class GameplayViewModel:
    """PLAYING 场景只读视图模型（阶段3首批）。"""

    major_round: int
    minor_round: int
    player_country: str | None
    country_labels: Mapping[str, str]
