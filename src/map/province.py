"""
这里定义了 "Province"（省份/地块）类。
每一个 Province 代表地图上的一个六边形格子。
它是数据的容器，存储着这个格子的所有信息：属于哪个国家、地形是什么、防守值多少、驻扎了哪些部队。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import List, Tuple

from src.game_objects.unit import UnitState

# SQRT3 是根号3 (约等于 1.732)，在六边形几何计算中非常重要。
# 因为正六边形的高等于 根号3 倍的边长。
SQRT3 = sqrt(3)


@dataclass
class Province:
    """
    Province 类用于存储单个地图格子的所有属性。
    使用 @dataclass 可以帮我们省去写一大堆 __init__ 代码的麻烦。
    """
    province_id: int    # 格子的唯一编号，比如 1, 2, 3...
    name: str           # 格子的名字，比如 "洛阳", "长安"
    country: str        # 归属国家，比如 "WEI" (魏), "SHU" (蜀)
    terrain: str        # 地形类型，比如 "plain" (平原), "mountain" (山地)
    defense: float      # 防御加成值
    victory_point: float # 占领这个点的分数
    x_factor: float     # 在逻辑地图上的横坐标 (不是像素坐标)
    y_factor: float     # 在逻辑地图上的纵坐标
    units: List[UnitState] = field(default_factory=list)    # 当前格子上有什么兵，存的是 UnitState 对象
    
    # 缓存字段 (不要在 init 里传参)
    center_cache: pg.math.Vector2 | None = field(default=None, init=False)
    vertices_cache: List[pg.math.Vector2] | None = field(default=None, init=False)

    def compute_center(self, hex_side: float) -> Tuple[int, int]:
        """
        计算这个格子在屏幕上的像素中心点坐标 (x, y)。
        
        参数:
            hex_side: 六边形的边长 (像素)
            
        原理:
            我们的地图坐标系 (x_factor, y_factor) 已经被转换好了。
            横向 x = hex_side * x_factor
            纵向 y = hex_side * 根号3 * y_factor
            这把逻辑坐标变成了屏幕上的像素坐标。
        """
        x = int(self.x_factor * hex_side)
        y = int(self.y_factor * SQRT3 * hex_side)
        return x, y
