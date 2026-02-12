"""
这里包含了整个游戏应用的核心逻辑：GameApp。
它是总导演，管理着游戏状态、循环、渲染和逻辑更新。
"""
from __future__ import annotations

import logging
from enum import Enum, auto
from math import sqrt, dist
import random
from typing import Dict, List, Sequence, Tuple

import pygame as pg

from settings import Settings
from src.core.camera import Camera
from src.core.events import EventManager
from src.game_objects.kingdom import KingdomRepository
from src.game_objects.unit import UnitRenderer, UnitRepository
from src.map.map_manager import MapManager
from src.ui.panels import SelectionOverlay
from src.ui.info_panel import InfoPanel

logger = logging.getLogger(__name__)

SQRT3 = sqrt(3)

# --- 河流数据定义 ---
# 这些是预定义好的坐标点序列，用来在地图上画出长江和黄河的线条。
# 坐标单位是逻辑格子单位，之后会被转换成屏幕像素坐标。
YANGTZE_POINTS_1: Sequence[Tuple[float, float]] = (
    (4.5, 6.0),
    (5.0, 5.5),
    (6.0, 5.5),
    (6.5, 5.0),
    (7.5, 5.0),
    (8.0, 5.5),
    (9.0, 5.5),
    (9.5, 5.0),
    (10.5, 5.0),
    (11.0, 4.5),
    (12.0, 4.5),
    (12.5, 5.0),
    (13.5, 5.0),
    (14.0, 4.5),
    (15.0, 4.5),
    (15.5, 4.0),
)
YANGTZE_POINTS_2: Sequence[Tuple[float, float]] = (
    (10.5, 5.0),
    (11.0, 5.5),
    (10.5, 6.0),
    (11.0, 6.5),
    (10.5, 7.0),
)
YELLOW_RIVER_POINTS: Sequence[Tuple[float, float]] = (
    (9.0, 0.5),
    (9.5, 1.0),
    (9.0, 1.5),
    (9.5, 2.0),
    (9.0, 2.5),
    (9.5, 3.0),
    (10.5, 3.0),
    (11.0, 2.5),
    (12.0, 2.5),
    (12.5, 2.0),
    (13.5, 2.0),
    (14.0, 1.5),
)
# 这是一条禁止通行的线（可能是山脉或者关隘）
BAN_LINE_POINTS: Sequence[Tuple[float, float]] = (
    (7.5, 9.0),
    (8.0, 8.5),
    (7.5, 8.0),
    (8.0, 7.5),
    (9.0, 7.5),
    (9.5, 7.0),
    (10.5, 7.0),
)

SelectionEntry = Tuple[int, int]


class GameState(Enum):
    """
    游戏状态枚举。
    游戏在任一时刻只能处于以下一种状态：
    - LOADING: 初始加载界面
    - CHOOSING: 选择势力界面
    - PLAYING: 正式游玩状态
    """
    LOADING = auto()
    CHOOSING = auto()
    PLAYING = auto()


