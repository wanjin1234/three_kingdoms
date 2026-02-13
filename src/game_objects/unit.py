"""
这个文件负责加载和管理所有的“兵种”数据，以及把它们画在屏幕上。
你可以把这里想象成兵营的“人事部”和“美工部”。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pygame as pg

# Slot 是一个类型别名，表示一个坐标点 (x, y)
Slot = Tuple[int, int]


@dataclass
class UnitState:
    """
    单个作战单位的实时状态。
    包含：类型、血量、是否混乱、本回合攻击次数等。
    """
    unit_type: str
    hp: int = 2
    is_confused: bool = False
    attack_count: int = 0
    
    @property
    def is_injured(self) -> bool:
        return self.hp < 2

@dataclass(frozen=True)
class UnitDefinition:
    """
    定义一个兵种的数据结构。
    比如：步兵跑得慢、攻击力多少、防御力多少。
    """
    unit_type: str         # 兵种代号，如 "infantry"
    move: int              # 移动力
    attack: int            # 攻击力
    defense: int           # 防御力
    range: int             # 射程
    country: str | None    # 专属国家，如果是 None 表示通用兵种
    icon_path: Path        # 图标文件的路径


class UnitRepository:
    """
    兵种仓库。
    它的工作是：
    1. 从 json 文件里读取所有兵种的数值设定。
    2. 顺便把兵种的图片文件也读取进来（load image），准备好给后面用。
    """

    def __init__(self, json_file: Path, asset_root: Path) -> None:
        # 打开兵种配置文件 (units.json)
        with json_file.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
        
        self._definitions: Dict[str, UnitDefinition] = {}
        self._raw_icons: Dict[str, pg.Surface] = {}
        
        # 遍历每一个兵种配置，创建 UnitDefinition 对象
        for entry in payload:
            unit_type = entry["type"]
            definition = UnitDefinition(
                unit_type=unit_type,
                move=entry["move"],
                attack=entry["attack"],
                defense=entry["defense"],
                range=entry["range"],
                country=entry["country"],
                icon_path=asset_root / entry["icon"], # 拼出图标的完整路径
            )
            self._definitions[unit_type] = definition
            
            # 这里直接读取图片并缓存起来，避免每次画图都读硬盘
            # 增加自动后缀检测：如果指定的 icon 不存在，尝试找 .png 或 .jpg
            icon_path = definition.icon_path
            if not icon_path.exists():
                # 如果找不到文件，尝试其它后缀
                stem = icon_path.stem
                parent = icon_path.parent
                for ext in [".png", ".jpg", ".jpeg"]:
                    alt_path = parent / (stem + ext)
                    if alt_path.exists():
                        icon_path = alt_path
                        break
            
            try:
                self._raw_icons[unit_type] = pg.image.load(icon_path).convert_alpha()
            except Exception as e:
                # print(f"Error loading unit icon for {unit_type}: {e}")
                # 使用一个洋红色方块作为占位符，避免崩溃
                fallback = pg.Surface((64, 64))
                fallback.fill(pg.Color("magenta"))
                self._raw_icons[unit_type] = fallback

    def get_definition(self, unit_type: str) -> UnitDefinition:
        """查阅兵种属性手册"""
        return self._definitions[unit_type]

    def get_icon_surface(self, unit_type: str) -> pg.Surface:
        """获取兵种的原始图片"""
        return self._raw_icons[unit_type]

    def iter_icon_surfaces(self) -> Sequence[tuple[str, pg.Surface]]:
        """遍历所有兵种的图片"""
        return tuple(self._raw_icons.items())


class UnitRenderer:
    """
    兵种渲染器。
    它负责把兵种图标画在地图格子上。
    特别是当一个格子里有好几个兵时，它要负责排版（比如排成 2x2 的样子）。
    """

    def __init__(self, *, repository: UnitRepository, slot_factor: float) -> None:
        self._repository = repository
        self._slot_factor = slot_factor  # 图标缩放比例
        self._icon_size = 0  # 图标在屏幕上的实际大小（像素），稍后计算
        self._scaled_icons: Dict[str, pg.Surface] = {} # 缓存缩放后的图片

    def on_hex_side_changed(self, hex_side: float) -> None:
        """
        当 hex_side (格子的边长) 改变时调用。
        意味着地图缩放了，我们也要重新把图标缩放到合适的大小。
        """
        # 计算图标大小：大约是格子边长的一定比例
        self._icon_size = max(1, int(hex_side * self._slot_factor))
        self._scaled_icons.clear()
        
        # 重新生成所有缩放后的图片
        for unit_type, surface in self._repository.iter_icon_surfaces():
            self._scaled_icons[unit_type] = pg.transform.smoothscale(
                surface, (self._icon_size, self._icon_size)
            )

    def draw_units(self, surface: pg.Surface, center: Tuple[int, int], units: Sequence[UnitState]) -> None:
        """
        画兵的主函数。
        surface: 画布（屏幕）
        center: 格子的中心像素坐标
        units: 这个格子里有哪些兵（UnitState 对象列表）
        """
        if not units or not self._icon_size:
            return
        
        # 遍历每个兵，算出它的位置，然后画上去
        for idx, unit_state in enumerate(units):
            icon = self._scaled_icons.get(unit_state.unit_type)
            if icon is None:
                continue
            # 计算第 idx 个兵应该放在格子的哪个小角落
            pos = self._slot_position(center, idx)
            surface.blit(icon, pos)
            
            # TODO: 如果受伤或混乱，可以在这里画状态图标
            if unit_state.is_confused:
                # 简单画个紫色圈表示混乱
                cx, cy = pos[0] + self._icon_size // 2, pos[1] + self._icon_size // 2
                pg.draw.circle(surface, pg.Color("purple"), (cx, cy), 5)
            elif unit_state.is_injured:
                # 简单画个红点表示受伤
                pg.draw.circle(surface, pg.Color("red"), (pos[0] + 5, pos[1] + 5), 4)

    def selection_rects(self, center: Tuple[int, int], unit_count: int) -> List[pg.Rect]:
        """
        计算点击区域。
        返回一组矩形区域，用来检测鼠标点击了哪个兵。
        """
        rects: List[pg.Rect] = []
        if not self._icon_size:
            return rects
        for idx in range(unit_count):
            pos = self._slot_position(center, idx)
            rects.append(pg.Rect(pos[0], pos[1], self._icon_size, self._icon_size))
        return rects

    def _slot_position(self, center: Tuple[int, int], slot_index: int) -> Slot:
        """
        【重要】计算兵种图标在一个 2x2 网格中的位置。
        布局逻辑：
        - 左上角：留给地形图标了（在 map_manager.py 里画）
        - 右上角：第 1 个兵 (idx=0)
        - 右下角：第 2 个兵 (idx=1)
        - 左下角：第 3 个兵 (idx=2)
        """
        cx, cy = center
        # icon_size 大约是半个格子的边长
        offset = int(self._icon_size) 
        
        # 定义四个可能的槽位坐标（这里存的是绘图时的左上角坐标）
        slots = [
            (cx, cy - offset),      # 兵1：右上角
            (cx, cy),               # 兵2：右下角
            (cx - offset, cy),      # 兵3：左下角
        ]
        
        # 防止兵太多溢出，如果超出了3个，就都叠在最后一个位置上
        if slot_index >= len(slots):
            return slots[-1]
            
        return slots[slot_index]
