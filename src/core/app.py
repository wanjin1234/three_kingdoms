"""
这里包含了整个游戏应用的核心逻辑：GameApp。
它是总导演，管理着游戏状态、循环、渲染和逻辑更新。
"""

from __future__ import annotations

import ctypes
import logging
import os
import random
from enum import Enum, auto
from math import dist, sqrt
from typing import Callable, Dict, List, Sequence, Tuple

import pygame as pg

try:
    import fitz  # PyMuPDF，用于PDF渲染

    _FITZ_AVAILABLE = True
except ImportError:
    _FITZ_AVAILABLE = False
from settings import Settings

from src.core.ai_service import AIService
from src.core.camera import Camera
from src.core.combat import (
    COMBAT_TABLE,
    CombatPreview,
    get_ratio_column,
    resolve_combat,
)
from src.core.combat_flow_service import CombatFlowService
from src.core.combat_resolution_service import CombatResolutionService
from src.core.combat_utils_service import CombatUtilsService
from src.core.console_service import ConsoleService
from src.core.country_stats_overlay_service import CountryStatsOverlayService
from src.core.event_card_service import EventCardService
from src.core.evt_info_tooltip_service import EvtInfoTooltipService
from src.core.events import EventManager
from src.core.gameplay_render_service import GameplayRenderService
from src.core.help_rule_load_service import HelpRuleLoadService
from src.core.map_bounds_service import MapBoundsService
from src.core.music_manager import MUSIC_END_EVENT, MusicManager
from src.core.movement_service import MovementService
from src.core.overlay_ui_service import OverlayUIService
from src.core.playing_input_service import PlayingInputService
from src.core.polyline_render_service import PolylineRenderService
from src.core.province_query_service import ProvinceQueryService
from src.core.selection_service import SelectionService
from src.core.turn_presentation_coordinator import TurnPresentationCoordinator
from src.core.screen_render_service import ScreenRenderService
from src.core.score_manager import ScoreManager
from src.core.state_models import CombatState, EventCardState, TurnState, UIState
from src.core.turn_runtime_coordinator import TurnRuntimeCoordinator
from src.core.turn_service import TurnService
from src.core.volume_ui_service import VolumeUIService
from src.game_objects.card import CardManager, CardRepository
from src.game_objects.card_effects import CardEffectManager
from src.game_objects.event_card import EventCardDeck, EventCardDef
from src.game_objects.kingdom import KingdomRepository
from src.game_objects.unit import UnitRenderer, UnitRepository, UnitState
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
    - MODE_SELECT: 选择游戏模式界面
    - CHOOSING: 选择势力界面（单人模式专用）
    - PLAYING: 正式游玩状态
    """

    LOADING = auto()
    MODE_SELECT = auto()
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
        self.min_window_width = min(960, display_info.current_w)
        self.min_window_height = min(540, display_info.current_h)
        self.screen_width = min(
            display_info.current_w,
            max(self.min_window_width, int(display_info.current_w * 0.9)),
        )
        self.screen_height = min(
            display_info.current_h,
            max(self.min_window_height, int(display_info.current_h * 0.9)),
        )
        self.is_fullscreen: bool = False
        self._windowed_size: Tuple[int, int] = (self.screen_width, self.screen_height)
        flags = pg.RESIZABLE
        self.display_surface = pg.display.set_mode(
            (self.screen_width, self.screen_height), flags
        )
        self.display_width, self.display_height = self.display_surface.get_size()
        # 逻辑画布（固定设计分辨率）：所有UI都在这上面绘制，再整体缩放到真实窗口
        self.window = pg.Surface((self.screen_width, self.screen_height)).convert()
        self._logical_window_size: Tuple[int, int] = (
            self.screen_width,
            self.screen_height,
        )
        self._direct_render: bool = False
        self._base_screen_width: int = self.screen_width  # 设计分辨率宽，固定不变
        self._base_screen_height: int = self.screen_height  # 设计分辨率高，固定不变
        self.viewport_rect = pg.Rect(0, 0, self.display_width, self.display_height)
        self._viewport_scale = 1.0
        pg.display.set_caption(settings.window_title)

        # 设置窗口图标（任务栏 / Alt+Tab 显示）
        try:
            from settings import BASE_DIR

            _icon_path = BASE_DIR / "icon.ico"
            if _icon_path.exists():
                _icon_surf = pg.image.load(str(_icon_path))
                pg.display.set_icon(_icon_surf)
        except Exception:
            pass

        # 初始化背景音乐管理器
        try:
            from settings import BASE_DIR as _BASE_DIR

            self.music_manager = MusicManager(_BASE_DIR / "src" / "music")
        except Exception as _e:
            logger.warning("背景音乐初始化失败：%s", _e)
            self.music_manager = None

        # 计算六边形格子的边长，使其刚好能铺满屏幕高度的一部分
        self.hex_side = self.screen_height * 2 / (19 * SQRT3)

        # 初始状态设为 LOADING
        self.state = GameState.LOADING
        if self.music_manager:
            self.music_manager.play_menu()
        self.player_country: str | None = None  # 当前行动的国家
        self.human_country: str | None = None  # 玩家选择控制的国家

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
        self.turn_service = TurnService(
            turn_order=self.turn_order,
            max_major_rounds=self.max_major_rounds,
            max_minor_rounds=self.max_minor_rounds,
        )
        self.ai_service = AIService()
        self.event_card_service = EventCardService()
        self.console_service = ConsoleService()
        self.combat_utils_service = CombatUtilsService()
        self.combat_flow_service = CombatFlowService()
        self.combat_resolution_service = CombatResolutionService()
        self.screen_render_service = ScreenRenderService()
        self.gameplay_render_service = GameplayRenderService()
        self.overlay_ui_service = OverlayUIService()
        self.country_stats_overlay_service = CountryStatsOverlayService()
        self.evt_info_tooltip_service = EvtInfoTooltipService()
        self.volume_ui_service = VolumeUIService()
        self.polyline_render_service = PolylineRenderService()
        self.map_bounds_service = MapBoundsService()
        self.help_rule_load_service = HelpRuleLoadService()
        self.playing_input_service = PlayingInputService()
        self.province_query_service = ProvinceQueryService()
        self.movement_service = MovementService()
        self.selection_service = SelectionService()
        self.turn_runtime = TurnRuntimeCoordinator()
        self.turn_presentation = TurnPresentationCoordinator()
        self.major_round: int = 1
        self.minor_round: int = 1
        self.turn_game_finished: bool = False

        # 国家公共属性（初始为0；回合推进与重开均不自动重置）
        self.country_stats: Dict[str, Dict[str, int]] = (
            self.turn_service.create_country_stats()
        )
        self.major_round_choice_pending: bool = False
        self.major_round_choice_done: Dict[str, bool] = {
            country: False for country in self.turn_order
        }
        self.country_stat_choice_btns: Dict[str, Dict[str, pg.Rect]] = {}

        # 移动后可追加一次“仅该单位”的攻击（可选）
        self.pending_post_move_attack: bool = False
        self.pending_attacker: SelectionEntry | None = None
        # 当前选中的单位列表 [(province_id, slot_index), ...]
        self.selected_units: List[SelectionEntry] = []

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

        # ====================================================================
        # 事件卡系统
        # ====================================================================
        self.event_card_deck = EventCardDeck(settings.event_cards_file)

        # 抽卡按钮（每帧由 render 重建）
        self.draw_event_btn_rect: pg.Rect | None = None

        # 事件卡展示覆盖层（None = 未展示）
        # 结构: {"card": EventCardDef, "drawer": str, "safe": bool}
        self.event_card_overlay: dict | None = None
        self.evt_overlay_ok_btn: pg.Rect | None = None
        # 事件卡图片缓存：{card_name: pg.Surface}
        self._event_card_image_cache: Dict[str, pg.Surface | None] = {}

        # 事件卡单位/地块目标选择
        self.selecting_evt_target: bool = False
        self.pending_evt_card_id: str | None = None
        self.pending_evt_drawer: str | None = None

        # ---- 小回合级别标志（持续到抽取者下次回合开始时清除） ----
        self.evt_flag_liukang: bool = (
            False  # 联刘抗曹（WU卡）：SHU/WU本回合不互攻，抗取者下次回合开始时清除
        )
        self.evt_flag_liukang_drawer: str = ""  # 联刘抗曹抽取方
        self.evt_flag_wuwei: bool = (
            False  # 吴魏媾和（WEI卡）：东吴不能攻魏，抽取者下次回合开始时清除
        )
        self.evt_flag_wuwei_drawer: str = ""  # 吴魏媾和抽取方
        self.evt_flag_all_attack: bool = (
            False  # 奖率三军（公共卡）：全军进攻+1，抽取者下次回合开始时清除
        )
        self.evt_all_attack_drawer: str = ""  # 记录奖率三军的抽取方
        self.evt_temp_pp: Dict[str, int] = {}  # 老骥伏枥：临时政治点数（key=country）

        # ---- 大回合级别标志（_end_full_round 时清除） ----
        self.evt_flag_hefei: bool = False  # 合肥十万：吴攻魏骰点-1
        self.evt_flag_she_hushu: bool = False  # 舍身护主：吴防御时全部+1（本大回合）
        self.evt_flag_hu_recruit: bool = False  # 胡人袭扰：魏本大回合禁止招募

        # ---- 五子良将 ----
        self.evt_wuzi_rounds: int = 0  # 剩余生效小回合数
        self.evt_wuzi_bonus: int = 0  # 当前累积骰点加成（max 3）

        # ---- 跨次抽卡标志 ----
        self.evt_xingluo_active: bool = (
            False  # 星落秋风已触发（等下次隆中定计额外+1 PP）
        )
        self.evt_laomaikuai_active: bool = False  # 老迈昏聩已触发（下次江东才俊无效）

        # ---- 会话级持久技能标志 ----
        self.evt_lonzhong_skill: int = 0  # 蜀汉"隆中定计"攻吴骰+N（每次抽取+1，可叠加）
        self.evt_jingzhu_skill: int = 0  # 东吴"荆州之主"攻蜀骰+N（可叠加）
        self.evt_yishen_skill: int = (
            0  # 蜀汉"一身是胆"剩余触发次数（每次抽取+1，触发时-1）
        )

        # 不懈于内：下次抽卡若负效果无效
        self.evt_draw_again_safe: bool = False

        # 本小回合各国已生效事件卡记录 {country: [(card_name, card_desc), ...]}
        self.evt_applied_this_round: Dict[str, List[Tuple[str, str]]] = {}
        # 本大回合持久事件卡记录（大回合结束才清除）{country: [(card_name, card_desc), ...]}
        self.evt_applied_major_round: Dict[str, List[Tuple[str, str]]] = {}
        # 本小回合已使用锦囊卡记录 {country: [(card_name, card_desc), ...]}
        self.jingnang_applied: Dict[str, List[Tuple[str, str]]] = {}
        # 本大回合持久锦囊卡记录（大回合结束才清除）{country: [(card_name, card_desc), ...]}
        self.jingnang_applied_major: Dict[str, List[Tuple[str, str]]] = {}
        # 割须弃袍：一次性免伤标志，战斗结束后自动清除（WEI专属锦囊卡）
        self.gexu_guard_active: bool = False
        # 各国"！"悬停按钮区域（每帧由 _draw_country_stats_overlay 刷新）
        self.evt_info_btns: Dict[str, pg.Rect] = {}

        # AI 每小回合抓卡限制：{country: True} 表示本小回合已抑节 1 张卡
        self.evt_ai_drawn_this_turn: Dict[str, bool] = {}

        # ---- 帮助/规则书覆盖层 ----
        self.help_overlay_visible: bool = False  # 是否显示规则图片界面
        self.help_current_page: int = 0  # 当前页码（0-based）
        self._help_rule_surfaces: List = []  # 加载好的 rule_1–rule_13 Surface 列表
        self._help_overlay_content_rect: pg.Rect | None = None
        self._help_prev_btn: pg.Rect | None = None  # 上一页按钮 Rect
        self._help_next_btn: pg.Rect | None = None  # 下一页按钮 Rect
        self._help_load_anim_frame: int = 0
        self._help_rule_loading: bool = False
        self._help_rule_load_failed: bool = False

        # ---- 民心等级效果（2-5级）----
        self.morale_lv2_used: Dict[
            str, int
        ] = {}  # {country: major_round} 令行禁止已用大回合
        self.morale_lv3_used: Dict[
            str, int
        ] = {}  # {country: major_round} 老乡指路已用大回合
        self.morale_lv4_pending: Dict[str, bool] = {}  # {country: True} 军容严整待处理
        self.morale_free_move_mode: bool = (
            False  # 令行禁止：自由移动1格模式（不消耗行动力）
        )
        self.morale_bonus_mp_mode: bool = False  # 老乡指路：选择单位获得+1行动力模式
        self.morale_cure_mode: bool = False  # 军容严整：选择混乱单位解除混乱模式
        self.morale_lv2_btn_rect: pg.Rect | None = None
        self.morale_lv3_btn_rect: pg.Rect | None = None
        self.morale_lv4_btn_rect: pg.Rect | None = None
        self.combat_table_btn_rect: pg.Rect | None = None  # 战斗判定表按鈕

        # ---- 使用政治点数（PP）行动系统 ----
        self.pp_spend_mode: bool = False  # 进入PP行动模式
        self.pp_summon_target_prov = None  # 待召唤目标省（Province | None）
        self.pp_spend_end_btn_rect: pg.Rect | None = None  # "结束行动"按钮
        self.pp_btn_rect: pg.Rect | None = None  # 顶部"使用政治点数"入口按钮
        self.pp_summon_btns: list = []  # 召唤子面板按钮列表

        # 事件卡抽取阶段（每个小回合开始时的强制阶段）
        self.evt_draw_phase: bool = False  # True = 当前处于抽取阶段，禁止调兵
        self.evt_skip_draw_btn_rect: pg.Rect | None = None  # 「跳过」按钮区域

        # 卡牌目标选择状态
        self.selecting_card_target = False  # 是否正在选择卡牌目标
        self.selected_card_for_effect: str | None = None  # 待应用的卡牌 ID

        # ====================================================================
        # 分数管理系统
        # ====================================================================
        self.score_manager = ScoreManager()
        self.score_manager_initial_recorded = False

        # 分数显示状态（None = 不显示）
        # 结构：{"type": "wei_turn" | "game_over", "record": ScoreRecord, "net_scores": Dict}
        self.show_score_screen: dict | None = None

        # 音量控制
        self.volume_slider_visible: bool = False
        self.volume_level: float = 1.0
        self._vol_dragging: bool = False
        self._vol_slider_rect: pg.Rect | None = None
        self._vol_track_top: int = 0
        self._vol_track_x: int = 0

        # 改回使用默认的 Arial 字体，因为中文字体 (msyh) 的垂直基线会导致数字无法垂直居中
        self.selection_overlay = SelectionOverlay()
        # 本小回合移动高亮：移出格和移入格，值为执行动作的国家（用于取对应颜色）
        self.move_src_provs: dict = {}  # province_id -> country
        self.move_dst_provs: dict = {}  # province_id -> country
        # 对应的槽位索引记录，只框住实际移动/招募的那个单位
        self.move_src_slots: dict = {}  # province_id -> list[int]
        self.move_dst_slots: dict = {}  # province_id -> list[int]

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
        self._build_mode_select_assets()
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
        # 民心等级效果按钮预渲染（只显示名称，效果描述通过 hover 浮窗展示）
        self._morale_lv2_btn_surf = self.combat_ui_font.render(
            "令行禁止", True, pg.Color("white")
        )
        self._morale_lv3_btn_surf = self.combat_ui_font.render(
            "老乡指路", True, pg.Color("white")
        )
        self._morale_lv4_btn_surf = self.combat_ui_font.render(
            "军容严整", True, pg.Color("white")
        )
        # 战斗判定表按钮预渲染
        self._combat_table_btn_surf = self.combat_ui_font.render(
            "战斗判定表", True, pg.Color("white")
        )
        # PP行动按钮预渲染
        self._pp_btn_surf = self.combat_ui_font.render(
            "使用政治点数", True, pg.Color("white")
        )
        self._pp_end_btn_surf = self.combat_ui_font.render(
            "结束行动", True, pg.Color("white")
        )

        # Tooltip Caching
        self._last_tooltip_data = None
        self._cached_tooltip_surface: pg.Surface | None = None

        # 初始化悬停提示字体 (比标准字体小一圈)
        tooltip_size = max(12, int(self.screen_height * 0.018))
        self.tooltip_font = self._font("msyh.ttc", tooltip_size)
        self.tooltip_bold_font = self._font("msyhbd.ttc", tooltip_size)
        # 民心按钮专用浮窗字体（更小，防止超出屏幕）
        morale_tt_size = max(10, int(self.screen_height * 0.014))
        self.morale_tt_font = self._font("msyh.ttc", morale_tt_size)
        # 控制台字体
        console_font_size = max(14, int(self.screen_height * 0.022))
        self.console_font = self._font("msyh.ttc", console_font_size)

        # 初始化 CardPanel
        # 垂直位置 60% - 85%，水平同 InfoPanel
        card_rect = pg.Rect(
            panel_x,
            int(self.screen_height * 0.60),
            panel_w,
            int(self.screen_height * 0.25),  # 85% - 60%
        )
        cards_dir = str(self.settings.graphics_dir / "ui" / "cards")
        self.card_panel = CardPanel(
            card_rect,
            info_font,
            font_path=font_path,
            base_font_size=font_size,
            cards_dir=cards_dir,
            allow_jiangdong_selection=False,  # 初始为 False，之后会在 _update_card_panel 中更新
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

        # ====================================================================
        # 控制台状态（按 ` 键调出，输入指令后回车执行）
        # ====================================================================
        self.console_visible: bool = False  # 控制台是否可见
        self.console_input: str = ""  # 当前输入的文字
        self.console_message: str = ""  # 上一条执行结果反馈

        # ====================================================================
        # 阶段1：状态模型（与现有字段并存，保持行为等价）
        # ====================================================================
        self.turn_state = TurnState(self)
        self.ui_state = UIState(self)
        self.combat_state = CombatState(self)
        self.event_card_state = EventCardState(self)

        # 初始填充行动力
        self._replenish_action_points()

    def _get_people_support_level(self, country: str) -> int:
        """获取国家当前民心等级（点数即等级，支持负数）"""
        return self.turn_state.country_stats.get(country, {}).get("people_support", 0)

    def _has_confused_units_for_country(self, country: str) -> bool:
        """检查该国是否有任何混乱状态的单位"""
        for prov in self.map_manager.provinces:
            if prov.country == country:
                for u in prov.units:
                    if u.is_confused:
                        return True
        return False

    def _is_special_unit(self, unit_state) -> bool:
        """判断是否为特殊兵种（虎豹骑/无当飞军/解烦兵）"""
        t = (unit_state.unit_type or "").lower()
        return "hubao" in t or "wudang" in t or "jiefan" in t

    def _get_pp_heal_cost(self, unit_state) -> int:
        """获取回复该单位1点血量的PP消耗：普通1PP，特殊2PP"""
        return 2 if self._is_special_unit(unit_state) else 1

    def _get_total_pp(self, country: str) -> int:
        """获取国家当前可用PP总量（普通+临时）"""
        pp = self.turn_state.country_stats.get(country, {}).get("political_points", 0)
        temp = self.event_card_state.evt_temp_pp.get(country, 0)
        return pp + temp

    def _pp_can_use(self, country: str) -> bool:
        """PP是否满足最低使用门槛（≥1）"""
        return self._get_total_pp(country) >= 1

    def _ai_cure_confused_unit(self, country: str) -> bool:
        """AI 自动解除该国第一个混乱单位的混乱状态（军容严整效果）。返回是否成功。"""
        for prov in self.map_manager.provinces:
            if prov.country == country:
                for u in prov.units:
                    if u.is_confused:
                        u.is_confused = False
                        return True
        return False

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

                # 特殊逻辑：虎豹骑固定为4 (defs里应该是4，如果不是，这里强制设定也可以，但defs优先)
                # defs里已经是4了.

                unit.mp = max_mp + getattr(unit, "major_mp_bonus", 0)
                # 注意：回合结束时不清除混乱状态
                # temp_river_immunity / temp_terrain_immunity / temp_dice_bonus
                # 是大回合级效果，不在此处清除，在大回合结束时清除

    def _update_card_panel(self) -> None:
        """更新卡牌面板显示"""
        if self.card_panel and self.card_manager:
            available_cards = self.card_manager.get_available_cards()

            # 江东止啼仅在"被进攻（魏方防守）"时可用（灰色不可选状态）
            # 但始终显示在卡牌列表中，让玩家能看到
            self.card_panel.set_available_cards(available_cards)
            # 更新江东止啼的可用状态
            self.card_panel.allow_jiangdong_selection = self.allow_jiangdong_selection

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
            # 记录江东止啊（魏防守卡）
            self.jingnang_applied.setdefault("WEI", []).append(
                (card_def.name, card_def.description or "")
            )
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
                    # 记录进攻锦囊卡
                    _jn_c = self.player_country or ""
                    self.jingnang_applied.setdefault(_jn_c, []).append(
                        (card_def.name, card_def.description or "")
                    )
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
            _desc = card_def.description or ""
            self.info_panel.show_message(
                f"【{card_def.name}】\n{_desc}\n请点击目标格子来应用", duration=-1
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

        # 记录本小回合已使用锦囊卡
        _jn_c = self.player_country or ""
        self.jingnang_applied.setdefault(_jn_c, []).append(
            (card_def.name, card_def.description or "")
        )

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
        # 注意：province_id 可能是 int，统一转为 str 以匹配 get_effect(str(...)) 的查找方式
        success = self.card_effect_manager.apply_card_effect(
            card_id,
            card_def.name,
            str(province_id),
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

            if card_id == "card_gexu_qibao":
                # 割须弃袍：激活免伤标志，只保护当前这场战斗（战斗后自动清除）
                self.gexu_guard_active = True
                self.info_panel.show_message(
                    "割须弃袍已激活：本小回合内魏方防御最高单位受伤时免除一次伤害",
                    duration=2.5,
                )

            # 大回合持久锦囊卡：额外记录到大回合字典
            if card_id in (
                "card_baiyue_dujiang",
                "card_touduo_yinping",
                "card_kongcheng_mouce",
            ):
                _jn_c = self.player_country or ""
                self.jingnang_applied_major.setdefault(_jn_c, []).append(
                    (card_def.name, card_def.description or "")
                )

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
        # 新局重置移动高亮
        self.move_src_provs = {}
        self.move_dst_provs = {}
        self.move_src_slots = {}
        self.move_dst_slots = {}

        # 记录开局分数（在游戏真正开始时）
        self.score_manager.record_initial_scores(self.map_manager.provinces)
        self.score_manager_initial_recorded = True

        self._start_major_round_choice_phase()
        self.clear_selection()
        self._update_card_panel()
        self.state = GameState.PLAYING
        if self.music_manager:
            self.music_manager.play_game()

        # 如果第一个行动国是 AI，安排延迟触发
        if self.human_country is not None and self.player_country != self.human_country:
            self._ai_turn_timer = pg.time.get_ticks() + 800

    def _start_major_round_choice_phase(self) -> None:
        """每个大回合开始：三国各自选择 +2 民心点数 或 +2 政治点数。"""
        (
            self.major_round_choice_pending,
            self.major_round_choice_done,
        ) = self.turn_service.begin_major_round_choice()
        self.country_stat_choice_btns = {}
        # AI 国家立即自动完成加点：
        # 策略 — PP 为 0 时选政治点数（保证能抽卡/招募），否则选民心
        if self.human_country is not None:
            for _c in list(self.turn_order):
                if _c != self.human_country:
                    _ai_pp = self._get_total_pp(_c)
                    _auto_choice = self.turn_service.choose_major_round_bonus(_ai_pp)
                    self._apply_major_round_choice(_c, _auto_choice)

    def _apply_major_round_choice(self, country: str, choice: str) -> None:
        """应用国家在大回合开始时的加点选择。"""
        if not self.major_round_choice_pending:
            return
        applied = self.turn_service.apply_major_round_choice(
            country_stats=self.country_stats,
            major_round_choice_done=self.major_round_choice_done,
            country=country,
            choice=choice,
        )
        if not applied:
            return

        if choice == "support":
            # 民心等级提升后，检查是否达成"天下归心"胜利条件
            self._check_tianxia_guixin_victory()

        if self.turn_service.all_major_round_choices_done(self.major_round_choice_done):
            self.major_round_choice_pending = False
            if self.info_panel:
                self.info_panel.show_message(
                    f"第{self.major_round}大回合加点完成：三国均已选择"
                )
            # 加点完成后，第一个行动国进入事件卡抽取阶段
            self._enter_evt_draw_phase_if_needed()

    def _end_full_round(self) -> None:
        """三个国家都行动完后触发（每小回合结束调用）：清理小回合效果并复位行动力。"""
        self.card_effect_manager.clear_turn_effects()  # 仅清除小回合级格子效果，保留大回合 is_major 效果（空城妙计等）
        self._replenish_action_points()
        # ── 小回合级标志清除 ──
        # 注意：gexu_guard_active（割须弃袍）在每场战斗结束时即清除，大回合结束时若未消耗则清除兜底
        self.gexu_guard_active = False
        self.jingnang_applied.clear()  # 锦囊卡小回合记录清除

    def _remove_from_major_round(
        self, card_name: str, country: str | None = None
    ) -> None:
        """从 evt_applied_major_round 中移除指定卡牌名称的显示记录。

        Args:
            card_name: 要移除的卡牌名称。
            country: 指定国家时仅移除该国记录；为 None 时对所有国家操作。
        """
        targets = [country] if country else list(self.evt_applied_major_round.keys())
        for c in targets:
            if c in self.evt_applied_major_round:
                self.evt_applied_major_round[c] = [
                    (n, d) for n, d in self.evt_applied_major_round[c] if n != card_name
                ]

    def _refresh_session_skill_display(self) -> None:
        """重建会话级持久技能（隆中定计、一身是胆、星落秋风）在 evt_applied_major_round
        中的显示条目。在计数变化（抽牌、触发消耗）或大回合记录被清除后调用。"""
        for skill_name in ("隆中定计", "一身是胆", "星落秋风"):
            self._remove_from_major_round(skill_name, "SHU")
        if self.evt_lonzhong_skill > 0:
            self.evt_applied_major_round.setdefault("SHU", []).append(
                ("隆中定计", f"蜀汉进攻东吴骰点+1（剩余 {self.evt_lonzhong_skill} 次）")
            )
        if self.evt_yishen_skill > 0:
            self.evt_applied_major_round.setdefault("SHU", []).append(
                (
                    "一身是胆",
                    f"被进攻低于1:1时自动触发（剩余 {self.evt_yishen_skill} 次）",
                )
            )
        if self.evt_xingluo_active:
            self.evt_applied_major_round.setdefault("SHU", []).append(
                ("星落秋风", "下次抽到「隆中定计」时蜀汉额外+1政治点数")
            )

    def _show_score_screen(self, screen_type: str) -> None:
        """
        显示分数屏幕。

        Args:
            screen_type: "wei_turn" (魏国行动完) 或 "game_over" (游戏结束)
        """
        # 获取详细分数信息
        record = self.score_manager.get_detailed_scores(
            self.map_manager.provinces, self.country_stats
        )

        # 计算净得分
        net_scores = {
            "SHU": record.shu_score - record.shu_initial,
            "WEI": record.wei_score - record.wei_initial,
            "WU": record.wu_score - record.wu_initial,
        }

        # 设置显示状态
        self.show_score_screen = {
            "type": screen_type,
            "record": record,
            "net_scores": net_scores,
        }

        # 游戏结束时切换到结算音乐
        if screen_type == "game_over" and self.music_manager:
            self.music_manager.play_score()

        # 检查游戏结束时的胜利条件
        if screen_type == "game_over":
            # 检查"天下归心"
            tianxia_winner = self.score_manager.check_tianxia_guixin(
                self.map_manager.provinces, self.country_stats
            )
            if tianxia_winner:
                self.show_score_screen["tianxia_winner"] = tianxia_winner
            else:
                # 检查"一代枭雄"
                winner, net = self.score_manager.get_winner_by_score(
                    self.map_manager.provinces, self.country_stats
                )
                self.show_score_screen["score_winner"] = winner
                self.show_score_screen["net_scores"] = net

    def _render_score_screen(self) -> None:
        """渲染分数显示屏幕（白屏）"""
        if not self.show_score_screen:
            return

        # 填充白色背景
        self.window.fill(pg.Color("white"))

        record = self.show_score_screen["record"]
        net_scores = self.show_score_screen["net_scores"]
        screen_type = self.show_score_screen["type"]

        # 字体设置
        title_size = int(self.screen_height * 0.05)
        body_size = int(self.screen_height * 0.035)
        small_size = int(self.screen_height * 0.025)

        title_font = self._font("msyh.ttc", title_size)
        body_font = self._font("msyh.ttc", body_size)
        small_font = self._font("msyh.ttc", small_size)

        # 辅助：将文本按最大像素宽度自动换行，返回行列表
        def wrap_text(text: str, font: pg.font.Font, max_w: int) -> list[str]:
            words = list(text)  # 中文逐字分割
            lines: list[str] = []
            cur = ""
            for ch in text:
                test = cur + ch
                if font.size(test)[0] <= max_w:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = ch
            if cur:
                lines.append(cur)
            return lines if lines else [text]

        # 特殊地点中文名映射
        special_names_map = {
            "Hanzhong": "汉中",
            "Jingzhou": "荆州",
            "Chengdu": "成都",
            "Liangzhou": "凉州",
            "Youzhou": "幽州",
            "Xiangyang": "襄阳",
            "Hefei": "合肥",
            "Changan": "长安",
            "Luoyang": "洛阳",
            "Wuchang": "武昌",
            "Changsha": "长沙",
            "Jianye": "建业",
        }

        # 标题
        if screen_type == "wei_turn":
            title_text = "魏国行动完毕 - 各国分数"
        else:
            title_text = "游戏结束 - 最终分数"

        title_surf = title_font.render(title_text, True, pg.Color("black"))
        title_rect = title_surf.get_rect(centerx=self.screen_width // 2, top=40)
        self.window.blit(title_surf, title_rect)

        y_offset = title_rect.bottom + 40

        countries = [
            ("SHU", "蜀汉", pg.Color("red")),
            ("WEI", "曹魏", pg.Color("blue")),
            ("WU", "孙吴", pg.Color("green")),
        ]

        col_width = self.screen_width // 3
        # 盒子宽度固定为列宽减去左右各 10px 边距
        box_width = col_width - 20
        inner_w = box_width - 30  # 文字可用宽度
        line_gap = 4
        section_gap = 12

        # ---- 第一遍：计算每个国家盒子的动态高度 ----
        def calc_box_content(country):
            """返回该国所有行的列表 [(text, font, color, is_section_start)]"""
            rows = []
            if country == "SHU":
                current, initial, net = (
                    record.shu_score,
                    record.shu_initial,
                    net_scores["SHU"],
                )
                support = record.shu_people_support
                special, normal = record.shu_special, record.shu_normal
            elif country == "WEI":
                current, initial, net = (
                    record.wei_score,
                    record.wei_initial,
                    net_scores["WEI"],
                )
                support = record.wei_people_support
                special, normal = record.wei_special, record.wei_normal
            else:
                current, initial, net = (
                    record.wu_score,
                    record.wu_initial,
                    net_scores["WU"],
                )
                support = record.wu_people_support
                special, normal = record.wu_special, record.wu_normal

            sign = "+" if net >= 0 else ""
            net_color = pg.Color("darkgreen") if net >= 0 else pg.Color("red")

            rows.append((f"当前分数：{current:.1f}", small_font, pg.Color("black")))
            rows.append((f"开局分数：{initial:.1f}", small_font, pg.Color("black")))
            rows.append((f"净得分：{sign}{net:.1f}", small_font, net_color))
            rows.append((f"民心等级：{support}", small_font, pg.Color("black")))

            if special:
                names_str = ", ".join([special_names_map.get(n, n) for n in special])
                full_text = f"特殊地点：{names_str}"
                for line in wrap_text(full_text, small_font, inner_w):
                    rows.append((line, small_font, pg.Color("black")))
            rows.append((f"普通地块：{normal}", small_font, pg.Color("black")))
            return rows

        # 收集所有国家内容，计算统一最大高度
        all_rows = {c: calc_box_content(c) for c, _, _ in countries}

        def rows_height(rows):
            h = 0
            for text, font, _ in rows:
                h += font.get_height() + line_gap
            return h

        name_area = body_font.get_height() + 15 + section_gap
        padding_bottom = 15
        box_height = (
            max(
                rows_height(rows) + name_area + padding_bottom
                for rows in all_rows.values()
            )
            + 20
        )  # 统一所有盒子高度

        # ---- 第二遍：绘制 ----
        for i, (country, cn_name, color) in enumerate(countries):
            box_x = i * col_width + (col_width - box_width) // 2
            box_y = y_offset

            box_rect = pg.Rect(box_x, box_y, box_width, box_height)
            pg.draw.rect(
                self.window, pg.Color(250, 250, 250), box_rect, border_radius=10
            )
            pg.draw.rect(self.window, color, box_rect, 3, border_radius=10)

            # 国家名称
            name_surf = body_font.render(cn_name, True, color)
            name_rect = name_surf.get_rect(
                centerx=box_x + box_width // 2, top=box_y + 10
            )
            self.window.blit(name_surf, name_rect)

            info_y = name_rect.bottom + section_gap
            for text, font, txt_color in all_rows[country]:
                surf = font.render(text, True, txt_color)
                self.window.blit(surf, (box_x + 15, info_y))
                info_y += font.get_height() + line_gap

        # 游戏结束时显示胜利者
        if screen_type == "game_over":
            winner_y = y_offset + box_height + 40

            if "tianxia_winner" in self.show_score_screen:
                winner = self.show_score_screen["tianxia_winner"]
                winner_names = {"SHU": "蜀汉", "WEI": "曹魏", "WU": "孙吴"}
                winner_text = (
                    f"胜利：{winner_names.get(winner, winner)} 达成「天下归心」!"
                )
                winner_surf = title_font.render(winner_text, True, pg.Color("gold"))
                self.window.blit(
                    winner_surf,
                    winner_surf.get_rect(centerx=self.screen_width // 2, top=winner_y),
                )
            elif "score_winner" in self.show_score_screen:
                winner = self.show_score_screen["score_winner"]
                winner_names = {"SHU": "蜀汉", "WEI": "曹魏", "WU": "孙吴"}
                winner_text = (
                    f"胜利：{winner_names.get(winner, winner)} 获得「一代枭雄」!"
                    if winner
                    else "平局！"
                )
                winner_surf = title_font.render(winner_text, True, pg.Color("gold"))
                self.window.blit(
                    winner_surf,
                    winner_surf.get_rect(centerx=self.screen_width // 2, top=winner_y),
                )

        # 底部提示
        hint_surf = small_font.render("按 ESC 退出", True, pg.Color("gray"))
        hint_rect = hint_surf.get_rect(
            centerx=self.screen_width // 2, bottom=self.screen_height - 30
        )
        self.window.blit(hint_surf, hint_rect)

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
        # 民心效果模式清除
        self.morale_free_move_mode = False
        self.morale_bonus_mp_mode = False
        self.morale_cure_mode = False
        # PP行动模式清除
        self.pp_spend_mode = False
        self.pp_summon_target_prov = None
        self.pp_summon_btns = []

        if not keep_info_message:
            self.combat_result_title = None
            self.combat_result_timer = 0
            if self.info_panel:
                self.info_panel.show_properties("")

    def _advance_country_turn(self, keep_info_message: bool = False) -> None:
        """切换到下一个国家。"""
        if self.turn_game_finished:
            return

        self.turn_runtime.prepare_turn_switch(
            self, keep_info_message=keep_info_message
        )

        advance = self.turn_service.advance_turn(
            turn_index=self.turn_index,
            minor_round=self.minor_round,
            major_round=self.major_round,
        )
        self.turn_index = advance.turn_index
        self.minor_round = advance.minor_round
        self.major_round = advance.major_round

        if advance.game_finished:
            # 5个大回合 * 6个小回合结束，对局终止
            self.turn_presentation.handle_game_finished(self)
            return

        if advance.completed_minor_round:
            # 一个小回合（蜀->吴->魏）结束
            self._end_full_round()
        elif advance.started_new_major_round:
            # 小回合满6后进入下一个大回合
            self.turn_runtime.apply_major_round_rollover(self)

        self.player_country = self.turn_order[self.turn_index]
        # 该国开始自己的回合时，仅清除本国上一回合遗留的移动高亮
        # （不再区分人类/AI：让所有国家的高亮保持到下轮轮到该国时才清除，
        #   确保魏国行动的蓝框在蜀汉回合开始时仍可见，直到魏国下次行动时清除）
        _new_c = self.player_country
        # 事件卡"持续到抽取者下次回合"与该国移动高亮，在该国下次回合开始时清除
        self.turn_runtime.on_country_turn_start(self, new_country=_new_c)
        self.turn_presentation.on_country_activated(self)

    def _finish_country_action(
        self, action_name: str, keep_info_message: bool = False
    ) -> None:
        """当前国家执行完一个动作后，自动轮换到下一国家。"""
        self._advance_country_turn(keep_info_message=keep_info_message)

    # ---------------------------------------------------------------
    # AI TURN
    # ---------------------------------------------------------------

    def _run_ai_turn(self) -> None:
        """AI 行动：自动完成大回合加点选择 + 移动/攻击，然后结束本国回合。
        策略：先将所有内陆部队整省调往边境，全部到位后再发动进攻。
        同时会抽取事件卡、使用锦囊卡、招募部队、解除混乱。"""
        self.ai_service.run_turn(self)

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
        # 4.5 重置三国政治点数和民心
        self.country_stats = self.turn_service.create_country_stats()
        # 5. 重置事件卡系统（重新开局）
        from settings import SETTINGS as settings_module

        self.event_card_deck = EventCardDeck(settings_module.event_cards_file)
        self.event_card_overlay = None
        self.evt_overlay_ok_btn = None
        self.selecting_evt_target = False
        self.pending_evt_card_id = None
        self.pending_evt_drawer = None
        self.evt_flag_liukang = False
        self.evt_flag_liukang_drawer = ""
        self.evt_flag_she_hushu = False
        self.evt_flag_hu_recruit = False
        self.evt_flag_wuwei = False
        self.evt_flag_wuwei_drawer = ""
        self.evt_temp_pp = {}
        self.evt_flag_hefei = False
        self.evt_flag_all_attack = False
        self.evt_all_attack_drawer = ""
        self.gexu_guard_active = False
        self.jingnang_applied = {}
        self.evt_applied_this_round = {}
        self.evt_applied_major_round = {}
        self.jingnang_applied_major = {}
        self.evt_wuzi_rounds = 0
        self.evt_wuzi_bonus = 0
        self.evt_xingluo_active = False
        self.evt_laomaikuai_active = False
        self.evt_lonzhong_skill = 0
        self.evt_jingzhu_skill = 0
        self.evt_yishen_skill = 0
        self.evt_draw_again_safe = False
        self.evt_draw_phase = False
        self.evt_skip_draw_btn_rect = None
        # 民心等级效果重置
        self.morale_lv2_used = {}
        self.morale_lv3_used = {}
        self.morale_lv4_pending = {}
        self.morale_free_move_mode = False
        self.morale_bonus_mp_mode = False
        self.morale_cure_mode = False
        # PP行动系统重置
        self.pp_spend_mode = False
        self.pp_summon_target_prov = None
        self.pp_summon_btns = []
        self.state = GameState.MODE_SELECT
        if self.music_manager:
            self.music_manager.play_menu()
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
            self._present_frame()
            # 休息一小会儿，以保持稳定的 FPS
            self.clock.tick(self.settings.fps)

        pg.quit()

    def stop(self) -> None:
        """停止游戏循环，准备退出"""
        self._running = False

    def _reflow_after_window_change(self) -> None:
        """更新逻辑画布到真实窗口的缩放比例与留白区域。"""
        self.display_width, self.display_height = self.display_surface.get_size()
        if self._direct_render:
            # 全屏：铺满屏幕不留白
            self._viewport_scale = 1.0
            self.viewport_rect = pg.Rect(0, 0, self.display_width, self.display_height)
            return

        base_w = self._base_screen_width
        base_h = self._base_screen_height
        scale_x = self.display_width / base_w
        scale_y = self.display_height / base_h

        if scale_x > scale_y:
            # 矮胖：以高度为基准缩放，扩展逻辑画布宽度
            # 右侧面板锚定到新的 screen_width 右边缘，中间自然留白
            self._viewport_scale = scale_y
            new_logical_w = max(base_w, int(round(self.display_width / scale_y)))
            self.viewport_rect = pg.Rect(0, 0, self.display_width, self.display_height)
            if new_logical_w != self.screen_width or self.screen_height != base_h:
                self.screen_width = new_logical_w
                self.screen_height = base_h
                self.window = pg.Surface(
                    (self.screen_width, self.screen_height)
                ).convert()
                self._rebuild_layout_for_screen_size()
        else:
            # 瘦高/等比：以宽度为基准缩放，上下留白
            self._viewport_scale = min(scale_x, scale_y)
            target_w = max(1, int(base_w * self._viewport_scale))
            target_h = max(1, int(base_h * self._viewport_scale))
            offset_x = (self.display_width - target_w) // 2
            offset_y = (self.display_height - target_h) // 2
            self.viewport_rect = pg.Rect(offset_x, offset_y, target_w, target_h)
            if self.screen_width != base_w or self.screen_height != base_h:
                self.screen_width = base_w
                self.screen_height = base_h
                self.window = pg.Surface(
                    (self.screen_width, self.screen_height)
                ).convert()
                self._rebuild_layout_for_screen_size()

    def _rebuild_layout_for_screen_size(self) -> None:
        """当逻辑分辨率变化时，重建地图比例、字体与UI布局。"""
        self.hex_side = self.screen_height * 2 / (19 * SQRT3)
        self.map_manager.set_hex_side(self.hex_side)
        self.unit_renderer.on_hex_side_changed(self.hex_side)

        # 全屏模式：面板按当前分辨率比例缩放（整体铺满屏幕）
        # 窗口模式：面板宽度固定（基于原始设计宽度），位置锚定到逻辑画布右边缘，中间留白
        if self._direct_render:
            panel_w = int(self.screen_width * 0.30)
        else:
            panel_w = int(self._base_screen_width * 0.30)
        panel_x = self.screen_width - panel_w
        panel_y = int(self.screen_height * 0.15)
        panel_h = int(self.screen_height * 0.45)
        panel_rect = pg.Rect(panel_x, panel_y, panel_w, panel_h)

        font_size = int(self.screen_height * 0.025)
        info_font = self._font("msyh.ttc", font_size)
        font_path = str(self.settings.fonts_dir / "msyh.ttc")

        if self.info_panel:
            self.info_panel.rect = panel_rect
            self.info_panel.font = info_font
            self.info_panel.font_path = font_path
            self.info_panel.base_font_size = font_size
            self.info_panel._font_cache = {}

        if self.card_panel:
            self.card_panel.rect = pg.Rect(
                panel_x,
                int(self.screen_height * 0.60),
                panel_w,
                int(self.screen_height * 0.25),
            )
            self.card_panel.font = info_font
            self.card_panel.font_path = font_path
            self.card_panel.base_font_size = font_size
            self.card_panel._font_cache = {}
            self.card_panel.tooltip_font = None

        self.combat_ui_font = info_font
        self._recover_btn_surf = self.combat_ui_font.render(
            "解除混乱", True, pg.Color("white")
        )
        self._no_attack_btn_surf = self.combat_ui_font.render(
            "不攻击", True, pg.Color("white")
        )
        self._morale_lv2_btn_surf = self.combat_ui_font.render(
            "令行禁止", True, pg.Color("white")
        )
        self._morale_lv3_btn_surf = self.combat_ui_font.render(
            "老乡指路", True, pg.Color("white")
        )
        self._morale_lv4_btn_surf = self.combat_ui_font.render(
            "军容严整", True, pg.Color("white")
        )
        self._combat_table_btn_surf = self.combat_ui_font.render(
            "战斗判定表", True, pg.Color("white")
        )
        self._pp_btn_surf = self.combat_ui_font.render(
            "使用政治点数", True, pg.Color("white")
        )
        self._pp_end_btn_surf = self.combat_ui_font.render(
            "结束行动", True, pg.Color("white")
        )

        tooltip_size = max(12, int(self.screen_height * 0.018))
        self.tooltip_font = self._font("msyh.ttc", tooltip_size)
        self.tooltip_bold_font = self._font("msyhbd.ttc", tooltip_size)
        morale_tt_size = max(10, int(self.screen_height * 0.014))
        self.morale_tt_font = self._font("msyh.ttc", morale_tt_size)
        console_font_size = max(14, int(self.screen_height * 0.022))
        self.console_font = self._font("msyh.ttc", console_font_size)

        self._build_loading_assets()
        self._build_mode_select_assets()
        self._build_choosing_assets()
        self._build_play_assets()
        self._cached_tooltip_surface = None
        self._last_tooltip_data = None

    def _present_frame(self) -> None:
        """将逻辑画布按比例缩放并显示到真实窗口。"""
        if not self.display_surface:
            return

        if self._direct_render:
            pg.display.flip()
            return

        self.display_surface.fill(pg.Color("white"))
        scaled = pg.transform.smoothscale(
            self.window, (self.viewport_rect.width, self.viewport_rect.height)
        )
        self.display_surface.blit(scaled, self.viewport_rect.topleft)
        pg.display.flip()

    def _to_logical_pos(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        """把真实窗口坐标转换为逻辑画布坐标。"""
        x, y = pos
        if self._direct_render:
            return (x, y)
        if not self.viewport_rect.collidepoint((x, y)):
            return (-10_000, -10_000)

        lx = int(
            (x - self.viewport_rect.x) * self.screen_width / self.viewport_rect.width
        )
        ly = int(
            (y - self.viewport_rect.y) * self.screen_height / self.viewport_rect.height
        )
        lx = max(0, min(self.screen_width - 1, lx))
        ly = max(0, min(self.screen_height - 1, ly))
        return (lx, ly)

    def _get_logical_mouse_pos(self) -> Tuple[int, int]:
        """获取当前鼠标在逻辑画布中的坐标。"""
        return self._to_logical_pos(pg.mouse.get_pos())

    def _adapt_event_to_logical(self, event: pg.event.Event) -> pg.event.Event:
        """将带坐标的鼠标事件转换到逻辑画布坐标系。"""
        if hasattr(event, "pos"):
            data = dict(event.dict)
            data["pos"] = self._to_logical_pos(event.pos)
            return pg.event.Event(event.type, data)
        return event

    def _resize_windowed(self, width: int, height: int) -> None:
        """调整窗口模式尺寸（带边框，可拖拽，可缩放）。"""
        width = max(self.min_window_width, width)
        height = max(self.min_window_height, height)
        self.display_surface = pg.display.set_mode((width, height), pg.RESIZABLE)
        self._windowed_size = (width, height)
        self.is_fullscreen = False
        self._direct_render = False
        self._reflow_after_window_change()

    def _toggle_fullscreen_mode(self) -> None:
        """在窗口模式与真正全屏之间切换，不改系统分辨率。"""
        if not self.is_fullscreen:
            self._windowed_size = self.display_surface.get_size()
            # (0, 0) + FULLSCREEN：SDL2 标准桌面全屏，以当前桌面分辨率进入，无偏移。
            self.display_surface = pg.display.set_mode((0, 0), pg.FULLSCREEN)
            self.is_fullscreen = True
            self._direct_render = True
            self.window = self.display_surface
            self.screen_width, self.screen_height = self.display_surface.get_size()
            self._rebuild_layout_for_screen_size()
        else:
            self.display_surface = pg.display.set_mode(
                self._windowed_size, pg.RESIZABLE
            )
            self.is_fullscreen = False
            self._direct_render = False
            # screen_width/height 此时还是全屏分辨率，_reflow 会检测差异并重建
            self.window = pg.Surface(
                (self._base_screen_width, self._base_screen_height)
            ).convert()
        self._reflow_after_window_change()

    def _draw_global_fullscreen_btn(self) -> None:
        """在逻辑画布底部居中绘制全屏提示文字（所有界面通用）。"""
        font_size = max(10, int(self.screen_height * 0.018))
        hint_font = self._font("msyh.ttc", font_size)
        hint_surf = hint_font.render(
            "按 F11 切换全屏/窗口模式", True, pg.Color("#888888")
        )
        x = (self.screen_width - hint_surf.get_width()) // 2
        y = self.screen_height - hint_surf.get_height() - 8
        self.window.blit(hint_surf, (x, y))

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

    def add_selection(
        self,
        province_id: int,
        slot_index: int,
        allow_cross_province: bool = False,
    ) -> None:
        """添加一个选中单位。
        allow_cross_province=True 时（Shift+点击）允许跨格子多选，否则强制同格操作。
        """
        # 只要发生了新的选择操作，肯定要清空上一轮战斗的残留结果
        self.combat_result_title = None
        self.combat_result_timer = 0

        # 防止重复添加
        new_entry = (province_id, slot_index)
        if new_entry in self.selected_units:
            return

        # 若已有选中单位且来自不同格子，先清空再选新格子（强制同格操作）
        # Shift+点击时跳过此限制，允许跨格子多选
        if not allow_cross_province and self.selected_units:
            existing_pids = {pid for pid, _ in self.selected_units}
            if province_id not in existing_pids:
                self.selected_units.clear()

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
        # 背景音乐：曲目结束时自动播放下一首
        if event.type == MUSIC_END_EVENT:
            if self.music_manager:
                self.music_manager.on_track_end()
            return

        if event.type == pg.QUIT:
            self.stop()
            return

        if event.type in (pg.VIDEORESIZE, pg.WINDOWSIZECHANGED):
            if not self.is_fullscreen:
                if event.type == pg.VIDEORESIZE:
                    new_w, new_h = event.w, event.h
                else:
                    new_w = getattr(event, "x", self.display_width)
                    new_h = getattr(event, "y", self.display_height)

                if (new_w, new_h) != (self.display_width, self.display_height):
                    self._resize_windowed(new_w, new_h)
            return

        event = self._adapt_event_to_logical(event)

        # F11 全局切换全屏
        if event.type == pg.KEYDOWN and event.key == pg.K_F11:
            self._toggle_fullscreen_mode()
            return

        # ` 键（反引号）切换控制台显示/隐藏
        if event.type == pg.KEYDOWN and event.key == pg.K_BACKQUOTE:
            self._toggle_console()
            return

        # 控制台打开时，所有后续事件交由控制台处理，不传递给游戏逻辑
        if self.console_visible:
            self._handle_console_event(event)
            return

        # 如果正在显示分数屏，优先处理
        if self.show_score_screen:
            self._handle_score_screen_event(event)
            return

        if self.state == GameState.LOADING:
            self._handle_loading_event(event)
        elif self.state == GameState.MODE_SELECT:
            self._handle_mode_select_event(event)
        elif self.state == GameState.CHOOSING:
            self._handle_choosing_event(event)
        elif self.state == GameState.PLAYING:
            self._handle_playing_event(event)

    # ====================================================================
    # 控制台系统
    # ====================================================================

    def _toggle_console(self) -> None:
        """切换控制台显示状态。"""
        self.console_service.toggle_console(self)

    def _handle_console_event(self, event: pg.event.Event) -> None:
        """控制台输入事件处理。"""
        self.console_service.handle_console_event(self, event)

    def _process_console_command(self, cmd: str) -> None:
        """解析并执行控制台命令（cmd 已统一转为小写，大小写不敏感）。"""
        self.console_service.process_console_command(self, cmd)

    def _enable_observe_mode(self) -> None:
        """激活观察者模式：所有三个国家均由 AI 接管。"""
        self.console_service.enable_observe_mode(self)

    def _tag_command(self, target: str) -> None:
        """tag 指令：切换玩家控制的国家（shu/wu/wei）。"""
        self.console_service.tag_command(self, target)

    # ====================================================================

    def _handle_loading_event(self, event: pg.event.Event) -> None:
        """处理加载界面的事件（比如点击开始按钮）"""
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if self.start_button_rect.collidepoint(event.pos):
                self.state = GameState.MODE_SELECT

    def _handle_mode_select_event(self, event: pg.event.Event) -> None:
        """处理选择游戏模式界面的事件"""
        if event.type != pg.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.mode_single_rect.collidepoint(event.pos):
            # 单人游戏：跳到选择势力界面
            self.state = GameState.CHOOSING
        elif self.mode_multi_rect.collidepoint(event.pos):
            # 三人游戏：直接开始，所有国家均由玩家操控
            self._start_turn_based_game(human_country=None)

    def _handle_choosing_event(self, event: pg.event.Event) -> None:
        """处理选择势力界面的事件"""
        if event.type != pg.MOUSEBUTTONDOWN or event.button != 1:
            return
        for country, button in self.faction_buttons.items():
            cx, cy = button["center"]
            dx = event.pos[0] - cx
            dy = event.pos[1] - cy
            if (dx * dx + dy * dy) <= self.faction_button_radius**2:
                self._start_turn_based_game(human_country=country)
                return

    def _handle_score_screen_event(self, event: pg.event.Event) -> None:
        """处理分数屏幕的事件"""
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                # 关闭分数屏幕
                self.show_score_screen = None
                # 如果是游戏结束，按 ESC 后返回模式选择界面
                if self.state == GameState.PLAYING and self.turn_game_finished:
                    self._restart_game()

    def _handle_playing_event(self, event: pg.event.Event) -> None:
        """处理游戏中的事件"""
        if self.playing_input_service.handle_help_overlay_wheel(self, event):
            return

        if self.playing_input_service.handle_help_overlay_click(self, event):
            return

        if event.type == pg.KEYDOWN:
            if self.playing_input_service.handle_keydown(self, event):
                return
        elif event.type == pg.MOUSEBUTTONDOWN:
            if event.button == 1:
                # ---- 事件卡覆盖层：优先处理（模态） ----
                if self.event_card_overlay:
                    if self.evt_overlay_ok_btn and self.evt_overlay_ok_btn.collidepoint(
                        event.pos
                    ):
                        self._confirm_event_card()
                    return

                # 0.0 检查功能按钮
                if self.playing_input_service.handle_control_button_click(
                    self,
                    event.pos,
                ):
                    return

                if self.playing_input_service.handle_volume_slider_click(
                    volume_slider_visible=self.volume_slider_visible,
                    slider_rect=self._vol_slider_rect,
                    pos=event.pos,
                    on_start_drag=lambda: setattr(self, "_vol_dragging", True),
                    on_update_volume=self._update_volume_from_y,
                    on_hide_slider=lambda: setattr(self, "volume_slider_visible", False),
                ):
                    return

                # 0.0x 大回合开始加点按钮（三国）
                if self.playing_input_service.handle_major_round_choice_click(
                    self,
                    event.pos,
                ):
                    return

                # 0.0y 事件卡抽取阶段：仅允许「抽取」和「跳过」，阻挡所有其他操作
                # 例外：若正在等待玩家点选事件卡目标，放行到下方目标选择处理
                if self.playing_input_service.handle_evt_draw_phase_click(
                    self,
                    event.pos,
                ):
                    return

                # 0. 优先处理顶部的战斗按钮
                if self.playing_input_service.handle_combat_ui_click(self, event.pos):
                    return

                # 0.05 事件卡目标选择
                if self.playing_input_service.handle_evt_target_click(self, event.pos):
                    return

                # 0.06 抽事件卡按钮
                if self.playing_input_service.handle_draw_event_button_click(
                    self,
                    event.pos,
                ):
                    return

                # 0.07 使用政治点数（PP）系统
                if self.playing_input_service.handle_pp_click(self, event.pos):
                    return

                # 0.08 民心等级效果按钮（令行禁止 / 老乡指路 / 军容严整）
                if self.playing_input_service.handle_morale_click(self, event.pos):
                    return

                # 0.1 检查“解除混乱”按钮
                if self.playing_input_service.handle_recover_click(self, event.pos):
                    return

                # 0.15 检查“移动后不攻击”按钮
                if self.playing_input_service.handle_no_attack_click(self, event.pos):
                    return

                # 0.2 检查卡牌面板点击
                if self.playing_input_service.handle_card_panel_click(
                    self,
                    event.pos,
                ):
                    return

                # 优先处理 UI 面板点击
                if self.playing_input_service.handle_info_panel_click(self, event.pos):
                    return

                # 如果正在选择卡牌目标，检查是否点击了一个格子
                if self.playing_input_service.handle_card_target_click(
                    self,
                    event.pos,
                ):
                    return

                if self.playing_input_service.handle_unit_selection_click(
                    self,
                    event.pos,
                ):
                    return

            elif event.button == 3:
                if self.playing_input_service.should_block_right_click(
                    major_round_choice_pending=self.major_round_choice_pending,
                    evt_draw_phase=self.evt_draw_phase,
                    selecting_evt_target=self.selecting_evt_target,
                    on_block_message=(
                        (lambda msg: self.info_panel.show_message(msg))
                        if self.info_panel
                        else None
                    ),
                ):
                    return
                self._handle_game_right_click(event.pos)
        elif event.type == pg.MOUSEMOTION:
            self.playing_input_service.handle_mouse_motion(
                vol_dragging=self._vol_dragging,
                volume_slider_visible=self.volume_slider_visible,
                slider_rect=self._vol_slider_rect,
                pos=event.pos,
                on_update_volume=self._update_volume_from_y,
                card_panel=self.card_panel,
            )
        elif event.type == pg.MOUSEBUTTONUP:
            if event.button == 1:
                self.playing_input_service.handle_left_button_up(
                    on_stop_drag=lambda: setattr(self, "_vol_dragging", False)
                )

    def _get_unit_slot_at(self, pos: Tuple[int, int]) -> Tuple[int, int] | None:
        """根据鼠标点击位置获取被点击的单位"""
        return self.province_query_service.get_unit_slot_at(
            provinces=self.map_manager.provinces,
            unit_renderer=self.unit_renderer,
            hex_side=self.hex_side,
            pos=pos,
        )

    def _get_province_at(
        self, pos: Tuple[int, int]
    ) -> object | None:  # object -> Province
        """简单的点击拾取检测"""
        return self.province_query_service.get_province_at(
            provinces=self.map_manager.provinces,
            hex_side=self.hex_side,
            pos=pos,
        )

    def _handle_game_right_click(self, pos: Tuple[int, int]) -> None:
        """处理游戏场景的右键逻辑"""
        self.playing_input_service.handle_game_right_click(self, pos)

    def _handle_movement(self, target: object) -> None:  # target: Province
        """处理移动逻辑：同一格子上的单位可作为整体一起移动。"""
        self.movement_service.handle_movement(self, target)

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

        # 事件卡永久加成（挟帝发令 / 江东铁壁 / 愿打愿挨）
        atk += getattr(unit_state, "attack_bonus", 0)
        dfs += getattr(unit_state, "defense_bonus", 0)

        # 受伤减半
        if unit_state.is_injured:
            atk *= INJURY_PENALTY
            dfs *= INJURY_PENALTY

        # 混乱 -1
        if unit_state.is_confused:
            atk = max(0, atk - CONFUSION_PENALTY)
            dfs = max(0, dfs - CONFUSION_PENALTY)

        return atk, dfs

    # ------------------------------------------------------------------
    # 音量滑块
    # ------------------------------------------------------------------

    def _draw_speaker_icon(self, cx: int, cy: int, radius: int) -> None:
        """在圆形按钮内绘制喇叭图案（白色，居中）。"""
        self.volume_ui_service.draw_speaker_icon(self.window, cx, cy, radius)

    def _update_volume_from_y(self, y: int) -> None:
        """根据鼠标 Y 坐标更新音量（0.0-1.0），并同步应用到 mixer。"""
        _new_vol = self.volume_ui_service.calculate_volume_from_y(
            y=y,
            ty_top=self._vol_track_top,
            ty_bot=self._vol_track_bottom,
        )
        if _new_vol is None:
            return
        self.volume_level = _new_vol
        if pg.mixer.get_init():
            pg.mixer.music.set_volume(self.volume_level)

    def _render_volume_slider(self) -> None:
        """在屏幕上绘制音量调节滑块浮窗。"""
        self.volume_ui_service.render_volume_slider(
            window=self.window,
            slider_rect=self._vol_slider_rect,
            track_x=self._vol_track_x,
            track_top=self._vol_track_top,
            track_bottom=self._vol_track_bottom,
            volume_level=self.volume_level,
            font_loader=self._font,
            tooltip_font=getattr(self, "tooltip_font", None),
            combat_ui_font=getattr(self, "combat_ui_font", None),
        )

    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 帮助/游戏规则图片覆盖层
    # ------------------------------------------------------------------

    def _load_help_rule_thread(self) -> None:
        """后台线程：依次读取 rule_1.png – rule_13.png，存为原始像素列表。"""
        surfaces, failed = self.help_rule_load_service.load_help_rule_surfaces(
            graphics_dir=self.settings.graphics_dir
        )
        if failed:
            self._help_rule_load_failed = True
            self._help_rule_loading = False
            return
        self._help_rule_surfaces = surfaces
        self._help_rule_loading = False

    def _start_help_rule_load(self) -> None:
        """启动后台线程加载规则图片（若尚未加载）。"""
        started = self.help_rule_load_service.start_help_rule_load(
            has_surfaces=bool(self._help_rule_surfaces),
            is_loading=self._help_rule_loading,
            load_target=self._load_help_rule_thread,
        )
        if started:
            self._help_rule_loading = True

    def _render_help_overlay(self) -> None:
        """渲染游戏规则图片覆盖层（单页显示 + 左右翻页按钮）。"""
        if not self.help_overlay_visible:
            return

        # 触发后台加载（不阻塞）
        if not self._help_rule_surfaces and not self._help_rule_loading:
            self._start_help_rule_load()

        # 半透明暗色背景遮罩
        _mask = pg.Surface((self.screen_width, self.screen_height), pg.SRCALPHA)
        _mask.fill((0, 0, 0, 190))
        self.window.blit(_mask, (0, 0))

        # 内容面板
        margin = 50
        nav_w = 72  # 左右导航按钮宽度
        content_w = self.screen_width - margin * 2
        content_h = self.screen_height - margin * 2
        content_x = margin
        content_y = margin
        content_rect = pg.Rect(content_x, content_y, content_w, content_h)
        self._help_overlay_content_rect = content_rect

        pg.draw.rect(self.window, pg.Color("#1a1a1a"), content_rect, border_radius=10)
        pg.draw.rect(
            self.window, pg.Color("#5a3a1a"), content_rect, 3, border_radius=10
        )

        # --- 加载中 / 失败 ---
        if not self._help_rule_surfaces:
            _info_font = self._font("msyh.ttc", 22)
            if self._help_rule_load_failed:
                msg = "无法加载规则图片（assets/graphics/rule/ 目录不存在）"
                _err = _info_font.render(msg, True, pg.Color("#cc4444"))
                self.window.blit(_err, _err.get_rect(center=content_rect.center))
            else:
                self._help_load_anim_frame += 1
                dots = "●" * ((self._help_load_anim_frame // 12) % 4)
                _loading = _info_font.render(
                    f"正在加载规则{dots}", True, pg.Color("#f5f0e8")
                )
                self.window.blit(
                    _loading, _loading.get_rect(center=content_rect.center)
                )
            # ESC 提示
            _hint_font = self._font("msyh.ttc", 14)
            _hint = _hint_font.render("ESC 或点击外部关闭", True, pg.Color("#888888"))
            self.window.blit(
                _hint,
                (
                    content_x + content_w - _hint.get_width() - 16,
                    content_y + content_h - _hint.get_height() - 6,
                ),
            )
            return

        total_pages = len(self._help_rule_surfaces)
        self.help_current_page = max(0, min(self.help_current_page, total_pages - 1))
        slide_surf = self._help_rule_surfaces[self.help_current_page]

        # 图片显示区（去掉左右导航按钮占用宽度）
        img_area_x = content_x + nav_w
        img_area_y = content_y + 8
        img_area_w = content_w - nav_w * 2
        img_area_h = content_h - 44  # 留底部页码区

        # 等比缩放至显示区
        sw, sh = slide_surf.get_width(), slide_surf.get_height()
        scale = min(img_area_w / max(sw, 1), img_area_h / max(sh, 1))
        dw, dh = max(1, int(sw * scale)), max(1, int(sh * scale))
        scaled_slide = pg.transform.smoothscale(slide_surf, (dw, dh))
        blit_x = img_area_x + (img_area_w - dw) // 2
        blit_y = img_area_y + (img_area_h - dh) // 2
        self.window.blit(scaled_slide, (blit_x, blit_y))

        # 页码文字（底部居中）
        _page_font = self._font("msyh.ttc", 18)
        _page_surf = _page_font.render(
            f"{self.help_current_page + 1} / {total_pages}", True, pg.Color("#f5f0e8")
        )
        self.window.blit(
            _page_surf,
            _page_surf.get_rect(
                centerx=content_rect.centerx, bottom=content_rect.bottom - 8
            ),
        )

        # ESC 提示
        _hint_font = self._font("msyh.ttc", 14)
        _hint = _hint_font.render("ESC 或点击外部关闭", True, pg.Color("#666666"))
        self.window.blit(
            _hint, (content_x + content_w - _hint.get_width() - 16, content_y + 6)
        )

        # 左右导航按钮
        btn_h = 100
        btn_cy = content_y + content_h // 2
        prev_rect = pg.Rect(content_x + 6, btn_cy - btn_h // 2, nav_w - 12, btn_h)
        next_rect = pg.Rect(
            content_x + content_w - nav_w + 6, btn_cy - btn_h // 2, nav_w - 12, btn_h
        )
        self._help_prev_btn = prev_rect
        self._help_next_btn = next_rect

        prev_active = self.help_current_page > 0
        next_active = self.help_current_page < total_pages - 1
        _arrow_font = self._font("msyh.ttc", 36)

        prev_color = pg.Color("#5a3a1a") if prev_active else pg.Color("#3a3a3a")
        pg.draw.rect(self.window, prev_color, prev_rect, border_radius=8)
        _prev_t = _arrow_font.render(
            "◀", True, pg.Color("#f5f0e8") if prev_active else pg.Color("#666666")
        )
        self.window.blit(_prev_t, _prev_t.get_rect(center=prev_rect.center))

        next_color = pg.Color("#5a3a1a") if next_active else pg.Color("#3a3a3a")
        pg.draw.rect(self.window, next_color, next_rect, border_radius=8)
        _next_t = _arrow_font.render(
            "▶", True, pg.Color("#f5f0e8") if next_active else pg.Color("#666666")
        )
        self.window.blit(_next_t, _next_t.get_rect(center=next_rect.center))

    def _is_mountain_terrain(self, province: object) -> bool:
        return self.combat_utils_service.is_mountain_terrain(province)

    def _is_fort_or_city(self, province: object) -> bool:
        return self.combat_utils_service.is_fort_or_city(province)

    def _is_river_crossing(self, from_id: int, to_id: int) -> bool:
        return self.combat_utils_service.is_river_crossing(self, from_id, to_id)

    def _get_attack_terrain_penalty(
        self, attacker_prov: object, target_prov: object, unit_state
    ) -> int:
        """跨河/攻山地惩罚：满足任一条件时攻击力-1（无当飞军除外）。"""
        return self.combat_utils_service.get_attack_terrain_penalty(
            self, attacker_prov, target_prov, unit_state
        )

    def _find_path_cost_ignore_mountain(self, start_id: int, target_id: int) -> int:
        """计算移动消耗：忽略山地额外消耗，但保留基础步耗和跨河消耗。"""
        return self.combat_utils_service.find_path_cost_ignore_mountain(
            self, start_id, target_id
        )

    def _find_path_ignore_mountain(self, start_id: int, target_id: int) -> list:
        """返回忽略山地消耗的最短路径（省ID列表，含首尾）。"""
        return self.combat_utils_service.find_path_ignore_mountain(
            self, start_id, target_id
        )

    def _try_apply_gexu_guard(
        self, province: object, units: List[UnitState], pre_hp_map: Dict[int, int]
    ) -> bool:
        """割须弃袍：本小回合内，魏方防御最高单位受伤时免除一次伤害（全局标志）。"""
        return self.combat_utils_service.try_apply_gexu_guard(
            self, province, units, pre_hp_map
        )

    def _has_attackable_target_for_unit(self, province: object, unit_state) -> bool:
        """判断某单位在当前位置是否存在可攻击目标。"""
        return self.combat_utils_service.has_attackable_target_for_unit(
            self, province, unit_state
        )

    def _get_base_unit_type(self, unit_type: str) -> str:
        """提取兵种的基础类型 (infantry/cavalry/archer)。"""
        return self.combat_utils_service.get_base_unit_type(unit_type)

    def _get_target_selection_key(self, unit_state) -> Tuple[int, int]:
        """计算单位的目标选择优先级 (用于伤害和混乱分配)。"""
        return self.combat_utils_service.get_target_selection_key(self, unit_state)

    def _get_unit_relationship(self, attacker_type: str, defender_type: str) -> int:
        """判断兵种克制关系。返回: 1=克制, -1=被克制, 0=中立。"""
        return self.combat_utils_service.get_unit_relationship(
            attacker_type, defender_type
        )

    def _handle_combat(self, target: object) -> None:  # target: Province
        """处理战斗逻辑。"""
        self.combat_flow_service.handle_combat(self, target)

    def _execute_combat(self, attackers: List, target_province: object) -> None:
        """执行战斗，每次点击投骰子时重新计算攻防比。"""
        self.combat_flow_service.execute_combat(self, attackers, target_province)

    def _resolve_combat(
        self, col_index: int, attackers: List, target_province: object
    ) -> None:
        """投骰子后的回调。"""
        self.combat_flow_service.resolve_combat(
            self, col_index, attackers, target_province
        )

    def _apply_damage(self, units: List[UnitState], amount: int) -> None:
        """分配伤害。"""
        self.combat_resolution_service.apply_damage(self, units, amount)

    def _apply_confusion(self, unit_tuples: List, amount: int = 1) -> None:
        """应用混乱。"""
        self.combat_resolution_service.apply_confusion(self, unit_tuples, amount)

    def _handle_retreat(self, province: object) -> None:
        """处理撤退。"""
        self.combat_resolution_service.handle_retreat(self, province)

    def _cleanup_dead_units(self, attackers: List, target: object) -> None:
        """清理战场。"""
        self.combat_resolution_service.cleanup_dead_units(attackers, target)

    def _advance_after_combat(self, attackers: List, target: object) -> None:
        """进占: 按选择顺序派出至多2个相邻进攻单位。"""
        self.combat_resolution_service.advance_after_combat(self, attackers, target)

    def _check_tianxia_guixin_victory(self) -> None:
        """
        检查是否有势力达成"天下归心"胜利条件。
        条件：民心等级达 5 级，且同时占领洛阳、成都、建邺。
        如果达成，立即显示分数屏并结束游戏。
        """
        winner = self.score_manager.check_tianxia_guixin(
            self.map_manager.provinces, self.country_stats
        )

        if winner:
            # 达成天下归心胜利
            self.turn_game_finished = True
            self.player_country = None
            self.card_manager = None
            if self.card_panel:
                self.card_panel.set_available_cards([])

            # 准备胜利信息
            if not self.score_manager_initial_recorded:
                self.score_manager.record_initial_scores(self.map_manager.provinces)
                self.score_manager_initial_recorded = True

            record = self.score_manager.get_detailed_scores(
                self.map_manager.provinces, self.country_stats
            )

            net_scores = {
                "SHU": record.shu_score - record.shu_initial,
                "WEI": record.wei_score - record.wei_initial,
                "WU": record.wu_score - record.wu_initial,
            }

            self.show_score_screen = {
                "type": "game_over",
                "record": record,
                "net_scores": net_scores,
                "tianxia_winner": winner,
            }

            # 显示胜利消息
            winner_names = {"SHU": "蜀汉", "WEI": "曹魏", "WU": "孙吴"}
            if self.info_panel:
                self.info_panel.show_message(
                    f"{winner_names.get(winner, winner)} 达成「天下归心」胜利！"
                )

    def _get_neighbors(self, unit_prov: object) -> List[object]:
        """获取邻居"""
        return self.map_manager.get_neighbors(unit_prov.province_id)

    def _handle_selection_click(self, mouse_pos: Tuple[int, int]) -> None:
        """检查鼠标是否点击到了某个己方单位。"""
        self.selection_service.handle_selection_click(
            player_country=self.player_country,
            provinces=self.map_manager.provinces,
            unit_renderer=self.unit_renderer,
            hex_side=self.hex_side,
            mouse_pos=mouse_pos,
            on_add_selection=self.add_selection,
        )

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

        # 注：AI 事件卡覆盖层现在需要玩家手动点击「确认生效」来确认，
        # 不再自动跳过，以便玩家看到 AI 抽到了哪张事件卡。

    def _render(self) -> None:
        """渲染总控：根据状态画对应的界面"""
        self.screen_render_service.render_main_scene(self)
        self.screen_render_service.render_top_overlays(self)

    def _render_console(self) -> None:
        """渲染控制台浮层（位于屏幕底部，按 ` 键开关）。"""
        self.screen_render_service.render_console(self)

    def _render_loading_screen(self) -> None:
        """画加载/开始界面。"""
        self.screen_render_service.render_loading_screen(self)

    def _render_mode_select_screen(self) -> None:
        """画选择游戏模式界面。"""
        self.screen_render_service.render_mode_select_screen(self)

    def _render_choosing_screen(self) -> None:
        """画选择势力界面。"""
        self.screen_render_service.render_choosing_screen(self)

    def _render_gameplay(self) -> None:
        self.gameplay_render_service.render_gameplay(self)

    def _render_pp_summon_panel(self) -> None:
        """绘制PP召唤子面板（居中覆盖层），并填充 self.pp_summon_btns。"""
        self.overlay_ui_service.render_pp_summon_panel(self)

    def _get_map_bounds_rect(self) -> pg.Rect:
        """基于六边形中心与边长，计算地图像素包围盒。"""
        return self.map_bounds_service.get_map_bounds_rect(
            provinces=self.map_manager.provinces,
            hex_side=self.hex_side,
            screen_width=self.screen_width,
            screen_height=self.screen_height,
        )

    def _draw_country_stats_overlay(self) -> None:
        """绘制三国民心/政治点数信息，避免与地图六边形重叠。"""
        self.country_stats_overlay_service.draw_country_stats_overlay(self)

    def _draw_evt_info_tooltip(self) -> None:
        """当鼠标悬停于国家"！"按钮时，绘制本回合已生效事件卡的多行浮窗。"""
        self.evt_info_tooltip_service.draw_evt_info_tooltip(self)

    def _draw_hover_tooltip(self) -> None:
        """Draw tooltip for hovered element."""
        self.overlay_ui_service.draw_hover_tooltip(self)

    def _get_display_name(self, key: str) -> str | None:
        """获取显示名称。"""
        return self.overlay_ui_service.get_display_name(key)

    def _draw_smooth_polyline(
        self, color: pg.Color, points: Sequence[pg.math.Vector2], width: int
    ) -> None:
        """
        绘制硬朗连接的折线（Miter Join）。
        普通的 pg.draw.lines 会有缺口，而画圆填充太圆润了。
        这个方法通过计算几何转角，生成一个完美闭合的多边形，
        让河流的转弯呈现出整齐的 120 度切角，符合六边形地图的风格。
        """
        self.polyline_render_service.draw_smooth_polyline(
            window=self.window,
            color=color,
            points=points,
            width=width,
        )

    # --- 资源构建辅助方法 (Asset Builders) -------------------------------------------------
    # 这些方法负责在游戏开始前把图片、文字预先处理好存入内存

    def _build_mode_select_assets(self) -> None:
        """准备选择游戏模式界面的文字和按钮"""
        height = self.screen_height
        width = self.screen_width

        self.mode_select_title_surface = self._render_text(
            "STLITI.TTF", int(width * 0.08), "选择模式"
        )
        self.mode_select_title_pos = (int(width * 0.32), 0)

        btn_w = int(width * 0.28)
        btn_h = int(height * 0.12)
        btn_y = int(height * 0.65)

        self.mode_single_rect = pg.Rect(int(width * 0.18), btn_y, btn_w, btn_h)
        self.mode_multi_rect = pg.Rect(int(width * 0.54), btn_y, btn_w, btn_h)

        self.mode_single_surface = self._render_text(
            "STXINGKA.TTF", int(height * 0.08), "单人游戏"
        )
        self.mode_multi_surface = self._render_text(
            "STXINGKA.TTF", int(height * 0.08), "三人游戏"
        )

        sw = self.mode_single_surface.get_width()
        sh = self.mode_single_surface.get_height()
        self.mode_single_text_pos = (
            self.mode_single_rect.centerx - sw // 2,
            self.mode_single_rect.centery - sh // 2,
        )
        mw = self.mode_multi_surface.get_width()
        mh = self.mode_multi_surface.get_height()
        self.mode_multi_text_pos = (
            self.mode_multi_rect.centerx - mw // 2,
            self.mode_multi_rect.centery - mh // 2,
        )

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

        # 加载背景图片（保持原始比例，左上角对齐屏幕）
        self.bg_image = self._load_ui_image("背景.png", None)
        # 计算缩放比例，让背景高度匹配屏幕高度
        bg_orig_width, bg_orig_height = self.bg_image.get_size()
        scale = height / bg_orig_height
        self.bg_image = pg.transform.smoothscale(
            self.bg_image, (int(bg_orig_width * scale), height)
        )

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

        labels = ["重开一局", "退出游戏", "当前各国分数", "", ""]
        actions = ["RESTART", "EXIT", "SCORE", "VOLUME", "HELP"]

        self.control_btns = []

        # 起始X坐标：右侧内边距
        current_x_right = int(width - 20)

        for label, action in zip(labels, actions):
            surf = btn_font.render(label, True, pg.Color("white"))
            base_h = surf.get_height() + 10
            # 音量/帮助按钮做成正方形（渲染时画圆）
            if action in ("VOLUME", "HELP"):
                w = h = base_h
            else:
                w = surf.get_width() + 20
                h = base_h

            x = current_x_right - w
            # 贴近底部
            y = int(height - h - 12)

            rect = pg.Rect(x, y, w, h)

            btn_color = (
                pg.Color("#1a5276")
                if action == "SCORE"
                else pg.Color("#2d6a4f")
                if action == "VOLUME"
                else pg.Color("#7b3f00")
                if action == "HELP"
                else pg.Color("#444444")
            )
            # 圆形按钮文字居中
            if action in ("VOLUME", "HELP"):
                text_pos = surf.get_rect(center=rect.center).topleft
            else:
                text_pos = (x + 10, y + 5)
            self.control_btns.append(
                {
                    "rect": rect,
                    "surface": surf,
                    "text_pos": text_pos,
                    "action": action,
                    "bg_color": btn_color,
                    "border_color": pg.Color("white"),
                    "shape": "circle" if action in ("VOLUME", "HELP") else "rect",
                }
            )

            # 往左移，留出间隙
            current_x_right -= w + 10

        # 初始化音量滑块几何信息（在按钮布局完之后计算）
        vol_btn_entry = next(
            (b for b in self.control_btns if b["action"] == "VOLUME"), None
        )
        if vol_btn_entry:
            vr = vol_btn_entry["rect"]
            slider_w, slider_h = 72, 140
            sx = vr.centerx - slider_w // 2
            sy = vr.top - slider_h - 8
            self._vol_slider_rect = pg.Rect(sx, sy, slider_w, slider_h)
            self._vol_track_top = sy + 14
            self._vol_track_bottom = sy + slider_h - 30
            self._vol_track_x = sx + slider_w // 2

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

    def _load_ui_image(self, filename: str, size: Tuple[int, int] | None) -> pg.Surface:
        """
        加载图片并缩放到指定大小。
        如果是 SVG，尽量按需加载；如果失败，回退到普通加载。
        如果 size 为 None，则返回原始尺寸的图片。
        """
        filepath = self.settings.ui_graphics_dir / filename

        # 尝试直接加载 (Pygame 2.0+ 的 SDL_image 对 SVG 支持较好，直接 load 往往比魔改稳)
        try:
            surface = pg.image.load(filepath).convert_alpha()
            # 如果指定了 size，则缩放到目标尺寸
            if size is not None:
                if surface.get_width() != size[0] or surface.get_height() != size[1]:
                    return pg.transform.smoothscale(surface, size)
            return surface
        except Exception as e:
            logger.error(f"Error loading image {filename}: {e}")
            # 返回一个洋红色的方块作为错误占位符
            err_size = size if size is not None else (100, 100)
            err_surf = pg.Surface(err_size)
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

    # ====================================================================
    # 事件卡系统 — 抽卡、效果应用、渲染
    # ====================================================================

    def _can_draw_event_card(self, country: str) -> bool:
        """判断 country 当前是否可以消耗 1 政治点数抽取事件卡。"""
        return self.event_card_service.can_draw_event_card(self, country)

    def _spend_pp(self, country: str, amount: int = 1) -> bool:
        """消耗政治点数（优先消耗临时 PP，再消耗普通 PP）。"""
        return self.event_card_service.spend_pp(self, country, amount)

    def _trigger_draw_event_card(self, country: str) -> None:
        """尝试让 country 消耗 1 政治点数抽取一张事件卡。"""
        self.event_card_service.trigger_draw_event_card(self, country)

    def _is_negative_event(self, card, country: str) -> bool:
        """判定事件卡对抽卡方 country 是否为负面效果（用于'不懈于内'）。"""
        return self.event_card_service.is_negative_event(self, card, country)

    def _confirm_event_card(self) -> None:
        """玩家点击了「确认」，执行事件卡效果。"""
        self.event_card_service.confirm_event_card(self)

    def _apply_event_card(self, card, drawer: str) -> None:
        """执行事件卡效果。"""
        self.event_card_service.apply_event_card(self, card, drawer)

    def _apply_evt_target_unit(self, prov_id: int, slot: int) -> None:
        """完成需要点击单位的事件卡效果。"""
        self.event_card_service.apply_evt_target_unit(self, prov_id, slot)

    def _apply_evt_target_province(self, prov_id: int) -> None:
        """完成需要点击地块的事件卡效果（江东铁壁）。"""
        self.event_card_service.apply_evt_target_province(self, prov_id)

    # ====================================================================
    # 事件卡覆盖层渲染
    # ====================================================================

    def _get_event_card_image(self, card_name: str) -> "pg.Surface | None":
        """按卡牌名称加载 card/ 目录下的图片，结果缓存避免重复 IO。"""
        return self.event_card_service.get_event_card_image(self, card_name)

    def _render_event_card_overlay(self) -> None:
        """绘制事件卡展示面板（模态覆盖层）。"""
        self.event_card_service.render_event_card_overlay(self)

    # ====================================================================
    # 事件卡抽取阶段管理
    # ====================================================================

    def _enter_evt_draw_phase_if_needed(self) -> None:
        """若当前为人类玩家且有政治点数，进入事件卡抽取阶段。"""
        self.event_card_service.enter_evt_draw_phase_if_needed(self)

    def _exit_evt_draw_phase(self) -> None:
        """退出事件卡抽取阶段，进入正常行动阶段。"""
        self.event_card_service.exit_evt_draw_phase(self)

    def _check_evt_draw_phase_pp(self) -> None:
        """确认/目标完成后，若 PP 耗尽则自动退出抽卡阶段。"""
        self.event_card_service.check_evt_draw_phase_pp(self)

    def _render_draw_event_btn(self) -> None:
        """事件卡抽取阶段按钮组：「抽事件卡」+ 「跳过」；等待目标选择时显示提示。"""
        self.event_card_service.render_draw_event_btn(self)

    def _tag_w_cache(self) -> int:
        """返回国家标签宽度（粗略估算）"""
        if self.player_country and self.player_country in self.country_tag_surfaces:
            return self.country_tag_surfaces[self.player_country].get_width()
        return 60
