"""
这个文件负责管理地图的核心功能：加载、绘制地形、计算格子坐标。
它是游戏地图的“大管家”。
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

import pygame as pg

from .geometry import hex_vertices
from .province import Province

# ColorResolver 是一个函数类型的别名，它接收一个国家代码字符串，返回一个颜色对象。
# 这样做是为了让类型提示更清晰。
ColorResolver = Callable[[str], pg.Color]


class MapManager:
    """地图管理器类"""

    def __init__(
        self,
        *,
        definition_file: Path,      # 地图定义文件 (CSV) 的路径
        terrain_graphics_dir: Path, # 地形图片文件夹的路径
        color_resolver: ColorResolver, # 用来获取国家颜色的函数
    ) -> None:
        self._definition_file = definition_file
        self._terrain_graphics_dir = terrain_graphics_dir
        self._color_resolver = color_resolver
        
        # 加载所有格子数据
        self._provinces = self._load_provinces(definition_file)
        
        self._hex_side = 0.0  # 格子边长 (像素)，初始为0，稍后会设置
        self._terrain_cache: Dict[str, pg.Surface | None] = {} # 缓存地形图片，避免重复读取硬盘
        self._border_width = 10 # 格子边框的粗细

    @staticmethod
    def _load_provinces(definition_file: Path) -> List[Province]:
        """
        从 CSV 文件读取地图定义。
        CSV 里的每一行代表一个格子 (Province)。
        """
        provinces: List[Province] = []
        with definition_file.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                # 解析单位列表，比如 "unit1;unit2" 分割成 ["unit1", "unit2"]
                units_raw = row.get("units", "").strip()
                units = [token for token in units_raw.split(";") if token]
                
                provinces.append(
                    Province(
                        province_id=int(row["id"]),
                        name=row["name"],
                        country=row["country"],
                        terrain=row["terrain"],
                        defense=float(row["defense"]),
                        victory_point=float(row["point"]),
                        x_factor=float(row["x_factor"]),
                        y_factor=float(row["y_factor"]),
                        units=units,
                    )
                )
        return provinces

    def set_hex_side(self, side_length: float) -> None:
        """设置格子的边长，这通常在窗口大小确定后调用"""
        self._hex_side = side_length

    @property
    def provinces(self) -> Sequence[Province]:
        """返回所有格子的列表（只读）"""
        return self._provinces

    def get_by_id(self, province_id: int) -> Province | None:
        """根据 ID 查找格子"""
        # 这是一个生成器表达式，寻找第一个匹配在这个 ID 的格子
        return next((p for p in self._provinces if p.province_id == province_id), None)

    def draw(self, surface: pg.Surface) -> None:
        """
        绘制整个地图。
        这个函数会在每一帧被调用，所以效率很重要。
        """
        if not self._hex_side:
            raise RuntimeError("Hex side length has not been initialized (格子边长未初始化)")

        for province in self._provinces:
            # 1. 计算中心点
            center = province.compute_center(self._hex_side)
            # 2. 获取所属国家的颜色
            color = self._color_resolver(province.country)
            # 3. 计算六边形的 6 个顶点坐标
            vertices = hex_vertices(center, self._hex_side)
            
            # 4. 画白色的底色（填充）
            pg.draw.polygon(surface, pg.Color("white"), vertices)
            # 5. 画彩色的边框
            pg.draw.polygon(surface, color, vertices, self._border_width)
            # 6. 画地形图标 (山、城等)
            self._draw_terrain_icon(surface, province.terrain, center)

    def _draw_terrain_icon(self, surface: pg.Surface, terrain: str, center: tuple[int, int]) -> None:
        """绘制地形图标，放在格子的左上角"""
        icon = self._get_terrain_icon(terrain)
        if icon is None:
            return
            
        # 2x2 网格布局: 左上角留给地形
        # 计算偏移量，大约是边长的一半
        offset = int(self._hex_side * 0.5)
        
        # 计算左上角的坐标
        # 注意: blit 函数通常以图片的左上角为锚点
        pos = (center[0] - offset, center[1] - offset)
        surface.blit(icon, pos)

    def _get_terrain_icon(self, terrain: str) -> pg.Surface | None:
        """
        获取地形对应的图片。
        使用缓存机制：第一次用到某个地形时才加载图片，之后就直接用缓存。
        """
        key = terrain.lower()
        if key == "plain": # 平原没有图标
            return None
        
        if key not in self._terrain_cache:
            # 映射表：地形名称 -> 文件名
            filename = {
                "city": "city_icon.jpg",
                "hill": "hill_icon.jpg",
            }.get(key)
            
            if filename is None:
                # 如果没有定义图片，缓存 None，下次别再找了
                self._terrain_cache[key] = None
                return None
            
            # 加载并缩放图片
            surface = pg.image.load(self._terrain_graphics_dir / filename).convert_alpha()
            scale = int(0.5 * self._hex_side) # 图标大小设为格子边长的一半
            self._terrain_cache[key] = pg.transform.smoothscale(surface, (scale, scale))
            
        return self._terrain_cache[key]
