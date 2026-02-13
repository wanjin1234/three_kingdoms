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
from src.game_objects.unit import UnitState

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
                unit_types = [token for token in units_raw.split(";") if token]
                # 转换为 UnitState 对象
                units_objs = [UnitState(u_type) for u_type in unit_types]
                
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
                        units=units_objs,
                    )
                )
        return provinces

    def set_hex_side(self, side_length: float) -> None:
        """设置格子的边长，这通常在窗口大小确定后调用"""
        self._hex_side = side_length
        # 预计算所有格子的几何信息 (利用 Pygame Vector2 进行优化)
        for p in self._provinces:
            # 1. 计算中心点 (Tuple -> Vector2)
            cx, cy = p.compute_center(side_length)
            p.center_cache = pg.math.Vector2(cx, cy)
            
            # 2. 计算顶点 (Tuple -> Vector2)
            # hex_vertices 返回 Tuple[Tuple[int, int], ...]
            # 我们将其转换为 List[pg.math.Vector2] 方便后续数学计算
            raw_verts = hex_vertices((cx, cy), side_length)
            p.vertices_cache = [pg.math.Vector2(v) for v in raw_verts]
            
        # 3. 构建邻接图
        self._build_adjacency_graph()

    def _build_adjacency_graph(self) -> None:
        """
        基于几何距离构建格子的邻接关系图。
        用于寻路算法。
        """
        self._adjacency: Dict[int, List[int]] = {}
        # 两个正六边形邻居的中心距离约为 sqrt(3) * side
        # 我们给定一个稍微大一点的阈值 (1.1倍) 来容错
        threshold = (self._hex_side * (3**0.5)) * 1.1
        
        for p1 in self._provinces:
            self._adjacency[p1.province_id] = []
            for p2 in self._provinces:
                if p1.province_id == p2.province_id:
                    continue
                # 计算距离
                if p1.center_cache and p2.center_cache:
                    dist = p1.center_cache.distance_to(p2.center_cache)
                    if dist < threshold:
                        self._adjacency[p1.province_id].append(p2.province_id)

    def find_path_cost(self, start_id: int, target_id: int) -> int:
        """
        使用 Dijkstra 算法计算从起点到终点的移动消耗。
        返回消耗点数 (cost)。如果无法到达，返回 9999。
        
        消耗规则：
        - 基础消耗 1
        - 进入 山地(hill/mountain) 额外消耗 1 (共2)
        - // TODO: 跨河逻辑
        """
        # 如果起点和终点重合
        if start_id == target_id:
            return 0
            
        import heapq
        
        # Priority Queue: (current_cost, province_id)
        queue = [(0, start_id)]
        costs = {start_id: 0}
        
        while queue:
            current_cost, current_id = heapq.heappop(queue)
            
            # 如果找到终点 (注意: 我们可能发现更短路径，但Dijkstra保证第一次pop就是最短)
            if current_id == target_id:
                return current_cost
            
            # 如果当前路径比已知的长，跳过
            if current_cost > costs.get(current_id, float('inf')):
                continue
                
            # 遍历邻居
            neighbors = self._adjacency.get(current_id, [])
            for next_id in neighbors:
                next_prov = self.get_by_id(next_id)
                if not next_prov: continue
                
                # 计算移动到 next_id 的代价
                # 基础代价 1
                step_cost = 1
                
                # 地形判定: 如果目标地是山地，消耗+1
                terrain = next_prov.terrain.lower() if next_prov.terrain else ""
                if terrain in ("hill", "mountain", "hills", "mountains"):
                    step_cost += 1
                
                new_cost = current_cost + step_cost
                
                if new_cost < costs.get(next_id, float('inf')):
                    costs[next_id] = new_cost
                    heapq.heappush(queue, (new_cost, next_id))
                    
        return 9999

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
            # 1. 使用缓存的中心点 (Vector2)
            if province.center_cache is None or province.vertices_cache is None:
                # 如果尚未初始化缓存（理论上不会发生），回退或跳过
                continue
                
            center = province.center_cache
            # 2. 获取所属国家的颜色
            color = self._color_resolver(province.country)
            # 3. 使用缓存的顶点 (List[Vector2])
            vertices = province.vertices_cache
            
            # 4. 画白色的底色（填充）
            pg.draw.polygon(surface, pg.Color("white"), vertices)
            # 5. 画彩色的边框
            self._draw_hex_border(surface, color, vertices, self._border_width)
            # 6. 画地形图标 (山、城等)
            self._draw_terrain_icon(surface, province.terrain, center)

    def _draw_hex_border(self, surface: pg.Surface, color: pg.Color, vertices: Sequence[pg.math.Vector2], width: int) -> None:
        """
        绘制六边形的边框，使用硬朗的棱角连接 (Miter Join)。
        """
        if len(vertices) < 3:
            return

        # 把点转换成向量方便计算 (现在传入的就是 List[Vector2])
        vectors = vertices
        count = len(vectors)
        half_width = width / 2
        
        upper_edge = []
        lower_edge = []

        for i in range(count):
            curr = vectors[i]
            prev = vectors[(i - 1) % count]
            next_p = vectors[(i + 1) % count]
            
            # 计算前后两段线的方向
            v_in = (curr - prev).normalize()
            v_out = (next_p - curr).normalize()
            
            # 切线方向是角平分线
            tangent = (v_in + v_out).normalize()
            
            # 法线方向（垂直于切线）
            # (-y, x) 是逆时针旋转 90 度
            normal = pg.math.Vector2(-tangent.y, tangent.x)
            
            # 真实的段法线 (当前点到下一点的边的法线)
            segment_vec = next_p - curr
            segment_normal = pg.math.Vector2(-segment_vec.y, segment_vec.x).normalize()
            
            # 投影计算 Miter 长度
            cos_half_angle = normal.dot(segment_normal)
            if abs(cos_half_angle) < 0.1:
                miter_length = half_width
            else:
                miter_length = half_width / cos_half_angle

            # 生成两个边缘点
            p_upper = curr + normal * miter_length
            p_lower = curr - normal * miter_length
            
            upper_edge.append(p_upper)
            lower_edge.append(p_lower)

        # 1. 填充实体颜色
        # 我们用6个四边形拼出一个闭合的粗框
        for i in range(count):
            next_i = (i + 1) % count
            poly = [
                upper_edge[i],
                upper_edge[next_i],
                lower_edge[next_i],
                lower_edge[i]
            ]
            pg.draw.polygon(surface, color, poly)

    def _draw_terrain_icon(self, surface: pg.Surface, terrain: str, center: pg.math.Vector2) -> None:
        """绘制地形图标，放在格子的左上角"""
        if not terrain: return
        
        # 2x2 网格布局: 左上角留给地形
        # 统一使用 0.6 倍边长作为图标大小，与兵种图标保持一致
        icon_size = self._hex_side * 0.6
        
        # 计算左上角的坐标
        # pos = center - (icon_size, icon_size)
        pos = (center.x - icon_size, center.y - icon_size)
        
        icon = self._get_terrain_icon(terrain)
        if icon:
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
            # 优先尝试 png（支持透明），然后 jpg
            filename_map = {
                "city": ["city_icon.png", "city_icon.jpg"],
                "hill": ["hill_icon.png", "hill_icon.jpg"],
            }
            
            candidates = filename_map.get(key)
            if not candidates:
                self._terrain_cache[key] = None
                return None
            
            loaded_surface = None
            for fname in candidates:
                fpath = self._terrain_graphics_dir / fname
                if fpath.exists():
                    try:
                        # 增加异常捕获的详细程度，并做一下防御性编程
                        surf = pg.image.load(fpath).convert_alpha()
                        
                        target_size = int(0.6 * self._hex_side)
                        if target_size <= 0:
                            # 防止尺寸过小导致崩溃
                            target_size = 1
                            
                        # 先尝试 smoothscale，如果报错则退化为 scale
                        try:
                            loaded_surface = pg.transform.smoothscale(surf, (target_size, target_size))
                        except Exception as e:
                            print(f"smoothscale failed for {fname}, falling back to scale: {e}")
                            loaded_surface = pg.transform.scale(surf, (target_size, target_size))
                            
                        break
                    except Exception as e:
                        print(f"Failed to load {fname}: {e}")
                        continue
            
            self._terrain_cache[key] = loaded_surface
            
        return self._terrain_cache[key]
