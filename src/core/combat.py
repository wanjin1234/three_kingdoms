from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple
import logging
from math import floor

# Combat Results
RESULT_A2 = "A2"
RESULT_A1 = "A1"
RESULT_AG = "AG"
RESULT_AG_DG = "AG&DG"
RESULT_C = "C"
RESULT_DG = "DG"
RESULT_DR = "DR"
RESULT_D1 = "D1"
RESULT_D1R = "D1R"

COMBAT_TABLE = {
    # Dice: [1:2, 1:1, 2:1, 3:1, 4:1, 5:1]
    1: [RESULT_A2, RESULT_A1,    RESULT_A1,    RESULT_C,  RESULT_C,  RESULT_DG],
    2: [RESULT_A1, RESULT_AG,    RESULT_AG_DG, RESULT_DG, RESULT_DG, RESULT_DG],
    3: [RESULT_AG, RESULT_AG_DG, RESULT_C,     RESULT_DG, RESULT_DR, RESULT_DR],
    4: [RESULT_AG, RESULT_C,     RESULT_DG,    RESULT_DR, RESULT_DR, RESULT_DR],
    5: [RESULT_C,  RESULT_DG,    RESULT_DR,    RESULT_DR, RESULT_D1, RESULT_D1],
    6: [RESULT_DG, RESULT_DR,    RESULT_D1,    RESULT_D1, RESULT_D1, RESULT_D1R],
}

def resolve_combat(dice: int, ratio_col: int) -> str:
    """
    ratio_col: 0 for 1:2, 1 for 1:1, 2 for 2:1, ..., 5 for 5:1
    """
    col = max(0, min(5, ratio_col))
    return COMBAT_TABLE.get(dice, [RESULT_C] * 6)[col]

def get_ratio_column(attack_power: float, defense_power: float, is_flanked: bool = False) -> int:
    """
    Calculate column index for the CRT.
    0: 1:2
    1: 1:1
    2: 2:1
    3: 3:1
    4: 4:1
    5: 5:1
    
    计算比值时，先约分后抹去小数。
    例如：6:3 = 2:1, 7:3 = 2.33:1 约为 2:1
    """
    if defense_power <= 0:
        return 5 # Instant win basically
    
    # 计算攻防比值
    ratio = attack_power / defense_power
    
    # 约分后向下取整：比值的整数部分决定列
    # ratio < 0.5: 1:2 (col=0)
    # 0.5 <= ratio < 1.5: 1:1 (col=1)
    # 1.5 <= ratio < 2.5: 2:1 (col=2)
    # 2.5 <= ratio < 3.5: 3:1 (col=3)
    # 3.5 <= ratio < 4.5: 4:1 (col=4)
    # ratio >= 4.5: 5:1 (col=5)
    if ratio < 0.5:
        col = 0  # 1:2
    elif ratio < 1.5:
        col = 1  # 1:1
    elif ratio < 2.5:
        col = 2  # 2:1
    elif ratio < 3.5:
        col = 3  # 3:1
    elif ratio < 4.5:
        col = 4  # 4:1
    else:
        col = 5  # 5:1及以上
        
    # 夹击：判定向不利于防守方的方向移动一列（有利于进攻方）
    if is_flanked:
        col = min(5, col + 1)
        
    return col

@dataclass
class CombatPreview:
    attacker_power: float
    defender_power: float
    ratio_str: str
    column_index: int
