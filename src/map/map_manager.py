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
        river_polylines: Sequence[Sequence[Tuple[float, float]]] = (), # 河流数据
        ban_polylines: Sequence[Sequence[Tuple[float, float]]] = (),   # 禁行线数据
    ) -> None:
        self._definition_file = definition_file
        self._terrain_graphics_dir = terrain_graphics_dir
        self._color_resolver = color_resolver
        self._river_polylines = river_polylines
        self._ban_polylines = ban_polylines
        
        # 加载所有格子数据
        self._provinces_list = self._load_provinces(definition_file)
        self._provinces_map: Dict[int, Province] = {p.province_id: p for p in self._provinces_list}
        
        self._hex_side = 0.0  # 格子边长 (像素)，初始为0，稍后会设置
        self._terrain_cache: Dict[str, pg.Surface | None] = {} # 缓存地形图片，避免重复读取硬盘
        self._border_width = 10 # 格子边框的粗细
        self._cached_background: pg.Surface | None = None # 预渲染的地图背景缓存

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
        # 重置缓存
        self._cached_background = None
        
        for p in self._provinces_list:
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
        同时计算是否跨越河流。
        """
        self._adjacency: Dict[int, List[int]] = {}
        # 存储跨河的边 (id1, id2) -> True
        self._river_crossing_edges: Dict[Tuple[int, int], bool] = {}
        
        threshold = (self._hex_side * (3**0.5)) * 1.5
        
        # 预先处理河流段，避免由每个格子去重复遍历
        # river_segments: list of ((x1, y1), (x2, y2)) logic coords
        river_segments = []
        for polyline in self._river_polylines:
            for i in range(len(polyline) - 1):
                river_segments.append((polyline[i], polyline[i+1]))
        
        # 预先处理禁行线段 (Ban lines)
        ban_segments = []
        for polyline in self._ban_polylines:
             for i in range(len(polyline) - 1):
                 ban_segments.append((polyline[i], polyline[i+1]))

        for p1 in self._provinces_list:
            self._adjacency[p1.province_id] = []
            for p2 in self._provinces_list:
                if p1.province_id == p2.province_id:
                    continue
                
                # 1. 距离判定是否相邻
                if p1.center_cache and p2.center_cache:
                    dist = p1.center_cache.distance_to(p2.center_cache)
                    if dist < threshold:
                        
                        # 检测是否被禁行线阻断
                        is_blocked = False
                        A = (p1.x_factor, p1.y_factor)
                        B = (p2.x_factor, p2.y_factor)
                        
                        for (C, D) in ban_segments:
                             if self._segments_intersect(A, B, C, D):
                                 is_blocked = True
                                 break
                        
                        # 如果没有被黑线阻断，才视为邻居
                        if not is_blocked:
                            self._adjacency[p1.province_id].append(p2.province_id)
                            
                            # 2. 判定是否跨河
                            is_crossing = False
                            for (C, D) in river_segments:
                                if self._segments_intersect(A, B, C, D):
                                    is_crossing = True
                                    break
                            
                            if is_crossing:
                                self._river_crossing_edges[(p1.province_id, p2.province_id)] = True

    def _segments_intersect(self, A, B, C, D) -> bool:
        """检测线段 AB 和 CD 是否相交"""
        def ccw(p1, p2, p3):
            return (p3[1]-p1[1]) * (p2[0]-p1[0]) > (p2[1]-p1[1]) * (p3[0]-p1[0])
        return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)

    def find_path_cost(self, start_id: int, target_id: int) -> int:
        """
        计算移动消耗 (Dijkstra 变体)。
        规则：
        1. 基础每步消耗为 1。
        2. 每经过一个山地（Start, Waypoint, End），该点都会贡献 +1 消耗。
           (如果起点就是山地，初始消耗就已经 +1)
        3. 每跨越一次河流，该步消耗额外 +1。
        
        Cost = 路径长度 + sum(1 for node in path if is_mountain(node)) + sum(1 for edge in path if is_river_crossing(edge))
        """
        if start_id == target_id:
            return 0
        
        start_prov = self.get_by_id(start_id)
        if not start_prov: return 9999
        
        # 检查起点山地惩罚
        start_t = start_prov.terrain.lower() if start_prov.terrain else ""
        start_is_mtn = start_t in ("hill", "mountain", "hills", "mountains")
        
        # 初始 Cost = 0 (位移) + (1 if 起点是山 else 0)
        initial_cost = 1 if start_is_mtn else 0
        
        import heapq
        
        # Priority Queue: (current_accumulated_cost, current_id)
        queue = [(initial_cost, start_id)]
        min_costs = {start_id: initial_cost}
        
        while queue:
            curr_total, curr_id = heapq.heappop(queue)
            
            if curr_total > min_costs.get(curr_id, float('inf')):
                continue
            
            if curr_id == target_id:
                return curr_total
            
            neighbors = self._adjacency.get(curr_id, [])
            for next_id in neighbors:
                next_prov = self.get_by_id(next_id)
                if not next_prov: continue
                
                # 计算这一步 (curr -> next) 的增量消耗
                step_cost = 1  # 基础移动消耗
                
                # 1. 目标点是否为山地? (如果是，移动进该点需额外 +1)
                nxt_t = next_prov.terrain.lower() if next_prov.terrain else ""
                is_nxt_mtn = nxt_t in ("hill", "mountain", "hills", "mountains")
                if is_nxt_mtn:
                    step_cost += 1
                
                # 2. 是否跨河?
                is_crossing = self._river_crossing_edges.get((curr_id, next_id), False)
                if is_crossing:
                    step_cost += 1
                
                new_total = curr_total + step_cost
                
                if new_total < min_costs.get(next_id, float('inf')):
                    min_costs[next_id] = new_total
                    heapq.heappush(queue, (new_total, next_id))
                    
        return 9999

    @property
    def provinces(self) -> Sequence[Province]:
        """返回所有格子的列表（只读）"""
        return self._provinces_list

    def get_by_id(self, province_id: int) -> Province | None:
        """根据 ID 查找格子"""
        return self._provinces_map.get(province_id)

    def get_neighbors(self, province_id: int) -> List[Province]:
        """获取相邻的格子"""
        ids = self._adjacency.get(province_id, [])
        return [self._provinces_map[i] for i in ids if i in self._provinces_map]

    def invalidate_cache(self) -> None:
        """使得缓存失效，强制下一帧重绘"""
        self._cached_background = None

    def draw(self, surface: pg.Surface) -> None:
        """
        绘制整个地图。
        使用缓存机制优化性能。
        """
        if not self._hex_side:
            raise RuntimeError("Hex side length has not been initialized (格子边长未初始化)")

        # 检查缓存是否有效 (存在且尺寸匹配)
        if (self._cached_background is None or 
            self._cached_background.get_size() != surface.get_size()):
            
            # 创建新的缓存层 (带透明通道)
            self._cached_background = pg.Surface(surface.get_size(), pg.SRCALPHA)
            
            # 在缓存层上绘制所有静态元素
            for province in self._provinces_list:
                # 1. 使用缓存的中心点 (Vector2)
                if province.center_cache is None or province.vertices_cache is None:
                    continue
                    
                center = province.center_cache
                # 2. 获取所属国家的颜色
                color = self._color_resolver(province.country)
                # 3. 使用缓存的顶点 (List[Vector2])
                vertices = province.vertices_cache
                
                # 4. 画白色的底色（填充）
                pg.draw.polygon(self._cached_background, pg.Color("white"), vertices)
                # 5. 画彩色的边框
                self._draw_hex_border(self._cached_background, color, vertices, self._border_width)
                # 6. 画地形图标 (山、城等)
                self._draw_terrain_icon(self._cached_background, province.terrain, center)
        
        # 直接将缓存好的地图绘制到屏幕上
        surface.blit(self._cached_background, (0, 0))

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
