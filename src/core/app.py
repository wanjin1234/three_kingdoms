"""
这里包含了整个游戏应用的核心逻辑：GameApp。
它是总导演，管理着游戏状态、循环、渲染和逻辑更新。
"""
from __future__ import annotations

import logging
import ctypes
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
from src.map.geometry import hex_vertices
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
            river_polylines=(
                YANGTZE_POINTS_1,
                YANGTZE_POINTS_2,
                YELLOW_RIVER_POINTS,
            ),
            ban_polylines=( BAN_LINE_POINTS, ),
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

        # 改回使用默认的 Arial 字体，因为中文字体 (msyh) 的垂直基线会导致数字无法垂直居中
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
        font_path = str(self.settings.fonts_dir / "msyh.ttc")
        self.info_panel = InfoPanel(panel_rect, info_font, font_path=font_path, base_font_size=font_size)
        
        # 保存字体给战斗UI使用
        self.combat_ui_font = info_font
        
        # 初始化悬停提示字体 (比标准字体小一圈)
        tooltip_size = max(12, int(self.screen_height * 0.018))
        self.tooltip_font = self._font("msyh.ttc", tooltip_size)
        self.tooltip_bold_font = self._font("msyhbd.ttc", tooltip_size)
        
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
        self.combat_target: object | None = None # 当前选中的攻击目标 (Province)
        self.combat_ratio_val: float = 0.0
        self.combat_callback: Callable[[], None] | None = None
        self.combat_btn_rect: pg.Rect | None = None  # 在 render 时计算
        
        # 解除混乱按钮区域
        self.recover_btn_rect: pg.Rect | None = None

        # 战斗结果显示 (Top UI area)
        self.combat_result_title: str | None = None # e.g. "1:1 · 骰6 · A1"
        self.combat_result_timer: float = 0.0       # 显示倒计时

        # 初始填充行动力
        self._replenish_action_points()

    def _replenish_action_points(self) -> None:
        """
        重置所有单位的行动力 (MP)。
        应该在回合开始时调用。
        """
        for prov in self.map_manager.provinces:
            for unit in prov.units:
                defn = self.unit_repository.get_definition(unit.unit_type)
                max_mp = defn.move
                
                # 特殊逻辑：无当飞军在山地行动力为3
                if unit.unit_type == "WUDANG_archer":
                    # 检查当前所在地形
                    t_terrain = prov.terrain.lower() if prov.terrain else ""
                    if t_terrain in ("hill", "mountain", "hills", "mountains"):
                        max_mp = 3
                
                # 特殊逻辑：虎豹骑固定为4 (defs里应该是4，如果不是，这里强制设定也可以，但defs优先)
                # defs里已经是4了.
                
                unit.mp = max_mp

    def _manual_end_turn(self) -> None:
        """手动结束回合：恢复行动力"""
        self._replenish_action_points()
        if self.info_panel:
            self.info_panel.show_message("回合结束，行动力已恢复")
            
    def _restart_game(self) -> None:
        """重置游戏状态并返回选人界面"""
        # 1. 重新加载地图以重置单位
        self.map_manager = MapManager(
            definition_file=self.settings.map_definition_file,
            terrain_graphics_dir=self.settings.map_graphics_dir,
            color_resolver=self.kingdom_repository.get_color,
            river_polylines=(
                YANGTZE_POINTS_1,
                YANGTZE_POINTS_2,
                YELLOW_RIVER_POINTS,
            ),
            ban_polylines=( BAN_LINE_POINTS, ),
        )
        self.map_manager.set_hex_side(self.hex_side)
        
        # 2. 清理选择和UI
        self.clear_selection()
        self.show_combat_ui = False
        self.combat_result_title = None
        if self.info_panel: 
             self.info_panel.show_properties("")
             
        # 3. 切换状态
        self.player_country = None
        self.state = GameState.CHOOSING
        logger.info("Game restarted.")

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
        
        self._cancel_combat_preview() # 清空战斗预览

        # 只要点击了地图上的其他东西（或者清空选择），就应该清空上一次的战果(Top UI)
        if clear_ui:
            self.combat_result_title = None
            self.combat_result_timer = 0
            if self.info_panel: 
                 self.info_panel.show_properties("") # 清空面板

    def _cancel_combat_preview(self) -> None:
        """取消战斗预览状态"""
        self.show_combat_ui = False
        self.combat_target = None
        self.combat_callback = None
        # 如果还有选中单位，恢复显示选中单位的信息
        self._update_selection_info()

    def add_selection(self, province_id: int, slot_index: int) -> None:
        """添加一个选中单位"""
        # 只要发生了新的选择操作，肯定要清空上一轮战斗的残留结果
        self.combat_result_title = None
        self.combat_result_timer = 0
        
        # 防止重复添加
        new_entry = (province_id, slot_index)
        if new_entry in self.selected_units:
            return
            
        self.selected_units.append(new_entry)
        self._update_selection_info() # 更新面板信息

    def remove_selection(self, province_id: int, slot_index: int) -> None:
        """移除一个选中单位"""
        # 移除也是变动，同样清空旧的战斗结果
        self.combat_result_title = None
        self.combat_result_timer = 0
        
        entry = (province_id, slot_index)
        if entry in self.selected_units:
            self.selected_units.remove(entry)
            self._update_selection_info()

    def _get_unit_abbr(self, unit_type: str) -> str:
        """获取单位类型的单字简称"""
        if unit_type == "HUBAO_cavalry": return "虎豹"
        if unit_type == "WUDANG_archer": return "无当"
        if unit_type == "JIEFAN_infantry": return "解烦"
        
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
        # 为了实现彩色，我们构建富文本字符串
        # 格式： 文本|#HexColor|彩色文本|#000000|文本
        # 注意默认文字颜色通常是黑色 #000000
        
        country = u_def.country
        color_hex = "#000000"
        if country:
            # 获取对应国家的颜色
            c = self.kingdom_repository.get_color(country) # pg.Color
            # 转为 hex
            color_hex = f"#{c.r:02x}{c.g:02x}{c.b:02x}"
        
        # 构建富文本行: "[" + "|#COLOR|" + ABBR + "|#000000|" + status + "]"
        abbr_part = f"|{color_hex}|{u_abbr}|#000000|"
        label = f"[{prefix}{abbr_part}{status_str}]"
        
        attrs = [
            f"血{u_state.hp}",
            f"攻{u_def.attack}",
            f"防{u_def.defense}",
            f"动{u_state.mp}/{u_def.move}",
            f"射{u_def.range}",
            f"疲{u_state.attack_count}"
        ]
        return f"{label} {'·'.join(attrs)}"

    def _update_selection_info(self) -> None:
        """更新信息面板显示的选中单位属性"""
        if not self.selected_units:
            # 如果清空了，要重置面板
            if self.info_panel:
                self.info_panel.show_properties("")
            return

        lines = []
        for i, (pid, idx) in enumerate(self.selected_units):
            prov = self.map_manager.get_by_id(pid)
            if not prov: continue
            u_state = prov.units[idx]
            # 还原为无序号显示
            info_str = self._format_unit_info(u_state)
            lines.append(info_str)
            
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
                # 0.0 检查功能按钮
                for btn in getattr(self, "control_btns", []):
                    if btn["rect"].collidepoint(event.pos):
                        action = btn["action"]
                        if action == "EXIT":
                            self.stop()
                        elif action == "RESTART":
                            self._restart_game()
                        elif action == "END_TURN":
                            self._manual_end_turn()
                        return

                # 0. 优先处理顶部的战斗按钮
                if self.show_combat_ui and self.combat_btn_rect and self.combat_btn_rect.collidepoint(event.pos):
                    if self.combat_callback:
                        self.combat_callback()
                    # 点击按钮后，UI会在 clear_selection 关闭，或者在 callback 里处理
                    # 这里 return 防止点穿到下面地图
                    return

                # 0.1 检查“解除混乱”按钮
                if self.recover_btn_rect and self.recover_btn_rect.collidepoint(event.pos):
                    # 执行解除混乱逻辑
                    # 再次确认条件 (虽然 UI 只在满足条件时显示，但 safe check 好习惯)
                    confused_list = []
                    for pid, slot in self.selected_units:
                        prov = self.map_manager.get_by_id(pid)
                        if prov and slot < len(prov.units):
                            u = prov.units[slot]
                            if u.is_confused:
                                confused_list.append(u)
                    
                    if len(confused_list) == 1:
                        confused_list[0].is_confused = False
                        self.info_panel.show_message("混乱状态已解除")
                        self._update_selection_info()
                    return

                # 优先处理 UI 面板点击
                if self.info_panel and self.info_panel.handle_click(event.pos):
                    return
                # 左键点击：尝试选择单位 (Toggle逻辑)
                # 之前是Shift+Click，现在改为直接左键点击
                # 但是要注意，如果点击的是空白处或者非单位，是否要取消选择？
                # 按照通常RTS逻辑，点击空地会取消选择。
                # 但这里我们希望是 Toggle 选择，如果点了空地可能不操作，或者移动视角？
                # 按照用户描述：“单击选中后，再次单击时，取消选中”，这通常指点在兵上。
                # 那如果点空地呢？用户没说。为了体验好，暂时不处理点空地，只处理点兵。
                
                # Check if clicked on a unit
                target_unit = self._get_unit_slot_at(event.pos)
                if target_unit:
                    prov_id, slot_idx = target_unit
                    
                    # --- 1. 检查是否选择了敌方单位 ---
                    prov = self.map_manager.get_by_id(prov_id)
                    if prov and prov.country and prov.country != self.player_country:
                        # 如果点击了敌方单位，不作为"选择"处理
                        # 但可以给个提示
                        self.info_panel.show_message("不能操作敌方单位")
                        return

                    # 检查是否已选中
                    if (prov_id, slot_idx) in self.selected_units:
                        self.remove_selection(prov_id, slot_idx)
                    else:
                        self.add_selection(prov_id, slot_idx)
                    return
                else:
                    # 如果点了空地，是否取消所有选择？
                    # 考虑到移动端/简化操作习惯，点空地取消通常是合理的。
                    # 但为了避免误触，如果用户只是想取消一个，点空地全没了会很烦。
                    # 用户没要求点空地取消，只要求Toggle。保持不动。
                    pass
                    
            elif event.button == 3:
                # 右键点击：移动或攻击
                self._handle_game_right_click(event.pos)

    def _get_unit_slot_at(self, pos: Tuple[int, int]) -> Tuple[int, int] | None:
        """根据鼠标点击位置获取被点击的单位"""
        # 遍历所有格子，检查点击点是否在某个单位的图标 rect 内
        for p in self.map_manager.provinces:
            if not p.units:
                continue
            
            # 简单的性能优化：如果离格子中心太远，就不检查这个格子里的单位
            # 图标一般在格子中心附近
            center = p.center_cache if p.center_cache else p.compute_center(self.hex_side)
            if dist(pos, center) > self.hex_side: 
                continue

            rects = self.unit_renderer.selection_rects(center, len(p.units))
            for i, r in enumerate(rects):
                if r.collidepoint(pos):
                    return (p.province_id, i)
        return None

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
            # 切换/取消 战斗目标逻辑
            # 如果再次点击已选目标 -> 取消选中
            if self.combat_target and self.combat_target == target_province:
                self._cancel_combat_preview()
            else:
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
        
        # 使用路径寻路计算 Cost
        # 如果 source == target，不需要移动
        if source.province_id == target.province_id:
            self.clear_selection()
            return

        # 调用 map_manager 的寻路算法
        # 注意：这里计算的是从 Source 到 Target 的最短路径 Cost
        # 假设所有选中单位走同一条路
        path_cost = self.map_manager.find_path_cost(source.province_id, target.province_id)
        
        # 寻路失败（比如不可达，虽然目前全图连通）
        if path_cost > 100: 
            self.info_panel.show_message("无法到达")
            return

        moving_units = []
        unit_costs = [] # 记录扣除的行动力
        
        for idx in selected_indices:
            unit_state = source.units[idx]
            
            # 1. 检查行动力是否为0
            if unit_state.mp <= 0:
                self.info_panel.show_message("行动力为0")
                return

            # 2. 检查行动力是否足够
            if unit_state.mp < path_cost:
                self.info_panel.show_message(f"行动力不足(需{path_cost})")
                return

            moving_units.append(unit_state)
            unit_costs.append(path_cost)
            
        # 3. 堆叠检查
        # 目标格子已有兵 + 即将移动过去的兵 > 3
        if len(target.units) + len(moving_units) > 3:
            self.info_panel.show_message("堆叠部队过多")
            return
            
        # 4. 执行移动
        new_source_list = []
        # 将未移动的单位保留在原地
        moved_indices = set(selected_indices)
        for i, u in enumerate(source.units):
            if i not in moved_indices:
                new_source_list.append(u)
        source.units = new_source_list
        
        # 扣除行动力并移动
        for u, c in zip(moving_units, unit_costs):
            u.mp -= c
            target.units.append(u)
        
        # 如果移动成功且有单位进入，占领该地
        
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

    def _get_counter_modifier(self, attacker_type: str, defender_type: str) -> float:
        """
        判断兵种克制关系，返回攻击力加成系数。
        克制规则：
        - 步兵 (infantry) 克制 弓兵 (archer)
        - 弓兵 (archer) 克制 骑兵 (cavalry)
        - 骑兵 (cavalry) 克制 步兵 (infantry)
        
        如果克制，攻击力 +1 (或者 +25%? 为了简单且数值显著，暂定+1.5)
        用户没说具体数值，但考虑到 base attack 是 3~4，+1 是个合理的 buff。
        我们这里保守点，给 +1 攻击力。
        """
        atk_type = attacker_type.lower()
        def_type = defender_type.lower()
        
        # 提取基础兵种类型 (可能有前缀，如 HUBAO_cavalry)
        def _base_type(t: str) -> str:
            if "infantry" in t: return "infantry"
            if "cavalry" in t: return "cavalry"
            if "archer" in t: return "archer"
            return ""

        a_base = _base_type(atk_type)
        d_base = _base_type(def_type)
        
        if not a_base or not d_base:
            return 0.0

        if a_base == "infantry" and d_base == "archer":
            return 1.0
        if a_base == "archer" and d_base == "cavalry":
            return 1.0
        if a_base == "cavalry" and d_base == "infantry":
            return 1.0
            
        return 0.0

    def _handle_combat(self, target: object) -> None: # target: Province
        """处理战斗逻辑"""
        unit_stride = SQRT3 * self.hex_side
        total_attack = 0.0
        
        participating_attackers = [] # List[(province, unit_state)]
        
        # 为了计算方便，预先获取防御方的类型列表
        defender_types = [u.unit_type for u in target.units]

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
                self.clear_selection(clear_ui=False)
                self.info_panel.show_message(f"距离不足:{definition.range}", duration=2.0)
                return
            
            # 行动力检查
            if unit_state.mp < 1:
                self.clear_selection(clear_ui=False)
                self.info_panel.show_message("行动力不足")
                return

            atk, _ = self._calculate_unit_powers(unit_state)
            
            # --- 兵种克制计算 ---
            # 规则：步兵克弓兵，弓兵克骑兵，骑兵克步兵
            # 加成：克制+0.5，被克制-0.5
            bonus = 0.0
            
            def get_relationship(attacker_type: str, defender_type: str) -> int:
                # return 1 for advantage, -1 for disadvantage, 0 for neutral
                a_type = attacker_type.lower()
                d_type = defender_type.lower()
                
                a_base = ""
                if "infantry" in a_type: a_base = "infantry"
                elif "cavalry" in a_type: a_base = "cavalry"
                elif "archer" in a_type: a_base = "archer"
                
                d_base = ""
                if "infantry" in d_type: d_base = "infantry"
                elif "cavalry" in d_type: d_base = "cavalry"
                elif "archer" in d_type: d_base = "archer"
                
                if not a_base or not d_base: return 0
                
                # 步(infantry) > 弓(archer) > 骑(cavalry) > 步(infantry)
                if a_base == "infantry":
                    if d_base == "archer": return 1
                    if d_base == "cavalry": return -1
                elif a_base == "archer":
                    if d_base == "cavalry": return 1
                    if d_base == "infantry": return -1
                elif a_base == "cavalry":
                    if d_base == "infantry": return 1
                    if d_base == "archer": return -1
                
                return 0

            has_adv = False
            has_dis = False
            
            for d_type in defender_types:
                rel = get_relationship(unit_state.unit_type, d_type)
                if rel == 1: has_adv = True
                if rel == -1: has_dis = True
            
            if has_adv: bonus += 0.5
            if has_dis: bonus -= 0.5
            
            total_attack += (atk + bonus)
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
        self.combat_target = target # 设置当前目标 (Province对象)
        
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
            
        # 疲劳判定 & 消耗行动力
        for _, u in attackers:
            u.mp -= 1 # 消耗1点行动力 (必须先于疲劳判定?)
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
            
    def _apply_damage(self, units: List[UnitState], amount: int) -> None:
        """分配伤害"""
        # 机制：
        # 1. 数字表示受到伤害的单位数 (即造成amount次单体伤害)
        # 2. 受到一次伤害就少一点血量
        # 3. 优先级：优先选取未受过伤的 -> 如果都未受过伤，按照防御值由低到高 -> 如果都一样，随便选
        
        for _ in range(amount):
            # 每一轮伤害都重新寻找最佳目标 (因为上一轮伤害可能改变了状态，比如从未伤变成了伤)
            # 过滤掉死人
            living_units = [u for u in units if u.hp > 0]
            if not living_units: break
            
            def sort_key(u):
                # (是否受伤(0/1), 防御力)
                # False(0) 排在 True(1) 前面 -> 优先打未受伤
                is_inj = 1 if u.is_injured else 0
                defense = self.unit_repository.get_definition(u.unit_type).defense
                return (is_inj, defense)
            
            candidates = sorted(living_units, key=sort_key)
            target = candidates[0]
            target.hp -= 1
            
    def _apply_confusion(self, unit_tuples: List, amount: int = 1) -> None:
        """应用混乱"""
        # 机制与伤害相同 (选取规则)
        units = [u for _, u in unit_tuples]
        
        for _ in range(amount):
            living_units = [u for u in units if u.hp > 0]
            if not living_units: break
            
            def sort_key(u):
                # 优先选 未受伤 -> 低防御
                is_inj = 1 if u.is_injured else 0
                defense = self.unit_repository.get_definition(u.unit_type).defense
                return (is_inj, defense)
            
            candidates = sorted(living_units, key=sort_key)
            target = candidates[0]
            
            if target.is_confused:
                # 如果连续两次进入混乱状态，则减少一点血量，但仍处于混乱状态。
                target.hp -= 1
            else:
                target.is_confused = True

    def _handle_retreat(self, province: object) -> None:
        """处理撤退"""
        # 撤退有1点行动力，可以自由选择撤退到1点行动力能到的地方。
        # 这里自动选择一个合法格子撤退 (简化为自动，非玩家手动操作撤退，因为战斗是瞬间结算的)
        
        # 1. 获取所有邻居
        # 2. 过滤：行动力为1能到的地方 (在网格寻路下，如果是山地且Cost=2，则1MP到不了)
        # 3. 同时也必须是友方或空格子
        
        if not province.units: return
        
        start_id = province.province_id
        valid_destinations = []
        
        # 获取逻辑邻居 (通过Graph)
        neighbor_ids = self.map_manager._adjacency.get(start_id, [])
        
        for nid in neighbor_ids:
            dest_prov = self.map_manager.get_by_id(nid)
            if not dest_prov: continue
            
            # 检查归属: 友方或无人地
            if dest_prov.country and dest_prov.country != province.country:
                continue
            
            # 堆叠限制
            if len(dest_prov.units) + len(province.units) > 3:
                continue
            
            # 检查是否能到达 (Cost check)
            # 基础 Cost=1。如果是山地，Cost=2。
            # 只有当 Cost <= 1 时才能撤退。
            # 计算移动消耗:
            step_cost = 1
            t_terrain = dest_prov.terrain.lower() if dest_prov.terrain else ""
            if t_terrain in ("hill", "mountain", "hills", "mountains"):
                step_cost += 1
                
            if step_cost <= 1:
                valid_destinations.append(dest_prov)
        
        if valid_destinations:
            # 随机选一个撤
            dest = valid_destinations[0] # 或 random.choice
            dest.units.extend(province.units)
            province.units.clear()
            logger.info(f"Defenders retreated to {dest.name}")
        else:
            # 如果没有地方可以撤退，则受到1点伤害
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
            
        # 2.5 画当前战斗目标的金色描边 Hex Outline
        if self.combat_target:
             # 安全获取 Province 对象
            target_prov = self.combat_target
            # 计算中心点
            c = target_prov.center_cache if target_prov.center_cache else target_prov.compute_center(self.hex_side)
            # 计算六边形顶点
            vertices = hex_vertices(c, self.hex_side)
            
            # 使用金色画笔画线，宽度为4
            pg.draw.lines(self.window, pg.Color("gold"), True, vertices, 4)

        # 3. 画河流和阻挡线
        for polyline in self.yangtze_polylines:
            self._draw_smooth_polyline(pg.Color(173, 216, 230), polyline, 20)
        self._draw_smooth_polyline(pg.Color(173, 216, 230), self.yellow_river_polyline, 20)
        self._draw_smooth_polyline(pg.Color("black"), self.ban_line_polyline, 20)

        # 3.5 画功能按钮
        for btn in getattr(self, "control_btns", []):
            # 简单的悬停效果
            color = btn["bg_color"]
            if btn["rect"].collidepoint(pg.mouse.get_pos()):
                color = pg.Color("#666666") # Lighter gray
            
            pg.draw.rect(self.window, color, btn["rect"], border_radius=5)
            pg.draw.rect(self.window, btn["border_color"], btn["rect"], 2, border_radius=5)
            self.window.blit(btn["surface"], btn["text_pos"])

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
                
                # 悬停变色逻辑
                btn_color = pg.Color("blue")
                if self.combat_btn_rect.collidepoint(pg.mouse.get_pos()):
                    btn_color = pg.Color("#4169E1") # RoyalBlue (Lighter than Blue)

                # 画按钮背景
                pg.draw.rect(self.window, btn_color, self.combat_btn_rect, border_radius=5)
                # 画文字
                text_rect = btn_surf.get_rect(center=self.combat_btn_rect.center)
                self.window.blit(btn_surf, text_rect)
                
                # 2. 攻防比文字
                ratio_str = f"攻防比 {self.combat_ratio_val:.1f}"
                ratio_surf = font.render(ratio_str, True, pg.Color("black"))
                
                ratio_x = btn_x - ratio_surf.get_width() - 30
                ratio_y = btn_y + (btn_h - ratio_surf.get_height()) // 2
                
                self.window.blit(ratio_surf, (ratio_x, ratio_y))
            
            # --- 检查是否需要显示“解除混乱”按钮 ---
            # 条件：1. 没有进入战斗准备 (show_combat_ui is False)
            #      2. 选中的单位中，【恰好】只有一个单位处于混乱状态
            #      3. (隐含) combat_target 为 None (show_combat_ui False 已经涵盖了大部分情况，双重保险)
            else:
                self.recover_btn_rect = None # Reset
                confused_list = []
                for pid, slot in self.selected_units:
                    prov = self.map_manager.get_by_id(pid)
                    if prov and slot < len(prov.units):
                        u = prov.units[slot]
                        if u.is_confused:
                             confused_list.append(u)
                
                if len(confused_list) == 1:
                    # 绘制解除混乱按钮
                    font = self.combat_ui_font
                    btn_text = "解除混乱"
                    btn_surf = font.render(btn_text, True, pg.Color("white"))
                    
                    btn_w = btn_surf.get_width() + 20
                    btn_h = btn_surf.get_height() + 10
                    
                    top_area_height = int(self.screen_height * 0.15)
                    tag_x = self.country_tag_pos[0]
                    # 和 combat button 相同的位置逻辑：Tag 左侧 30px
                    btn_x = tag_x - btn_w - 30
                    btn_y = (top_area_height - btn_h) // 2 
                    
                    self.recover_btn_rect = pg.Rect(btn_x, btn_y, btn_w, btn_h)
                    
                    # 悬停变色逻辑
                    btn_color = pg.Color("purple")
                    if self.recover_btn_rect.collidepoint(pg.mouse.get_pos()):
                        btn_color = pg.Color("#BA55D3") # MediumOrchid (Lighter Purple)

                    # 按照要求，按钮颜色为紫色
                    pg.draw.rect(self.window, btn_color, self.recover_btn_rect, border_radius=5)
                    
                    text_rect = btn_surf.get_rect(center=self.recover_btn_rect.center)
                    self.window.blit(btn_surf, text_rect)
                
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

        # 9. 画鼠标悬停提示 (Tooltip)
        self._draw_hover_tooltip()

    def _draw_hover_tooltip(self) -> None:
        """Draw tooltip for hovered element"""
        # 只在游戏进行中显示
        if self.state != GameState.PLAYING:
            return

        mouse_pos = pg.mouse.get_pos()
        # 确保鼠标在窗口内
        if not self.window.get_rect().collidepoint(mouse_pos):
            return

        # tooltip_parts: List of (text, color, is_bold, has_shadow)
        tooltip_parts: List[Tuple[str, pg.Color, bool, bool]] = []
        
        # 1. 优先检查单位 (Unit)
        hovered_unit = self._get_unit_slot_at(mouse_pos)
        if hovered_unit:
            pid, slot = hovered_unit
            prov = self.map_manager.get_by_id(pid)
            if prov and slot < len(prov.units):
                u_type = prov.units[slot].unit_type
                t_name = self._get_display_name(u_type)
                if t_name:
                    tooltip_parts.append((t_name, pg.Color("black"), False, False))

        # 2. 如果没悬停单位，先检查是否有河流或禁行区域
        if not tooltip_parts:
            if self._is_hovering_ban_line(mouse_pos):
                tooltip_parts.append(("禁行", pg.Color("black"), False, False))
            elif self._is_hovering_river(mouse_pos):
                tooltip_parts.append(("河流", pg.Color("black"), False, False))

        # 3. 如果没悬停单位也没河流，检查格子/地形 (Terrain/City)
        if not tooltip_parts:
            hovered_prov = self._get_province_at(mouse_pos)
            if hovered_prov:
                # 检查是否有特殊名称 (非 TileXX, BorderXX)
                p_name = hovered_prov.name
                
                # 城市名称映射表
                city_name_map = {
                    "Liangzhou": "凉州",
                    "Chengdu": "成都",
                    "Hanzhong": "汉中",
                    "Changan": "长安",
                    "Jingzhou": "荆州",
                    "Xiangyang": "襄阳",
                    "Luoyang": "洛阳",
                    "Wuchang": "武昌",
                    "Changsha": "长沙",
                    "Youzhou": "幽州",
                    "Hefei": "合肥",
                    "Jianye": "建业"
                }

                if p_name and not p_name.startswith("Tile") and not p_name.startswith("Border"):
                    # 如果在映射表中，显示中文；否则显示原名
                    base_name = city_name_map.get(p_name, p_name)
                else:
                    # 显示地形中文名
                    t_key = hovered_prov.terrain.lower() if hovered_prov.terrain else "plain"
                    base_name = self._get_display_name(t_key)
                
                if base_name:
                     # 城市名加粗变成深金色，并带阴影；其他地形默认黑色无阴影
                     is_city = (hovered_prov.terrain or "").lower() == "city"
                     if is_city:
                         # 使用更深的金色 (DarkGoldenrod #B8860B 或者是自定义)
                         # 用户觉得 gold (#FFD700) 太浅。尝试 #D4AF37 (Metallic Gold) 或 #C5A000
                         tooltip_parts.append((base_name, pg.Color("#D4AF37"), True, True)) 
                     else:
                         tooltip_parts.append((base_name, pg.Color("black"), False, False))

                # 附加国家信息
                if hovered_prov.country:
                    country_cn = self.country_labels.get(hovered_prov.country, hovered_prov.country)
                    # 尝试从 kingdom_repository 获取最准确的颜色
                    c_color = self.kingdom_repository.get_color(hovered_prov.country)
                    if not c_color:
                        # 兜底
                        c_color = self.country_button_colors.get(hovered_prov.country, pg.Color("black"))
                    
                    # 国家名加粗，用对应颜色
                    tooltip_parts.append((f"({country_cn})", c_color, True, True)) # 国家名也给个阴影会让颜色更突出

        if tooltip_parts:
             # 计算总宽度和高度
             font_regular = self.tooltip_font
             font_bold = self.tooltip_bold_font 
             
             # 渲染每个部分
             rendered_surfaces = []
             total_w = 0
             max_h = 0
             
             shadow_offset = (1, 1)
             shadow_color = pg.Color("black") # 或者深灰

             for text, color, is_bold, has_shadow in tooltip_parts:
                 font = font_bold if is_bold else font_regular
                 
                 # 渲染文字
                 fg_surf = font.render(text, True, color)
                 
                 if has_shadow:
                     # 渲染阴影 (渲染黑色并轻微模糊/偏移)
                     shadow_surf = font.render(text, True, shadow_color)
                     # 创建一个够大的容器容纳影子和正文
                     w = fg_surf.get_width() + abs(shadow_offset[0])
                     h = fg_surf.get_height() + abs(shadow_offset[1])
                     container = pg.Surface((w, h), pg.SRCALPHA)
                     
                     # 先画影子
                     container.blit(shadow_surf, shadow_offset)
                     # 再画正文
                     container.blit(fg_surf, (0, 0))
                     s = container
                 else:
                     s = fg_surf

                 rendered_surfaces.append(s)
                 total_w += s.get_width()
                 max_h = max(max_h, s.get_height())
             
             # 创建合成Surface
             
             # 创建合成Surface
             final_surf = pg.Surface((total_w, max_h), pg.SRCALPHA)
             current_x = 0
             for s in rendered_surfaces:
                 # 垂直居中
                 y_offset = (max_h - s.get_height()) // 2
                 final_surf.blit(s, (current_x, y_offset))
                 current_x += s.get_width()

             # 计算位置：鼠标右下方 15px
             x, y = mouse_pos
             x += 15
             y += 15
             
             rect = final_surf.get_rect(topleft=(x, y))
             
             # 边界检查
             if rect.right > self.screen_width:
                 rect.right = mouse_pos[0] - 5
             if rect.bottom > self.screen_height:
                 rect.bottom = mouse_pos[1] - 5
                 
             # 绘制背景框
             bg_rect = rect.inflate(10, 6) # 稍微紧凑一点 padding
             pg.draw.rect(self.window, pg.Color("white"), bg_rect, border_radius=3) # 白底
             pg.draw.rect(self.window, pg.Color("black"), bg_rect, 1, border_radius=3) # 黑框
             
             self.window.blit(final_surf, rect)

    def _get_display_name(self, key: str) -> str | None:
        """获取显示名称"""
        mapping = {
            "city": "城市",
            "hill": "山地",
            "mountain": "山地",
            "mountains": "山地",
            "hills": "山地",
            "plain": "平原",
            
            "infantry": "步兵",
            "cavalry": "骑兵",
            "archer": "弓兵",
            
            "HUBAO_cavalry": "虎豹骑",
            "WUDANG_archer": "无当飞军",
            "JIEFAN_infantry": "解烦兵"
        }
        
        if key in mapping: 
            return mapping[key]
            
        # 尝试后缀匹配 (针对通用兵种变体)
        key_lower = key.lower()
        if "infantry" in key_lower: return "步兵"
        if "cavalry" in key_lower: return "骑兵"
        if "archer" in key_lower: return "弓兵"
        
        return None # 其他普通地形如 plain 不显示，以免屏幕太乱

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

        # --- 右下角功能按钮 ---
        # 视觉顺序从左到右: [退出] [重开] [手动结束] [O]
        # 我们从圆圈左侧开始往左排布
        btn_font = self._font("msyh.ttc", int(height * 0.025))
        
        # 列表顺序：最靠近圆圈的是 "手动结束"，然后是 "重开"，最左是 "退出"
        labels = ["手动结束回合", "重开一局", "退出游戏"]
        actions = ["END_TURN", "RESTART", "EXIT"]
        
        self.control_btns = []
        
        # 起始X坐标：圆圈左边缘 (width - 2r) 再往左一点
        current_x_right = int(width - 2 * r - 20)
        
        for label, action in zip(labels, actions):
            surf = btn_font.render(label, True, pg.Color("white"))
            w = surf.get_width() + 20
            h = surf.get_height() + 10
            
            x = current_x_right - w
            # 垂直居中于圆心 y = height - r
            y = int(height - r - h / 2)
            
            rect = pg.Rect(x, y, w, h)
            
            self.control_btns.append({
                "rect": rect,
                "surface": surf,
                "text_pos": (x + 10, y + 5),
                "action": action,
                "bg_color": pg.Color("#444444"),  # 深灰背景
                "border_color": pg.Color("white")
            })
            
            # 往左移，留出间隙
            current_x_right -= (w + 10)
        # 往右调一点，之前是 width - height * 0.15，现在改为 0.05，更靠右
        self.country_tag_pos = (int(width - height * 0.12), 0)

        # 预计算河流的像素点
        self.yangtze_polylines = tuple(self._scale_points(points) for points in (YANGTZE_POINTS_1, YANGTZE_POINTS_2))
        self.yellow_river_polyline = tuple(self._scale_points(YELLOW_RIVER_POINTS))
        self.ban_line_polyline = tuple(self._scale_points(BAN_LINE_POINTS))

    def _is_hovering_ban_line(self, mouse_pos: Tuple[int, int]) -> bool:
        """检查鼠标是否悬停在黑线上"""
        return self._is_hovering_polyline(mouse_pos, [self.ban_line_polyline])

    def _is_hovering_river(self, mouse_pos: Tuple[int, int]) -> bool:
        """检查鼠标是否悬停在河流上"""
        polylines = []
        polylines.extend(self.yangtze_polylines)
        polylines.append(self.yellow_river_polyline)
        return self._is_hovering_polyline(mouse_pos, polylines)

    def _is_hovering_polyline(self, mouse_pos: Tuple[int, int], polylines_list) -> bool:
        """通用检查鼠标是否悬停在某组Polyline上"""
        threshold = 10.0 # 像素距离阈值
        m_vec = pg.math.Vector2(mouse_pos)
        
        for polyne in polylines_list:
            # polyne is a sequence of points
            if len(polyne) < 2: continue
            
            for i in range(len(polyne) - 1):
                p1 = polyne[i]
                p2 = polyne[i+1]
                
                # 计算点到线段距离
                # Vector P1->P2
                line_vec = p2 - p1
                # Vector P1->Mouse
                p1_m_vec = m_vec - p1
                
                line_len_sq = line_vec.length_squared()
                if line_len_sq == 0: continue
                
                # Project p1_m onto line_vec
                # t = dot(p1_m, line) / len_sq
                t = p1_m_vec.dot(line_vec) / line_len_sq
                
                # Clamp t to segment
                t = max(0.0, min(1.0, t))
                
                closest_point = p1 + line_vec * t
                dist_sq = m_vec.distance_squared_to(closest_point)
                
                if dist_sq < threshold * threshold:
                    return True
        return False
        
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
        """
        加载图片并缩放到指定大小。
        如果是 SVG，尽量按需加载；如果失败，回退到普通加载。
        """
        filepath = self.settings.ui_graphics_dir / filename
        
        # 尝试直接加载 (Pygame 2.0+ 的 SDL_image 对 SVG 支持较好，直接 load 往往比魔改稳)
        try:
            surface = pg.image.load(filepath).convert_alpha()
            # 如果是 SVG，加载出来的尺寸可能是原始尺寸，我们需要缩放
            if surface.get_width() != size[0] or surface.get_height() != size[1]:
                return pg.transform.smoothscale(surface, size)
            return surface
        except Exception as e:
            logger.error(f"Error loading image {filename}: {e}")
            # 返回一个洋红色的方块作为错误占位符
            err_surf = pg.Surface(size)
            err_surf.fill(pg.Color("magenta"))
            return err_surf

    def _font(self, filename: str, size: int) -> pg.font.Font:
        """加载字体"""
        return pg.font.Font(self.settings.fonts_dir / filename, size)

    def _render_text(self, filename: str, size: int, text: str, color: pg.Color | str = "black") -> pg.Surface:
        """使用指定字体和大小渲染一段文字，返回图片表面"""
        font = self._font(filename, size)
        return font.render(text, True, pg.Color(color))
