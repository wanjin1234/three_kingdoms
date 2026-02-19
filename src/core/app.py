"""
这里包含了整个游戏应用的核心逻辑：GameApp。
它是总导演，管理着游戏状态、循环、渲染和逻辑更新。
"""

from __future__ import annotations

import ctypes
import logging
import random
from enum import Enum, auto
from math import dist, sqrt
from typing import Callable, Dict, List, Sequence, Tuple

import pygame as pg
from settings import Settings

from src.core.camera import Camera
from src.core.combat import (
    COMBAT_TABLE,
    CombatPreview,
    get_ratio_column,
    resolve_combat,
)
from src.core.events import EventManager
from src.game_objects.card import CardManager, CardRepository
from src.game_objects.card_effects import CardEffectManager
from src.game_objects.kingdom import KingdomRepository
from src.game_objects.unit import UnitRenderer, UnitRepository, UnitState
from src.map.geometry import hex_vertices
from src.map.map_manager import MapManager
from src.ui.info_panel import CardPanel, InfoPanel
from src.ui.panels import SelectionOverlay

logger = logging.getLogger(__name__)

SQRT3 = sqrt(3)

# --- 游戏规则常量 ---
MAX_UNIT_STACK = 3  # 每个格子最多堆叠单位数
COUNTER_BONUS = 0.5  # 兵种克制加成/惩罚
INJURY_PENALTY = 0.5  # 受伤减少系数
CONFUSION_PENALTY = 1  # 混乱惩罚值

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
        self._running = False  # 游戏循环开关

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
        self.clock = pg.time.Clock()  # 用于控制游戏帧率

        # 获取当前屏幕分辨率并创建窗口
        display_info = pg.display.Info()
        self.screen_width = display_info.current_w
        self.screen_height = display_info.current_h
        flags = pg.NOFRAME if settings.borderless else 0
        self.window = pg.display.set_mode(
            (self.screen_width, self.screen_height), flags
        )
        pg.display.set_caption(settings.window_title)

        # 设置窗口图标 (可选，让 Alt+Tab 时显示漂亮的图标)
        # icon = pg.image.load(settings.graphics_dir / "icon.jpg")
        # pg.display.set_icon(icon)

        # 计算六边形格子的边长，使其刚好能铺满屏幕高度的一部分
        self.hex_side = self.screen_height * 2 / (19 * SQRT3)

        # 初始状态设为 LOADING
        self.state = GameState.LOADING
        self.player_country: str | None = None  # 当前行动的国家
        self.human_country: str | None = None   # 玩家选择控制的国家

        # 定义三个国家的标签和颜色
        self.country_labels: Dict[str, str] = {"SHU": "蜀", "WU": "吴", "WEI": "魏"}
        self.country_button_colors: Dict[str, pg.Color] = {
            "SHU": pg.Color("red"),
            "WU": pg.Color("green"),
            "WEI": pg.Color("blue"),
        }

        # 回合制顺序：蜀 -> 吴 -> 魏
        self.turn_order: List[str] = ["SHU", "WU", "WEI"]
        self.turn_index: int = 0
        self.max_major_rounds: int = 5
        self.max_minor_rounds: int = 6
        self.major_round: int = 1
        self.minor_round: int = 1
        self.turn_game_finished: bool = False

        # 国家公共属性（初始为0；回合推进与重开均不自动重置）
        self.country_stats: Dict[str, Dict[str, int]] = {
            country: {"people_support": 0, "political_points": 0}
            for country in self.turn_order
        }
        self.major_round_choice_pending: bool = False
        self.major_round_choice_done: Dict[str, bool] = {
            country: False for country in self.turn_order
        }
        self.country_stat_choice_btns: Dict[str, Dict[str, pg.Rect]] = {}

        # 移动后可追加一次“仅该单位”的攻击（可选）
        self.pending_post_move_attack: bool = False
        self.pending_attacker: SelectionEntry | None = None

        # AI 行动定时器（None = 不需要触发）
        self._ai_turn_timer: int | None = None

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
            ban_polylines=(BAN_LINE_POINTS,),
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

        # 初始化卡牌仓库
        self.card_repository = CardRepository(settings.cards_file)
        self.card_managers: Dict[str, CardManager] = {
            country: CardManager(self.card_repository, country)
            for country in self.turn_order
        }
        self.card_manager: CardManager | None = None
        self.card_effect_manager = CardEffectManager()  # 卡牌效果管理器

        # 卡牌目标选择状态
        self.selecting_card_target = False  # 是否正在选择卡牌目标
        self.selected_card_for_effect: str | None = None  # 待应用的卡牌ID

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
        panel_h = int(self.screen_height * 0.45)  # 60% - 15%

        panel_rect = pg.Rect(panel_x, panel_y, panel_w, panel_h)
        self.info_panel: InfoPanel | None = None
        self.card_panel: CardPanel | None = None

        # 预加载各个界面的素材，防止游戏运行时卡顿
        self._build_loading_assets()
        self._build_choosing_assets()
        self._build_play_assets()

        # 初始化 InfoPanel (在 build_play_assets 加载了字体之后)
        font_size = int(self.screen_height * 0.025)  # 字体大小约占屏幕高度的 2.5%
        info_font = self._font("msyh.ttc", font_size)
        font_path = str(self.settings.fonts_dir / "msyh.ttc")
        self.info_panel = InfoPanel(
            panel_rect, info_font, font_path=font_path, base_font_size=font_size
        )

        # 保存字体给战斗UI使用
        self.combat_ui_font = info_font
        # 预渲染解除混乱按钮文字
        self._recover_btn_surf = self.combat_ui_font.render(
            "解除混乱", True, pg.Color("white")
        )
        self._no_attack_btn_surf = self.combat_ui_font.render(
            "不攻击", True, pg.Color("white")
        )

        # Tooltip Caching
        self._last_tooltip_data = None
        self._cached_tooltip_surface: pg.Surface | None = None

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
            int(self.screen_height * 0.25),  # 85% - 60%
        )
        self.card_panel = CardPanel(
            card_rect, info_font, font_path=font_path, base_font_size=font_size
        )

        # 战斗UI状态 (位于顶部栏)
        self.show_combat_ui = False
        self.combat_target: object | None = None  # 当前选中的攻击目标 (Province)
        self.combat_ratio_val: float = 0.0
        self.combat_callback: Callable[[], None] | None = None
        self.combat_btn_rect: pg.Rect | None = None  # 在 render 时计算
        self.defense_jiangdong_btn_rect: pg.Rect | None = None
        self.defense_jiangdong_skip_btn_rect: pg.Rect | None = None
        self.defense_hold_btn_rect: pg.Rect | None = None
        self.defense_hold_skip_btn_rect: pg.Rect | None = None

        # 防守方可选决策（在战斗预览阶段切换）
        self.defender_can_use_jiangdong: bool = False
        self.defender_jiangdong_decided: bool = True
        self.defender_use_jiangdong: bool = False
        self.defender_can_hold_position: bool = False
        self.defender_hold_decided: bool = True
        self.defender_use_hold_position: bool = False
        self.waiting_defender_response: bool = False
        # 被进攻时是否允许从卡牌面板选择“江东止啼”
        self.allow_jiangdong_selection: bool = False

        # 解除混乱按钮区域
        self.recover_btn_rect: pg.Rect | None = None
        self.no_attack_btn_rect: pg.Rect | None = None
        self.skip_jiangdong_card_btn_rect: pg.Rect | None = None

        # 战斗结果显示 (Top UI area)
        self.combat_result_title: str | None = None  # e.g. "1:1 · 骰6 · A1"
        self.combat_result_timer: float = 0.0  # 显示倒计时

        # 初始填充行动力
        self._replenish_action_points()

    def _replenish_action_points(self) -> None:
        """
        重置所有单位的行动力 (MP)。
        应该在回合开始时调用。
        注意：根据规则，回合结束时只恢复行动力，不清除混乱状态。
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
                # 注意：回合结杞时不清除混乱状态，只重置攻击计数
                unit.attack_count = 0
                unit.temp_river_immunity = False
                unit.temp_terrain_immunity = False
                unit.temp_dice_bonus = 0

    def _update_card_panel(self) -> None:
        """更新卡牌面板显示"""
        if self.card_panel and self.card_manager:
            available_cards = self.card_manager.get_available_cards()

            # 江东止啼仅在“被进攻（魏方防守）”时可选
            if self.allow_jiangdong_selection:
                available_cards = [
                    c for c in available_cards if c.id == "card_jiangdong_zhiti"
                ]
            else:
                available_cards = [
                    c for c in available_cards if c.id != "card_jiangdong_zhiti"
                ]

            self.card_panel.set_available_cards(available_cards)

    def _play_selected_card(self) -> None:
        """打出选中的卡牌"""
        if not self.card_panel or not self.card_manager:
            return

        selected_card_id = self.card_panel.get_selected_card()
        if not selected_card_id:
            self.info_panel.show_message("请先选择一张卡牌")
            return

        # 检查卡牌是否已被使用
        if self.card_manager.is_card_used(selected_card_id):
            self.info_panel.show_message("该卡牌已被使用")
            return

        card_def = self.card_repository.get_definition(selected_card_id)
        if not card_def:
            return

        # 战斗中仅允许处理防守反应卡（江东止啼）
        if self.show_combat_ui and selected_card_id != "card_jiangdong_zhiti":
            self.info_panel.show_message("战斗进行中仅可使用江东止啼")
            return

        # 江东止啼：仅在被进攻（魏方防守）时可选择并使用
        if selected_card_id == "card_jiangdong_zhiti":
            if not self.allow_jiangdong_selection:
                self.info_panel.show_message("江东止啼仅在魏国被进攻时可选择")
                return

            # 立即消耗并登记本次战斗生效
            self.card_manager.use_card(selected_card_id)
            self.defender_use_jiangdong = True
            self.defender_jiangdong_decided = True
            self.allow_jiangdong_selection = False
            self.info_panel.show_message("已使用江东止啼：本次进攻方骰点-2")

            # 选择后恢复当前行动方卡牌显示
            if self.player_country and self.player_country in self.card_managers:
                self.card_manager = self.card_managers[self.player_country]
            self._update_card_panel()

            # 若此时正在等待防守方其他决策，且已满足条件，则继续战斗结算
            if (
                self.waiting_defender_response
                and self.defender_jiangdong_decided
                and self.defender_hold_decided
                and self.combat_callback
            ):
                self.waiting_defender_response = False
                self.combat_callback()
            return

        # 根据卡牌类型应用不同的处理方式
        if card_def.category == "offensive":
            # 威震华夏和火烧连营都直接激活，不需要目标选择
            if selected_card_id in [
                "card_zhenjing_huaxia_shu",
                "card_huoshao_lianying",
            ]:
                if self.card_effect_manager.activate_offensive_card(selected_card_id):
                    # 标记卡牌为已使用
                    self.card_manager.use_card(selected_card_id)
                    self.info_panel.show_message(
                        f"已激活锦囊卡: {card_def.name}", duration=2.0
                    )
                    self._update_card_panel()
                    logger.info(
                        f"Offensive card activated: {card_def.name} (ID: {selected_card_id})"
                    )
                return

        # buff、defensive、summon卡牌需要选择目标
        needs_target = card_def.category in ["buff", "defensive", "summon"]

        if needs_target:
            # 进入目标选择模式
            self.selecting_card_target = True
            self.selected_card_for_effect = selected_card_id
            self.info_panel.show_message(
                f"请点击目标格子来应用{card_def.name}", duration=-1
            )
        else:
            # 直接应用（当前暂无不需要目标的卡牌）
            self._apply_card_effect(selected_card_id, card_def)

    def _apply_card_effect(self, card_id: str, card_def: object) -> None:
        """
        应用卡牌效果到指定的目标格子。
        需要在目标格子选定后调用。
        """
        # 标记卡牌为已使用
        self.card_manager.use_card(card_id)

        # 显示卡牌使用提示
        self.info_panel.show_message(f"已使用锦囊卡: {card_def.name}", duration=2.0)

        # 更新卡牌面板（去掉已使用的卡牌）
        self._update_card_panel()

        logger.info(f"Card played: {card_def.name} (ID: {card_id})")

    def _apply_card_to_province(self, card_id: str, province_id: str) -> bool:
        """
        将卡牌效果应用到指定的格子。

        Args:
            card_id: 卡牌ID
            province_id: 目标格子ID

        Returns:
            是否成功应用
        """
        card_def = self.card_repository.get_definition(card_id)
        if not card_def:
            return False

        # 检查目标格子是否有效
        target_prov = self.map_manager.get_by_id(province_id)
        if not target_prov:
            self.info_panel.show_message("无效的目标格子")
            return False

        # 检查卡牌是否已被使用
        if self.card_manager.is_card_used(card_id):
            self.info_panel.show_message("该卡牌已被使用")
            return False

        # 仅允许对己方格子施放目标型卡牌
        if target_prov.country != self.player_country:
            self.info_panel.show_message("目标必须是己方格子")
            return False

        # 不再允许将 威震华夏 作为格子效果应用。该卡应当通过 Enter 全局激活。
        if card_id == "card_zhenjing_huaxia_shu":
            self.info_panel.show_message("威震华夏只能按 Enter 全局激活")
            return False

        # 江东止啼为反应卡，不接受手动指定格子
        if card_id == "card_jiangdong_zhiti":
            self.info_panel.show_message(
                "江东止啼无需指定格子，仅在魏国被进攻时可在卡牌面板选择"
            )
            return False

        # 召唤类卡牌：如果目标格子已有最大堆叠数，拒绝并提示（不消耗卡牌）
        if card_id in ("card_qilin_qishu", "card_guanmu_xiangkan"):
            if len(target_prov.units) >= MAX_UNIT_STACK:
                self.info_panel.show_message("超过堆叠数量，请重新选择格子")
                return False

        # 如果是召唤卡，要求只能部署在对应国家的格子
        if card_id == "card_qilin_qishu" and target_prov.country != "SHU":
            self.info_panel.show_message("七擒七纵只能部署在蜀国格子")
            return False
        if card_id == "card_guanmu_xiangkan" and target_prov.country != "WU":
            self.info_panel.show_message("刮目相看只能部署在吴国格子")
            return False

        # 应用卡牌效果（记录效果/标记格子）
        success = self.card_effect_manager.apply_card_effect(
            card_id,
            card_def.name,
            province_id,
            self.player_country,
        )

        if success:
            if card_id == "card_baiyue_dujiang":
                # 白衣渡江：目标格上现有单位本大回合跨河免疫，且骰点+1
                for u in target_prov.units:
                    u.temp_river_immunity = True
                    u.temp_dice_bonus = max(u.temp_dice_bonus, 1)

            if card_id == "card_touduo_yinping":
                # 偷渡阴平：目标格上现有单位本大回合行动力+2
                for u in target_prov.units:
                    u.mp += 2
                    u.temp_terrain_immunity = True

            # 处理召唤类卡牌的实际单位生成
            if card_id == "card_qilin_qishu":
                # 召唤 无当飞军 -> 对应单位类型 WUDANG_archer
                try:
                    unit_def = self.unit_repository.get_definition("WUDANG_archer")
                    new_unit = UnitState("WUDANG_archer")
                    new_unit.mp = unit_def.move
                    target_prov.units.append(new_unit)
                    self.map_manager.invalidate_cache()
                    self.info_panel.show_message(
                        f"在{target_prov.name}召唤了无当飞军", duration=2.0
                    )
                except Exception:
                    logger.exception("召唤 无当飞军 失败")

            if card_id == "card_guanmu_xiangkan":
                # 召唤 解烦兵 -> 对应单位类型 JIEFAN_infantry
                try:
                    unit_def = self.unit_repository.get_definition("JIEFAN_infantry")
                    new_unit = UnitState("JIEFAN_infantry")
                    new_unit.mp = unit_def.move
                    target_prov.units.append(new_unit)
                    self.map_manager.invalidate_cache()
                    self.info_panel.show_message(
                        f"在{target_prov.name}召唤了解烦兵", duration=2.0
                    )
                except Exception:
                    logger.exception("召唤 解烦兵 失败")

            # 标记卡牌为已使用并更新界面
            self._apply_card_effect(card_id, card_def)
            return True

        self.info_panel.show_message("无法应用卡牌效果")
        return False

    def _cancel_card_target_selection(self) -> None:
        """取消卡牌目标选择"""
        self.selecting_card_target = False
        self.selected_card_for_effect = None
        self.info_panel.show_message("已取消卡牌选择")

    def _province_has_river_neighbor(self, province_id: str) -> bool:
        """
        检查指定的格子是否有河流相邻。

        Args:
            province_id: 格子ID

        Returns:
            是否有河流在相邻边上
        """
        target_prov = self.map_manager.get_by_id(province_id)
        if not target_prov:
            return False

        # 遍历所有格子，检查与目标格子相邻的边是否有河流
        for prov in self.map_manager.provinces:
            # 检查两个方向的边
            if self.map_manager._river_crossing_edges.get(
                (province_id, prov.province_id), False
            ):
                return True
            if self.map_manager._river_crossing_edges.get(
                (prov.province_id, province_id), False
            ):
                return True

        return False

    def _start_turn_based_game(self, human_country: str = "SHU") -> None:
        """开始回合制对局。human_country 为玩家控制的国家。"""
        self.human_country = human_country
        self.turn_index = 0
        self.major_round = 1
        self.minor_round = 1
        self.turn_game_finished = False
        self.player_country = self.turn_order[self.turn_index]

        # 新对局重置卡牌使用状态
        self.card_managers = {
            country: CardManager(self.card_repository, country)
            for country in self.turn_order
        }
        self.card_manager = self.card_managers[self.player_country]

        self.card_effect_manager.clear_all_effects()
        self._replenish_action_points()
        self._start_major_round_choice_phase()
        self.clear_selection()
        self._update_card_panel()
        self.state = GameState.PLAYING

        # 如果第一个行动国是 AI，安排延迟触发
        if self.human_country is not None and self.player_country != self.human_country:
            self._ai_turn_timer = pg.time.get_ticks() + 800

    def _start_major_round_choice_phase(self) -> None:
        """每个大回合开始：三国各自选择 +2 民心点数 或 +2 政治点数。"""
        self.major_round_choice_pending = True
        self.major_round_choice_done = {country: False for country in self.turn_order}
        self.country_stat_choice_btns = {}
        # AI 国家立即自动完成加点（默认选 support）
        if self.human_country is not None:
            for _c in list(self.turn_order):
                if _c != self.human_country:
                    self._apply_major_round_choice(_c, "support")

    def _apply_major_round_choice(self, country: str, choice: str) -> None:
        """应用国家在大回合开始时的加点选择。"""
        if not self.major_round_choice_pending:
            return
        if country not in self.turn_order:
            return
        if self.major_round_choice_done.get(country, False):
            return

        stats = self.country_stats.setdefault(
            country, {"people_support": 0, "political_points": 0}
        )
        if choice == "support":
            stats["people_support"] = int(stats.get("people_support", 0)) + 2
        elif choice == "politics":
            stats["political_points"] = int(stats.get("political_points", 0)) + 2
        else:
            return

        self.major_round_choice_done[country] = True

        if all(self.major_round_choice_done.get(c, False) for c in self.turn_order):
            self.major_round_choice_pending = False
            if self.info_panel:
                self.info_panel.show_message(
                    f"第{self.major_round}大回合加点完成：三国均已选择"
                )

    def _end_full_round(self) -> None:
        """三个国家都行动完后触发：清理回合效果并复位行动力。"""
        self.card_effect_manager.clear_all_effects()
        self._replenish_action_points()

    def _clear_for_turn_switch(self, keep_info_message: bool = False) -> None:
        """切换国家前清理交互状态，可选保留信息面板内容（用于保留战果）。"""
        self.selected_units.clear()
        self.show_combat_ui = False
        self.combat_target = None
        self.combat_callback = None
        self.defense_jiangdong_btn_rect = None
        self.defense_jiangdong_skip_btn_rect = None
        self.defense_hold_btn_rect = None
        self.defense_hold_skip_btn_rect = None
        self.defender_can_use_jiangdong = False
        self.defender_jiangdong_decided = True
        self.defender_use_jiangdong = False
        self.defender_can_hold_position = False
        self.defender_hold_decided = True
        self.defender_use_hold_position = False
        self.waiting_defender_response = False
        self.allow_jiangdong_selection = False
        self.no_attack_btn_rect = None
        self.skip_jiangdong_card_btn_rect = None

        if not keep_info_message:
            self.combat_result_title = None
            self.combat_result_timer = 0
            if self.info_panel:
                self.info_panel.show_properties("")

    def _advance_country_turn(self, keep_info_message: bool = False) -> None:
        """切换到下一个国家。"""
        if self.turn_game_finished:
            return

        self.pending_post_move_attack = False
        self.pending_attacker = None
        self.selecting_card_target = False
        self.selected_card_for_effect = None
        self._clear_for_turn_switch(keep_info_message=keep_info_message)

        self.turn_index += 1
        if self.turn_index >= len(self.turn_order):
            self.turn_index = 0

            # 一个小回合（蜀->吴->魏）结束
            if self.minor_round < self.max_minor_rounds:
                self.minor_round += 1
                self._end_full_round()
            elif self.major_round < self.max_major_rounds:
                # 小回合满6后进入下一个大回合
                self.major_round += 1
                self.minor_round = 1
                self._end_full_round()
                self._start_major_round_choice_phase()
            else:
                # 5个大回合 * 6个小回合结束，对局终止
                self.turn_game_finished = True
                self.player_country = None
                self.card_manager = None
                if self.card_panel:
                    self.card_panel.set_available_cards([])
                if self.info_panel:
                    self.info_panel.show_message(
                        "对局结束：已完成5个大回合（每回合6个小回合）"
                    )
                return

        self.player_country = self.turn_order[self.turn_index]
        self.card_manager = self.card_managers[self.player_country]
        self._update_card_panel()

        # 若当前轮到的是 AI 国家，延迟触发 AI 行动
        if (
            self.human_country is not None
            and self.player_country != self.human_country
            and not self.turn_game_finished
        ):
            self._ai_turn_timer = pg.time.get_ticks() + 600  # 600ms 后执行
        else:
            self._ai_turn_timer = None

    def _finish_country_action(
        self, action_name: str, keep_info_message: bool = False
    ) -> None:
        """当前国家执行完一个动作后，自动轮换到下一国家。"""
        self._advance_country_turn(keep_info_message=keep_info_message)

    # ---------------------------------------------------------------
    # AI TURN
    # ---------------------------------------------------------------

    def _ai_get_border_provinces(self, country: str):
        """返回己方的边境省列表：与敌方省份相邻（距离 <= 1格）的己方省份，
        按其到最近敌省的像素距离升序排列（越靠前越接近敌方）。"""
        unit_stride = SQRT3 * self.hex_side
        border = []
        for prov in self.map_manager.provinces:
            if prov.country != country:
                continue
            p_center = prov.center_cache or prov.compute_center(self.hex_side)
            min_d = float("inf")
            for enemy in self.map_manager.provinces:
                if enemy.country == country or not enemy.country:
                    continue
                e_center = enemy.center_cache or enemy.compute_center(self.hex_side)
                d = dist(p_center, e_center)
                if d < min_d:
                    min_d = d
            # 1.1 格范围内有敌省即视为边境
            if min_d <= unit_stride * 1.1:
                border.append((min_d, prov))
        border.sort(key=lambda x: x[0])
        return [p for _, p in border]

    def _ai_execute_combat(self, province, slot_idx, target):
        """AI 直接执行战斗（跳过 UI 交互）。返回是否成功发起。"""
        self.selected_units = [(province.province_id, slot_idx)]
        self._handle_combat(target)
        if self.combat_callback and self.show_combat_ui:
            self.defender_jiangdong_decided = True
            self.defender_use_jiangdong = False
            self.defender_hold_decided = True
            self.defender_use_hold_position = False
            cb = self.combat_callback
            self.combat_callback = None
            self.show_combat_ui = False
            cb()
            return True
        return False

    def _run_ai_turn(self) -> None:
        """AI 行动：自动完成大回合加点选择 + 移动/攻击，然后结束本国回合。
        策略：先将所有内陆部队调往边境，全部到位后再发动进攻。"""
        if self.turn_game_finished:
            return
        country = self.player_country
        if country is None or country == self.human_country:
            return

        # --- 阶段1：大回合加点（如果还未选择） ---
        if self.major_round_choice_pending:
            for c in list(self.turn_order):
                if not self.major_round_choice_done.get(c, False):
                    self._apply_major_round_choice(c, "support")
            if self.major_round_choice_pending:
                self._ai_turn_timer = pg.time.get_ticks() + 300
                return

        # 预计算本国边境省集合
        border_provs = self._ai_get_border_provinces(country)
        border_ids = {p.province_id for p in border_provs}

        # 收集所有己方有行动力的单位，按"是否在边境"分两组
        border_units = []   # (province, slot_idx, unit_state)
        inland_units = []

        for province in self.map_manager.provinces:
            if province.country != country:
                continue
            for slot_idx, unit_state in enumerate(province.units):
                if unit_state.mp <= 0:
                    continue
                if province.province_id in border_ids:
                    border_units.append((province, slot_idx, unit_state))
                else:
                    inland_units.append((province, slot_idx, unit_state))

        action_taken = False

        # --- 阶段2（最高优先级）：内陆单位向边境线移动 ---
        # 只要还有内陆单位能移动，就优先集结，不发动攻击
        if inland_units:
            # 按距最近边境省由近到远排序，离边境最近的先动
            def _inland_priority(item):
                prov, _, _ = item
                p_c = prov.center_cache or prov.compute_center(self.hex_side)
                min_d = float("inf")
                for bp in border_provs:
                    b_c = bp.center_cache or bp.compute_center(self.hex_side)
                    d = dist(p_c, b_c)
                    if d < min_d:
                        min_d = d
                return min_d

            inland_units.sort(key=_inland_priority)

            for province, slot_idx, unit_state in inland_units:
                dest = self._ai_pick_move_target(province, unit_state, border_provs)
                if dest is not None:
                    self.selected_units = [(province.province_id, slot_idx)]
                    self._handle_movement(dest)
                    action_taken = True
                    break

        # --- 阶段3：所有单位均已在边境（或内陆无法移动），发动攻击 ---
        if not action_taken:
            for province, slot_idx, unit_state in border_units:
                if self._has_attackable_target_for_unit(province, unit_state):
                    target = self._ai_pick_attack_target(province, unit_state)
                    if target is not None:
                        if self._ai_execute_combat(province, slot_idx, target):
                            action_taken = True
                            break

        # --- 阶段4：无法攻击，边境单位向敌省压进 ---
        if not action_taken:
            for province, slot_idx, unit_state in border_units:
                dest = self._ai_pick_move_target(province, unit_state, None)
                if dest is not None:
                    self.selected_units = [(province.province_id, slot_idx)]
                    self._handle_movement(dest)
                    action_taken = True
                    break

        # --- 阶段5：结束本国回合 ---
        self._finish_country_action(f"AI({country})行动", keep_info_message=action_taken)

    def _ai_pick_attack_target(self, province, unit_state):
        """AI 选择攻击目标：优先选血量最少（单位数最少）的相邻敌省。"""
        definition = self.unit_repository.get_definition(unit_state.unit_type)
        unit_stride = SQRT3 * self.hex_side
        allowed_range_px = definition.range * unit_stride * 1.1
        p_center = (
            province.center_cache
            if province.center_cache
            else province.compute_center(self.hex_side)
        )
        best = None
        best_score = float("inf")
        for target in self.map_manager.provinces:
            if target.country == province.country:
                continue
            if not target.units and not self._is_fort_or_city(target):
                continue
            t_center = (
                target.center_cache
                if target.center_cache
                else target.compute_center(self.hex_side)
            )
            if dist(p_center, t_center) <= allowed_range_px:
                score = len(target.units)  # 越少越软
                if score < best_score:
                    best_score = score
                    best = target
        return best

    def _ai_pick_move_target(self, province, unit_state, border_provs=None):
        """AI 选择移动目标。
        - 若提供了 border_provs（边境省列表），内陆单位优先移向最近的边境省。
        - 边境单位或无边境时，移向最近的敌省旁的最优格子。
        """
        ap = unit_state.mp
        if ap <= 0:
            return None

        p_center = province.center_cache or province.compute_center(self.hex_side)

        # 决定"目标锚点"：内陆单位以最近边境省为锚，边境单位以最近敌省为锚
        anchor_center = None
        if border_provs:
            # 找最近的边境省（自己本身不算）
            best_d = float("inf")
            for bp in border_provs:
                if bp.province_id == province.province_id:
                    continue
                bc = bp.center_cache or bp.compute_center(self.hex_side)
                d = dist(p_center, bc)
                if d < best_d:
                    best_d = d
                    anchor_center = bc

        if anchor_center is None:
            # 回退：以最近敌省为锚
            best_d = float("inf")
            for target in self.map_manager.provinces:
                if target.country == province.country or not target.country:
                    continue
                tc = target.center_cache or target.compute_center(self.hex_side)
                d = dist(p_center, tc)
                if d < best_d:
                    best_d = d
                    anchor_center = tc

        if anchor_center is None:
            return None

        # 在行动力范围内找距锚点最近的可移动格子
        best_dest = None
        best_dist_to_anchor = float("inf")
        for candidate in self.map_manager.provinces:
            if candidate.province_id == province.province_id:
                continue
            # 不能移入敌方占领的省（有敌军驻守的）
            if candidate.country not in (province.country, None, ""):
                continue
            path_cost = self.map_manager.find_path_cost(
                province.province_id, candidate.province_id
            )
            if path_cost > ap or path_cost > 100:
                continue
            c_center = candidate.center_cache or candidate.compute_center(self.hex_side)
            d_to_anchor = dist(c_center, anchor_center)
            if d_to_anchor < best_dist_to_anchor:
                best_dist_to_anchor = d_to_anchor
                best_dest = candidate

        return best_dest

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
            ban_polylines=(BAN_LINE_POINTS,),
        )
        self.map_manager.set_hex_side(self.hex_side)

        # 2. 初始化单位的行动力和状态
        self._replenish_action_points()

        # 3. 清理选择和UI
        self.clear_selection()
        self.show_combat_ui = False
        self.combat_result_title = None
        if self.info_panel:
            self.info_panel.show_properties("")

        # 3.5 重置卡牌系统
        self.card_managers = {
            country: CardManager(self.card_repository, country)
            for country in self.turn_order
        }
        self.card_manager = None
        self.card_effect_manager.clear_all_effects()  # 清除卡牌效果
        self.selecting_card_target = False  # 退出卡牌目标选择模式
        self.selected_card_for_effect = None
        if self.card_panel:
            self.card_panel.set_available_cards([])

        self.pending_post_move_attack = False
        self.pending_attacker = None

        # 4. 切换状态
        self.player_country = None
        self.human_country = None
        self.turn_index = 0
        self.major_round = 1
        self.minor_round = 1
        self.turn_game_finished = False
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
            self.event_manager.process()  # 1. 处理鼠标键盘输入
            self._update()  # 2. 更新游戏逻辑
            self._render()  # 3. 绘制画面

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

        self._cancel_combat_preview()  # 清空战斗预览

        # 只要点击了地图上的其他东西（或者清空选择），就应该清空上一次的战果(Top UI)
        if clear_ui:
            self.combat_result_title = None
            self.combat_result_timer = 0
            if self.info_panel:
                self.info_panel.show_properties("")  # 清空面板

    def _cancel_combat_preview(self) -> None:
        """取消战斗预览状态"""
        self.show_combat_ui = False
        self.combat_target = None
        self.combat_callback = None
        self.defense_jiangdong_btn_rect = None
        self.defense_jiangdong_skip_btn_rect = None
        self.defense_hold_btn_rect = None
        self.defense_hold_skip_btn_rect = None
        self.defender_can_use_jiangdong = False
        self.defender_jiangdong_decided = True
        self.defender_use_jiangdong = False
        self.defender_can_hold_position = False
        self.defender_hold_decided = True
        self.defender_use_hold_position = False
        self.waiting_defender_response = False
        self.allow_jiangdong_selection = False
        self.no_attack_btn_rect = None
        self.skip_jiangdong_card_btn_rect = None

        # 退出战斗预览时恢复当前行动国卡牌面板
        if self.player_country and self.player_country in self.card_managers:
            self.card_manager = self.card_managers[self.player_country]
            self._update_card_panel()
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
        self._update_selection_info()  # 更新面板信息

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
        if unit_type == "HUBAO_cavalry":
            return "虎豹"
        if unit_type == "WUDANG_archer":
            return "无当"
        if unit_type == "JIEFAN_infantry":
            return "解烦"

        if "infantry" in unit_type:
            return "步"
        if "cavalry" in unit_type:
            return "骑"
        if "archer" in unit_type:
            return "弓"
        return unit_type[0].upper()

    def _format_unit_info(
        self, u_state, prefix: str = "", province_id: str | None = None
    ) -> str:
        """通用单位信息格式化"""
        u_def = self.unit_repository.get_definition(u_state.unit_type)
        u_abbr = self._get_unit_abbr(u_state.unit_type)

        status = []
        if u_state.is_injured:
            status.append("伤")
        if u_state.is_confused:
            status.append("乱")
        status_str = f"({''.join(status)})" if status else ""

        # [Prefix步(伤)]
        # 为了实现彩色，我们构建富文本字符串
        # 格式： 文本|#HexColor|彩色文本|#000000|文本
        # 注意默认文字颜色通常是黑色 #000000

        country = u_def.country
        color_hex = "#000000"
        if country:
            # 获取对应国家的颜色
            c = self.kingdom_repository.get_color(country)  # pg.Color
            # 转为 hex
            color_hex = f"#{c.r:02x}{c.g:02x}{c.b:02x}"

        # 构建富文本行: "[" + "|#COLOR|" + ABBR + "|#000000|" + status + "]"
        abbr_part = f"|{color_hex}|{u_abbr}|#000000|"
        label = f"[{prefix}{abbr_part}{status_str}]"

        # 计算实际攻防值（考虑受伤、混乱与格子上可能的卡牌效果）
        actual_atk, actual_dfs = self._calculate_unit_powers(u_state, province_id)

        attrs = [
            f"血{u_state.hp}",
            f"攻{actual_atk:.1f}",
            f"防{actual_dfs:.1f}",
            f"动{u_state.mp}/{u_def.move}",
            f"射{u_def.range}",
            f"疲{u_state.attack_count}",
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
            if not prov:
                continue
            u_state = prov.units[idx]
            # 还原为无序号显示，传入所在格子ID以便卡牌效果能生效
            info_str = self._format_unit_info(u_state, province_id=prov.province_id)
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
        """处理选择势力界面的事件"""
        if event.type != pg.MOUSEBUTTONDOWN or event.button != 1:
            return
        for country, button in self.faction_buttons.items():
            cx, cy = button["center"]
            dx = event.pos[0] - cx
            dy = event.pos[1] - cy
            if (dx * dx + dy * dy) <= self.faction_button_radius ** 2:
                self._start_turn_based_game(human_country=country)
                return

    def _handle_playing_event(self, event: pg.event.Event) -> None:
        """处理游戏中的事件"""
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                # 如果正在选择卡牌目标，取消目标选择
                if self.selecting_card_target:
                    self._cancel_card_target_selection()
                else:
                    # 否则取消单位选择
                    self.clear_selection()
            elif event.key == pg.K_RETURN:
                if self.major_round_choice_pending:
                    if self.info_panel:
                        self.info_panel.show_message("请先完成三国大回合加点选择")
                    return
                # 按 Enter 打出选中的卡牌（不占用本国回合动作次数）
                self._play_selected_card()
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
                        return

                # 0.0x 大回合开始加点按钮（三国）
                if self.major_round_choice_pending:
                    for country, btns in self.country_stat_choice_btns.items():
                        support_rect = btns.get("support")
                        politics_rect = btns.get("politics")
                        if support_rect and support_rect.collidepoint(event.pos):
                            self._apply_major_round_choice(country, "support")
                            return
                        if politics_rect and politics_rect.collidepoint(event.pos):
                            self._apply_major_round_choice(country, "politics")
                            return

                    if self.info_panel:
                        self.info_panel.show_message("请在三国面板中完成加点选择")
                    return

                # 0. 优先处理顶部的战斗按钮
                if (
                    self.show_combat_ui
                    and self.combat_btn_rect
                    and self.combat_btn_rect.collidepoint(event.pos)
                ):
                    if (
                        self.defender_can_use_jiangdong
                        and not self.defender_jiangdong_decided
                    ):
                        self.waiting_defender_response = True
                        self.allow_jiangdong_selection = True
                        wei_manager = self.card_managers.get("WEI")
                        if wei_manager:
                            self.card_manager = wei_manager
                        self._update_card_panel()
                        self.info_panel.show_message(
                            "进攻方已投骰，请防守方选择江东止啼（或点击不使用）"
                        )
                        return

                    if (
                        self.defender_can_hold_position
                        and not self.defender_hold_decided
                    ):
                        self.waiting_defender_response = True
                        self.info_panel.show_message("进攻方已投骰，等待防守方即时决策")
                        return
                    if self.combat_callback:
                        self.combat_callback()
                    # 点击按钮后，UI会在 clear_selection 关闭，或者在 callback 里处理
                    # 这里 return 防止点穿到下面地图
                    return

                if (
                    self.show_combat_ui
                    and self.defense_hold_btn_rect
                    and self.defense_hold_btn_rect.collidepoint(event.pos)
                ):
                    if (
                        self.waiting_defender_response
                        and self.defender_can_hold_position
                        and not self.defender_hold_decided
                    ):
                        self.defender_use_hold_position = True
                        self.defender_hold_decided = True
                        self.info_panel.show_message(
                            "已选择：防守方选择：DR改D1DG", duration=1.2
                        )
                        if (
                            self.defender_jiangdong_decided
                            and self.defender_hold_decided
                            and self.combat_callback
                        ):
                            self.waiting_defender_response = False
                            self.combat_callback()
                    return

                if (
                    self.show_combat_ui
                    and self.defense_hold_skip_btn_rect
                    and self.defense_hold_skip_btn_rect.collidepoint(event.pos)
                ):
                    if (
                        self.waiting_defender_response
                        and self.defender_can_hold_position
                        and not self.defender_hold_decided
                    ):
                        self.defender_use_hold_position = False
                        self.defender_hold_decided = True
                        self.info_panel.show_message("已选择：保持正常DR", duration=1.2)
                        if (
                            self.defender_jiangdong_decided
                            and self.defender_hold_decided
                            and self.combat_callback
                        ):
                            self.waiting_defender_response = False
                            self.combat_callback()
                    return

                # 0.055 江东止啼：不使用按钮（放在卡牌区域）
                if (
                    self.show_combat_ui
                    and self.skip_jiangdong_card_btn_rect
                    and self.skip_jiangdong_card_btn_rect.collidepoint(event.pos)
                ):
                    if (
                        self.waiting_defender_response
                        and self.defender_can_use_jiangdong
                        and not self.defender_jiangdong_decided
                    ):
                        self.defender_use_jiangdong = False
                        self.defender_jiangdong_decided = True
                        self.allow_jiangdong_selection = False
                        if (
                            self.player_country
                            and self.player_country in self.card_managers
                        ):
                            self.card_manager = self.card_managers[self.player_country]
                        self._update_card_panel()
                        self.info_panel.show_message(
                            "已选择：本次不使用江东止啼", duration=1.2
                        )
                        if (
                            self.defender_jiangdong_decided
                            and self.defender_hold_decided
                            and self.combat_callback
                        ):
                            self.waiting_defender_response = False
                            self.combat_callback()
                    return

                # 0.1 检查“解除混乱”按钮
                if self.recover_btn_rect and self.recover_btn_rect.collidepoint(
                    event.pos
                ):
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
                        self._finish_country_action("解除混乱")
                    return

                # 0.15 检查“移动后不攻击”按钮
                if (
                    self.pending_post_move_attack
                    and self.no_attack_btn_rect
                    and self.no_attack_btn_rect.collidepoint(event.pos)
                ):
                    if self.info_panel:
                        self.info_panel.show_message(
                            "已选择不攻击，进入下一步", duration=1.0
                        )
                    self._finish_country_action("移动")
                    return

                # 0.2 检查卡牌面板点击
                if self.card_panel and self.card_panel.rect.collidepoint(event.pos):
                    card_id = self.card_panel.get_card_at(event.pos)
                    if card_id:
                        # 选中卡牌
                        self.card_panel.select_card(card_id)

                        # 防守响应阶段：点击“江东止啼”即立即生效并推进（无需再按 Enter）
                        if (
                            card_id == "card_jiangdong_zhiti"
                            and self.show_combat_ui
                            and self.waiting_defender_response
                            and self.allow_jiangdong_selection
                        ):
                            self._play_selected_card()
                            return

                        # 显示卡牌描述
                        # buff/defensive/summon 类：点击即进入目标选择模式；offensive 类：等待 Enter
                        card_def = self.card_repository.get_definition(card_id)
                        if card_def and card_def.category in (
                            "buff",
                            "defensive",
                            "summon",
                        ):
                            self._play_selected_card()
                            return
                        elif card_def:
                            self.info_panel.show_message(
                                f"已选中: {card_def.name}，按 Enter 使用"
                            )

                # 优先处理 UI 面板点击
                if self.info_panel and self.info_panel.handle_click(event.pos):
                    return

                # 如果正在选择卡牌目标，检查是否点击了一个格子
                if self.selecting_card_target and self.selected_card_for_effect:
                    target_prov = self._get_province_at(event.pos)
                    if target_prov:
                        # 尝试应用卡牌效果到目标格子
                        if self._apply_card_to_province(
                            self.selected_card_for_effect, target_prov.province_id
                        ):
                            # 成功应用，退出目标选择模式
                            self.selecting_card_target = False
                            self.selected_card_for_effect = None
                        return
                    else:
                        # 点击到了空地或法无效区域，提示并继续等待选择
                        self.info_panel.show_message(
                            "请点击地图上的一个格子", duration=1.0
                        )
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

                    # 移动后追加攻击窗口中，只允许该单位继续操作
                    if self.pending_post_move_attack and self.pending_attacker:
                        if (prov_id, slot_idx) != self.pending_attacker:
                            self.info_panel.show_message(
                                "请继续使用刚移动的单位，或右键结束该动作"
                            )
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
                if self.major_round_choice_pending:
                    if self.info_panel:
                        self.info_panel.show_message("请先完成三国大回合加点选择")
                    return
                self._handle_game_right_click(event.pos)
        elif event.type == pg.MOUSEMOTION:
            # 处理鼠标移动以显示卡牌描述提示
            if self.card_panel:
                self.card_panel.handle_mouse_motion(event.pos)

    def _get_unit_slot_at(self, pos: Tuple[int, int]) -> Tuple[int, int] | None:
        """根据鼠标点击位置获取被点击的单位"""
        # 遍历所有格子，检查点击点是否在某个单位的图标 rect 内
        for p in self.map_manager.provinces:
            if not p.units:
                continue

            # 简单的性能优化：如果离格子中心太远，就不检查这个格子里的单位
            # 图标一般在格子中心附近
            center = (
                p.center_cache if p.center_cache else p.compute_center(self.hex_side)
            )
            if dist(pos, center) > self.hex_side:
                continue

            rects = self.unit_renderer.selection_rects(center, len(p.units))
            for i, r in enumerate(rects):
                if r.collidepoint(pos):
                    return (p.province_id, i)
        return None

    def _get_province_at(
        self, pos: Tuple[int, int]
    ) -> object | None:  # object -> Province
        """简单的点击拾取检测"""
        best_p = None
        min_dist = float("inf")
        # 判定阈值：内切圆半径 = hex_side * sqrt(3)/2 ≈ 0.866
        threshold = self.hex_side * 0.9

        for province in self.map_manager.provinces:
            # 优先使用缓存的中心点
            center = (
                province.center_cache
                if province.center_cache
                else province.compute_center(self.hex_side)
            )
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

        # 检查是否是敌方
        is_enemy = target_province.country != self.player_country

        if is_enemy:
            target_effect = self.card_effect_manager.get_effect(
                str(target_province.province_id)
            )
            if target_effect and target_effect.protected:
                self.info_panel.show_message(
                    "该格处于空城妙计保护中，本大回合不可被进攻"
                )
                return

        can_attack = is_enemy and (
            len(target_province.units) > 0 or self._is_fort_or_city(target_province)
        )

        if can_attack:
            # 切换/取消 战斗目标逻辑
            # 如果再次点击已选目标 -> 取消选中
            if self.combat_target and self.combat_target == target_province:
                self._cancel_combat_preview()
            else:
                self._handle_combat(target_province)
        else:
            # 移动或占领空地
            if self.pending_post_move_attack:
                # 移动后攻击窗口中，不再通过右键空地结束；需点击“不攻击”按钮
                if self.info_panel:
                    self.info_panel.show_message("请选择攻击单位或不攻击")
                return
            self._handle_movement(target_province)

    def _handle_movement(self, target: object) -> None:  # target: Province
        """处理移动逻辑"""
        # 动作1：移动仅允许一个单位
        if len(self.selected_units) != 1:
            self.info_panel.show_message("移动行动只能选择1个单位")
            return

        # 1. 检查选中单位的来源（只能来自同一个格子）
        source_ids = {pid for pid, _ in self.selected_units}
        if len(source_ids) > 1:
            self.info_panel.show_message("选择单位过多")
            return

        # 获取源格子
        source_id = list(source_ids)[0]
        source = self.map_manager.get_by_id(source_id)
        if not source:
            return

        if source.province_id == target.province_id:
            return  # 原地不动

        # 2. 检查移动距离与行动点
        selected_indices = sorted(
            [idx for pid, idx in self.selected_units if pid == source_id]
        )
        if not selected_indices:
            return

        # 使用路径寻路计算 Cost
        # 如果 source == target，不需要移动
        if source.province_id == target.province_id:
            self.clear_selection()
            return

        # 调用 map_manager 的寻路算法
        # 注意：这里计算的是从 Source 到 Target 的最短路径 Cost
        # 假设所有选中单位走同一条路
        selected_unit = source.units[selected_indices[0]]
        source_effect = self.card_effect_manager.get_effect(str(source.province_id))
        ignore_mountain = bool(getattr(selected_unit, "temp_terrain_immunity", False))
        if source_effect and source_effect.terrain_immunity:
            ignore_mountain = True

        if ignore_mountain:
            path_cost = self._find_path_cost_ignore_mountain(
                source.province_id, target.province_id
            )
        else:
            path_cost = self.map_manager.find_path_cost(
                source.province_id, target.province_id
            )

        # 寻路失败（比如不可达，虽然目前全图连通）
        if path_cost > 100:
            self.info_panel.show_message("无法到达")
            return

        moving_units = []
        unit_costs = []  # 记录扣除的行动力

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
        # 目标格子已有兵 + 即将移动过去的兵 > MAX_UNIT_STACK
        if len(target.units) + len(moving_units) > MAX_UNIT_STACK:
            self.info_panel.show_message("堆叠部队过多")
            return

        # 仅当“移动前可攻击”且“移动后可攻击”时，才提供移动后攻击选择
        # （根据规则：当且仅当移动前后都能攻击）
        pre_move_can_attack = (
            selected_unit.mp > 0
            and self._has_attackable_target_for_unit(source, selected_unit)
        )

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
            self.map_manager.invalidate_cache()

        # 移除选中状态
        self.clear_selection()

        # 简单反馈
        logger.info(
            f"Moved {len(moving_units)} units from {source.name} to {target.name}"
        )

        moved_unit = moving_units[0] if moving_units else None
        post_move_can_attack = bool(
            moved_unit
            and moved_unit.mp > 0
            and self._has_attackable_target_for_unit(target, moved_unit)
        )

        if moved_unit and pre_move_can_attack and post_move_can_attack:
            # 允许追加一次仅该单位的攻击
            moved_slot = target.units.index(moved_unit)
            self.pending_post_move_attack = True
            self.pending_attacker = (target.province_id, moved_slot)
            self.add_selection(target.province_id, moved_slot)
            self.info_panel.show_message("请选择攻击单位或不攻击")
            return

        self._finish_country_action("移动")

    def _calculate_unit_powers(
        self, unit_state, province_id: str | None = None
    ) -> Tuple[float, float]:
        """计算单位当前的攻击力和防御力 (考虑受伤、混乱及格子上卡牌效果)

        Args:
            unit_state: 单位状态对象
            province_id: 可选，单位所在格子的ID，用于查询格子上的卡牌效果
        """
        definition = self.unit_repository.get_definition(unit_state.unit_type)
        atk = float(definition.attack)
        dfs = float(definition.defense)

        # 受伤减半
        if unit_state.is_injured:
            atk *= INJURY_PENALTY
            dfs *= INJURY_PENALTY

        # 混乱 -1
        if unit_state.is_confused:
            atk = max(0, atk - CONFUSION_PENALTY)
            dfs = max(0, dfs - CONFUSION_PENALTY)

        return atk, dfs

    def _is_mountain_terrain(self, province: object) -> bool:
        terrain = (province.terrain or "").lower()
        return terrain in ("hill", "mountain", "hills", "mountains")

    def _is_fort_or_city(self, province: object) -> bool:
        terrain = (province.terrain or "").lower()
        # 本项目规则：关隘 = 城市
        return terrain == "city"

    def _is_river_crossing(self, from_id: int, to_id: int) -> bool:
        return self.map_manager._river_crossing_edges.get(
            (from_id, to_id), False
        ) or self.map_manager._river_crossing_edges.get((to_id, from_id), False)

    def _get_attack_terrain_penalty(
        self, attacker_prov: object, target_prov: object, unit_state
    ) -> int:
        """跨河/攻山地惩罚：满足任一条件时攻击力-1（无当飞军除外）"""
        unit_type_lower = (unit_state.unit_type or "").lower()
        if "wudang" in unit_type_lower:
            return 0

        effect = self.card_effect_manager.get_effect(str(attacker_prov.province_id))
        river_immune = bool(effect and effect.river_immunity) or bool(
            getattr(unit_state, "temp_river_immunity", False)
        )
        terrain_immune = bool(effect and effect.terrain_immunity) or bool(
            getattr(unit_state, "temp_terrain_immunity", False)
        )

        is_river = self._is_river_crossing(
            attacker_prov.province_id, target_prov.province_id
        )
        is_mountain = self._is_mountain_terrain(target_prov)

        if (is_river and not river_immune) or (is_mountain and not terrain_immune):
            return -1
        return 0

    def _find_path_cost_ignore_mountain(self, start_id: int, target_id: int) -> int:
        """计算移动消耗：忽略山地额外消耗，但保留基础步耗和跨河消耗。"""
        if start_id == target_id:
            return 0

        import heapq

        queue = [(0, start_id)]
        min_costs = {start_id: 0}

        while queue:
            curr_total, curr_id = heapq.heappop(queue)

            if curr_total > min_costs.get(curr_id, float("inf")):
                continue

            if curr_id == target_id:
                return curr_total

            for next_id in self.map_manager._adjacency.get(curr_id, []):
                step_cost = 1
                if self._is_river_crossing(curr_id, next_id):
                    step_cost += 1

                new_total = curr_total + step_cost
                if new_total < min_costs.get(next_id, float("inf")):
                    min_costs[next_id] = new_total
                    heapq.heappush(queue, (new_total, next_id))

        return 9999

    def _try_apply_gexu_guard(
        self, province: object, units: List[UnitState], pre_hp_map: Dict[int, int]
    ) -> bool:
        """割须弃袍：若防御最高单位在本次战斗受伤，则免除其1点伤害（一次性）。"""
        effect = self.card_effect_manager.get_effect(str(province.province_id))
        if not effect or not effect.gexu_guard or not units:
            return False

        highest_def_unit = max(
            units,
            key=lambda u: self._calculate_unit_powers(u, province.province_id)[1],
        )

        before_hp = pre_hp_map.get(id(highest_def_unit), highest_def_unit.hp)
        if highest_def_unit.hp < before_hp:
            highest_def_unit.hp += 1
            self.card_effect_manager.remove_effect(str(province.province_id))
            return True

        return False

    def _has_attackable_target_for_unit(self, province: object, unit_state) -> bool:
        """判断某单位在当前位置是否存在可攻击目标。"""
        definition = self.unit_repository.get_definition(unit_state.unit_type)
        unit_stride = SQRT3 * self.hex_side
        allowed_range_px = definition.range * unit_stride * 1.1

        p_center = (
            province.center_cache
            if province.center_cache
            else province.compute_center(self.hex_side)
        )

        for target in self.map_manager.provinces:
            if target.country == self.player_country:
                continue
            if not target.units and not self._is_fort_or_city(target):
                continue

            t_center = (
                target.center_cache
                if target.center_cache
                else target.compute_center(self.hex_side)
            )
            if dist(p_center, t_center) <= allowed_range_px:
                return True

        return False

    def _get_base_unit_type(self, unit_type: str) -> str:
        """提取兵种的基础类型 (infantry/cavalry/archer)"""
        unit_lower = unit_type.lower()
        if "infantry" in unit_lower:
            return "infantry"
        if "cavalry" in unit_lower:
            return "cavalry"
        if "archer" in unit_lower:
            return "archer"
        return ""

    def _get_target_selection_key(self, unit_state) -> Tuple[int, int]:
        """计算单位的目标选择优先级 (用于伤害和混乱分配)
        返回: (是否受伤, 防御力)
        优先级: 未受伤 > 已受伤, 低防御 > 高防御
        """
        is_inj = 1 if unit_state.is_injured else 0
        defense = self.unit_repository.get_definition(unit_state.unit_type).defense
        return (is_inj, defense)

    def _get_unit_relationship(self, attacker_type: str, defender_type: str) -> int:
        """
        判断兵种克制关系。
        克制规则：
        - 步兵 (infantry) 克制 弓兵 (archer)
        - 弓兵 (archer) 克制 骑兵 (cavalry)
        - 骑兵 (cavalry) 克制 步兵 (infantry)

        返回: 1=克制, -1=被克制, 0=中立
        """
        a_base = self._get_base_unit_type(attacker_type)
        d_base = self._get_base_unit_type(defender_type)

        if not a_base or not d_base:
            return 0

        # 步(infantry) > 弓(archer) > 骑(cavalry) > 步(infantry)
        if a_base == "infantry":
            if d_base == "archer":
                return 1
            if d_base == "cavalry":
                return -1
        elif a_base == "archer":
            if d_base == "cavalry":
                return 1
            if d_base == "infantry":
                return -1
        elif a_base == "cavalry":
            if d_base == "infantry":
                return 1
            if d_base == "archer":
                return -1

        return 0

    def _handle_combat(self, target: object) -> None:  # target: Province
        """处理战斗逻辑"""
        if self.pending_post_move_attack and self.pending_attacker:
            if (
                len(self.selected_units) != 1
                or self.selected_units[0] != self.pending_attacker
            ):
                self.info_panel.show_message("当前仅可由移动后的单位发起攻击")
                return

        unit_stride = SQRT3 * self.hex_side
        total_attack = 0.0

        participating_attackers = []  # List[(province, unit_state)]

        # 为了计算方便，预先获取防御方的类型列表
        defender_types = [u.unit_type for u in target.units]

        # 1. 检查所有攻击者的射程并计算攻击力
        for pid, idx in self.selected_units:
            province = self.map_manager.get_by_id(pid)
            if not province:
                continue

            unit_state = province.units[idx]
            definition = self.unit_repository.get_definition(unit_state.unit_type)

            p_center = (
                province.center_cache
                if province.center_cache
                else province.compute_center(self.hex_side)
            )
            t_center = (
                target.center_cache
                if target.center_cache
                else target.compute_center(self.hex_side)
            )

            current_distance = dist(p_center, t_center)
            allowed_range_px = definition.range * unit_stride * 1.1

            if current_distance > allowed_range_px:
                self.clear_selection(clear_ui=False)
                self.info_panel.show_message(
                    f"距离不足:{definition.range}", duration=2.0
                )
                return

            # 行动力检查
            if unit_state.mp < 1:
                self.clear_selection(clear_ui=False)
                self.info_panel.show_message("行动力不足")
                return

            atk, _ = self._calculate_unit_powers(unit_state, province.province_id)
            atk += self._get_attack_terrain_penalty(province, target, unit_state)
            atk = max(0, atk)

            # --- 兵种克制计算 ---
            # 规则：步兵克弓兵，弓兵克骑兵，骑兵克步兵
            # 加成：克制+COUNTER_BONUS，被克制-COUNTER_BONUS
            bonus = 0.0
            has_adv = False
            has_dis = False

            for d_type in defender_types:
                rel = self._get_unit_relationship(unit_state.unit_type, d_type)
                if rel == 1:
                    has_adv = True
                if rel == -1:
                    has_dis = True

            if has_adv:
                bonus += COUNTER_BONUS
            if has_dis:
                bonus -= COUNTER_BONUS

            total_attack += atk + bonus
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
        if target.units:
            for u in target.units:
                _, dfs = self._calculate_unit_powers(u, target.province_id)
                total_defense += dfs
        elif self._is_fort_or_city(target):
            # 关隘/城市空城守备：默认有防御力2
            total_defense = 2.0

        if total_defense <= 0.1:
            total_defense = 0.1  # 防止除零

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
        target_center = (
            target.center_cache
            if target.center_cache
            else target.compute_center(self.hex_side)
        )
        neighbor_threshold = unit_stride * 1.1

        for p_id in attacker_provinces:
            prov = self.map_manager.get_by_id(p_id)
            if not prov:
                continue

            p_center = (
                prov.center_cache
                if prov.center_cache
                else prov.compute_center(self.hex_side)
            )
            d = dist(p_center, target_center)
            if d < neighbor_threshold:
                neighbor_count += 1

        is_flanked = neighbor_count >= 2

        # 4. 计算 CRT 列
        col_index = get_ratio_column(total_attack, total_defense, is_flanked)

        # 关隘/城市受攻：判定向防守方有利方向移动一列
        if self._is_fort_or_city(target):
            col_index = max(0, col_index - 1)

        # 应用卡牌效果修饰
        # 威震华夏：如果已激活且目标格子旁有河流，判定列向利于进攻方移动一列
        if self.card_effect_manager.is_offensive_card_active(
            "card_zhenjing_huaxia_shu"
        ):
            if self._province_has_river_neighbor(target.province_id):
                col_index = min(5, col_index + 1)

        # 火烧连营：如果激活且敌方有多个部队堆叠，判定列向利于进攻方移动一列
        if self.card_effect_manager.is_offensive_card_active("card_huoshao_lianying"):
            if len(target.units) > 1:
                col_index = min(5, col_index + 1)

        ratio_val = total_attack / total_defense

        # 5. 准备投骰子
        # 生成进攻方预览信息
        atk_lines = []
        for prov, u_state in participating_attackers:
            atk_lines.append(
                self._format_unit_info(
                    u_state, prefix="攻", province_id=prov.province_id
                )
            )
        attacker_info = "\n".join(atk_lines)

        # 生成防守方预览信息
        def_lines = []
        if target.units:
            for u in target.units:
                def_lines.append(
                    self._format_unit_info(
                        u, prefix="防", province_id=target.province_id
                    )
                )
        elif self._is_fort_or_city(target):
            def_lines.append("守备：防御2（空城）")
        defender_info = "\n".join(def_lines)

        # 设置战斗 UI 状态
        self.show_combat_ui = True
        self.combat_target = target  # 设置当前目标 (Province对象)

        # 防守方决策选项（在投骰前可切换）
        wei_manager = self.card_managers.get("WEI")
        self.defender_can_use_jiangdong = (
            target.country == "WEI"
            and wei_manager is not None
            and not wei_manager.is_card_used("card_jiangdong_zhiti")
        )
        self.defender_use_jiangdong = False
        # 仅在进攻方点击投骰后，才进入江东止啼选择阶段
        self.defender_jiangdong_decided = not self.defender_can_use_jiangdong
        self.waiting_defender_response = False

        # 战斗预览阶段维持进攻方卡牌显示；投骰后再切到防守方江东止啼选择
        self.allow_jiangdong_selection = False
        if self.player_country and self.player_country in self.card_managers:
            self.card_manager = self.card_managers[self.player_country]
            self._update_card_panel()

        self.defender_can_hold_position = self._is_fort_or_city(target) and bool(
            target.units
        )
        self.defender_hold_decided = not self.defender_can_hold_position
        self.defender_use_hold_position = False

        # 既然开始了新的战斗准备，就清空上一轮的战果显示
        self.combat_result_title = None
        self.combat_result_timer = 0

        self.combat_ratio_val = ratio_val
        # 使用lambda包装，确保每次点击投鞒子时重新计算攻防比
        self.combat_callback = lambda: self._execute_combat(
            participating_attackers, target
        )

        # 面板只显示详情
        self.info_panel.show_combat_details(attacker_info, defender_info)

        # 若防守方是 AI 国家，立即做出所有防守决策（不使用任何防守卡牌）
        if self.human_country is not None and target.country != self.human_country:
            self.defender_jiangdong_decided = True
            self.defender_use_jiangdong = False
            self.defender_hold_decided = True
            self.defender_use_hold_position = False

    def _execute_combat(self, attackers: List, target_province: object) -> None:
        """执行战斗，每次点击投鞒子时重新计算攻防比"""
        # 重新计算攻击力
        total_attack = 0.0
        for prov, u_state in attackers:
            atk, _ = self._calculate_unit_powers(u_state, prov.province_id)
            atk += self._get_attack_terrain_penalty(prov, target_province, u_state)
            atk = max(0, atk)

            # 重新计算克制加成
            bonus = 0.0
            has_adv = False
            has_dis = False

            defender_types = [u.unit_type for u in target_province.units]
            for d_type in defender_types:
                rel = self._get_unit_relationship(u_state.unit_type, d_type)
                if rel == 1:
                    has_adv = True
                if rel == -1:
                    has_dis = True

            if has_adv:
                bonus += COUNTER_BONUS
            if has_dis:
                bonus -= COUNTER_BONUS

            total_attack += atk + bonus

        # 重新计算防御力
        total_defense = 0.0
        if target_province.units:
            for u in target_province.units:
                _, dfs = self._calculate_unit_powers(u, target_province.province_id)
                total_defense += dfs
        elif self._is_fort_or_city(target_province):
            total_defense = 2.0

        if total_defense <= 0.1:
            total_defense = 0.1

        # 重新计算夹击
        unit_stride = SQRT3 * self.hex_side
        attacker_provinces = {p.province_id for p, _ in attackers}
        neighbor_count = 0
        target_center = (
            target_province.center_cache
            if target_province.center_cache
            else target_province.compute_center(self.hex_side)
        )
        neighbor_threshold = unit_stride * 1.1

        for p_id in attacker_provinces:
            prov = self.map_manager.get_by_id(p_id)
            if not prov:
                continue

            p_center = (
                prov.center_cache
                if prov.center_cache
                else prov.compute_center(self.hex_side)
            )
            d = dist(p_center, target_center)
            if d < neighbor_threshold:
                neighbor_count += 1

        is_flanked = neighbor_count >= 2

        # 计算最新的攻防比列索引
        col_index = get_ratio_column(total_attack, total_defense, is_flanked)

        if self._is_fort_or_city(target_province):
            col_index = max(0, col_index - 1)

        # 威震华夏（在战斗发起前可能已全局激活）：若已激活且目标格子旁有河流，判定向进攻方有利移动一列
        if self.card_effect_manager.is_offensive_card_active(
            "card_zhenjing_huaxia_shu"
        ):
            if self._province_has_river_neighbor(target_province.province_id):
                col_index = min(5, col_index + 1)

        # 调用原有的战斗解决逻辑
        self._resolve_combat(col_index, attackers, target_province)

    def _resolve_combat(
        self, col_index: int, attackers: List, target_province: object
    ) -> None:
        """投骰子后的回调"""
        # 先缓存防守方决策，避免 clear_selection 清理战斗预览时重置状态
        use_jiangdong = self.defender_use_jiangdong
        use_hold_position = self.defender_use_hold_position

        # 战斗开始结算，立刻清除选中状态，防止后续操作引用到已死亡或移动的单位
        self.clear_selection(clear_ui=False)

        # 记录战斗前的防守方列表（引用），以便战后统计（其中单位的属性会被修改）
        # target_province.units 之后会被清理移除死亡单位，所以由于我们要显示战损，需要先存一份
        defenders_snapshot = list(target_province.units)
        has_garrison_only = (not target_province.units) and self._is_fort_or_city(
            target_province
        )

        # 投掷骰子
        raw_dice = random.randint(1, 6)
        dice = raw_dice

        # 检查进攻/防守双方格子效果（骰点加成）
        attacker_dice_bonus = 0
        for prov, _ in attackers:
            effect = self.card_effect_manager.get_effect(str(prov.province_id))
            if effect and effect.dice_bonus > 0:
                attacker_dice_bonus = max(attacker_dice_bonus, effect.dice_bonus)
        for _, u in attackers:
            attacker_dice_bonus = max(
                attacker_dice_bonus, getattr(u, "temp_dice_bonus", 0)
            )

        defender_dice_bonus = 0
        target_effect = self.card_effect_manager.get_effect(
            str(target_province.province_id)
        )
        if target_effect and target_effect.dice_bonus > 0:
            defender_dice_bonus = target_effect.dice_bonus
        for u in target_province.units:
            defender_dice_bonus = max(
                defender_dice_bonus, getattr(u, "temp_dice_bonus", 0)
            )

        # 江东止啼：防守方即时选择"使用"后生效（一次性），进攻方骰点-2
        if use_jiangdong and target_province.country == "WEI":
            attacker_dice_bonus -= 2

        dice = max(1, min(6, raw_dice + attacker_dice_bonus + defender_dice_bonus))
        logger.debug(
            "DICE: raw=%d atk_bonus=%d def_bonus=%d use_jd=%s => final=%d | atk_units=%s",
            raw_dice,
            attacker_dice_bonus,
            defender_dice_bonus,
            use_jiangdong,
            dice,
            [(u.unit_type, getattr(u, "temp_dice_bonus", 0)) for _, u in attackers],
        )

        result_code = resolve_combat(dice, col_index)

        # 解析结果并应用伤害
        import re

        # 伤害统计
        dmg_attacker = 0
        dmg_defender = 0
        confused_defender = False
        retreat_defender = False

        if "A2" in result_code:
            dmg_attacker = 2
        elif "A1" in result_code:
            dmg_attacker = 1

        if "D1" in result_code:
            dmg_defender = 1

        if "AG" in result_code:
            self._apply_confusion(attackers)

        if "DG" in result_code:
            if target_province.units:
                self._apply_confusion([(None, u) for u in target_province.units])
            confused_defender = True

        if (
            "DR" in result_code or "R" in result_code and "D" in result_code
        ):  # D1R or DR
            retreat_defender = True

        # 记录受伤前血量（用于割须弃袍免伤判定）
        pre_def_hp = {id(u): u.hp for u in target_province.units}
        attacker_groups: Dict[int, List[UnitState]] = {}
        for prov, unit in attackers:
            attacker_groups.setdefault(prov.province_id, []).append(unit)
        pre_atk_hp_by_prov = {
            pid: {id(u): u.hp for u in units} for pid, units in attacker_groups.items()
        }

        # Apply Damage
        if dmg_attacker > 0:
            self._apply_damage([u for _, u in attackers], dmg_attacker)

        if dmg_defender > 0 and target_province.units:
            self._apply_damage(target_province.units, dmg_defender)

        # 割须弃袍：免除防御最高单位一次伤害（一次性）
        self._try_apply_gexu_guard(target_province, target_province.units, pre_def_hp)
        for pid, units in attacker_groups.items():
            prov = self.map_manager.get_by_id(pid)
            if prov:
                self._try_apply_gexu_guard(prov, units, pre_atk_hp_by_prov.get(pid, {}))

        # Retreat Logic
        if retreat_defender:
            # 关隘/城市受攻时：防守方可选择 D1DG 代替 DR
            if (
                self._is_fort_or_city(target_province)
                and target_province.units
                and use_hold_position
            ):
                for defender in target_province.units:
                    defender.is_confused = True
                    defender.confusion_count = max(1, defender.confusion_count)
                    defender.hp -= 1
                retreat_defender = False
                confused_defender = True
                result_code = result_code.replace("DR", "D1DG")
            elif not has_garrison_only:
                self._handle_retreat(target_province)
            else:
                # 空城守备没有可撤退实体
                retreat_defender = False

        # 疲劳判定 & 消耗行动力
        for _, u in attackers:
            u.mp -= 1  # 消耗1点行动力 (必须先于疲劳判定?)
            u.attack_count += 1
            if u.attack_count >= 2:
                u.is_confused = True

        # 战斗后清理
        self._cleanup_dead_units(attackers, target_province)

        # 进占逻辑
        can_occupy = not target_province.units
        # 关隘/城市空城守备：只有打出 DR 或 DG 才视为成功占领
        if has_garrison_only:
            can_occupy = ("DR" in result_code) or ("DG" in result_code)

        if can_occupy:
            self._advance_after_combat(attackers, target_province)

        # --- 生成详细战报 ---

        # 1. 战果标题: 比值·骰点·结果
        ratio_strs = ["1:2", "1:1", "2:1", "3:1", "4:1", "5:1"]
        # col_index 可能会稍越界（比如夹击后），限制一下查找
        r_idx = max(0, min(5, col_index))
        ratio_str = ratio_strs[r_idx]

        # 结果标题行： 1:1 · 骰6 · A1（有加成时显示 骰原→实际）
        bonus_total = attacker_dice_bonus + defender_dice_bonus
        if bonus_total != 0:
            sign = "+" if bonus_total > 0 else ""
            dice_str = f"骰{raw_dice}{sign}{bonus_total}={dice}"
        else:
            dice_str = f"骰{dice}"
        title_line = " · ".join([ratio_str, dice_str, result_code])

        # 结果简报行： 攻损X · 防损Y
        summary_parts = [f"攻损{dmg_attacker}", f"防损{dmg_defender}"]
        summary_line = " · ".join(summary_parts)

        status_msgs = []
        if confused_defender:
            status_msgs.append("防乱")
        if retreat_defender:
            status_msgs.append("防退")
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
        for prov, u_state in attackers:
            logs.append(
                self._format_unit_info(
                    u_state, prefix="攻", province_id=prov.province_id
                )
            )

        # 3. 防守方战后状态
        # 使用 defenders_snapshot 确保显示所有参与战斗的单位（包括死亡的）
        if defenders_snapshot:
            logs.append("--- 防守方 ---")
            for u_state in defenders_snapshot:
                logs.append(
                    self._format_unit_info(
                        u_state, prefix="防", province_id=target_province.province_id
                    )
                )
        elif has_garrison_only:
            logs.append("--- 防守方 ---")
            logs.append("守备：防御2（空城）")
        else:
            logs.append("防守方全灭或撤离")

        # 3. 显示结果 (Top UI) + 详情 (InfoPanel)
        self.combat_result_title = full_title_str
        self.combat_result_timer = -1  # <0 表示不自动消失

        # 不再让 Panel 显示标题
        self.info_panel.show_combat_result(None, None, "\n".join(logs))

        # 战斗动作完成后自动切换到下一国家
        action_name = "移动后攻击" if self.pending_post_move_attack else "攻击"
        self._finish_country_action(action_name, keep_info_message=True)

    def _apply_damage(self, units: List[UnitState], amount: int) -> None:
        """分配伤害"""
        # 机制：
        # 1. 数字表示受到伤害的单位数 (即造成amount次单体伤害)
        # 2. 受到一次伤害就少一点血量
        # 3. 优先级：优先选取未受过伤的 -> 如果都未受过伤，按照防御值由低到高 -> 如果都一样，随便选

        for _ in range(amount):
            # 每一轮伤害都重新寻找最佳目标 (因为上一轮伤害可能改变了状态，比如从未伤变成了伤)
            living_units = [u for u in units if u.hp > 0]
            if not living_units:
                break

            candidates = sorted(living_units, key=self._get_target_selection_key)
            target = candidates[0]
            target.hp -= 1

    def _apply_confusion(self, unit_tuples: List, amount: int = 1) -> None:
        """应用混乱"""
        # 机制与伤害相同 (选取规则)
        units = [u for _, u in unit_tuples]

        for _ in range(amount):
            living_units = [u for u in units if u.hp > 0]
            if not living_units:
                break

            candidates = sorted(living_units, key=self._get_target_selection_key)
            target = candidates[0]

            if target.is_confused:
                # 已经处于混乱状态，连续混乱则减少一点血量，但仍保持混乱状态
                target.confusion_count += 1
                target.hp -= 1
                # 保持混乱状态
                target.is_confused = True
            else:
                # 首次进入混乱状态
                target.is_confused = True
                target.confusion_count = 1

    def _handle_retreat(self, province: object) -> None:
        """处理撤退"""
        # 撤退有1点行动力，可以自由选择撤退到1点行动力能到的地方。
        # 这里自动选择一个合法格子撤退 (简化为自动，非玩家手动操作撤退，因为战斗是瞬间结算的)

        # 1. 获取所有邻居
        # 2. 过滤：行动力为1能到的地方 (在网格寻路下，如果是山地且Cost=2，则1MP到不了)
        # 3. 同时也必须是友方或空格子

        if not province.units:
            return

        start_id = province.province_id
        valid_destinations = []

        # 获取逻辑邻居 (通过Graph)
        neighbor_ids = self.map_manager._adjacency.get(start_id, [])

        for nid in neighbor_ids:
            dest_prov = self.map_manager.get_by_id(nid)
            if not dest_prov:
                continue

            # 检查归属: 友方或无人地
            if dest_prov.country and dest_prov.country != province.country:
                continue

            # 堆叠限制
            if len(dest_prov.units) + len(province.units) > MAX_UNIT_STACK:
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
            # 随机选一个撤退目的地
            dest = random.choice(valid_destinations)
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
            if movers >= limit:
                break
            if unit.hp > 0 and unit in prov.units:  # 确保还在原格子里（有的可能死了）
                prov.units.remove(unit)
                target.units.append(unit)
                # 占领变更
                target.country = self.player_country
                movers += 1

        if movers > 0:
            self.map_manager.invalidate_cache()

    def _get_neighbors(self, unit_prov: object) -> List[object]:
        """获取邻居"""
        return self.map_manager.get_neighbors(unit_prov.province_id)

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
            center = (
                province.center_cache
                if province.center_cache
                else province.compute_center(self.hex_side)
            )
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
            self.combat_result_timer -= 1.0 / self.settings.fps
            if self.combat_result_timer < 0:
                self.combat_result_timer = 0
                self.combat_result_title = None

        # 处理 AI 行动计时器
        if (
            self._ai_turn_timer is not None
            and pg.time.get_ticks() >= self._ai_turn_timer
        ):
            self._ai_turn_timer = None
            self._run_ai_turn()

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
            pg.draw.circle(
                self.window,
                button["color"],
                button["center"],
                self.faction_button_radius,
            )
            self.window.blit(button["label_surface"], button["label_pos"])

    def _render_gameplay(self) -> None:
        """画游戏主战场"""
        self.window.fill(pg.Color("white"))

        # 1. 画地图底层（格子+地形）
        self.map_manager.draw(self.window)

        # 2. 画所有兵种单位
        for province in self.map_manager.provinces:
            center = (
                province.center_cache
                if province.center_cache
                else province.compute_center(self.hex_side)
            )
            self.unit_renderer.draw_units(self.window, center, province.units)

        # 2.5 画当前战斗目标的金色描边 Hex Outline
        if self.combat_target:
            # 安全获取 Province 对象
            target_prov = self.combat_target
            # 计算中心点
            c = (
                target_prov.center_cache
                if target_prov.center_cache
                else target_prov.compute_center(self.hex_side)
            )
            # 计算六边形顶点
            vertices = hex_vertices(c, self.hex_side)

            # 使用金色画笔画线，宽度为4
            pg.draw.lines(self.window, pg.Color("gold"), True, vertices, 4)

        # 3. 画河流和阻挡线
        # 河流使用双层绘制：先画所有深蓝色描边，再画所有浅蓝色河流
        river_light_blue = pg.Color(173, 216, 230)  # 浅蓝色
        river_dark_blue = pg.Color(30, 80, 120)  # 深蓝色描边

        # 第一步：画所有河流的深蓝色描边
        for polyline in self.yangtze_polylines:
            self._draw_smooth_polyline(river_dark_blue, polyline, 28)  # 深蓝色描边
        self._draw_smooth_polyline(river_dark_blue, self.yellow_river_polyline, 28)

        # 第二步：画所有河流的浅蓝色主体
        for polyline in self.yangtze_polylines:
            self._draw_smooth_polyline(river_light_blue, polyline, 20)  # 浅蓝色河流
        self._draw_smooth_polyline(river_light_blue, self.yellow_river_polyline, 20)

        # 画阻挡线：双层绘制，先画黑色描边，再画紫色主体
        self._draw_smooth_polyline(
            pg.Color("black"), self.ban_line_polyline, 28
        )  # 黑色描边
        self._draw_smooth_polyline(
            pg.Color(120, 0, 120), self.ban_line_polyline, 20
        )  # 紫色主体

        # 3.5 画功能按钮
        for btn in getattr(self, "control_btns", []):
            # 简单的悬停效果
            color = btn["bg_color"]
            if btn["rect"].collidepoint(pg.mouse.get_pos()):
                color = pg.Color("#666666")  # Lighter gray

            pg.draw.rect(self.window, color, btn["rect"], border_radius=5)
            pg.draw.rect(
                self.window, btn["border_color"], btn["rect"], 2, border_radius=5
            )
            self.window.blit(btn["surface"], btn["text_pos"])

        # 4. 右下角显示回合信息（避开功能按钮）
        country_label = (
            self.country_labels.get(self.player_country, "")
            if self.player_country
            else ""
        )
        round_text = f"回合 {self.major_round}-{self.minor_round}"
        if country_label:
            round_text = f"{round_text} · {country_label}"
        round_surf = self.round_counter_font.render(round_text, True, pg.Color("black"))

        # 默认贴右下角
        round_rect = round_surf.get_rect(
            bottomright=(self.screen_width - 20, self.screen_height - 12)
        )

        # 若与右下角按钮重叠，则上移到按钮上方
        control_rects = [btn["rect"] for btn in getattr(self, "control_btns", [])]
        if control_rects and any(round_rect.colliderect(r) for r in control_rects):
            top_y = min(r.top for r in control_rects)
            round_rect.bottom = max(20, top_y - 8)

        # 轻微底衬，提高可读性
        bg_rect = round_rect.inflate(12, 6)
        pg.draw.rect(
            self.window, pg.Color(255, 255, 255, 180), bg_rect, border_radius=6
        )
        self.window.blit(round_surf, round_rect)

        # 4.5 常态显示三国“民心/政治点数”
        self._draw_country_stats_overlay()

        # 5. 画当前玩家国家标签
        if self.player_country:
            tag_surface = self.country_tag_surfaces[self.player_country]
            self.window.blit(tag_surface, self.country_tag_pos)

            # --- 画战斗UI (攻防比 + 投骰子) ---
            if self.show_combat_ui:
                # 使用跟 InfoPanel 一样的字体
                font = self.combat_ui_font

                # 先清空防守按钮矩形，按可用性重建
                self.defense_jiangdong_btn_rect = None
                self.defense_jiangdong_skip_btn_rect = None
                self.defense_hold_btn_rect = None
                self.defense_hold_skip_btn_rect = None

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
                    btn_color = pg.Color("#4169E1")  # RoyalBlue (Lighter than Blue)

                # 画按钮背景
                pg.draw.rect(
                    self.window, btn_color, self.combat_btn_rect, border_radius=5
                )
                # 画文字
                text_rect = btn_surf.get_rect(center=self.combat_btn_rect.center)
                self.window.blit(btn_surf, text_rect)

                # 2. 攻防比文字
                ratio_str = f"攻防比 {self.combat_ratio_val:.1f}"
                ratio_surf = font.render(ratio_str, True, pg.Color("black"))

                ratio_x = btn_x - ratio_surf.get_width() - 30
                ratio_y = btn_y + (btn_h - ratio_surf.get_height()) // 2

                self.window.blit(ratio_surf, (ratio_x, ratio_y))

                # 3. 防守方决策按钮（样式参考投骰子按钮）
                option_right_x = ratio_x - 20
                row_gap = 8
                show_hold = (
                    self.waiting_defender_response
                    and self.defender_can_hold_position
                    and not self.defender_hold_decided
                )

                if show_hold:
                    title = "防守方即时决策"
                    title_surf = font.render(title, True, pg.Color("black"))
                    title_y = btn_y - title_surf.get_height() - 6
                    self.window.blit(
                        title_surf,
                        (option_right_x - title_surf.get_width(), title_y),
                    )

                next_col_right = option_right_x

                # 列2：DR改D1DG（上下两行、统一宽度）
                if show_hold:
                    hold_yes_txt = "防守方选择：DR改D1DG"
                    hold_no_txt = "保持正常DR"
                    hold_yes_surf = font.render(hold_yes_txt, True, pg.Color("white"))
                    hold_no_surf = font.render(hold_no_txt, True, pg.Color("white"))
                    hold_col_w = (
                        max(hold_yes_surf.get_width(), hold_no_surf.get_width()) + 20
                    )

                    hold_yes_rect = pg.Rect(
                        next_col_right - hold_col_w, btn_y, hold_col_w, btn_h
                    )
                    hold_no_rect = pg.Rect(
                        next_col_right - hold_col_w,
                        btn_y + btn_h + row_gap,
                        hold_col_w,
                        btn_h,
                    )
                    self.defense_hold_btn_rect = hold_yes_rect
                    self.defense_hold_skip_btn_rect = hold_no_rect

                    hold_yes_color = pg.Color("#8B0000")
                    if hold_yes_rect.collidepoint(pg.mouse.get_pos()):
                        hold_yes_color = pg.Color("#A52A2A")
                    hold_no_color = pg.Color("#4B4B4B")
                    if hold_no_rect.collidepoint(pg.mouse.get_pos()):
                        hold_no_color = pg.Color("#666666")

                    pg.draw.rect(
                        self.window, hold_yes_color, hold_yes_rect, border_radius=5
                    )
                    pg.draw.rect(
                        self.window, hold_no_color, hold_no_rect, border_radius=5
                    )
                    self.window.blit(
                        hold_yes_surf,
                        hold_yes_surf.get_rect(center=hold_yes_rect.center),
                    )
                    self.window.blit(
                        hold_no_surf, hold_no_surf.get_rect(center=hold_no_rect.center)
                    )

            # --- 检查是否需要显示“解除混乱”按钮 ---
            # 条件：1. 没有进入战斗准备 (show_combat_ui is False)
            #      2. 选中的单位中，【恰好】只有一个单位处于混乱状态
            #      3. (隐含) combat_target 为 None (show_combat_ui False 已经涵盖了大部分情况，双重保险)
            else:
                self.recover_btn_rect = None  # Reset
                self.no_attack_btn_rect = None

                # 移动后攻击选择窗口：显示“不攻击”按钮
                if self.pending_post_move_attack and self.pending_attacker:
                    btn_surf = self._no_attack_btn_surf
                    btn_w = btn_surf.get_width() + 22
                    btn_h = btn_surf.get_height() + 10

                    top_area_height = int(self.screen_height * 0.15)
                    tag_x = self.country_tag_pos[0]
                    btn_x = tag_x - btn_w - 30
                    btn_y = (top_area_height - btn_h) // 2

                    self.no_attack_btn_rect = pg.Rect(btn_x, btn_y, btn_w, btn_h)

                    btn_color = pg.Color("#555555")
                    if self.no_attack_btn_rect.collidepoint(pg.mouse.get_pos()):
                        btn_color = pg.Color("#6f6f6f")

                    pg.draw.rect(
                        self.window, btn_color, self.no_attack_btn_rect, border_radius=5
                    )
                    text_rect = btn_surf.get_rect(center=self.no_attack_btn_rect.center)
                    self.window.blit(btn_surf, text_rect)

                # 正常情况下才绘制“解除混乱”按钮
                confused_list = []
                if not self.pending_post_move_attack:
                    for pid, slot in self.selected_units:
                        prov = self.map_manager.get_by_id(pid)
                        if prov and slot < len(prov.units):
                            u = prov.units[slot]
                            if u.is_confused:
                                confused_list.append(u)

                if (not self.pending_post_move_attack) and len(confused_list) == 1:
                    # 绘制解除混乱按钮
                    btn_surf = self._recover_btn_surf

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
                        btn_color = pg.Color("#BA55D3")  # MediumOrchid (Lighter Purple)

                    # 按照要求，按钮颜色为紫色
                    pg.draw.rect(
                        self.window, btn_color, self.recover_btn_rect, border_radius=5
                    )

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
                total_text_h = (
                    len(lines) * line_height + (len(lines) - 1) * 5
                )  # 5px 行间距

                start_y = (top_area_height - total_text_h) // 2

                for line_idx, line in enumerate(lines):
                    # 对每一行执行之前的“从右向左渲染”逻辑
                    parts = line.split(" · ")

                    # 当前行的 Y 坐标
                    current_y_center = (
                        start_y + line_idx * (line_height + 5) + line_height // 2
                    )

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
                            self.window.blit(
                                sep_surf, (current_right_x - sep_sw, sep_y)
                            )

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

        # 8. 绘制卡牌面板（卡牌不占用回合动作次数）
        self.skip_jiangdong_card_btn_rect = None
        if self.card_panel:
            self.card_panel.draw(self.window)

            # 江东止啼“不使用”按钮：放在卡牌区域（叠加在江东止啼卡牌位置）
            show_jiangdong_skip = (
                self.show_combat_ui
                and self.waiting_defender_response
                and self.defender_can_use_jiangdong
                and not self.defender_jiangdong_decided
            )
            if show_jiangdong_skip:
                jd_rect = self.card_panel.card_rects.get("card_jiangdong_zhiti")
                if jd_rect:
                    overlay_h = max(20, int(jd_rect.height * 0.33))
                    btn_rect = pg.Rect(
                        jd_rect.left + 4,
                        jd_rect.bottom - overlay_h - 4,
                        jd_rect.width - 8,
                        overlay_h,
                    )
                    self.skip_jiangdong_card_btn_rect = btn_rect

                    btn_color = pg.Color("#4B4B4B")
                    if btn_rect.collidepoint(pg.mouse.get_pos()):
                        btn_color = pg.Color("#666666")

                    pg.draw.rect(self.window, btn_color, btn_rect, border_radius=6)
                    skip_surf = self.tooltip_font.render(
                        "不使用江东止啼", True, pg.Color("white")
                    )
                    self.window.blit(
                        skip_surf, skip_surf.get_rect(center=btn_rect.center)
                    )

            # 卡牌 tooltip 始终在卡牌面板最顶层绘制（不受江东止啼条件限制）
            self.card_panel.draw_tooltip(self.window)

        # 9. 画鼠标悬停提示 (Tooltip)
        self._draw_hover_tooltip()

    def _get_map_bounds_rect(self) -> pg.Rect:
        """基于六边形中心与边长，计算地图像素包围盒。"""
        if not self.map_manager.provinces:
            return pg.Rect(0, 0, self.screen_width, self.screen_height)

        x_min = float("inf")
        y_min = float("inf")
        x_max = float("-inf")
        y_max = float("-inf")

        half_h = (SQRT3 * self.hex_side) / 2
        for province in self.map_manager.provinces:
            center = (
                province.center_cache
                if province.center_cache
                else province.compute_center(self.hex_side)
            )
            cx, cy = center
            x_min = min(x_min, cx - self.hex_side)
            x_max = max(x_max, cx + self.hex_side)
            y_min = min(y_min, cy - half_h)
            y_max = max(y_max, cy + half_h)

        left = max(0, int(x_min))
        top = max(0, int(y_min))
        right = min(self.screen_width, int(x_max))
        bottom = min(self.screen_height, int(y_max))
        return pg.Rect(left, top, max(1, right - left), max(1, bottom - top))

    def _draw_country_stats_overlay(self) -> None:
        """绘制三国民心/政治点数信息，避免与地图六边形重叠。"""
        map_rect = self._get_map_bounds_rect()
        title_font = self.country_stat_title_font
        body_font = self.country_stat_font
        self.country_stat_choice_btns = {}

        # 先计算统一面板尺寸
        content_specs = {}
        panel_w = 0
        panel_h = 0
        for country in self.turn_order:
            stats = self.country_stats.get(country, {})
            lines = [
                self.country_labels.get(country, country),
                f"民心点数：{stats.get('people_support', 0)}",
                f"政治点数：{stats.get('political_points', 0)}",
            ]
            title_surf = title_font.render(lines[0], True, pg.Color("black"))
            line1_surf = body_font.render(lines[1], True, pg.Color("black"))
            line2_surf = body_font.render(lines[2], True, pg.Color("black"))
            content_specs[country] = (title_surf, line1_surf, line2_surf)

            local_w = max(
                title_surf.get_width(), line1_surf.get_width(), line2_surf.get_width()
            )
            panel_w = max(panel_w, local_w + 22)
            local_h = (
                title_surf.get_height()
                + line1_surf.get_height()
                + line2_surf.get_height()
                + 18
            )
            panel_h = max(panel_h, local_h)

        # 左侧基准位（用于蜀、魏）
        left_x = max(10, map_rect.left - panel_w - 16)

        # 魏：左上缺口，但整体下移一些
        wei_x = left_x
        wei_y = max(
            10,
            min(self.screen_height - panel_h - 10, map_rect.top + int(panel_h * 0.45)),
        )

        # 蜀：地图左侧中部
        shu_x = left_x
        shu_y = max(
            10, min(self.screen_height - panel_h - 10, map_rect.centery - panel_h // 2)
        )

        control_rects = [btn["rect"] for btn in getattr(self, "control_btns", [])]
        safe_bottom = self.screen_height - 12
        if control_rects:
            safe_bottom = min(safe_bottom, min(r.top for r in control_rects) - 10)

        gap = 8

        # 魏：严格避免和地图六边形区域重叠（优先向下挪）
        wei_rect = pg.Rect(wei_x, wei_y, panel_w, panel_h)
        try_count = 0
        while wei_rect.colliderect(map_rect) and try_count < 20:
            wei_rect.y = min(self.screen_height - panel_h - 10, wei_rect.y + 12)
            try_count += 1
        # 若仍重叠，再尽量向左挪
        try_count = 0
        while wei_rect.colliderect(map_rect) and try_count < 20:
            wei_rect.x = max(10, wei_rect.x - 12)
            try_count += 1

        wei_x, wei_y = wei_rect.x, wei_rect.y

        # 若蜀与魏重叠，则把蜀下移
        if shu_y < wei_y + panel_h + gap:
            shu_y = min(self.screen_height - panel_h - 10, wei_y + panel_h + gap)

        # 吴：向左下挪，且避免与右侧 panel 重叠
        if self.info_panel:
            wu_x = self.info_panel.rect.left - panel_w - 28
        else:
            wu_x = map_rect.right + 14
        wu_x = max(10, min(self.screen_width - panel_w - 10, wu_x))

        # 吴：与屏幕下边缘的间距 = 魏/蜀与屏幕左边缘的间距
        left_margin = min(shu_x, wei_x)
        wu_y = self.screen_height - panel_h - left_margin
        wu_y = max(10, min(self.screen_height - panel_h - 10, wu_y))

        # 避免与魏/蜀重叠（必要时上移，不改变“左移优先”原则）
        wu_min_y = max(wei_y + panel_h + gap, shu_y + panel_h + gap)
        if wu_y < wu_min_y:
            wu_y = min(self.screen_height - panel_h - 10, wu_min_y)

        # 吴：严格避免与右侧面板重叠（InfoPanel / CardPanel）
        blockers: List[pg.Rect] = []
        if self.info_panel:
            blockers.append(self.info_panel.rect)
        if self.card_panel:
            blockers.append(self.card_panel.rect)

        wu_rect = pg.Rect(wu_x, wu_y, panel_w, panel_h)
        try_count = 0
        while (
            blockers
            and any(wu_rect.colliderect(r) for r in blockers)
            and try_count < 30
        ):
            # 用户要求“往左下移”：这里优先继续左移，保持底边距规则
            wu_rect.x = max(10, wu_rect.x - 12)
            try_count += 1

        wu_x, wu_y = wu_rect.x, wu_rect.y

        placements = {
            "SHU": pg.Rect(shu_x, shu_y, panel_w, panel_h),
            "WEI": pg.Rect(wei_x, wei_y, panel_w, panel_h),
            "WU": pg.Rect(wu_x, wu_y, panel_w, panel_h),
        }

        for country in self.turn_order:
            rect = placements[country]
            title_surf, line1_surf, line2_surf = content_specs[country]

            # 不透明浅底 + 国家色边框
            pg.draw.rect(self.window, pg.Color(245, 245, 245), rect, border_radius=8)
            pg.draw.rect(
                self.window,
                self.country_button_colors.get(country, pg.Color("black")),
                rect,
                2,
                border_radius=8,
            )

            x = rect.x + 10
            y = rect.y + 6
            self.window.blit(title_surf, (x, y))

            # 大回合开始加点阶段：用按钮替代属性显示
            if self.major_round_choice_pending:
                if not self.major_round_choice_done.get(country, False):
                    # 按钮尺寸收紧，确保不会超出国家框
                    top_gap = 4
                    bottom_gap = 6
                    row_gap = 4
                    btn_w = rect.width - 16
                    btn_x = rect.x + 8

                    available_h = rect.height - (
                        title_surf.get_height() + top_gap + bottom_gap
                    )
                    btn_h = min(
                        max(18, body_font.get_height() + 4),
                        (available_h - row_gap) // 2,
                    )
                    btn_h = max(16, btn_h)

                    btn1_y = y + title_surf.get_height() + top_gap
                    btn2_y = btn1_y + btn_h + row_gap

                    support_rect = pg.Rect(btn_x, btn1_y, btn_w, btn_h)
                    politics_rect = pg.Rect(btn_x, btn2_y, btn_w, btn_h)

                    support_color = pg.Color("#7a1f1f")
                    if support_rect.collidepoint(pg.mouse.get_pos()):
                        support_color = pg.Color("#9b2a2a")
                    politics_color = pg.Color("#1f4f7a")
                    if politics_rect.collidepoint(pg.mouse.get_pos()):
                        politics_color = pg.Color("#2b6aa2")

                    pg.draw.rect(
                        self.window, support_color, support_rect, border_radius=6
                    )
                    pg.draw.rect(
                        self.window, politics_color, politics_rect, border_radius=6
                    )

                    support_surf = body_font.render(
                        "+2 民心点数", True, pg.Color("white")
                    )
                    politics_surf = body_font.render(
                        "+2 政治点数", True, pg.Color("white")
                    )
                    self.window.blit(
                        support_surf,
                        support_surf.get_rect(center=support_rect.center),
                    )
                    self.window.blit(
                        politics_surf,
                        politics_surf.get_rect(center=politics_rect.center),
                    )

                    self.country_stat_choice_btns[country] = {
                        "support": support_rect,
                        "politics": politics_rect,
                    }
                else:
                    done_surf = body_font.render("已选择", True, pg.Color("black"))
                    done_x = min(
                        rect.right - done_surf.get_width() - 8,
                        x + title_surf.get_width() + 8,
                    )
                    done_y = y + max(
                        0, (title_surf.get_height() - done_surf.get_height()) // 2
                    )
                    self.window.blit(
                        done_surf,
                        (done_x, done_y),
                    )
                    y2 = y + title_surf.get_height() + 4
                    self.window.blit(line1_surf, (x, y2))
                    y2 += line1_surf.get_height() + 2
                    self.window.blit(line2_surf, (x, y2))
            else:
                y += title_surf.get_height() + 4
                self.window.blit(line1_surf, (x, y))
                y += line1_surf.get_height() + 2
                self.window.blit(line2_surf, (x, y))

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
                tooltip_parts.append(
                    (
                        " 跨河移动行动力消耗+1；进攻跨河部队攻击力-1",
                        pg.Color("#555555"),
                        False,
                        False,
                    )
                )

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
                    "Jianye": "建业",
                }

                if (
                    p_name
                    and not p_name.startswith("Tile")
                    and not p_name.startswith("Border")
                ):
                    # 如果在映射表中，显示中文；否则显示原名
                    base_name = city_name_map.get(p_name, p_name)
                else:
                    # 显示地形中文名
                    t_key = (
                        hovered_prov.terrain.lower()
                        if hovered_prov.terrain
                        else "plain"
                    )
                    base_name = self._get_display_name(t_key)

                if base_name:
                    # 城市名加粗变成深金色，并带阴影；其他地形默认黑色无阴影
                    terrain_lower = (hovered_prov.terrain or "").lower()
                    is_city = terrain_lower == "city"
                    is_mountain = terrain_lower in (
                        "hill",
                        "mountain",
                        "hills",
                        "mountains",
                    )
                    if is_city:
                        # 使用更深的金色 (DarkGoldenrod #B8860B 或者是自定义)
                        # 用户觉得 gold (#FFD700) 太浅。尝试 #D4AF37 (Metallic Gold) 或 #C5A000
                        tooltip_parts.append(
                            (base_name, pg.Color("#D4AF37"), True, True)
                        )
                        tooltip_parts.append(
                            (
                                " 进攻此格，攻防比向左移动一列",
                                pg.Color("#555555"),
                                False,
                                False,
                            )
                        )
                    else:
                        tooltip_parts.append(
                            (base_name, pg.Color("black"), False, False)
                        )
                        if is_mountain:
                            tooltip_parts.append(
                                (
                                    " 行动力消耗+1；进攻此格部队攻击力-1",
                                    pg.Color("#555555"),
                                    False,
                                    False,
                                )
                            )

                # 附加国家信息
                if hovered_prov.country:
                    country_cn = self.country_labels.get(
                        hovered_prov.country, hovered_prov.country
                    )
                    # 尝试从 kingdom_repository 获取最准确的颜色
                    c_color = self.kingdom_repository.get_color(hovered_prov.country)
                    if not c_color:
                        # 兜底
                        c_color = self.country_button_colors.get(
                            hovered_prov.country, pg.Color("black")
                        )

                    # 国家名加粗，用对应颜色
                    tooltip_parts.append(
                        (f"({country_cn})", c_color, True, True)
                    )  # 国家名也给个阴影会让颜色更突出

        if tooltip_parts:
            # 检查缓存
            if (
                tooltip_parts == self._last_tooltip_data
                and self._cached_tooltip_surface
            ):
                final_surf = self._cached_tooltip_surface
            else:
                # 计算总宽度和高度
                font_regular = self.tooltip_font
                font_bold = self.tooltip_bold_font

                # 渲染每个部分
                rendered_surfaces = []
                total_w = 0
                max_h = 0

                shadow_offset = (1, 1)
                shadow_color = pg.Color("black")  # 或者深灰

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
                final_surf = pg.Surface((total_w, max_h), pg.SRCALPHA)
                current_x = 0
                for s in rendered_surfaces:
                    # 垂直居中
                    y_offset = (max_h - s.get_height()) // 2
                    final_surf.blit(s, (current_x, y_offset))
                    current_x += s.get_width()

                # 更新缓存
                self._last_tooltip_data = tooltip_parts
                self._cached_tooltip_surface = final_surf

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
            bg_rect = rect.inflate(10, 6)  # 稍微紧凑一点 padding
            pg.draw.rect(
                self.window, pg.Color("white"), bg_rect, border_radius=3
            )  # 白底
            pg.draw.rect(
                self.window, pg.Color("black"), bg_rect, 1, border_radius=3
            )  # 黑框

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
            "JIEFAN_infantry": "解烦兵",
        }

        if key in mapping:
            return mapping[key]

        # 尝试后缀匹配 (针对通用兵种变体)
        key_lower = key.lower()
        if "infantry" in key_lower:
            return "步兵"
        if "cavalry" in key_lower:
            return "骑兵"
        if "archer" in key_lower:
            return "弓兵"

        return None  # 其他普通地形如 plain 不显示，以免屏幕太乱

    def _draw_smooth_polyline(
        self, color: pg.Color, points: Sequence[pg.math.Vector2], width: int
    ) -> None:
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
                tangent = v_in + v_out
                if tangent.length() < 0.01:
                    tangent = pg.math.Vector2(-v_in.y, v_in.x)  # 垂直方向
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
                real_segment_normal = pg.math.Vector2(
                    -(vectors[i + 1] - curr).y, (vectors[i + 1] - curr).x
                ).normalize()
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
        self.loading_image_left = pg.transform.flip(raw_left, True, False)  # 镜像翻转
        self.loading_image_left_pos = (int(height * 0.03), int(height * 0.25))

        self.start_button_rect = pg.Rect(
            int(width * 0.3),
            int(height * 0.75),
            int(width * 0.4),
            int(height * 0.1),
        )

        self.loading_title_surface = self._render_text(
            "STLITI.TTF", int(width * 0.1), "三足鼎立"
        )
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

        self.choosing_title_surface = self._render_text(
            "SIMLI.TTF", int(height * 0.1), "选择势力"
        )
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

        # 底部回合计数字体
        self.round_counter_font = self._font("msyhbd.ttc", int(height * 0.032))
        # 三国属性（民心/政治点数）显示字体
        self.country_stat_title_font = self._font("STZHONGS.TTF", int(height * 0.038))
        self.country_stat_font = self._font("msyh.ttc", int(height * 0.022))

        self.country_tag_font = self._font("STZHONGS.TTF", int(height * 0.1))
        self.country_tag_surfaces = {
            country: self.country_tag_font.render(label, True, pg.Color("black"))
            for country, label in self.country_labels.items()
        }

        # --- 右下角功能按钮 ---
        # 视觉顺序从左到右: [退出] [重开]
        btn_font = self._font("msyh.ttc", int(height * 0.025))

        labels = ["重开一局", "退出游戏"]
        actions = ["RESTART", "EXIT"]

        self.control_btns = []

        # 起始X坐标：右侧内边距
        current_x_right = int(width - 20)

        for label, action in zip(labels, actions):
            surf = btn_font.render(label, True, pg.Color("white"))
            w = surf.get_width() + 20
            h = surf.get_height() + 10

            x = current_x_right - w
            # 贴近底部
            y = int(height - h - 12)

            rect = pg.Rect(x, y, w, h)

            self.control_btns.append(
                {
                    "rect": rect,
                    "surface": surf,
                    "text_pos": (x + 10, y + 5),
                    "action": action,
                    "bg_color": pg.Color("#444444"),  # 深灰背景
                    "border_color": pg.Color("white"),
                }
            )

            # 往左移，留出间隙
            current_x_right -= w + 10
        # 往右调一点，之前是 width - height * 0.15，现在改为 0.05，更靠右
        self.country_tag_pos = (int(width - height * 0.12), 0)

        # 预计算河流的像素点
        self.yangtze_polylines = tuple(
            self._scale_points(points)
            for points in (YANGTZE_POINTS_1, YANGTZE_POINTS_2)
        )
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
        threshold = 10.0  # 像素距离阈值
        m_vec = pg.math.Vector2(mouse_pos)

        for polyne in polylines_list:
            # polyne is a sequence of points
            if len(polyne) < 2:
                continue

            for i in range(len(polyne) - 1):
                p1 = polyne[i]
                p2 = polyne[i + 1]

                # 计算点到线段距离
                # Vector P1->P2
                line_vec = p2 - p1
                # Vector P1->Mouse
                p1_m_vec = m_vec - p1

                line_len_sq = line_vec.length_squared()
                if line_len_sq == 0:
                    continue

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

    def _scale_points(
        self, normalized_points: Sequence[Tuple[float, float]]
    ) -> List[pg.math.Vector2]:
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

    def _render_text(
        self, filename: str, size: int, text: str, color: pg.Color | str = "black"
    ) -> pg.Surface:
        """使用指定字体和大小渲染一段文字，返回图片表面"""
        font = self._font(filename, size)
        return font.render(text, True, pg.Color(color))
