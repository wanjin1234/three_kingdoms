"""
六边形几何计算模块。
这里包含了画正六边形所需的数学公式。
"""
from math import cos, sin, pi, radians, sqrt
from typing import Tuple

Point = Tuple[int, int]


def hex_vertices(center: Point, side_length: float) -> Tuple[Point, ...]:
    """
    计算正六边形的 6 个顶点坐标。
    
    参数:
        center: 六边形中心的像素坐标 (x, y)
        side_length: 六边形的边长
        
    返回:
        一个包含 6 个 (x, y) 坐标元组的元组。
        
    原理:
        这里采用的是 flat-topped (平顶) 六边形。
        我们从右边的顶点开始，逆时针或顺时针计算每个顶点的位置。
        half = 0.5 * side
        vertical = sqrt(3)/2 * side
    """
    cx, cy = center
    half = 0.5 * side_length
    vertical = 0.5 * sqrt(3) * side_length
    
    return (
        (int(cx + side_length), int(cy)),              # 右边的顶点 (3点钟方向)
        (int(cx + half), int(cy + vertical)),          # 右下的顶点 (5点钟方向)
        (int(cx - half), int(cy + vertical)),          # 左下的顶点 (7点钟方向)
        (int(cx - side_length), int(cy)),              # 左边的顶点 (9点钟方向)
        (int(cx - half), int(cy - vertical)),          # 左上的顶点 (11点钟方向)
        (int(cx + half), int(cy - vertical)),          # 右上的顶点 (1点钟方向)
    )
