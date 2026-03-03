"""
回合流程服务：抽离纯规则层的回合推进与大回合加点选择逻辑。

该模块不依赖 pygame，不处理 UI，仅负责状态计算。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class TurnAdvanceResult:
    """一次国家切换后的回合推进结果。"""

    turn_index: int
    minor_round: int
    major_round: int
    completed_minor_round: bool
    started_new_major_round: bool
    game_finished: bool


class TurnService:
    """回合规则服务。"""

    def __init__(
        self,
        *,
        turn_order: List[str],
        max_major_rounds: int,
        max_minor_rounds: int,
    ) -> None:
        self._turn_order = list(turn_order)
        self._max_major_rounds = int(max_major_rounds)
        self._max_minor_rounds = int(max_minor_rounds)

    def create_country_stats(self) -> Dict[str, Dict[str, int]]:
        """构建国家基础属性初始值。"""
        return {
            country: {"people_support": 0, "political_points": 0}
            for country in self._turn_order
        }

    @staticmethod
    def choose_major_round_bonus(total_pp: int) -> str:
        """AI 在大回合加点阶段的默认策略。"""
        return "politics" if int(total_pp) == 0 else "support"

    def begin_major_round_choice(self) -> tuple[bool, Dict[str, bool]]:
        """初始化大回合加点状态。"""
        return True, {country: False for country in self._turn_order}

    def apply_major_round_choice(
        self,
        *,
        country_stats: Dict[str, Dict[str, int]],
        major_round_choice_done: Dict[str, bool],
        country: str,
        choice: str,
    ) -> bool:
        """应用单个国家的大回合加点选择。成功返回 True。"""
        if country not in self._turn_order:
            return False
        if major_round_choice_done.get(country, False):
            return False

        stats = country_stats.setdefault(
            country, {"people_support": 0, "political_points": 0}
        )
        if choice == "support":
            stats["people_support"] = int(stats.get("people_support", 0)) + 2
        elif choice == "politics":
            stats["political_points"] = int(stats.get("political_points", 0)) + 2
        else:
            return False

        major_round_choice_done[country] = True
        return True

    def all_major_round_choices_done(self, major_round_choice_done: Dict[str, bool]) -> bool:
        """判断三国是否都完成了大回合加点。"""
        return all(major_round_choice_done.get(c, False) for c in self._turn_order)

    def advance_turn(
        self,
        *,
        turn_index: int,
        minor_round: int,
        major_round: int,
    ) -> TurnAdvanceResult:
        """推进到下一个国家，返回新的回合计数和阶段标记。"""
        next_turn_index = turn_index + 1
        wrapped = next_turn_index >= len(self._turn_order)
        if wrapped:
            next_turn_index = 0

        next_minor_round = minor_round
        next_major_round = major_round
        completed_minor_round = False
        started_new_major_round = False
        game_finished = False

        if wrapped:
            if minor_round < self._max_minor_rounds:
                next_minor_round = minor_round + 1
                completed_minor_round = True
            elif major_round < self._max_major_rounds:
                next_major_round = major_round + 1
                next_minor_round = 1
                started_new_major_round = True
            else:
                game_finished = True

        return TurnAdvanceResult(
            turn_index=next_turn_index,
            minor_round=next_minor_round,
            major_round=next_major_round,
            completed_minor_round=completed_minor_round,
            started_new_major_round=started_new_major_round,
            game_finished=game_finished,
        )
