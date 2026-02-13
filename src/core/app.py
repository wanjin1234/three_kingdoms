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
from src.core.combat import get_ratio_column, resolve_combat, COMBAT_TABLE, CombatPreview
from src.game_objects.kingdom import KingdomRepository
from src.game_objects.unit import UnitRenderer, UnitRepository
from src.map.map_manager import MapManager
from src.ui.panels import SelectionOverlay
from src.ui.info_panel import InfoPanel, CardPanel

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

        # 在初始化 Pygame 之前设置 DPI 感知，以确保获取到正确的物理分辨率
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

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
        
        # 设置窗口图标 (可选，让 Alt+Tab 时显示漂亮的图标)
        # icon = pg.image.load(settings.graphics_dir / "icon.jpg")
        # pg.display.set_icon(icon)

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
        
        # 初始化右侧信息面板 (使用相对坐标使其自适应分辨率)
        # 左侧位于屏幕70%，右侧位于100%（即拓宽5%），上侧位于15%，下侧60%（往下移10%）
        panel_x = int(self.screen_width * 0.70)
        panel_y = int(self.screen_height * 0.15)
        panel_w = int(self.screen_width * 0.30)  
        panel_h = int(self.screen_height * 0.45) # 60% - 15%
        
        panel_rect = pg.Rect(panel_x, panel_y, panel_w, panel_h)
        self.info_panel: InfoPanel | None = None
        self.card_panel: CardPanel | None = None

        # 预加载各个界面的素材，防止游戏运行时卡顿
        self._build_loading_assets()
        self._build_choosing_assets()
        self._build_play_assets()
        
        # 初始化 InfoPanel (在 build_play_assets 加载了字体之后)
        font_size = int(self.screen_height * 0.025) # 字体大小约占屏幕高度的 2.5%
        info_font = self._font("msyh.ttc", font_size) 
        self.info_panel = InfoPanel(panel_rect, info_font)
        
        # 保存字体给战斗UI使用
        self.combat_ui_font = info_font
        
        # 初始化 CardPanel
        # 垂直位置 60% - 85%，水平同 InfoPanel
        card_rect = pg.Rect(
            panel_x,
            int(self.screen_height * 0.60),
            panel_w,
            int(self.screen_height * 0.25) # 85% - 60%
        )
        self.card_panel = CardPanel(card_rect, info_font)
        
        # 战斗UI状态 (位于顶部栏)
        self.show_combat_ui = False
        self.combat_ratio_val: float = 0.0
        self.combat_callback: Callable[[], None] | None = None
        self.combat_btn_rect: pg.Rect | None = None  # 在 render 时计算
        
        # 战斗结果显示 (Top UI area)
        self.combat_result_title: str | None = None # e.g. "1:1 · 骰6 · A1"
        self.combat_result_timer: float = 0.0       # 显示倒计时

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

    def clear_selection(self, clear_ui: bool = True) -> None:
        """清空当前选中的单位"""
        self.selected_units.clear()
        
        # 无论如何，只要取消选择，战斗请求UI（按钮）就应该消失
        self.show_combat_ui = False 
        
        # 只要点击了地图上的其他东西（或者清空选择），就应该清空上一次的战果(Top UI)
        if clear_ui:
            self.combat_result_title = None
            self.combat_result_timer = 0
            if self.info_panel: 
                 self.info_panel.show_properties("") # 清空面板

    def add_selection(self, province_id: int, slot_index: int) -> None:
        """添加一个选中单位"""
        # 防止重复添加
        new_entry = (province_id, slot_index)
        if new_entry in self.selected_units:
            return
            
        self.selected_units.append(new_entry)
        self._update_selection_info() # 更新面板信息

    def _get_unit_abbr(self, unit_type: str) -> str:
        """获取单位类型的单字简称"""
        if "infantry" in unit_type: return "步"
        if "cavalry" in unit_type: return "骑"
        if "archer" in unit_type: return "弓"
        return unit_type[0].upper()

    def _format_unit_info(self, u_state, prefix: str = "") -> str:
        """通用单位信息格式化"""
        u_def = self.unit_repository.get_definition(u_state.unit_type)
        u_abbr = self._get_unit_abbr(u_state.unit_type)
        
        status = []
        if u_state.is_injured: status.append("伤")
        if u_state.is_confused: status.append("乱")
        status_str = f"({''.join(status)})" if status else ""
        
        # [Prefix步(伤)]
        label = f"[{prefix}{u_abbr}{status_str}]"
        
        attrs = [
            f"血{u_state.hp}",
            f"攻{u_def.attack}",
            f"防{u_def.defense}",
            f"移{u_def.move}",
            f"射{u_def.range}",
            f"疲{u_state.attack_count}"
        ]
        return f"{label} {'·'.join(attrs)}"

    def _update_selection_info(self) -> None:
        """更新信息面板显示的选中单位属性"""
        if not self.selected_units:
            return

        lines = []
        for pid, idx in self.selected_units:
            prov = self.map_manager.get_by_id(pid)
            if not prov: continue
            u_state = prov.units[idx]
            lines.append(self._format_unit_info(u_state))
            # lines.append("-" * 15) # 不需要分割线了
            
        if self.info_panel:
            self.info_panel.show_properties("\n".join(lines))

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
                # 0. 优先处理顶部的战斗按钮
                if self.show_combat_ui and self.combat_btn_rect and self.combat_btn_rect.collidepoint(event.pos):
                    if self.combat_callback:
                        self.combat_callback()
                    # 点击按钮后，UI会在 clear_selection 关闭，或者在 callback 里处理
                    # 这里 return 防止点穿到下面地图
                    return

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
            # 优先使用缓存的中心点
            center = province.center_cache if province.center_cache else province.compute_center(self.hex_side)
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
            
        # 3. 如果目标地是敌方且有兵 -> 战斗
        # 4. 如果目标地是敌方但无兵 -> 移动（占领）
        # 5. 如果目标地是己方 -> 移动（调动）
        
        # 检查是否是敌方
        is_enemy = (target_province.country != self.player_country)
        has_enemy_units = (len(target_province.units) > 0)
        
        if is_enemy and has_enemy_units:
            self._handle_combat(target_province)
        else:
            # 移动或占领空地
            self._handle_movement(target_province)

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
        
        # 计算物理距离 (优先使用缓存)
        start_pos = source.center_cache if source.center_cache else source.compute_center(self.hex_side)
        end_pos = target.center_cache if target.center_cache else target.compute_center(self.hex_side)
        pixel_dist = dist(start_pos, end_pos)
        
        # 单位移动步长 (一格圆心距)
        unit_stride = SQRT3 * self.hex_side
        
        moving_units = []
        for idx in selected_indices:
            unit_state = source.units[idx]
            definition = self.unit_repository.get_definition(unit_state.unit_type)
            
            # 允许的像素距离 = Move * stride * 1.1 (宽松系数)
            max_pixel_dist = definition.move * unit_stride * 1.1
            
            if pixel_dist > max_pixel_dist:
                self.info_panel.show_message("距离过远")
                return
            moving_units.append(unit_state)
            
        # 3. 堆叠检查
        # 目标格子已有兵 + 即将移动过去的兵 > 3
        if len(target.units) + len(moving_units) > 3:
            self.info_panel.show_message("堆叠部队过多")
            return
            
        # 4. 执行移动
        new_source_list = []
        for i, u in enumerate(source.units):
            if i not in selected_indices:
                new_source_list.append(u)
        source.units = new_source_list
        
        # 添加到目标格子
        target.units.extend(moving_units)
        
        # 如果移动成功且有单位进入，占领该地
        if moving_units:
             target.country = self.player_country
        
        # 移除选中状态
        self.clear_selection()
        
        # 简单反馈
        logger.info(f"Moved {len(moving_units)} units from {source.name} to {target.name}")

    def _calculate_unit_powers(self, unit_state) -> Tuple[float, float]:
        """计算单位当前的攻击力和防御力 (考虑受伤和混乱)"""
        definition = self.unit_repository.get_definition(unit_state.unit_type)
        atk = float(definition.attack)
        dfs = float(definition.defense)
        
        # 受伤减半
        if unit_state.is_injured:
            atk *= 0.5
            dfs *= 0.5
            
        # 混乱 -1
        if unit_state.is_confused:
            atk = max(0, atk - 1)
            dfs = max(0, dfs - 1)
            
        return atk, dfs

    def _handle_combat(self, target: object) -> None: # target: Province
        """处理战斗逻辑"""
        unit_stride = SQRT3 * self.hex_side
        total_attack = 0.0
        
        participating_attackers = [] # List[(province, unit_state)]
        
        # 1. 检查所有攻击者的射程并计算攻击力
        for pid, idx in self.selected_units:
            province = self.map_manager.get_by_id(pid)
            if not province: continue
            
            unit_state = province.units[idx]
            definition = self.unit_repository.get_definition(unit_state.unit_type)
            
            p_center = province.center_cache if province.center_cache else province.compute_center(self.hex_side)
            t_center = target.center_cache if target.center_cache else target.compute_center(self.hex_side)
            
            current_distance = dist(p_center, t_center)
            allowed_range_px = definition.range * unit_stride * 1.1 
            
            if current_distance > allowed_range_px:
                self.info_panel.show_message(f"距离不足:{definition.range}", duration=2.0)
                self.clear_selection(clear_ui=False)
                return

            atk, _ = self._calculate_unit_powers(unit_state)
            total_attack += atk
            participating_attackers.append((province, unit_state))

        if total_attack <= 0:
            self.info_panel.show_message("攻击力太低")
            return

        # 2. 计算防御总和 (单位防御总和)
        # 地形防御加成 (Target Defense) 暂不是防御力的一部分？通常是防御力 + 地形？
        # 用户需求："计算防御时按照它们防御力的总和"。没提地形。这里先忽略地形defense属性，或者地形作为修正？
        # 大部分游戏是 (UnitDef + Terrain) * Stack。还是 UnitDef * Stack + Terrain? 
        # 用户说："计算防御时按照它们防御力的总和"。严格按字面意思。
        total_defense = 0.0
        for u in target.units:
            _, dfs = self._calculate_unit_powers(u)
            total_defense += dfs
            
        if total_defense <= 0.1:
            total_defense = 0.1 # 防止除零
            
        # 3. 夹击检测
        # "一方单位所在格子周围的6格上有两格及以上存在参与进攻的敌方部队...判定向不利于其的方向移动一列"
        # 这里判断防守方(target)是否被夹击
        # 我们检查参与进攻的部队来自哪些格子
        attacker_provinces = {p.province_id for p, _ in participating_attackers}
        # 还要检查其他未参与进攻但 adjacent 的 friendly units?
        # 用户说："存在参与进攻的敌方部队"。Implicitly MUST be participating.
        # 所以只看 attacker_provinces.
        
        # 理论上 attacker_provinces 肯定是 target 的邻居 (range 1) 或者 range 2.
        # 如果 range 2 即使不相邻也算夹击吗？ "所在格子周围的6格上有..." -> 必须相邻。
        
        neighbor_count = 0
        target_center = target.center_cache if target.center_cache else target.compute_center(self.hex_side)
        neighbor_threshold = unit_stride * 1.1
        
        for p_id in attacker_provinces:
            prov = self.map_manager.get_by_id(p_id)
            if not prov: continue 
            
            p_center = prov.center_cache if prov.center_cache else prov.compute_center(self.hex_side)
            d = dist(p_center, target_center)
            if d < neighbor_threshold:
                neighbor_count += 1
                
        is_flanked = (neighbor_count >= 2)

        # 4. 计算 CRT 列
        col_index = get_ratio_column(total_attack, total_defense, is_flanked)
        ratio_val = total_attack / total_defense
        
        # 5. 准备投骰子
        # 生成进攻方预览信息
        atk_lines = []
        for _, u_state in participating_attackers:
             atk_lines.append(self._format_unit_info(u_state, prefix="攻"))
        attacker_info = "\n".join(atk_lines)

        # 生成防守方预览信息
        def_lines = []
        for u in target.units:
             def_lines.append(self._format_unit_info(u, prefix="防"))
        defender_info = "\n".join(def_lines)

        # 设置战斗 UI 状态
        self.show_combat_ui = True
        
        # 既然开始了新的战斗准备，就清空上一轮的战果显示
        self.combat_result_title = None
        self.combat_result_timer = 0
        
        self.combat_ratio_val = ratio_val
        self.combat_callback = lambda: self._resolve_combat(col_index, participating_attackers, target)
        
        # 面板只显示详情
        self.info_panel.show_combat_details(attacker_info, defender_info)

    def _resolve_combat(self, col_index: int, attackers: List, target_province: object) -> None:
        """投骰子后的回调"""
        # 战斗开始结算，立刻清除选中状态，防止后续操作引用到已死亡或移动的单位
        self.clear_selection(clear_ui=False)
        
        # 记录战斗前的防守方列表（引用），以便战后统计（其中单位的属性会被修改）
        # target_province.units 之后会被清理移除死亡单位，所以由于我们要显示战损，需要先存一份
        defenders_snapshot = list(target_province.units)

        dice = random.randint(1, 6)
        result_code = resolve_combat(dice, col_index)
        
        # 解析结果并应用伤害
        import re
        
        # 伤害统计
        dmg_attacker = 0
        dmg_defender = 0
        confused_defender = False
        retreat_defender = False
        
        if "A2" in result_code: dmg_attacker = 2
        elif "A1" in result_code: dmg_attacker = 1
        
        if "D1" in result_code: dmg_defender = 1
        
        if "AG" in result_code:
            self._apply_confusion(attackers)
            
        if "DG" in result_code:
            self._apply_confusion([(None, u) for u in target_province.units])
            confused_defender = True
            
        if "DR" in result_code or "R" in result_code and "D" in result_code: # D1R or DR
            retreat_defender = True
            
        # Apply Damage
        if dmg_attacker > 0:
            self._apply_damage([u for _, u in attackers], dmg_attacker)
            
        if dmg_defender > 0:
            self._apply_damage(target_province.units, dmg_defender)
            
        # Retreat Logic
        if retreat_defender:
            self._handle_retreat(target_province)
            
        # 疲劳判定
        for _, u in attackers:
            u.attack_count += 1
            if u.attack_count >= 2:
                u.is_confused = True
                
        # 战斗后清理
        self._cleanup_dead_units(attackers, target_province)
        
        # 进占逻辑
        if not target_province.units:
            self._advance_after_combat(attackers, target_province)
            
        # --- 生成详细战报 ---
        
        # 1. 战果标题: 比值·骰点·结果
        ratio_strs = ["1:2", "1:1", "2:1", "3:1", "4:1", "5:1"]
        # col_index 可能会稍越界（比如夹击后），限制一下查找
        r_idx = max(0, min(5, col_index))
        ratio_str = ratio_strs[r_idx]
        
        # 结果标题行： 1:1 · 骰6 · A1
        title_line = " · ".join([ratio_str, f"骰{dice}", result_code])
        
        # 结果简报行： 攻损X · 防损Y
        summary_parts = [f"攻损{dmg_attacker}", f"防损{dmg_defender}"]
        summary_line = " · ".join(summary_parts)
        
        status_msgs = []
        if confused_defender: status_msgs.append("防乱")
        if retreat_defender: status_msgs.append("防退")
        status_line = " · ".join(status_msgs) if status_msgs else None
        
        # 最终组合：把所有非空行用换行符连起来
        title_lines = [title_line, summary_line]
        if status_line:
            title_lines.append(status_line)
            
        full_title_str = "\n".join(title_lines)
        
        # 详细列表日志 (只保留具体单位状态)
        logs = []
        
        # 2. 进攻方战后状态
        logs.append("--- 进攻方 ---")
        for _, u_state in attackers:
            logs.append(self._format_unit_info(u_state, prefix="攻"))
                
        # 3. 防守方战后状态
        # 使用 defenders_snapshot 确保显示所有参与战斗的单位（包括死亡的）
        if defenders_snapshot:
            logs.append("--- 防守方 ---")
            for u_state in defenders_snapshot:
                logs.append(self._format_unit_info(u_state, prefix="防"))
        else:
             logs.append("防守方全灭或撤离")
        
        # 3. 显示结果 (Top UI) + 详情 (InfoPanel)
        self.combat_result_title = full_title_str
        self.combat_result_timer = -1 # <0 表示不自动消失
        
        # 不再让 Panel 显示标题
        self.info_panel.show_combat_result(None, None, "\n".join(logs))
            
    def _apply_damage(self, units: List, amount: int) -> None:
        """分配伤害"""
        # 排序：未受伤(False) < 已受伤(True). 防御力低 < 防御力高.
        # Key: (is_injured, defense)
        # 我们希望打 未受伤且防御低 的。
        # (False, 3), (False, 5), (True, 3)
        # Sort Ascending works perfectly.
        
        # 为了能 modifying state, we create a list of candidates
        candidates = sorted(units, key=lambda u: (u.is_injured, self.unit_repository.get_definition(u.unit_type).defense))
        
        hits_left = amount
        for u in candidates:
            if hits_left <= 0: break
            # 扣血
            u.hp -= 1
            hits_left -= 1
            
    def _apply_confusion(self, unit_tuples: List) -> None:
        """应用混乱，传入 (prov, unit) 列表"""
        # 这里的排序逻辑同伤害
        units = [u for _, u in unit_tuples]
        candidates = sorted(units, key=lambda u: (u.is_injured, self.unit_repository.get_definition(u.unit_type).defense))
        
        if candidates:
            target = candidates[0] # 只混乱一个？"DG" usually entire stack or 1? 
            # Rule: "选取混乱单位的机制与伤害相同" implies singular target or distributed? 
            # Usually status effects apply to the stack or top unit. 
            # "DG" likely means "Defender Disordered/Grim".
            # Given "机制与伤害相同", and damage has a number (1,2), maybe confusion is 1 unit?
            # Let's assume 1 unit for now.
            
            if target.is_confused:
                target.hp -= 1 # 连续混乱 -> 扣血
            else:
                target.is_confused = True

    def _handle_retreat(self, province: object) -> None:
        """处理撤退"""
        # 尝试找一个友方或空的格子
        neighbors = self._get_neighbors(province)
        valid_retreats = [n for n in neighbors if n.country == province.country or not n.units]
        
        if valid_retreats:
            # 随机选一个撤
            dest = valid_retreats[0]
            dest.units.extend(province.units)
            province.units.clear()
            logger.info(f"Defenders retreated to {dest.name}")
        else:
            # 没地方跑 -> 受到 1 点额外伤害
            self._apply_damage(province.units, 1)

    def _cleanup_dead_units(self, attackers: List, target: object) -> None:
        """清理战场"""
        # 清理进攻方
        # 注意：UnitState 和 Province 是 mutable dataclass，不能直接放入 set 哈希去重
        # 所以我们需要通过 id 或遍历来检查
        
        any_dead = False
        for _, u in attackers:
            if u.hp <= 0:
                any_dead = True
                break
        
        if any_dead:
            # 找出涉及的省份并去重 (通过 province_id)
            seen_prov_ids = set()
            unique_provs = []
            for p, _ in attackers:
                if p.province_id not in seen_prov_ids:
                    seen_prov_ids.add(p.province_id)
                    unique_provs.append(p)
            
            # 对每个省份执行清理
            for p in unique_provs:
                p.units = [u for u in p.units if u.hp > 0]
                
        # 清理防守方
        target.units = [u for u in target.units if u.hp > 0]
        
    def _advance_after_combat(self, attackers: List, target: object) -> None:
        """进占: 派出至多2个单位"""
        # 简单策略：移动前两个还能动的进攻单位
        movers = 0
        limit = 2
        
        # 必须是未死亡的
        # 为了避免 modify list while iterating, we query current state
        # attackers links to (prov, unit_state)
        
        for prov, unit in attackers:
            if movers >= limit: break
            if unit.hp > 0 and unit in prov.units: # 确保还在原格子里（有的可能死了）
                prov.units.remove(unit)
                target.units.append(unit)
                # 占领变更
                target.country = self.player_country
                movers += 1
                
    def _get_neighbors(self, unit_prov: object) -> List[object]:
        """获取邻居"""
        # 简单暴力遍历判断距离
        # 优化：应该在 map_manager 里存邻接表，这里先实时算
        nbs = []
        center = unit_prov.center_cache if unit_prov.center_cache else unit_prov.compute_center(self.hex_side)
        threshold = SQRT3 * self.hex_side * 1.5
        for p in self.map_manager.provinces:
            if p == unit_prov: continue
            
            p_center = p.center_cache if p.center_cache else p.compute_center(self.hex_side)
            if dist(center, p_center) < threshold:
                nbs.append(p)
        return nbs

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
            center = province.center_cache if province.center_cache else province.compute_center(self.hex_side)
            # 获取该格子里所有单位的矩形框
            rects = self.unit_renderer.selection_rects(center, len(province.units))
            for idx, rect in enumerate(rects):
                if rect.collidepoint(mouse_pos):
                    self.add_selection(province.province_id, idx)
                    return

    def _update(self) -> None:
        """更新每一帧的数据逻辑（目前只有镜头输入检查）"""
        self.camera.handle_input()
        
        # 更新战斗结果显示计时 (如果 timer > 0)
        # 如果 timer < 0，则表示永久显示直到被覆盖
        if self.combat_result_timer > 0:
            self.combat_result_timer -= (1.0 / self.settings.fps)
            if self.combat_result_timer < 0:
                self.combat_result_timer = 0
                self.combat_result_title = None

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
            center = province.center_cache if province.center_cache else province.compute_center(self.hex_side)
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

            # --- 画战斗UI (攻防比 + 投骰子) ---
            if self.show_combat_ui:
                # 使用跟 InfoPanel 一样的字体
                font = self.combat_ui_font
                
                # 1. 投骰子按钮
                btn_text = "投骰子"
                btn_surf = font.render(btn_text, True, pg.Color("white"))
                
                # 按钮背景尺寸
                btn_w = btn_surf.get_width() + 20
                btn_h = btn_surf.get_height() + 10
                
                # 位置：在国家标签左侧 30px 处，且在 TOP 15% 区域内垂直居中
                top_area_height = int(self.screen_height * 0.15)
                
                tag_x = self.country_tag_pos[0]
                btn_x = tag_x - btn_w - 30
                btn_y = (top_area_height - btn_h) // 2 
                
                self.combat_btn_rect = pg.Rect(btn_x, btn_y, btn_w, btn_h)
                
                # 画按钮背景
                pg.draw.rect(self.window, pg.Color("blue"), self.combat_btn_rect, border_radius=5)
                # 画文字
                text_rect = btn_surf.get_rect(center=self.combat_btn_rect.center)
                self.window.blit(btn_surf, text_rect)
                
                # 2. 攻防比文字
                ratio_str = f"攻防比 {self.combat_ratio_val:.1f}"
                ratio_surf = font.render(ratio_str, True, pg.Color("black"))
                
                ratio_x = btn_x - ratio_surf.get_width() - 30
                ratio_y = btn_y + (btn_h - ratio_surf.get_height()) // 2
                
                self.window.blit(ratio_surf, (ratio_x, ratio_y))
                
            # --- 画战斗结果 (Top UI) ---
            # 如果 timer != 0，则显示 (timer<0 为永久，timer>0 为倒计时)
            if self.combat_result_title and self.combat_result_timer != 0:
                font = self.combat_ui_font
                
                # 总高度区域
                top_area_height = int(self.screen_height * 0.15)
                # 以国家标签为参考点
                tag_x = self.country_tag_pos[0]
                
                # 获取所有行
                lines = self.combat_result_title.split("\n")
                
                # 倒序渲染行，确保最上面一行在最上面，但我们从下往上排？
                # 或者从上往下排？因为这块区域在 header 
                # 之前是 centered vertical.
                # 由于是多行，我们先算总高度
                line_height = font.get_height()
                total_text_h = len(lines) * line_height + (len(lines) - 1) * 5 # 5px 行间距
                
                start_y = (top_area_height - total_text_h) // 2
                
                for line_idx, line in enumerate(lines):
                    # 对每一行执行之前的“从右向左渲染”逻辑
                    parts = line.split(" · ")
                    
                    # 当前行的 Y 坐标
                    current_y_center = start_y + line_idx * (line_height + 5) + line_height // 2
                    
                    # 从右向左渲染，起始位置在 Tag 左边 30px
                    current_right_x = tag_x - 30
                    
                    # 倒序遍历: A1, 骰6, 1:1
                    reversed_parts = list(reversed(parts))
                    
                    for i, part in enumerate(reversed_parts):
                        # 1. 绘制部件
                        color = pg.Color("blue") if "骰" in part else pg.Color("black")
                        surf = font.render(part, True, color)
                        w, h_surf = surf.get_width(), surf.get_height()
                        y = current_y_center - h_surf // 2
                        
                        self.window.blit(surf, (current_right_x - w, y))
                        current_right_x -= w
                        
                        # 2. 绘制分隔符 (只要不是最后一个部件)
                        if i < len(reversed_parts) - 1:
                            # 右边距
                            current_right_x -= 5
                            
                            sep_surf = font.render("·", True, pg.Color("black"))
                            sep_sw = sep_surf.get_width()
                            sep_y = current_y_center - sep_surf.get_height() // 2
                            self.window.blit(sep_surf, (current_right_x - sep_sw, sep_y))
                            
                            current_right_x -= sep_sw
                            # 左边距
                            current_right_x -= 5

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
            
        # 8. 画卡牌面板
        if self.card_panel:
            self.card_panel.draw(self.window)

    def _draw_smooth_polyline(self, color: pg.Color, points: Sequence[pg.math.Vector2], width: int) -> None:
        """
        绘制硬朗连接的折线（Miter Join）。
        普通的 pg.draw.lines 会有缺口，而画圆填充太圆润了。
        这个方法通过计算几何转角，生成一个完美闭合的多边形，
        让河流的转弯呈现出整齐的 120 度切角，符合六边形地图的风格。
        """
        if len(points) < 2:
            return

        # 已经全部是 Vector2 了
        vectors = points
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

        # 调整右下角回合结束按钮
        # 仅占下方 12%，对齐右下角
        # 半径 = 高度 * 12% / 2 = 6%
        r = int(height * 0.06)
        self.next_turn_radius = r
        # 中心点：紧贴右下角 (留一点点缝隙比如 5px 可能会更好看，但用户说对齐右下角)
        self.next_turn_center = (int(width - r), int(height - r))

        # 箭头图片随之缩小
        # 假设箭头是个正方形，边长稍微比直径小一点点
        # 再次缩小，使其看起来更精致 (r * 1.4 -> r * 1.0)
        arrow_size = int(r * 1.0) 
        self.arrow_image = self._load_ui_image("arrow.jpg", (arrow_size, arrow_size))
        # 箭头居中于圆心
        self.arrow_pos = (
            self.next_turn_center[0] - arrow_size // 2,
            self.next_turn_center[1] - arrow_size // 2,
        )

        self.country_tag_font = self._font("STZHONGS.TTF", int(height * 0.1))
        self.country_tag_surfaces = {
            country: self.country_tag_font.render(label, True, pg.Color("black"))
            for country, label in self.country_labels.items()
        }
        # 往右调一点，之前是 width - height * 0.15，现在改为 0.05，更靠右
        self.country_tag_pos = (int(width - height * 0.12), 0)

        # 预计算河流的像素点
        self.yangtze_polylines = tuple(self._scale_points(points) for points in (YANGTZE_POINTS_1, YANGTZE_POINTS_2))
        self.yellow_river_polyline = tuple(self._scale_points(YELLOW_RIVER_POINTS))
        self.ban_line_polyline = tuple(self._scale_points(BAN_LINE_POINTS))

    # --- 辅助工具方法 (Helpers) --------------------------------------------------------
    
    def _scale_points(self, normalized_points: Sequence[Tuple[float, float]]) -> List[pg.math.Vector2]:
        """
        将逻辑坐标转换为屏幕像素坐标。
        逻辑坐标 -> (乘以边长) -> 像素坐标
        Y轴需要额外乘以 根号3，这是六边形几何的特性。
        """
        scaled = []
        for point in normalized_points:
            x_factor, y_factor = point
            x = x_factor * self.hex_side
            y = y_factor * SQRT3 * self.hex_side
            scaled.append(pg.math.Vector2(x, y))
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