class GameApp:
    def __init__(self, *, settings: Settings, debug: bool = False) -> None:
        """
        初始化游戏应用。
        就像搭建舞台一样，准备好所有的资源、管理器和变量。
        """
        self.settings = settings
        self.debug = debug
        self._running = False # 游戏循环开关

        # 初始化 Pygame 库
        pg.init()
        self.clock = pg.time.Clock() # 用于控制游戏帧率
        
        # 获取当前屏幕分辨率并创建窗口
        display_info = pg.display.Info()
        self.screen_width = display_info.current_w
        self.screen_height = display_info.current_h
        flags = pg.NOFRAME if settings.borderless else 0
        self.window = pg.display.set_mode((self.screen_width, self.screen_height), flags)
        pg.display.set_caption(settings.window_title)

        # 计算六边形格子的边长，使其刚好能铺满屏幕高度的一部分
        self.hex_side = self.screen_height * 2 / (19 * SQRT3)

        # 初始状态设为 LOADING
        self.state = GameState.LOADING
        self.player_country: str | None = None # 玩家选择的国家
        
        # 定义三个国家的标签和颜色
        self.country_labels: Dict[str, str] = {"SHU": "蜀", "WU": "吴", "WEI": "魏"}
        self.country_button_colors: Dict[str, pg.Color] = {
            "SHU": pg.Color("red"),
            "WU": pg.Color("green"),
            "WEI": pg.Color("blue"),
        }

        # 初始化各个子系统管理器
        self.kingdom_repository = KingdomRepository(settings.kingdoms_file)
        
        self.map_manager = MapManager(
            definition_file=settings.map_definition_file,
            terrain_graphics_dir=settings.map_graphics_dir,
            color_resolver=self.kingdom_repository.get_color,
        )
        self.map_manager.set_hex_side(self.hex_side)

        self.unit_repository = UnitRepository(
            settings.units_file,
            settings.asset_root,
        )
        self.unit_renderer = UnitRenderer(
            repository=self.unit_repository,
            slot_factor=settings.icon_slot_size_factor,
        )
        self.unit_renderer.on_hex_side_changed(self.hex_side)

        self.selection_overlay = SelectionOverlay()
        self.selected_units: List[SelectionEntry] = []

        self.camera = Camera()
        self.event_manager = EventManager(self)
        
        # 初始化右侧信息面板
        # 假设右侧留白区域宽度为 300 像素
        panel_rect = pg.Rect(self.screen_width - 300, 50, 280, 400)
        # 我们可以复用一个现有的字体或者稍后在 build_assets 里加载
        # 这里为了避免 None，稍微把 InfoPanel 的初始化推迟到 _build_play_assets 或者先给个默认字体
        self.info_panel: InfoPanel | None = None

        # 预加载各个界面的素材，防止游戏运行时卡顿
        self._build_loading_assets()
        self._build_choosing_assets()
        self._build_play_assets()
        
        # 初始化 InfoPanel (在 build_play_assets 加载了字体之后)
        info_font = self._font("msyh.ttc", 20) # 微软雅黑，大小20
        self.info_panel = InfoPanel(panel_rect, info_font)

    def run(self) -> None:
        """
        启动游戏主循环。
        这是一个死循环，直到 _running 变为 False。
        顺序：处理事件 -> 更新数据 -> 重新绘制
        """
        self._running = True
        logger.info(
            "Starting game loop at %s FPS, resolution %sx%s",
            self.settings.fps,
            self.screen_width,
            self.screen_height,
        )
        while self._running:
            self.event_manager.process() # 1. 处理鼠标键盘输入
            self._update()               # 2. 更新游戏逻辑
            self._render()               # 3. 绘制画面
            
            # pg.display.flip() 将绘制好的缓冲区画面一次性显示到屏幕上
            pg.display.flip()
            # 休息一小会儿，以保持稳定的 FPS
            self.clock.tick(self.settings.fps)

        pg.quit()

    def stop(self) -> None:
        """停止游戏循环，准备退出"""
        self._running = False

    def clear_selection(self) -> None:
        """清空当前选中的单位"""
        self.selected_units.clear()

    def add_selection(self, province_id: int, slot_index: int) -> None:
        """添加一个选中单位"""
        self.selected_units.append((province_id, slot_index))

    def handle_event(self, event: pg.event.Event) -> None:
        """
        分发处理具体的事件。
        根据当前的游戏状态（LOADING/CHOOSING/PLAYING），交给不同的函数处理。
        """
        if event.type == pg.QUIT:
            self.stop()
            return

        if self.state == GameState.LOADING:
            self._handle_loading_event(event)
        elif self.state == GameState.CHOOSING:
            self._handle_choosing_event(event)
        elif self.state == GameState.PLAYING:
            self._handle_playing_event(event)

    def _handle_loading_event(self, event: pg.event.Event) -> None:
        """处理加载界面的事件（比如点击开始按钮）"""
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if self.start_button_rect.collidepoint(event.pos):
                self.state = GameState.CHOOSING

    def _handle_choosing_event(self, event: pg.event.Event) -> None:
        """处理选人界面的事件（点击三个国家的圆球）"""
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            for country, button in self.faction_buttons.items():
                cx, cy = button["center"]
                dx = event.pos[0] - cx
                dy = event.pos[1] - cy
                # 判断点击点是否在圆形按钮内：距离平方 <= 半径平方
                if dx * dx + dy * dy <= self.faction_button_radius**2:
                    self.player_country = country
                    self.state = GameState.PLAYING
                    self.clear_selection()
                    return

    def _handle_playing_event(self, event: pg.event.Event) -> None:
        """处理游戏中的事件"""
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            self.clear_selection() # 按ESC取消选择
        elif event.type == pg.MOUSEBUTTONDOWN:
            if event.button == 1:
                # 优先处理 UI 面板点击
                if self.info_panel and self.info_panel.handle_click(event.pos):
                    return
                # Shift + 左键：选择单位
                if pg.key.get_mods() & pg.KMOD_SHIFT:
                    self._handle_selection_click(event.pos)
            elif event.button == 3:
                # 右键点击：移动或攻击
                self._handle_game_right_click(event.pos)

    def _get_province_at(self, pos: Tuple[int, int]) -> object | None: # object -> Province
        """简单的点击拾取检测"""
        best_p = None
        min_dist = float("inf")
        # 判定阈值：内切圆半径 = hex_side * sqrt(3)/2 ≈ 0.866
        threshold = self.hex_side * 0.9 
        
        for province in self.map_manager.provinces:
            center = province.compute_center(self.hex_side)
            d = dist(pos, center)
            if d < min_dist:
                min_dist = d
                best_p = province
                
        if min_dist <= threshold:
            return best_p
        return None

    def _handle_game_right_click(self, pos: Tuple[int, int]) -> None:
        """处理游戏场景的右键逻辑"""
        if not self.selected_units:
            return
            
        target_province = self._get_province_at(pos)
        if not target_province:
            return
            
        # 根据目标格子的归属判断是移动还是进攻
        # (假设非玩家控制的国家都是敌人/中立，可攻击)
        if target_province.country == self.player_country:
            self._handle_movement(target_province)
        else:
            self._handle_combat(target_province)

    def _handle_movement(self, target: object) -> None: # target: Province
        """处理移动逻辑"""
        # 1. 检查选中单位的来源（只能来自同一个格子）
        source_ids = {pid for pid, _ in self.selected_units}
        if len(source_ids) > 1:
            self.info_panel.show_message("选择单位过多")
            return
        
        # 获取源格子
        source_id = list(source_ids)[0]
        source = self.map_manager.get_by_id(source_id)
        if not source: return
        
        if source.province_id == target.province_id:
            return # 原地不动
            
        # 2. 检查移动距离与行动点
        selected_indices = sorted([idx for pid, idx in self.selected_units if pid == source_id])
        if not selected_indices: return
        
        # 计算物理距离
        start_pos = source.compute_center(self.hex_side)
        end_pos = target.compute_center(self.hex_side)
        pixel_dist = dist(start_pos, end_pos)
        
        # 单位移动步长 (一格圆心距)
        unit_stride = SQRT3 * self.hex_side
        
        moving_units = []
        for idx in selected_indices:
            unit_type = source.units[idx]
            definition = self.unit_repository.get_definition(unit_type)
            
            # 允许的像素距离 = Move * stride * 1.1 (宽松系数)
            # 例如 Move=2，允许移动约 2 格距离
            max_pixel_dist = definition.move * unit_stride * 1.1
            
            if pixel_dist > max_pixel_dist:
                # 按照需求：如果可以移动到就...，如果不可以呢？这里假定有一个跑不到就都不跑
                self.info_panel.show_message("距离过远")
                return
            moving_units.append(unit_type)
            
        # 3. 堆叠检查
        # 目标格子已有兵 + 即将移动过去的兵 > 3
        if len(target.units) + len(moving_units) > 3:
            self.info_panel.show_message("堆叠部队过多")
            return
            
        # 4. 执行移动
        # 从源格子移除及其 tricky，因为 indices 是下标。
        # 我们用 rebuild 的方式最安全
        new_source_list = []
        for i, u in enumerate(source.units):
            if i not in selected_indices:
                new_source_list.append(u)
        source.units = new_source_list
        
        # 添加到目标格子
        target.units.extend(moving_units)
        
        # 移除选中状态
        self.clear_selection()
        
        # 简单反馈
        logger.info(f"Moved {len(moving_units)} units from {source.name} to {target.name}")

    def _handle_combat(self, target: object) -> None: # target: Province
        """处理战斗逻辑"""
        unit_stride = SQRT3 * self.hex_side
        total_attack = 0
        
        # 1. 检查所有攻击者的射程
        for pid, idx in self.selected_units:
            province = self.map_manager.get_by_id(pid)
            if not province: continue
            
            unit_type = province.units[idx]
            definition = self.unit_repository.get_definition(unit_type)
            
            distance = dist(province.compute_center(self.hex_side), target.compute_center(self.hex_side))
            
            # 射程判定
            # Range=1: 覆盖 1 格 (约 1.0 * stride)
            # Range=2: 覆盖 2 格 (约 2.0 * stride)
            allowed_range_px = definition.range * unit_stride * 1.1 # 1.1 是容差
            
            if distance > allowed_range_px:
                self.info_panel.show_message("攻击距离不足", duration=2.0)
                self.clear_selection()
                return

            total_attack += definition.attack

        if total_attack == 0:
            return

        # 2. 计算防御总和
        total_defense = target.defense
        for u in target.units:
            total_defense += self.unit_repository.get_definition(u).defense
            
        # 避免除以0
        if total_defense <= 0.1:
            total_defense = 1.0
            
        ratio = total_attack / total_defense
        
        # 3. 准备投骰子
        self.info_panel.show_combat_request(ratio, lambda: self._resolve_combat(ratio))

    def _resolve_combat(self, ratio: float) -> None:
        """投骰子后的回调"""
        dice = random.randint(1, 6)
        # 规则：这里暂定为 simple score
        # 实际规则可以按需修改
        final_score = ratio * dice
        
        # 显示结果
        if final_score > 5:
            msg = f"大胜! ({final_score:.1f})"
        elif final_score > 2:
            msg = f"小胜 ({final_score:.1f})"
        else:
            msg = f"进攻受挫 ({final_score:.1f})"
            
        self.info_panel.show_combat_result(dice, msg)

    def _handle_selection_click(self, mouse_pos: Tuple[int, int]) -> None:
        """
        检查鼠标是否点击到了某个己方单位。
        """
        if not self.player_country:
            return
        
        # 遍历所有格子，检查点击碰撞
        for province in self.map_manager.provinces:
            if province.country != self.player_country or not province.units:
                continue
            center = province.compute_center(self.hex_side)
            # 获取该格子里所有单位的矩形框
            rects = self.unit_renderer.selection_rects(center, len(province.units))
            for idx, rect in enumerate(rects):
                if rect.collidepoint(mouse_pos):
                    self.add_selection(province.province_id, idx)
                    return

    def _update(self) -> None:
        """更新每一帧的数据逻辑（目前只有镜头输入检查）"""
        self.camera.handle_input()

    def _render(self) -> None:
        """渲染总控：根据状态画对应的界面"""
        if self.state == GameState.LOADING:
            self._render_loading_screen()
        elif self.state == GameState.CHOOSING:
            self._render_choosing_screen()
        else:
            self._render_gameplay()

    def _render_loading_screen(self) -> None:
        """画加载/开始界面"""
        self.window.fill(pg.Color("white"))
        self.window.blit(self.loading_image_right, self.loading_image_right_pos)
        self.window.blit(self.loading_image_left, self.loading_image_left_pos)
        self.window.blit(self.loading_title_surface, self.loading_title_pos)
        pg.draw.rect(self.window, pg.Color("yellow"), self.start_button_rect)
        self.window.blit(self.loading_button_surface, self.loading_button_pos)

    def _render_choosing_screen(self) -> None:
        """画选择势力界面"""
        self.window.fill(pg.Color("white"))
        for surface, position in self.choosing_portraits:
            self.window.blit(surface, position)
        self.window.blit(self.choosing_title_surface, self.choosing_title_pos)
        for country, button in self.faction_buttons.items():
            pg.draw.circle(self.window, button["color"], button["center"], self.faction_button_radius)
            self.window.blit(button["label_surface"], button["label_pos"])

    def _render_gameplay(self) -> None:
        """画游戏主战场"""
        self.window.fill(pg.Color("white"))
        
        # 1. 画地图底层（格子+地形）
        self.map_manager.draw(self.window)
        
        # 2. 画所有兵种单位
        for province in self.map_manager.provinces:
            center = province.compute_center(self.hex_side)
            self.unit_renderer.draw_units(self.window, center, province.units)

        # 3. 画河流和阻挡线
        for polyline in self.yangtze_polylines:
            self._draw_smooth_polyline(pg.Color(173, 216, 230), polyline, 20)
        self._draw_smooth_polyline(pg.Color(173, 216, 230), self.yellow_river_polyline, 20)
        self._draw_smooth_polyline(pg.Color("black"), self.ban_line_polyline, 20)

        # 4. 画回合结束按钮（右下角的圆圈）
        pg.draw.circle(
            self.window,
            pg.Color("black"),
            self.next_turn_center,
            self.next_turn_radius,
            10,
        )
        self.window.blit(self.arrow_image, self.arrow_pos)

        # 5. 画当前玩家国家标签
        if self.player_country:
            tag_surface = self.country_tag_surfaces[self.player_country]
            self.window.blit(tag_surface, self.country_tag_pos)

        # 6. 画选中框（覆盖在最上层）
        self.selection_overlay.draw(
            surface=self.window,
            selections=self.selected_units,
            province_lookup=self.map_manager.get_by_id,
            rect_provider=self.unit_renderer.selection_rects,
            hex_side=self.hex_side,
        )
        
        # 7. 画右侧信息面板 (UI)
        if self.info_panel:
            self.info_panel.draw(self.window)

    def _draw_smooth_polyline(self, color: pg.Color, points: Sequence[Tuple[int, int]], width: int) -> None:
        """
        绘制硬朗连接的折线（Miter Join）。
        普通的 pg.draw.lines 会有缺口，而画圆填充太圆润了。
        这个方法通过计算几何转角，生成一个完美闭合的多边形，
        让河流的转弯呈现出整齐的 120 度切角，符合六边形地图的风格。
        """
        if len(points) < 2:
            return

        # 把点转换成向量方便计算
        vectors = [pg.math.Vector2(p) for p in points]
        half_width = width / 2
        
        # 存储“上岸”和“下岸”的顶点列表
        upper_edge = []
        lower_edge = []

        for i in range(len(vectors)):
            curr = vectors[i]
            
            # 计算当前点的切线方向（即线条走向）
            if i == 0:
                # 起点：切线就是第一段的方向
                tangent = (vectors[1] - vectors[0]).normalize()
            elif i == len(vectors) - 1:
                # 终点：切线就是最后一段的方向
                tangent = (vectors[-1] - vectors[-2]).normalize()
            else:
                # 中间点：切线是前后两段方向的平均值（角平分线方向）
                v_in = (curr - vectors[i - 1]).normalize()
                v_out = (vectors[i + 1] - curr).normalize()
                # 如果两段线几乎反向（折返），为了避免除零错误，稍微偏移一点
                tangent = (v_in + v_out)
                if tangent.length() < 0.01:
                    tangent = pg.math.Vector2(-v_in.y, v_in.x) # 垂直方向
                else:
                    tangent = tangent.normalize()

            # 计算法线方向（垂直于切线）
            # 我们需要把法线旋转 90 度得到宽度方向
            # (-y, x) 是逆时针旋转 90 度
            normal = pg.math.Vector2(-tangent.y, tangent.x)

            # 计算 Miter 长度修正
            # 在转角处，线条会变宽，需要根据角度进行修正
            # 修正系数 miter_len = width / 2 / sin(angle/2)
            # 这里用点积简化计算：dot(normal, segment_normal)
            if 0 < i < len(vectors) - 1:
                # 真实的段法线
                real_segment_normal = pg.math.Vector2(-(vectors[i+1]-curr).y, (vectors[i+1]-curr).x).normalize()
                # 投影长度，避免尖角过长，限制最大长度
                cos_half_angle = normal.dot(real_segment_normal)
                # 防止极其尖锐的角度导致射线过长
                if abs(cos_half_angle) < 0.1: 
                    miter_length = half_width
                else:
                    miter_length = half_width / cos_half_angle
            else:
                miter_length = half_width

            # 生成两个边缘点
            p_upper = curr + normal * miter_length
            p_lower = curr - normal * miter_length
            
            upper_edge.append(p_upper)
            lower_edge.append(p_lower)

        # 构建闭合多边形：上岸点正序 + 下岸点倒序
        full_poly = upper_edge + lower_edge[::-1]
        
        # 1. 绘制实心多边形
        pg.draw.polygon(self.window, color, full_poly)

    # --- 资源构建辅助方法 (Asset Builders) -------------------------------------------------
    # 这些方法负责在游戏开始前把图片、文字预先处理好存入内存
    
    def _build_loading_assets(self) -> None:
        """准备加载界面的图片和文字"""
        height = self.screen_height
        width = self.screen_width

        self.loading_image_right = self._load_ui_image(
            "start_ZHUGELIANG.jpg", (int(height * 0.6), int(height * 0.7))
        )
        self.loading_image_right_pos = (int(width - height * 0.65), int(height * 0.2))

        raw_left = self._load_ui_image(
            "start_SIMAYI.jpg", (int(height * 0.5), int(height * 0.625))
        )
        self.loading_image_left = pg.transform.flip(raw_left, True, False) # 镜像翻转
        self.loading_image_left_pos = (int(height * 0.03), int(height * 0.25))

        self.start_button_rect = pg.Rect(
            int(width * 0.3),
            int(height * 0.75),
            int(width * 0.4),
            int(height * 0.1),
        )

        self.loading_title_surface = self._render_text("STLITI.TTF", int(width * 0.1), "三足鼎立")
        self.loading_title_pos = (int(width * 0.3), 0)

        self.loading_button_surface = self._render_text(
            "STXINGKA.TTF", int(height * 0.1), "开始游戏"
        )
        self.loading_button_pos = (int(width * 0.5 - height * 0.2), int(height * 0.75))

    def _build_choosing_assets(self) -> None:
        """准备选人界面的图片和文字"""
        height = self.screen_height
        width = self.screen_width
        image_size = (int(height * 0.3), int(height * 0.3))
        self.choosing_portraits = [
            (
                self._load_ui_image("choosing_LIUBEI.jpg", image_size),
                (int(width * 0.4 - height * 0.45), int(height * 0.2)),
            ),
            (
                self._load_ui_image("choosing_SUNQUAN.jpg", image_size),
                (int(width * 0.5 - height * 0.15), int(height * 0.2)),
            ),
            (
                self._load_ui_image("choosing_CAOCAO.jpg", image_size),
                (int(width * 0.6 + height * 0.15), int(height * 0.2)),
            ),
        ]

        self.choosing_title_surface = self._render_text("SIMLI.TTF", int(height * 0.1), "选择势力")
        self.choosing_title_pos = (int(width * 0.5 - height * 0.2), 0)

        self.faction_button_radius = int(height * 0.1)
        self.faction_buttons: Dict[str, Dict[str, object]] = {}

        label_surfaces = {
            country: self._render_text("STLITI.TTF", int(height * 0.1), label)
            for country, label in self.country_labels.items()
        }

        self.faction_buttons["SHU"] = {
            "center": (int(width * 0.4 - height * 0.3), int(height * 0.7)),
            "color": self.country_button_colors["SHU"],
            "label_surface": label_surfaces["SHU"],
            "label_pos": (int(width * 0.4 - height * 0.35), int(height * 0.65)),
        }
        self.faction_buttons["WU"] = {
            "center": (int(width * 0.5), int(height * 0.7)),
            "color": self.country_button_colors["WU"],
            "label_surface": label_surfaces["WU"],
            "label_pos": (int(width * 0.5 - height * 0.05), int(height * 0.65)),
        }
        self.faction_buttons["WEI"] = {
            "center": (int(width * 0.6 + height * 0.3), int(height * 0.7)),
            "color": self.country_button_colors["WEI"],
            "label_surface": label_surfaces["WEI"],
            "label_pos": (int(width * 0.6 + height * 0.25), int(height * 0.65)),
        }

    def _build_play_assets(self) -> None:
        """准备游戏主界面的图片（箭头、标签等）"""
        height = self.screen_height
        width = self.screen_width

        self.next_turn_center = (int(width - height * 0.15), int(height * 0.85))
        self.next_turn_radius = int(height * 0.15)

        arrow_size = int(height * 0.13 * sqrt(2))
        self.arrow_image = self._load_ui_image("arrow.jpg", (arrow_size, arrow_size))
        self.arrow_pos = (
            int(width - height * 0.15 - height * 0.13 * 0.5 * sqrt(2)),
            int(height * 0.85 - height * 0.065 * sqrt(2)),
        )

        self.country_tag_font = self._font("STZHONGS.TTF", int(height * 0.1))
        self.country_tag_surfaces = {
            country: self.country_tag_font.render(label, True, pg.Color("black"))
            for country, label in self.country_labels.items()
        }
        self.country_tag_pos = (int(width - height * 0.15), 0)

        # 预计算河流的像素点
        self.yangtze_polylines = tuple(self._scale_points(points) for points in (YANGTZE_POINTS_1, YANGTZE_POINTS_2))
        self.yellow_river_polyline = tuple(self._scale_points(YELLOW_RIVER_POINTS))
        self.ban_line_polyline = tuple(self._scale_points(BAN_LINE_POINTS))

    # --- 辅助工具方法 (Helpers) --------------------------------------------------------
    
    def _scale_points(self, normalized_points: Sequence[Tuple[float, float]]) -> List[Tuple[int, int]]:
        """
        将逻辑坐标转换为屏幕像素坐标。
        逻辑坐标 -> (乘以边长) -> 像素坐标
        Y轴需要额外乘以 根号3，这是六边形几何的特性。
        """
        scaled = []
        for x_factor, y_factor in normalized_points:
            x = int(x_factor * self.hex_side)
            y = int(y_factor * SQRT3 * self.hex_side)
            scaled.append((x, y))
        return scaled

    def _load_ui_image(self, filename: str, size: Tuple[int, int]) -> pg.Surface:
        """加载图片并直接缩放到指定大小"""
        surface = pg.image.load(self.settings.ui_graphics_dir / filename).convert_alpha()
        return pg.transform.smoothscale(surface, size)

    def _font(self, filename: str, size: int) -> pg.font.Font:
        """加载字体"""
        return pg.font.Font(self.settings.fonts_dir / filename, size)

    def _render_text(self, filename: str, size: int, text: str, color: pg.Color | str = "black") -> pg.Surface:
        """使用指定字体和大小渲染一段文字，返回图片表面"""
        font = self._font(filename, size)
        return font.render(text, True, pg.Color(color))
