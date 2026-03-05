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

from src.core import app_context_factory
from src.core.ai_service import AIService
from src.core.asset_build_service import AssetBuildService
from src.core.app_contexts import (
    AIAutoSelectEventTargetContext,
    AIBorderProvincesContext,
    AIRunTurnContext,
    ApplyMajorRoundChoiceContext,
    AdvanceCountryTurnContext,
    CardApplyEffectContext,
    CardCancelSelectionContext,
    CheckTianxiaVictoryContext,
    ClearForTurnSwitchContext,
    EndFullRoundContext,
    EventConfirmContext,
    EventDrawPhaseContext,
    EventTargetApplyContext,
    FinishCountryActionContext,
    RefreshSessionSkillDisplayContext,
    RemoveMajorRoundContext,
    StartMajorRoundChoiceContext,
)
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
from src.core.card_play_service import CardPlayService
from src.core.country_stats_overlay_service import CountryStatsOverlayService
from src.core.event_card_service import EventCardService
from src.core.evt_info_tooltip_service import EvtInfoTooltipService
from src.core.events import EventManager
from src.core.app_event_card_mixin import AppEventCardMixin
from src.core.gameplay_render_service import GameplayRenderService
from src.core.game_event_router_service import GameEventRouterService
from src.core.game_reset_service import GameResetService
from src.core.help_overlay_render_service import HelpOverlayRenderService
from src.core.help_rule_load_service import HelpRuleLoadService
from src.core.major_round_status_service import MajorRoundStatusService
from src.core.map_bounds_service import MapBoundsService
from src.core.music_manager import MUSIC_END_EVENT, MusicManager
from src.core.movement_service import MovementService
from src.core.overlay_ui_service import OverlayUIService
from src.core.playing_input_service import PlayingInputService
from src.core.playing_input_args_service import PlayingInputArgsService
from src.core.playing_event_orchestrator_service import PlayingEventOrchestratorService
from src.core.playing_command_service import PlayingCommandService
from src.core.polyline_render_service import PolylineRenderService
from src.core.province_query_service import ProvinceQueryService
from src.core.selection_service import SelectionService
from src.core.selection_presentation_service import SelectionPresentationService
from src.core.turn_presentation_coordinator import TurnPresentationCoordinator
from src.core.screen_render_service import ScreenRenderService
from src.core.score_screen_service import ScoreScreenService
from src.core.score_manager import ScoreManager
from src.core.state_models import CombatState, EventCardState, TurnState, UIState
from src.core.runtime_loop_service import RuntimeLoopService
from src.core.turn_orchestration_service import TurnOrchestrationService
from src.core.turn_start_orchestration_service import TurnStartOrchestrationService
from src.core.ui_render_helper_service import UIRenderHelperService
from src.core.turn_runtime_coordinator import TurnRuntimeCoordinator
from src.core.turn_resource_service import TurnResourceService
from src.core.turn_service import TurnService
from src.core.view_models import GameplayViewModel, MainSceneViewModel
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


class GameApp(AppEventCardMixin):
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
        # O1: present_frame 缩放目标 Surface（reflow 时预分配，避免逐帧 ~2.9 MB 分配）
        self._scaled_surface: pg.Surface | None = None
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
        self.card_play_service = CardPlayService()
        self.console_service = ConsoleService()
        self.combat_utils_service = CombatUtilsService()
        self.combat_flow_service = CombatFlowService()
        self.combat_resolution_service = CombatResolutionService()
        self.screen_render_service = ScreenRenderService()
        self.score_screen_service = ScoreScreenService()
        self.gameplay_render_service = GameplayRenderService()
        self.overlay_ui_service = OverlayUIService()
        self.country_stats_overlay_service = CountryStatsOverlayService()
        self.evt_info_tooltip_service = EvtInfoTooltipService()
        self.volume_ui_service = VolumeUIService()
        self.polyline_render_service = PolylineRenderService()
        self.map_bounds_service = MapBoundsService()
        self.help_rule_load_service = HelpRuleLoadService()
        self.help_overlay_render_service = HelpOverlayRenderService()
        self.game_event_router_service = GameEventRouterService()
        self.game_reset_service = GameResetService()
        self.runtime_loop_service = RuntimeLoopService()
        self.turn_orchestration_service = TurnOrchestrationService()
        self.turn_start_orchestration_service = TurnStartOrchestrationService()
        self.major_round_status_service = MajorRoundStatusService()
        self.ui_render_helper_service = UIRenderHelperService()
        self.playing_input_service = PlayingInputService()
        self.playing_input_args_service = PlayingInputArgsService()
        self.playing_event_orchestrator_service = PlayingEventOrchestratorService()
        self.playing_command_service = PlayingCommandService()
        self.asset_build_service = AssetBuildService()
        self.province_query_service = ProvinceQueryService()
        self.movement_service = MovementService()
        self.selection_service = SelectionService()
        self.selection_presentation_service = SelectionPresentationService()
        self.turn_resource_service = TurnResourceService()
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
        self._help_mask_cache_key: Tuple[int, int, int] | None = None
        self._help_mask_cache_surface: pg.Surface | None = None
        self._help_scaled_slide_cache_key: Tuple[int, int, int, int, int, int] | None = None
        self._help_scaled_slide_cache_surface: pg.Surface | None = None

        # 脏帧标志：True 时才执行完整渲染+present，False 时跳过并让出 CPU
        self._dirty: bool = True

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
        self._score_screen_cache_key: tuple | None = None
        self._score_screen_cache_surface: pg.Surface | None = None

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
        # 临时地块高亮：AI操作、召唤等动作的地图视觉反馈 {province_id: expire_ticks_ms}
        self.temp_province_highlights: dict = {}

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
        # O2: 国家统计面板布局/文字缓存（dirty-key 驱动，数据不变时跳过 font.render 和布局重算）
        self._cs_overlay_cache: dict | None = None
        # O3: 战斗判定表预渲染 Surface 缓存（字体对象 id 为 key）
        self._combat_table_cache_key: int | None = None
        self._combat_table_cache_surf: pg.Surface | None = None

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
        """委托：获取国家当前民心等级（点数即等级，支持负数）。"""
        return self.turn_resource_service.get_people_support_level(
            self.turn_state.country_stats,
            country,
        )

    def _has_confused_units_for_country(self, country: str) -> bool:
        """委托：检查该国是否有任何混乱状态的单位。"""
        return self.turn_resource_service.has_confused_units_for_country(
            self.map_manager.provinces,
            country,
        )

    def _is_special_unit(self, unit_state) -> bool:
        """委托：判断是否为特殊兵种（虎豹骑/无当飞军/解烦兵）。"""
        return self.turn_resource_service.is_special_unit(unit_state)

    def _get_pp_heal_cost(self, unit_state) -> int:
        """委托：获取回复该单位1点血量的PP消耗。"""
        return self.turn_resource_service.get_pp_heal_cost(unit_state)

    def _get_total_pp(self, country: str) -> int:
        """委托：获取国家当前可用PP总量（普通+临时）。"""
        return self.turn_resource_service.get_total_pp(
            self.turn_state.country_stats,
            self.event_card_state.evt_temp_pp,
            country,
        )

    def _pp_can_use(self, country: str) -> bool:
        """委托：PP是否满足最低使用门槛（≥1）。"""
        return self.turn_resource_service.pp_can_use(
            self.turn_state.country_stats,
            self.event_card_state.evt_temp_pp,
            country,
        )

    def _ai_cure_confused_unit(self, country: str) -> bool:
        """委托：AI 自动解除该国第一个混乱单位的混乱状态（军容严整效果）。"""
        return self.turn_resource_service.ai_cure_confused_unit(
            self.map_manager.provinces,
            country,
        )

    def _replenish_action_points(self) -> None:
        """委托：重置所有单位行动力（MP），不清除混乱状态。"""
        self.turn_resource_service.replenish_action_points(
            self.map_manager.provinces,
            self.unit_repository,
        )

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
        """委托：打出选中的卡牌。"""
        self.card_play_service.play_selected_card(self)

    def _build_card_apply_effect_context(self) -> CardApplyEffectContext:
        return app_context_factory.build_card_apply_effect_context(self)

    def _build_cancel_card_target_selection_context(self) -> CardCancelSelectionContext:
        return app_context_factory.build_cancel_card_target_selection_context(self)

    def _apply_card_effect(self, card_id: str, card_def: object) -> None:
        """委托：应用卡牌效果到指定目标后，完成消费与UI更新。"""
        self.card_play_service.apply_card_effect_with_context(
            self._build_card_apply_effect_context(),
            card_id,
            card_def,
        )

    def _apply_card_to_province(self, card_id: str, province_id: str) -> bool:
        """委托：将卡牌效果应用到指定格子。"""
        return self.card_play_service.apply_card_to_province(self, card_id, province_id)

    def _cancel_card_target_selection(self) -> None:
        """委托：取消卡牌目标选择。"""
        self.card_play_service.cancel_card_target_selection_with_context(
            self._build_cancel_card_target_selection_context()
        )

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
        """委托：开始回合制对局。"""
        self.turn_start_orchestration_service.start_turn_based_game(self, human_country)

    def _start_major_round_choice_phase(self) -> None:
        """委托：每个大回合开始加点阶段。"""
        self.turn_start_orchestration_service.start_major_round_choice_phase_with_context(
            self._build_start_major_round_choice_context()
        )

    def _apply_major_round_choice(self, country: str, choice: str) -> None:
        """委托：应用国家在大回合开始时的加点选择。"""
        self.turn_start_orchestration_service.apply_major_round_choice_with_context(
            self._build_apply_major_round_choice_context(),
            country,
            choice,
        )

    def _end_full_round(self) -> None:
        """委托：小回合结束收尾。"""
        self.turn_start_orchestration_service.end_full_round_with_context(
            self._build_end_full_round_context()
        )

    def _remove_from_major_round(
        self, card_name: str, country: str | None = None
    ) -> None:
        """委托：移除大回合显示记录。"""
        self.major_round_status_service.remove_from_major_round_with_context(
            self._build_remove_major_round_context(),
            card_name,
            country,
        )

    def _refresh_session_skill_display(self) -> None:
        """委托：刷新会话级持久技能显示。"""
        self.major_round_status_service.refresh_session_skill_display_with_context(
            self._build_refresh_session_skill_display_context()
        )

    def _build_start_major_round_choice_context(self) -> StartMajorRoundChoiceContext:
        return app_context_factory.build_start_major_round_choice_context(self)

    def _build_apply_major_round_choice_context(self) -> ApplyMajorRoundChoiceContext:
        return app_context_factory.build_apply_major_round_choice_context(self)

    def _build_end_full_round_context(self) -> EndFullRoundContext:
        return app_context_factory.build_end_full_round_context(self)

    def _build_remove_major_round_context(self) -> RemoveMajorRoundContext:
        return app_context_factory.build_remove_major_round_context(self)

    def _build_refresh_session_skill_display_context(
        self,
    ) -> RefreshSessionSkillDisplayContext:
        return app_context_factory.build_refresh_session_skill_display_context(self)

    def _show_score_screen(self, screen_type: str) -> None:
        """委托：显示分数屏幕。"""
        self.score_screen_service.show_score_screen(self, screen_type)

    def _render_score_screen(self) -> None:
        """委托：渲染分数显示屏幕。"""
        self.score_screen_service.render_score_screen(self)

    def _clear_for_turn_switch(self, keep_info_message: bool = False) -> None:
        """切换国家前清理交互状态，可选保留信息面板内容（用于保留战果）。"""
        self.turn_orchestration_service.clear_for_turn_switch_with_context(
            self._build_clear_for_turn_switch_context(),
            keep_info_message=keep_info_message,
        )

    def _advance_country_turn(self, keep_info_message: bool = False) -> None:
        """切换到下一个国家。"""
        self.turn_orchestration_service.advance_country_turn_with_context(
            self._build_advance_country_turn_context(),
            keep_info_message=keep_info_message,
        )

    def _finish_country_action(
        self, action_name: str, keep_info_message: bool = False
    ) -> None:
        """当前国家执行完一个动作后，自动轮换到下一国家。"""
        self.turn_orchestration_service.finish_country_action_with_context(
            self._build_finish_country_action_context(),
            action_name,
            keep_info_message=keep_info_message,
        )

    def _build_clear_for_turn_switch_context(self) -> ClearForTurnSwitchContext:
        return app_context_factory.build_clear_for_turn_switch_context(self)

    def _build_advance_country_turn_context(self) -> AdvanceCountryTurnContext:
        return app_context_factory.build_advance_country_turn_context(self)

    def _build_finish_country_action_context(self) -> FinishCountryActionContext:
        return app_context_factory.build_finish_country_action_context(self)

    # ---------------------------------------------------------------
    # AI TURN
    # ---------------------------------------------------------------

    def _run_ai_turn(self) -> None:
        """AI 行动：自动完成大回合加点选择 + 移动/攻击，然后结束本国回合。
        策略：先将所有内陆部队整省调往边境，全部到位后再发动进攻。
        同时会抽取事件卡、使用锦囊卡、招募部队、解除混乱。"""
        self.ai_service.run_turn_with_context(self._build_ai_run_turn_context())

    def _build_ai_run_turn_context(self) -> AIRunTurnContext:
        return app_context_factory.build_ai_run_turn_context(self)

    def _build_ai_border_provinces_context(self) -> AIBorderProvincesContext:
        return app_context_factory.build_ai_border_provinces_context(self)

    def _ai_auto_select_evt_target(self, selector_country: str) -> None:
        """AI 自动为待选目标事件卡选择目标（契约化委托）。"""
        self.ai_service.auto_select_evt_target_with_context(
            self._build_ai_auto_select_event_target_context(),
            selector_country,
        )

    def _build_ai_auto_select_event_target_context(self) -> AIAutoSelectEventTargetContext:
        return app_context_factory.build_ai_auto_select_event_target_context(self)

    def _restart_game(self) -> None:
        """重置游戏状态并返回选人界面"""
        self.game_reset_service.restart_game(
            self,
            map_manager_cls=MapManager,
            card_manager_cls=CardManager,
            event_card_deck_cls=EventCardDeck,
            game_state=GameState,
            yangtze_points_1=YANGTZE_POINTS_1,
            yangtze_points_2=YANGTZE_POINTS_2,
            yellow_river_points=YELLOW_RIVER_POINTS,
            ban_line_points=BAN_LINE_POINTS,
        )

    def run(self) -> None:
        """
        启动游戏主循环。
        这是一个死循环，直到 _running 变为 False。
        顺序：处理事件 -> 更新数据 -> 重新绘制
        """
        self.runtime_loop_service.run(self)

    def stop(self) -> None:
        """停止游戏循环，准备退出"""
        self.runtime_loop_service.stop(self)

    def _reflow_after_window_change(self) -> None:
        """更新逻辑画布到真实窗口的缩放比例与留白区域。"""
        self.runtime_loop_service.reflow_after_window_change(self)

    def _rebuild_layout_for_screen_size(self) -> None:
        """当逻辑分辨率变化时，重建地图比例、字体与UI布局。"""
        self.runtime_loop_service.rebuild_layout_for_screen_size(self)

    def _present_frame(self) -> None:
        """将逻辑画布按比例缩放并显示到真实窗口。"""
        self.runtime_loop_service.present_frame(self)

    def _to_logical_pos(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        """把真实窗口坐标转换为逻辑画布坐标。"""
        return self.runtime_loop_service.to_logical_pos(self, pos)

    def _get_logical_mouse_pos(self) -> Tuple[int, int]:
        """获取当前鼠标在逻辑画布中的坐标。"""
        return self.runtime_loop_service.get_logical_mouse_pos(self)

    def _adapt_event_to_logical(self, event: pg.event.Event) -> pg.event.Event:
        """将带坐标的鼠标事件转换到逻辑画布坐标系。"""
        return self.runtime_loop_service.adapt_event_to_logical(self, event)

    def _resize_windowed(self, width: int, height: int) -> None:
        """调整窗口模式尺寸（带边框，可拖拽，可缩放）。"""
        self.runtime_loop_service.resize_windowed(self, width, height)

    def _toggle_fullscreen_mode(self) -> None:
        """在窗口模式与真正全屏之间切换，不改系统分辨率。"""
        self.runtime_loop_service.toggle_fullscreen_mode(self)

    def _draw_global_fullscreen_btn(self) -> None:
        """在逻辑画布底部居中绘制全屏提示文字（所有界面通用）。"""
        self.runtime_loop_service.draw_global_fullscreen_btn(self)

    def _highlight_province_temp(self, prov_id: int, duration_ms: int = 2500) -> None:
        """在地图上临时高亮指定省份（黄色/橙色六边形轮廓），用于AI操作的视觉反馈。"""
        import pygame as pg
        self.temp_province_highlights[prov_id] = pg.time.get_ticks() + duration_ms

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
        """委托：获取单位类型的单字简称。"""
        return self.selection_presentation_service.get_unit_abbr(unit_type)

    def _format_unit_info(
        self, u_state, prefix: str = "", province_id: str | None = None
    ) -> str:
        """委托：通用单位信息格式化。"""
        return self.selection_presentation_service.format_unit_info(
            self,
            u_state,
            prefix=prefix,
            province_id=province_id,
        )

    def _update_selection_info(self) -> None:
        """委托：更新信息面板显示的选中单位属性。"""
        self.selection_presentation_service.update_selection_info(self)

    def handle_event(self, event: pg.event.Event) -> None:
        """
        分发处理具体的事件。
        根据当前的游戏状态（LOADING/CHOOSING/PLAYING），交给不同的函数处理。
        """
        self.game_event_router_service.handle_event(
            self,
            event,
            music_end_event=MUSIC_END_EVENT,
            game_state=GameState,
        )

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
        self.game_event_router_service.handle_loading_event(
            self,
            event,
            game_state=GameState,
        )

    def _handle_mode_select_event(self, event: pg.event.Event) -> None:
        """处理选择游戏模式界面的事件"""
        self.game_event_router_service.handle_mode_select_event(
            self,
            event,
            game_state=GameState,
        )

    def _handle_choosing_event(self, event: pg.event.Event) -> None:
        """处理选择势力界面的事件"""
        self.game_event_router_service.handle_choosing_event(self, event)

    def _handle_score_screen_event(self, event: pg.event.Event) -> None:
        """处理分数屏幕的事件"""
        self.game_event_router_service.handle_score_screen_event(
            self,
            event,
            game_state=GameState,
        )

    def _handle_playing_event(self, event: pg.event.Event) -> None:
        """处理游戏中的事件"""
        self.playing_event_orchestrator_service.handle_playing_event(self, event)

    def _execute_playing_input_commands(
        self,
        commands: list[dict],
        *,
        on_show_message: Callable[[str], None] | None,
    ) -> None:
        """执行输入服务发出的命令（阶段4：执行逻辑下沉到服务）。"""
        self.playing_command_service.execute(
            app=self,
            commands=commands,
            on_show_message=on_show_message,
        )

    def _set_help_overlay_visible(self, visible: bool) -> None:
        self.help_overlay_visible = visible

    def _reset_morale_modes(self) -> None:
        self.morale_free_move_mode = False
        self.morale_bonus_mp_mode = False
        self.morale_cure_mode = False

    def _set_pp_summon_target_prov(self, prov) -> None:
        self.pp_summon_target_prov = prov

    def _clear_pp_summon_btns(self) -> None:
        self.pp_summon_btns = []

    def _set_pp_spend_mode(self, enabled: bool) -> None:
        self.pp_spend_mode = enabled

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
        """委托：后台线程加载规则图片。"""
        self.help_overlay_render_service.load_help_rule_thread(self)

    def _start_help_rule_load(self) -> None:
        """委托：启动后台线程加载规则图片（若尚未加载）。"""
        self.help_overlay_render_service.start_help_rule_load(self)

    def _render_help_overlay(self) -> None:
        """委托：渲染游戏规则图片覆盖层（单页显示 + 左右翻页按钮）。"""
        self.help_overlay_render_service.render_help_overlay(self)

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
        self.turn_orchestration_service.check_tianxia_guixin_victory_with_context(
            self._build_check_tianxia_victory_context()
        )

    def _build_check_tianxia_victory_context(self) -> CheckTianxiaVictoryContext:
        return app_context_factory.build_check_tianxia_victory_context(self)

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
            self._dirty = True  # 战斗计时器倒计时中，持续重绘

        # 处理 AI 行动计时器
        if (
            self._ai_turn_timer is not None
            and pg.time.get_ticks() >= self._ai_turn_timer
        ):
            self._ai_turn_timer = None
            self._run_ai_turn()
            self._dirty = True  # AI 行动执行后必须重绘一次

        # AI 计时器等待期间持续重绘（显示等待提示）
        if self._ai_turn_timer is not None:
            self._dirty = True

        # 规则图片加载动画需持续重绘（点点动画）
        if self._help_rule_loading:
            self._dirty = True

        # 省份高亮淡出动画需持续重绘
        if self.temp_province_highlights:
            self._dirty = True

        # 注：AI 事件卡覆盖层现在需要玩家手动点击「确认生效」来确认，
        # 不再自动跳过，以便玩家看到 AI 抽到了哪张事件卡。

    def _render(self) -> None:
        """渲染总控：根据状态画对应的界面"""
        scene_vm = self._build_main_scene_view_model()
        self.screen_render_service.render_main_scene(self, scene_vm)
        self.screen_render_service.render_top_overlays(self)

    def _build_main_scene_view_model(self) -> MainSceneViewModel:
        """构建主场景只读视图模型。"""
        return MainSceneViewModel(
            show_score_screen=bool(self.show_score_screen),
            state=self.state,
        )

    def _build_gameplay_view_model(self) -> GameplayViewModel:
        """构建PLAYING场景只读视图模型。"""
        return GameplayViewModel(
            major_round=self.major_round,
            minor_round=self.minor_round,
            player_country=self.player_country,
            country_labels=self.country_labels,
        )

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
        gameplay_vm = self._build_gameplay_view_model()
        self.gameplay_render_service.render_gameplay(self, gameplay_vm)

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
        self.asset_build_service.build_mode_select_assets(self)

    def _build_loading_assets(self) -> None:
        """准备加载界面的图片和文字"""
        self.asset_build_service.build_loading_assets(self)

    def _build_choosing_assets(self) -> None:
        """准备选人界面的图片和文字"""
        self.asset_build_service.build_choosing_assets(self)

    def _build_play_assets(self) -> None:
        """准备游戏主界面的图片（箭头、标签等）"""
        self.asset_build_service.build_play_assets(
            self,
            yangtze_points_1=YANGTZE_POINTS_1,
            yangtze_points_2=YANGTZE_POINTS_2,
            yellow_river_points=YELLOW_RIVER_POINTS,
            ban_line_points=BAN_LINE_POINTS,
        )

    def _is_hovering_ban_line(self, mouse_pos: Tuple[int, int]) -> bool:
        """检查鼠标是否悬停在黑线上"""
        return self.ui_render_helper_service.is_hovering_ban_line(self, mouse_pos)

    def _is_hovering_river(self, mouse_pos: Tuple[int, int]) -> bool:
        """检查鼠标是否悬停在河流上"""
        return self.ui_render_helper_service.is_hovering_river(self, mouse_pos)

    def _is_hovering_polyline(self, mouse_pos: Tuple[int, int], polylines_list) -> bool:
        """通用检查鼠标是否悬停在某组Polyline上"""
        return self.ui_render_helper_service.is_hovering_polyline(
            self,
            mouse_pos,
            polylines_list,
        )

    # --- 辅助工具方法 (Helpers) --------------------------------------------------------

    def _scale_points(
        self, normalized_points: Sequence[Tuple[float, float]]
    ) -> List[pg.math.Vector2]:
        """
        将逻辑坐标转换为屏幕像素坐标。
        逻辑坐标 -> (乘以边长) -> 像素坐标
        Y轴需要额外乘以 根号3，这是六边形几何的特性。
        """
        return self.ui_render_helper_service.scale_points(self, normalized_points)

    def _load_ui_image(self, filename: str, size: Tuple[int, int] | None) -> pg.Surface:
        """
        加载图片并缩放到指定大小。
        如果是 SVG，尽量按需加载；如果失败，回退到普通加载。
        如果 size 为 None，则返回原始尺寸的图片。
        """
        return self.ui_render_helper_service.load_ui_image(self, filename, size)

    def _font(self, filename: str, size: int) -> pg.font.Font:
        """加载字体"""
        return self.ui_render_helper_service.font(self, filename, size)

    def _render_text(
        self, filename: str, size: int, text: str, color: pg.Color | str = "black"
    ) -> pg.Surface:
        """使用指定字体和大小渲染一段文字，返回图片表面"""
        return self.ui_render_helper_service.render_text(
            self,
            filename,
            size,
            text,
            color,
        )

    def _tag_w_cache(self) -> int:
        """返回国家标签宽度（粗略估算）"""
        if self.player_country and self.player_country in self.country_tag_surfaces:
            return self.country_tag_surfaces[self.player_country].get_width()
        return 60
