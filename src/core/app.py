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
from src.core.score_manager import ScoreManager
from src.game_objects.card import CardManager, CardRepository
from src.game_objects.card_effects import CardEffectManager
from src.game_objects.event_card import EventCardDeck, EventCardDef
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
        self.screen_width = display_info.current_w
        self.screen_height = display_info.current_h
        flags = pg.NOFRAME if settings.borderless else 0
        self.window = pg.display.set_mode(
            (self.screen_width, self.screen_height), flags
        )
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

        # 计算六边形格子的边长，使其刚好能铺满屏幕高度的一部分
        self.hex_side = self.screen_height * 2 / (19 * SQRT3)

        # 初始状态设为 LOADING
        self.state = GameState.LOADING
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

        # 事件卡单位/地块目标选择
        self.selecting_evt_target: bool = False
        self.pending_evt_card_id: str | None = None
        self.pending_evt_drawer: str | None = None

        # ---- 小回合级别标志（_advance_country_turn 时清除） ----
        self.evt_flag_liukang: bool = False  # 联刘抗曹：SHU/WU 本小回合不互攻
        self.evt_flag_she_hushu: bool = False  # 舍身护主：吴防御时全部+1
        self.evt_flag_hu_recruit: bool = False  # 胡人袭扰：魏本小回合禁止招募
        self.evt_flag_wuwei: bool = False  # 吴魏媾和：东吴本小回合不能攻魏
        self.evt_temp_pp: Dict[str, int] = {}  # 老骥伏枥：临时政治点数（key=country）

        # ---- 大回合级别标志（_end_full_round 时清除） ----
        self.evt_flag_hefei: bool = False  # 合肥十万：吴攻魏骰点-1
        self.evt_flag_all_attack: bool = False  # 奖率三军：全军进攻骰点+1

        # ---- 五子良将 ----
        self.evt_wuzi_rounds: int = 0  # 剩余生效小回合数
        self.evt_wuzi_bonus: int = 0  # 当前累积骰点加成（max 3）

        # ---- 跨次抽卡标志 ----
        self.evt_xingluo_active: bool = (
            False  # 星落秋风已触发（等下次隆中定计额外+1 PP）
        )
        self.evt_laomaikuai_active: bool = False  # 老迈昏聩已触发（下次江东才俊无效）

        # ---- 会话级持久技能标志 ----
        self.evt_lonzhong_skill: int = 0  # 蜀汉"隆中定计"攻吴骰+N（可叠加）
        self.evt_jingzhu_skill: int = 0  # 东吴"荆州之主"攻蜀骰+N（可叠加）
        self.evt_yishen_skill: bool = False  # 蜀汉"一身是胆"技能（全局唯一）
        self.evt_yishen_used: bool = False  # 一身是胆本次战斗是否已使用

        # 不懈于内：下次抽卡若负效果无效
        self.evt_draw_again_safe: bool = False

        # 本小回合各国已生效事件卡记录 {country: [(card_name, card_desc), ...]}
        self.evt_applied_this_round: Dict[str, List[Tuple[str, str]]] = {}
        # 各国"！"悬停按钮区域（每帧由 _draw_country_stats_overlay 刷新）
        self.evt_info_btns: Dict[str, pg.Rect] = {}

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

    def _get_people_support_level(self, country: str) -> int:
        """获取国家当前民心等级（点数即等级，支持负数）"""
        return self.country_stats.get(country, {}).get("people_support", 0)

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
        pp = self.country_stats.get(country, {}).get("political_points", 0)
        temp = self.evt_temp_pp.get(country, 0)
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

        # 记录开局分数（在游戏真正开始时）
        self.score_manager.record_initial_scores(self.map_manager.provinces)
        self.score_manager_initial_recorded = True

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
            # 民心等级提升后，检查是否达成"天下归心"胜利条件
            self._check_tianxia_guixin_victory()
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
            # 加点完成后，第一个行动国进入事件卡抽取阶段
            self._enter_evt_draw_phase_if_needed()

    def _end_full_round(self) -> None:
        """三个国家都行动完后触发：清理回合效果并复位行动力。"""
        self.card_effect_manager.clear_all_effects()
        self._replenish_action_points()
        # 大回合级事件标志清除
        self.evt_flag_hefei = False
        self.evt_flag_all_attack = False
        self.evt_yishen_used = False  # 一身是胆使用标志重置（每大回合重置）

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

        self.pending_post_move_attack = False
        self.pending_attacker = None
        self.selecting_card_target = False
        self.selected_card_for_effect = None
        # 小回合级事件标志清除
        self.evt_flag_liukang = False
        self.evt_flag_she_hushu = False
        self.evt_flag_hu_recruit = False
        self.evt_flag_wuwei = False
        self.evt_temp_pp = {}  # 临时政治点数回合结束消失
        self.evt_applied_this_round = {}  # 清除本小回合事件卡记录
        self.selecting_evt_target = False
        self.pending_evt_card_id = None
        self.pending_evt_drawer = None
        # 五子良将递减计数
        if self.evt_wuzi_rounds > 0:
            self.evt_wuzi_rounds -= 1
            if self.evt_wuzi_rounds == 0:
                self.evt_wuzi_bonus = 0
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
                # 大回合结束：民心4级效果（军容严整）各国可解除一个混乱单位
                for _c in list(self.turn_order):
                    if self._get_people_support_level(_c) >= 4:
                        if _c == self.human_country:
                            self.morale_lv4_pending[_c] = True
                        else:
                            self._ai_cure_confused_unit(_c)
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
                # 显示游戏结束分数
                self._show_score_screen("game_over")
                return

        self.player_country = self.turn_order[self.turn_index]
        self.card_manager = self.card_managers[self.player_country]
        self._update_card_panel()

        # 进入事件卡抽取阶段（若为人类玩家且有政治点数）
        self._enter_evt_draw_phase_if_needed()

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

    def _ai_get_main_threat_country(self, country: str) -> str | None:
        """返回在AI边境线对面兵力最多的敌国。
        统计与AI领土相邻（1.1格内）的所有敌省的兵力，按国家累加，取最多的那个。"""
        unit_stride = SQRT3 * self.hex_side
        own_provs = [p for p in self.map_manager.provinces if p.country == country]
        threat: dict[str, int] = {}
        for prov in self.map_manager.provinces:
            if prov.country == country or not prov.country:
                continue
            p_center = prov.center_cache or prov.compute_center(self.hex_side)
            for own in own_provs:
                o_center = own.center_cache or own.compute_center(self.hex_side)
                if dist(p_center, o_center) <= unit_stride * 1.1:
                    threat[prov.country] = threat.get(prov.country, 0) + len(prov.units)
                    break  # 每个敌省只计一次
        if not threat:
            return None
        return max(threat, key=lambda c: threat[c])

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

        # --- 民心等级效果（AI自动处理）---
        _ai_support = self._get_people_support_level(country)

        # 民心2级（令行禁止）：每大回合免费移动1格
        if (
            _ai_support >= 2
            and self.morale_lv2_used.get(country, 0) != self.major_round
        ):
            border_provs_lv2 = self._ai_get_border_provinces(country)
            _did_free_move = False
            for _bp in border_provs_lv2:
                if not _bp.units:
                    continue
                _dest = self._ai_pick_move_target(_bp, _bp.units[0], border_provs_lv2)
                if (
                    _dest
                    and self.map_manager.find_path_cost(
                        _bp.province_id, _dest.province_id
                    )
                    == 1
                ):
                    self.morale_free_move_mode = True
                    self.selected_units = [(_bp.province_id, 0)]
                    self._handle_movement(_dest)
                    _did_free_move = True
                    break
            # 无论是否找到目标都消耗额度（避免无限尝试）
            self.morale_lv2_used[country] = self.major_round
            self.morale_free_move_mode = False

        # 民心3级（老乡指路）：每大回合给一个边境单位+1行动力
        if (
            _ai_support >= 3
            and self.morale_lv3_used.get(country, 0) != self.major_round
        ):
            _border_p3 = self._ai_get_border_provinces(country)
            for _bp3 in _border_p3:
                if _bp3.units:
                    _bp3.units[0].mp += 1
                    self.morale_lv3_used[country] = self.major_round
                    break
            else:
                self.morale_lv3_used[country] = (
                    self.major_round
                )  # no units, still consume

        # 民心4级（军容严整）：大回合结束时解除混乱 - 在 _advance_country_turn 中处理

        # --- 阶段0：处理事件卡目标选择（needs_target 类卡牌的 AI 自动选择） ---
        if self.selecting_evt_target and self.pending_evt_card_id:
            card_def = self.event_card_deck.get_definition(self.pending_evt_card_id)
            if card_def:
                if card_def.target_type == "unit":
                    # AI 策略：优先选边境有部队的省，再退而求其次选任意己方单位
                    chosen_prov = None
                    chosen_slot = 0
                    border_provs = self._ai_get_border_provinces(country)
                    border_ids = {p.province_id for p in border_provs}
                    for prov in self.map_manager.provinces:
                        if prov.country == country and prov.units:
                            if prov.province_id in border_ids:
                                chosen_prov = prov
                                break
                    if chosen_prov is None:
                        for prov in self.map_manager.provinces:
                            if prov.country == country and prov.units:
                                chosen_prov = prov
                                break
                    if chosen_prov:
                        self._apply_evt_target_unit(
                            chosen_prov.province_id, chosen_slot
                        )
                    else:
                        # 无可用单位，直接清除状态
                        self.selecting_evt_target = False
                        self.pending_evt_card_id = None
                        self.pending_evt_drawer = None
                        self._check_evt_draw_phase_pp()
                elif card_def.target_type == "province":
                    # AI 策略：选单位最多的己方省
                    chosen_prov = max(
                        (
                            p
                            for p in self.map_manager.provinces
                            if p.country == country and p.units
                        ),
                        key=lambda p: len(p.units),
                        default=None,
                    )
                    if chosen_prov:
                        self._apply_evt_target_province(chosen_prov.province_id)
                    else:
                        self.selecting_evt_target = False
                        self.pending_evt_card_id = None
                        self.pending_evt_drawer = None
                        self._check_evt_draw_phase_pp()
            else:
                # 找不到卡定义，清除
                self.selecting_evt_target = False
                self.pending_evt_card_id = None
                self.pending_evt_drawer = None
            # 目标选择完毕，本帧 AI 行动结束，等待下一帧正常行动
            return

        # --- 阶段1：大回合加点（如果还未选择） ---
        if self.major_round_choice_pending:
            for c in list(self.turn_order):
                # 只代替 AI 国家自动选择，玩家国家必须等玩家手动点击
                if c == self.human_country:
                    continue
                if not self.major_round_choice_done.get(c, False):
                    self._apply_major_round_choice(c, "support")
            # 若玩家还未选择，等待玩家操作，暂不继续 AI 行动
            if self.major_round_choice_pending:
                self._ai_turn_timer = pg.time.get_ticks() + 300
                return

        # 预计算本国边境省集合
        border_provs = self._ai_get_border_provinces(country)
        border_ids = {p.province_id for p in border_provs}

        # 收集所有己方有行动力的单位，按"是否在边境"分两组
        border_units = []  # (province, slot_idx, unit_state)
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

        # 计算本国的主要威胁方，让边境单位优先面向该国行动
        _main_threat = self._ai_get_main_threat_country(country)

        def _border_threat_key(item):
            """优先选与主威胁国相邻的边境省"""
            prov, _, _ = item
            p_c = prov.center_cache or prov.compute_center(self.hex_side)
            unit_stride = SQRT3 * self.hex_side
            for ep in self.map_manager.provinces:
                if ep.country == _main_threat:
                    ec = ep.center_cache or ep.compute_center(self.hex_side)
                    if dist(p_c, ec) <= unit_stride * 1.1:
                        return 0  # 与主威胁国相邻 → 最高优先
            return 1

        border_units.sort(key=_border_threat_key)

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
                    # 检查回合是否已推进（_handle_movement 内部可能静默失败而不调用 _finish_country_action）
                    if self.player_country != country:
                        return  # 移动成功，回合已推进
                    # 移动失败（如堆叠满员），继续尝试下一个单位

        # --- 阶段3：所有单位均已在边境（或内陆无法移动），发动攻击 ---
        for province, slot_idx, unit_state in border_units:
            if self._has_attackable_target_for_unit(province, unit_state):
                target = self._ai_pick_attack_target(province, unit_state)
                if target is not None:
                    if self._ai_execute_combat(province, slot_idx, target):
                        # _execute_combat 已调用 _finish_country_action，直接返回
                        return

        # --- 阶段4：无法攻击，边境单位向敌省压进 ---
        for province, slot_idx, unit_state in border_units:
            dest = self._ai_pick_move_target(province, unit_state, None)
            if dest is not None:
                self.selected_units = [(province.province_id, slot_idx)]
                self._handle_movement(dest)
                # 检查回合是否已推进（_handle_movement 内部可能静默失败而不调用 _finish_country_action）
                if self.player_country != country:
                    return  # 移动成功，回合已推进
                # 移动失败（如堆叠满员），继续尝试下一个单位

        # --- 阶段4.5：移动/攻击都无法进行时，才考虑使用政治点数（PP）---
        # 治疗优先，其次才招募新兵；不抢占移动/攻击机会
        _ai_pp_used = False
        if self._pp_can_use(country):
            # 1) 治疗伤兵
            for _prov in self.map_manager.provinces:
                if _prov.country != country:
                    continue
                for _u in _prov.units:
                    if _u.hp < 2:
                        _cost = self._get_pp_heal_cost(_u)
                        if self._get_total_pp(country) >= _cost:
                            self._spend_pp(country, _cost)
                            _u.hp += 1
                            _ai_pp_used = True
            # 2) 有剩余PP则招募新兵到边境省
            _can_recruit = not (
                getattr(self, "evt_flag_hu_recruit", False) and country == "WEI"
            )
            if _can_recruit and self._get_total_pp(country) >= 1:
                _recruit_target = None
                _border_pset = {
                    p.province_id for p in self._ai_get_border_provinces(country)
                }
                for _rp in self.map_manager.provinces:
                    if _rp.country == country and len(_rp.units) < self.MAX_UNIT_STACK:
                        if _rp.province_id in _border_pset:
                            _recruit_target = _rp
                            break
                if _recruit_target is None:
                    for _rp in self.map_manager.provinces:
                        if (
                            _rp.country == country
                            and len(_rp.units) < self.MAX_UNIT_STACK
                        ):
                            _recruit_target = _rp
                            break
                if _recruit_target is not None:
                    _pp_left = self._get_total_pp(country)
                    if _pp_left >= 2:
                        new_u = UnitState("infantry")
                        new_u.hp = 2
                        self._spend_pp(country, 2)
                    else:
                        new_u = UnitState("infantry")
                        new_u.hp = 1
                        self._spend_pp(country, 1)
                    _recruit_target.units.append(new_u)
                    _ai_pp_used = True
            if _ai_pp_used:
                action_taken = True

        # --- 阶段5：结束本国回合 ---
        self._finish_country_action(
            f"AI({country})行动", keep_info_message=action_taken
        )

    def _ai_pick_attack_target(self, province, unit_state):
        """AI 选择攻击目标：优先进攻主要威胁国，其次选血量最少的相邻敌省。"""
        definition = self.unit_repository.get_definition(unit_state.unit_type)
        unit_stride = SQRT3 * self.hex_side
        allowed_range_px = definition.range * unit_stride * 1.1
        p_center = (
            province.center_cache
            if province.center_cache
            else province.compute_center(self.hex_side)
        )
        atk_c = province.country
        main_threat = self._ai_get_main_threat_country(atk_c)

        best = None
        best_score = (2, float("inf"))  # (非主威胁, 兵力)
        for target in self.map_manager.provinces:
            if target.country == province.country:
                continue
            if not target.units and not self._is_fort_or_city(target):
                continue
            def_c = target.country
            # 联刘抗曹：蜀汉与东吴本小回合不能互相攻击
            if self.evt_flag_liukang:
                if (atk_c == "SHU" and def_c == "WU") or (
                    atk_c == "WU" and def_c == "SHU"
                ):
                    continue
            # 吴魏媾和：东吴本小回合不能进攻曹魏
            if self.evt_flag_wuwei and atk_c == "WU" and def_c == "WEI":
                continue
            t_center = (
                target.center_cache
                if target.center_cache
                else target.compute_center(self.hex_side)
            )
            if dist(p_center, t_center) <= allowed_range_px:
                # 主威胁国优先级0，其余1
                priority = 0 if (main_threat and def_c == main_threat) else 1
                score = (priority, len(target.units))  # 越少越软
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

        # 决定"目标锚点"：内陆单位以边境省为锚（优先朝主威胁国方向的边境省），边境单位以最近敌省为锚
        anchor_center = None
        if border_provs:
            main_threat = self._ai_get_main_threat_country(province.country)
            unit_stride = SQRT3 * self.hex_side
            # 第一轮：找临近主威胁国的边境省中最近的
            best_d_threat = float("inf")
            best_d_any = float("inf")
            anchor_threat = None
            anchor_any = None
            for bp in border_provs:
                if bp.province_id == province.province_id:
                    continue
                bc = bp.center_cache or bp.compute_center(self.hex_side)
                d = dist(p_center, bc)
                # 检查该边境省是否与主威胁国相邻
                is_facing_threat = False
                if main_threat:
                    for ep in self.map_manager.provinces:
                        if ep.country == main_threat:
                            ec = ep.center_cache or ep.compute_center(self.hex_side)
                            if dist(bc, ec) <= unit_stride * 1.1:
                                is_facing_threat = True
                                break
                if is_facing_threat and d < best_d_threat:
                    best_d_threat = d
                    anchor_threat = bc
                if d < best_d_any:
                    best_d_any = d
                    anchor_any = bc
            anchor_center = anchor_threat or anchor_any

        if anchor_center is None:
            # 回退：以最近敌省为锚，优先瞄准主威胁国
            main_threat = self._ai_get_main_threat_country(province.country)
            best_d = float("inf")
            best_d_fallback = float("inf")
            anchor_center_threat = None
            anchor_center_fallback = None
            for target in self.map_manager.provinces:
                if target.country == province.country or not target.country:
                    continue
                tc = target.center_cache or target.compute_center(self.hex_side)
                d = dist(p_center, tc)
                if main_threat and target.country == main_threat:
                    if d < best_d:
                        best_d = d
                        anchor_center_threat = tc
                else:
                    if d < best_d_fallback:
                        best_d_fallback = d
                        anchor_center_fallback = tc
            anchor_center = anchor_center_threat or anchor_center_fallback

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
        # 4.5 重置三国政治点数和民心
        self.country_stats = {
            country: {"people_support": 0, "political_points": 0}
            for country in self.turn_order
        }
        # 5. 重置事件卡系统（重新开局）
        from settings import SETTINGS as settings_module

        self.event_card_deck = EventCardDeck(settings_module.event_cards_file)
        self.event_card_overlay = None
        self.evt_overlay_ok_btn = None
        self.selecting_evt_target = False
        self.pending_evt_card_id = None
        self.pending_evt_drawer = None
        self.evt_flag_liukang = False
        self.evt_flag_she_hushu = False
        self.evt_flag_hu_recruit = False
        self.evt_flag_wuwei = False
        self.evt_temp_pp = {}
        self.evt_flag_hefei = False
        self.evt_flag_all_attack = False
        self.evt_wuzi_rounds = 0
        self.evt_wuzi_bonus = 0
        self.evt_xingluo_active = False
        self.evt_laomaikuai_active = False
        self.evt_lonzhong_skill = 0
        self.evt_jingzhu_skill = 0
        self.evt_yishen_skill = False
        self.evt_yishen_used = False
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

        # 若已有选中单位且来自不同格子，先清空再选新格子（强制同格操作）
        if self.selected_units:
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
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                # 如果正在选择民心效果目标，取消该模式
                if (
                    self.morale_free_move_mode
                    or self.morale_bonus_mp_mode
                    or self.morale_cure_mode
                ):
                    self.morale_free_move_mode = False
                    self.morale_bonus_mp_mode = False
                    self.morale_cure_mode = False
                    if self.info_panel:
                        self.info_panel.show_message("已取消民心效果操作")
                # 如果在PP召唤子面板中，先退回子面板；否则退出整个PP模式
                elif self.pp_spend_mode:
                    if self.pp_summon_target_prov is not None:
                        self.pp_summon_target_prov = None
                        self.pp_summon_btns = []
                        if self.info_panel:
                            self.info_panel.show_message("已取消召唤选择，可继续使用PP")
                    else:
                        self.pp_spend_mode = False
                        if self.info_panel:
                            self.info_panel.show_message(
                                "已退出PP行动模式（回合未结束，可继续操作）"
                            )
                # 如果正在选择卡牌目标，取消目标选择
                elif self.selecting_card_target:
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
                # ---- 事件卡覆盖层：优先处理（模态） ----
                if self.event_card_overlay:
                    if self.evt_overlay_ok_btn and self.evt_overlay_ok_btn.collidepoint(
                        event.pos
                    ):
                        self._confirm_event_card()
                    return

                # 0.0 检查功能按钮
                for btn in getattr(self, "control_btns", []):
                    if btn["rect"].collidepoint(event.pos):
                        action = btn["action"]
                        if action == "EXIT":
                            self.stop()
                        elif action == "RESTART":
                            self._restart_game()
                        elif action == "SCORE":
                            if self.state == GameState.PLAYING:
                                self._show_score_screen("wei_turn")
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

                # 0.0y 事件卡抽取阶段：仅允许「抽取」和「跳过」，阻挡所有其他操作
                # 例外：若正在等待玩家点选事件卡目标，放行到下方目标选择处理
                if self.evt_draw_phase and not self.selecting_evt_target:
                    if (
                        self.evt_skip_draw_btn_rect
                        and self.evt_skip_draw_btn_rect.collidepoint(event.pos)
                    ):
                        self._exit_evt_draw_phase()
                        return
                    if (
                        self.draw_event_btn_rect
                        and self.draw_event_btn_rect.collidepoint(event.pos)
                    ):
                        self._trigger_draw_event_card(self.player_country)
                        # 若抽卡未弹出覆盖层（牌堆空/安全抽失败），立即检查并决定是否退出阶段
                        # 若已弹出覆盖层，确认时由 _confirm_event_card → _check_evt_draw_phase_pp 处理
                        if not self.event_card_overlay:
                            self._check_evt_draw_phase_pp()
                        return
                    # 点击到其他区域：提示玩家
                    if self.info_panel:
                        self.info_panel.show_message("请先完成事件卡阶段（抽取或跳过）")
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

                # 0.05 事件卡目标选择
                if self.selecting_evt_target and self.pending_evt_card_id:
                    card_def = self.event_card_deck.get_definition(
                        self.pending_evt_card_id
                    )
                    # 选择方 = pending_evt_drawer（卡牌所属国）
                    selector = self.pending_evt_drawer or self.player_country
                    if card_def and card_def.target_type == "unit":
                        target_unit = self._get_unit_slot_at(event.pos)
                        if target_unit:
                            prov_id, slot_idx = target_unit
                            prov = self.map_manager.get_by_id(prov_id)
                            if prov and prov.country == selector:
                                self._apply_evt_target_unit(prov_id, slot_idx)
                            else:
                                cn = self.country_labels.get(selector, selector)
                                if self.info_panel:
                                    self.info_panel.show_message(f"请点击{cn}的单位")
                        else:
                            if self.info_panel:
                                cn = self.country_labels.get(selector, selector)
                                self.info_panel.show_message(f"请点击{cn}的单位")
                        return
                    elif card_def and card_def.target_type == "province":
                        prov = self._get_province_at(event.pos)
                        if prov and prov.country == selector:
                            self._apply_evt_target_province(prov.province_id)
                        else:
                            cn = self.country_labels.get(selector, selector)
                            if self.info_panel:
                                self.info_panel.show_message(f"请点击{cn}的地块")
                        return

                # 0.06 抽事件卡按钮
                if self.draw_event_btn_rect and self.draw_event_btn_rect.collidepoint(
                    event.pos
                ):
                    self._trigger_draw_event_card(self.player_country)
                    return

                # 0.07 使用政治点数（PP）系统
                # -- 入口按钮 --
                if self.pp_btn_rect and self.pp_btn_rect.collidepoint(event.pos):
                    if self._pp_can_use(self.player_country):
                        self.pp_spend_mode = True
                        if self.info_panel:
                            self.info_panel.show_message(
                                "PP行动：左键点击受伤己方单位回血，右键点击己方地块召唤部队",
                                duration=3.0,
                            )
                    else:
                        self.info_panel.show_message("政治点数不足（需≥1才可使用）")
                    return

                # -- 模式内操作 --
                if self.pp_spend_mode:
                    # "结束行动"按钮
                    if (
                        self.pp_spend_end_btn_rect
                        and self.pp_spend_end_btn_rect.collidepoint(event.pos)
                    ):
                        self.pp_spend_mode = False
                        self.pp_summon_target_prov = None
                        self.pp_summon_btns = []
                        self._finish_country_action("使用政治点数")
                        return

                    # 召唤子面板按钮
                    if self.pp_summon_target_prov is not None:
                        for _sbtn in self.pp_summon_btns:
                            if _sbtn["rect"].collidepoint(event.pos):
                                if _sbtn["unit_type"] is None:
                                    # 取消召唤
                                    self.pp_summon_target_prov = None
                                    self.pp_summon_btns = []
                                    if self.info_panel:
                                        self.info_panel.show_message("已取消召唤")
                                elif _sbtn["enabled"]:
                                    _tprov = self.pp_summon_target_prov
                                    _utype = _sbtn["unit_type"]
                                    _uhp = _sbtn["hp"]
                                    _ucost = _sbtn["cost"]
                                    if (
                                        self.evt_flag_hu_recruit
                                        and self.player_country == "WEI"
                                    ):
                                        if self.info_panel:
                                            self.info_panel.show_message(
                                                "胡人袭扰：本回合魏国不能召唤新部队"
                                            )
                                    elif len(_tprov.units) >= MAX_UNIT_STACK:
                                        if self.info_panel:
                                            self.info_panel.show_message(
                                                "该地块部队已满（最多3支）"
                                            )
                                    elif self._spend_pp(self.player_country, _ucost):
                                        try:
                                            _udef = self.unit_repository.get_definition(
                                                _utype
                                            )
                                            _nu = UnitState(_utype)
                                            _nu.hp = _uhp
                                            _nu.mp = _udef.move
                                            _tprov.units.append(_nu)
                                            self.map_manager.invalidate_cache()
                                            _remain = self._get_total_pp(
                                                self.player_country
                                            )
                                            _uname = {
                                                "infantry": "步兵",
                                                "cavalry": "骑兵",
                                                "archer": "弓兵",
                                            }.get(_utype, _utype)
                                            if self.info_panel:
                                                self.info_panel.show_message(
                                                    f"在{_tprov.name}召唤了{_uname}（{_uhp}血），剩余PP：{_remain}"
                                                )
                                        except Exception as _e:
                                            logger.exception("PP召唤失败")
                                    else:
                                        if self.info_panel:
                                            self.info_panel.show_message("政治点数不足")
                                else:
                                    if self.info_panel:
                                        self.info_panel.show_message(
                                            "政治点数不足以执行此操作"
                                        )
                                # 关闭子面板（无论操作是否成功）
                                self.pp_summon_target_prov = None
                                self.pp_summon_btns = []
                                return
                        return  # 在召唤面板模式时，消耗掉所有点击

                    # 无召唤面板时：左键点击己方受伤单位回血
                    _unit_hit = self._get_unit_slot_at(event.pos)
                    if _unit_hit:
                        _hpid, _hslot = _unit_hit
                        _hprov = self.map_manager.get_by_id(_hpid)
                        if (
                            _hprov
                            and _hprov.country == self.player_country
                            and _hslot < len(_hprov.units)
                        ):
                            _hu = _hprov.units[_hslot]
                            if _hu.hp >= 2:
                                if self.info_panel:
                                    self.info_panel.show_message(
                                        "该单位已满血，无需回复"
                                    )
                            else:
                                _hcost = self._get_pp_heal_cost(_hu)
                                if self._get_total_pp(self.player_country) < _hcost:
                                    _utp = (
                                        "特殊" if self._is_special_unit(_hu) else "普通"
                                    )
                                    if self.info_panel:
                                        self.info_panel.show_message(
                                            f"政治点数不足（{_utp}单位回血需{_hcost}PP）"
                                        )
                                elif self._spend_pp(self.player_country, _hcost):
                                    _hu.hp += 1
                                    _remain2 = self._get_total_pp(self.player_country)
                                    _utp2 = (
                                        "特殊" if self._is_special_unit(_hu) else "普通"
                                    )
                                    if self.info_panel:
                                        self.info_panel.show_message(
                                            f"{_utp2}单位回复1血（消耗{_hcost}PP），剩余PP：{_remain2}"
                                        )
                        else:
                            if self.info_panel:
                                self.info_panel.show_message("请点击己方受伤单位")
                    return  # pp_spend_mode下，消耗掉所有左键点击

                # 0.08 民心等级效果按钮（令行禁止 / 老乡指路 / 军容严整）
                if self.morale_lv2_btn_rect and self.morale_lv2_btn_rect.collidepoint(
                    event.pos
                ):
                    self.morale_free_move_mode = True
                    if self.info_panel:
                        self.info_panel.show_message(
                            "令行禁止：请选中1个单位，再右键点击相邻格", duration=3.0
                        )
                    return
                if self.morale_lv3_btn_rect and self.morale_lv3_btn_rect.collidepoint(
                    event.pos
                ):
                    self.morale_bonus_mp_mode = True
                    if self.info_panel:
                        self.info_panel.show_message(
                            "老乡指路：请点击一个己方单位获得+1行动力", duration=3.0
                        )
                    return
                if self.morale_lv4_btn_rect and self.morale_lv4_btn_rect.collidepoint(
                    event.pos
                ):
                    if self._has_confused_units_for_country(self.player_country):
                        self.morale_cure_mode = True
                        if self.info_panel:
                            self.info_panel.show_message(
                                "军容严整：请点击一个混乱的己方单位", duration=3.0
                            )
                    else:
                        self.morale_lv4_pending.pop(self.player_country, None)
                        if self.info_panel:
                            self.info_panel.show_message("军容严整：当前无混乱单位")
                    return

                # 0.085 民心效果目标选择（老乡指路 & 军容严整 的单位点击处理）
                if self.morale_bonus_mp_mode:
                    unit_hit = self._get_unit_slot_at(event.pos)
                    if unit_hit:
                        _prov_id, _slot = unit_hit
                        _prov = self.map_manager.get_by_id(_prov_id)
                        if (
                            _prov
                            and _prov.country == self.player_country
                            and _slot < len(_prov.units)
                        ):
                            _prov.units[_slot].mp += 1
                            self.morale_bonus_mp_mode = False
                            self.morale_lv3_used[self.player_country] = self.major_round
                            if self.info_panel:
                                self.info_panel.show_message("老乡指路：该单位行动力+1")
                        else:
                            if self.info_panel:
                                self.info_panel.show_message("请点击己方单位")
                    else:
                        if self.info_panel:
                            self.info_panel.show_message("请点击己方单位")
                    return
                if self.morale_cure_mode:
                    unit_hit = self._get_unit_slot_at(event.pos)
                    if unit_hit:
                        _prov_id, _slot = unit_hit
                        _prov = self.map_manager.get_by_id(_prov_id)
                        if (
                            _prov
                            and _prov.country == self.player_country
                            and _slot < len(_prov.units)
                        ):
                            _u = _prov.units[_slot]
                            if _u.is_confused:
                                _u.is_confused = False
                                self.morale_cure_mode = False
                                self.morale_lv4_pending.pop(self.player_country, None)
                                if self.info_panel:
                                    self.info_panel.show_message(
                                        "军容严整：混乱已解除（大回合结束奖励）"
                                    )
                            else:
                                if self.info_panel:
                                    self.info_panel.show_message(
                                        "该单位未处于混乱状态，请重新选择"
                                    )
                        else:
                            if self.info_panel:
                                self.info_panel.show_message("请点击己方单位")
                    else:
                        if self.info_panel:
                            self.info_panel.show_message("请点击混乱状态的己方单位")
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
        # PP行动模式：右键点击己方地块 → 打开召唤子面板
        if self.pp_spend_mode and self.pp_summon_target_prov is None:
            _rc_prov = self._get_province_at(pos)
            if _rc_prov and _rc_prov.country == self.player_country:
                if len(_rc_prov.units) >= MAX_UNIT_STACK:
                    if self.info_panel:
                        self.info_panel.show_message(
                            "该地块部队已满（最多3支），无法召唤"
                        )
                elif self.evt_flag_hu_recruit and self.player_country == "WEI":
                    if self.info_panel:
                        self.info_panel.show_message(
                            "胡人袭扰：本回合魏国不能召唤新部队"
                        )
                else:
                    self.pp_summon_target_prov = _rc_prov
            else:
                if self.info_panel:
                    self.info_panel.show_message("请右键点击己方地块来召唤部队")
            return  # PP模式消耗右键点击

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

        # 民心5级（箪食壶浆）：对无守军的敌方城市可以直接占领，不触发战斗
        _danshi_lv = (
            self._get_people_support_level(self.player_country)
            if self.player_country
            else 0
        )
        _city_needs_combat = self._is_fort_or_city(target_province) and not (
            _danshi_lv >= 5 and len(target_province.units) == 0
        )
        can_attack = is_enemy and (len(target_province.units) > 0 or _city_needs_combat)

        if can_attack:
            # 令行禁止自由移动模式：禁止发动攻击
            if self.morale_free_move_mode:
                self.info_panel.show_message("令行禁止：只可移动，不可攻击")
                return
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
        """处理移动逻辑：同一格子上的单位可作为整体一起移动"""
        # 1. 检查选中单位的来源（只能来自同一个格子）
        source_ids = {pid for pid, _ in self.selected_units}
        if not source_ids:
            return
        if len(source_ids) > 1:
            self.info_panel.show_message("只能移动同一格子上的部队")
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

        # 令行禁止自由移动：只能移动到直接相邻的格子（不受地形代价限制）
        if self.morale_free_move_mode:
            _lxjz_neighbors = self.map_manager._adjacency.get(source.province_id, [])
            if target.province_id not in _lxjz_neighbors:
                self.info_panel.show_message("令行禁止：只能移动到相邻格子")
                return

        moving_units = []
        unit_costs = []  # 记录扣除的行动力

        for idx in selected_indices:
            unit_state = source.units[idx]

            if not self.morale_free_move_mode:
                # 1. 检查行动力是否为0
                if unit_state.mp <= 0:
                    self.info_panel.show_message("行动力为0")
                    return

                # 2. 检查行动力是否足够
                if unit_state.mp < path_cost:
                    self.info_panel.show_message(f"行动力不足(需{path_cost})")
                    return

            moving_units.append(unit_state)
            unit_costs.append(0 if self.morale_free_move_mode else path_cost)

        # 3. 堆叠检查
        # 目标格子已有兵 + 即将移动过去的兵 > MAX_UNIT_STACK
        if len(target.units) + len(moving_units) > MAX_UNIT_STACK:
            self.info_panel.show_message("堆叠部队过多")
            return

        # 仅当“移动前可攻击”且“移动后可攻击”时，才提供移动后攻击选择
        # （根据规则：当且仅当移动前后都能攻击）
        pre_move_can_attack = (
            len(moving_units) == 1
            and selected_unit.mp > 0
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
        if moving_units:
            target.country = self.player_country
            self.map_manager.invalidate_cache()

            # 检查是否达成"天下归心"胜利条件
            self._check_tianxia_guixin_victory()

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

        # 令行禁止免费移动完成：不结束回合，继续正常行动
        if self.morale_free_move_mode:
            if self.player_country:
                self.morale_lv2_used[self.player_country] = self.major_round
            self.morale_free_move_mode = False
            self.info_panel.show_message("令行禁止：移动完成，继续行动")
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
        # ---- 事件卡进攻禁令检查 ----
        atk_c = self.player_country
        def_c = target.country
        # 联刘抗曹：蜀汉和东吴本小回合不能互相攻击
        if self.evt_flag_liukang:
            if (atk_c == "SHU" and def_c == "WU") or (atk_c == "WU" and def_c == "SHU"):
                if self.info_panel:
                    self.info_panel.show_message(
                        "「联刘抗曹」：本回合蜀汉与东吴不能互相攻击"
                    )
                return
        # 吴魏媾和：东吴本小回合不能进攻曹魏
        if self.evt_flag_wuwei and atk_c == "WU" and def_c == "WEI":
            if self.info_panel:
                self.info_panel.show_message("「吴魏媾和」：本回合东吴不能进攻曹魏")
            return

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
                # 舍身护主：吴防御时每单位+1
                if target.country == "WU" and self.evt_flag_she_hushu:
                    dfs += 1
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
                # 舍身护主：吴国防御时每个单位防御+1
                if target_province.country == "WU" and self.evt_flag_she_hushu:
                    dfs += 1
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

        # ---- 事件卡战斗骰点修正 ----
        atk_country = self.player_country  # 进攻方国家
        def_country = target_province.country  # 防守方国家

        # 奖率三军：所有进攻骰点+1（大回合级）
        if self.evt_flag_all_attack:
            attacker_dice_bonus += 1

        # 五子良将：魏国进攻时骰点+evt_wuzi_bonus（小回合递减）
        if (
            atk_country == "WEI"
            and self.evt_wuzi_bonus > 0
            and self.evt_wuzi_rounds > 0
        ):
            attacker_dice_bonus += self.evt_wuzi_bonus

        # 合肥十万：东吴进攻曹魏时骰点-1
        if atk_country == "WU" and def_country == "WEI" and self.evt_flag_hefei:
            attacker_dice_bonus -= 1

        # 隆中定计：蜀汉进攻东吴时骰点+N
        if atk_country == "SHU" and def_country == "WU" and self.evt_lonzhong_skill > 0:
            attacker_dice_bonus += self.evt_lonzhong_skill

        # 荆州之主：东吴进攻蜀汉时骰点+N
        if atk_country == "WU" and def_country == "SHU" and self.evt_jingzhu_skill > 0:
            attacker_dice_bonus += self.evt_jingzhu_skill

        # 一身是胆：蜀汉被进攻且档位低于1:1时，强制按1:1计算（自动生效）
        if (
            def_country == "SHU"
            and self.evt_yishen_skill
            and not self.evt_yishen_used
            and col_index < 1
        ):
            col_index = 1
            self.evt_yishen_skill = False  # 一次性消耗
            self.evt_yishen_used = True
            if self.info_panel:
                self.info_panel.show_message(
                    "蜀汉使用「一身是胆」：按1:1档位计算！", duration=2.0
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

            # 检查是否达成"天下归心"胜利条件
            self._check_tianxia_guixin_victory()

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
        # 如果正在显示分数屏，优先渲染
        if self.show_score_screen:
            self._render_score_screen()
            return

        if self.state == GameState.LOADING:
            self._render_loading_screen()
        elif self.state == GameState.MODE_SELECT:
            self._render_mode_select_screen()
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

    def _render_mode_select_screen(self) -> None:
        """画选择游戏模式界面"""
        self.window.fill(pg.Color("white"))
        self.window.blit(self.loading_image_right, self.loading_image_right_pos)
        self.window.blit(self.loading_image_left, self.loading_image_left_pos)
        self.window.blit(self.mode_select_title_surface, self.mode_select_title_pos)
        # 单人游戏按钮
        pg.draw.rect(
            self.window, pg.Color("#f0c040"), self.mode_single_rect, border_radius=12
        )
        self.window.blit(self.mode_single_surface, self.mode_single_text_pos)
        # 三人游戏按钮
        pg.draw.rect(
            self.window, pg.Color("#80c0f0"), self.mode_multi_rect, border_radius=12
        )
        self.window.blit(self.mode_multi_surface, self.mode_multi_text_pos)

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

        # 4.6 绘制「抽事件卡」按钮
        self._render_draw_event_btn()

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

                # --- 民心等级效果按钮（2-4级）---
                self.morale_lv2_btn_rect = None
                self.morale_lv3_btn_rect = None
                self.morale_lv4_btn_rect = None
                if (
                    self.player_country
                    and not self.pending_post_move_attack
                    and not self.morale_free_move_mode
                    and not self.morale_bonus_mp_mode
                    and not self.morale_cure_mode
                ):
                    _m_support = self._get_people_support_level(self.player_country)
                    _top_h = int(self.screen_height * 0.15)
                    _tag_x = self.country_tag_pos[0]
                    _right_x = _tag_x - 30  # 从 Tag 左侧30px 处开始向左堆叠

                    # 4级：军容严整（按钮：橙色）
                    if self.morale_lv4_pending.get(self.player_country):
                        _s = self._morale_lv4_btn_surf
                        _bw = _s.get_width() + 20
                        _bh = _s.get_height() + 10
                        _bx = _right_x - _bw
                        _by = _top_h * 5 // 6 - _bh // 2  # 第3行：下三分之一
                        self.morale_lv4_btn_rect = pg.Rect(_bx, _by, _bw, _bh)
                        _bc = (
                            pg.Color("#FF8C00")
                            if not self.morale_lv4_btn_rect.collidepoint(
                                pg.mouse.get_pos()
                            )
                            else pg.Color("#FFA500")
                        )
                        pg.draw.rect(
                            self.window, _bc, self.morale_lv4_btn_rect, border_radius=5
                        )
                        self.window.blit(
                            _s, _s.get_rect(center=self.morale_lv4_btn_rect.center)
                        )
                        _right_x = _bx - 10

                    # 3级：老乡指路（按钮：蓝色）
                    if (
                        _m_support >= 3
                        and self.morale_lv3_used.get(self.player_country, 0)
                        != self.major_round
                    ):
                        _s = self._morale_lv3_btn_surf
                        _bw = _s.get_width() + 20
                        _bh = _s.get_height() + 10
                        _bx = _right_x - _bw
                        _by = _top_h * 5 // 6 - _bh // 2  # 第3行：下三分之一
                        self.morale_lv3_btn_rect = pg.Rect(_bx, _by, _bw, _bh)
                        _bc = (
                            pg.Color("#1E90FF")
                            if not self.morale_lv3_btn_rect.collidepoint(
                                pg.mouse.get_pos()
                            )
                            else pg.Color("#87CEEB")
                        )
                        pg.draw.rect(
                            self.window, _bc, self.morale_lv3_btn_rect, border_radius=5
                        )
                        self.window.blit(
                            _s, _s.get_rect(center=self.morale_lv3_btn_rect.center)
                        )
                        _right_x = _bx - 10

                    # 2级：令行禁止（按钮：绿色）
                    if (
                        _m_support >= 2
                        and self.morale_lv2_used.get(self.player_country, 0)
                        != self.major_round
                    ):
                        _s = self._morale_lv2_btn_surf
                        _bw = _s.get_width() + 20
                        _bh = _s.get_height() + 10
                        _bx = _right_x - _bw
                        _by = _top_h * 5 // 6 - _bh // 2  # 第3行：下三分之一
                        self.morale_lv2_btn_rect = pg.Rect(_bx, _by, _bw, _bh)
                        _bc = (
                            pg.Color("#2E8B57")
                            if not self.morale_lv2_btn_rect.collidepoint(
                                pg.mouse.get_pos()
                            )
                            else pg.Color("#3CB371")
                        )
                        pg.draw.rect(
                            self.window, _bc, self.morale_lv2_btn_rect, border_radius=5
                        )
                        self.window.blit(
                            _s, _s.get_rect(center=self.morale_lv2_btn_rect.center)
                        )

                    # --- 民心按鈕 Hover 浮窗 ---
                    _morale_tt_text = None
                    _morale_tt_anchor = None
                    _mx, _my = pg.mouse.get_pos()
                    if (
                        self.morale_lv4_btn_rect
                        and self.morale_lv4_btn_rect.collidepoint(_mx, _my)
                    ):
                        _morale_tt_text = "大回合结束时：解除本国一个混乱的己方单位"
                        _morale_tt_anchor = self.morale_lv4_btn_rect
                    elif (
                        self.morale_lv3_btn_rect
                        and self.morale_lv3_btn_rect.collidepoint(_mx, _my)
                    ):
                        _morale_tt_text = "每大回合：选择一个己方单位，获得+1行动力"
                        _morale_tt_anchor = self.morale_lv3_btn_rect
                    elif (
                        self.morale_lv2_btn_rect
                        and self.morale_lv2_btn_rect.collidepoint(_mx, _my)
                    ):
                        _morale_tt_text = "每大回合：免费移动一个己方单位至任意相邻格子"
                        _morale_tt_anchor = self.morale_lv2_btn_rect
                    if _morale_tt_text and _morale_tt_anchor:
                        _ft = self.morale_tt_font
                        _tts = _ft.render(_morale_tt_text, True, pg.Color("#E0FFFF"))
                        _pad_x, _pad_y = 10, 6
                        _fw = _tts.get_width() + _pad_x * 2
                        _fh = _tts.get_height() + _pad_y * 2
                        # X: 左对齐按钮，但确保不超出屏幕右边界
                        _fx = min(_morale_tt_anchor.left, self.screen_width - _fw - 6)
                        _fx = max(0, _fx)
                        _fy = max(0, _morale_tt_anchor.top - _fh - 6)
                        _frect = pg.Rect(_fx, _fy, _fw, _fh)
                        _fbg = pg.Surface((_fw, _fh), pg.SRCALPHA)
                        _fbg.fill((15, 25, 45, 210))
                        self.window.blit(_fbg, _frect.topleft)
                        pg.draw.rect(
                            self.window, pg.Color("#00FFCC"), _frect, 1, border_radius=5
                        )
                        self.window.blit(_tts, (_fx + _pad_x, _fy + _pad_y))

                # 当前处于某个民心效果模式时，顶部显示提示文字
                if (
                    self.morale_free_move_mode
                    or self.morale_bonus_mp_mode
                    or self.morale_cure_mode
                ):
                    _top_h = int(self.screen_height * 0.15)
                    _tag_x = self.country_tag_pos[0]
                    if self.morale_free_move_mode:
                        _hint = "令行禁止：请右键选择目标格（仅1格）"
                    elif self.morale_bonus_mp_mode:
                        _hint = "老乡指路：请左键点击一个己方单位"
                    else:
                        _hint = "军容严整：请左键点击一个混乱的己方单位"
                    _hint_surf = self.combat_ui_font.render(
                        _hint, True, pg.Color("#FFD700")
                    )
                    _hint_rect = _hint_surf.get_rect(
                        right=_tag_x - 30,
                        centery=_top_h * 5 // 6,  # 第3行
                    )
                    self.window.blit(_hint_surf, _hint_rect)

                # --- PP行动按钮 / PP模式渲染 ---
                self.pp_btn_rect = None
                self.pp_spend_end_btn_rect = None
                _top_h = int(self.screen_height * 0.15)
                _no_other_mode = (
                    not self.morale_free_move_mode
                    and not self.morale_bonus_mp_mode
                    and not self.morale_cure_mode
                )

                if _no_other_mode and self.player_country:
                    _pp_total = self._get_total_pp(self.player_country)

                    if self.pp_spend_mode:
                        # ---- 模式已激活：左侧显示"结束行动"按钮 + 当前PP + 提示 ----
                        _end_s = self._pp_end_btn_surf
                        _end_bw = _end_s.get_width() + 20
                        _end_bh = _end_s.get_height() + 10
                        _end_bx = 20
                        _end_by = self.screen_height - _end_bh - 20
                        self.pp_spend_end_btn_rect = pg.Rect(
                            _end_bx, _end_by, _end_bw, _end_bh
                        )
                        _end_c = (
                            pg.Color("#888888")
                            if self.pp_spend_end_btn_rect.collidepoint(
                                pg.mouse.get_pos()
                            )
                            else pg.Color("#555555")
                        )
                        pg.draw.rect(
                            self.window,
                            _end_c,
                            self.pp_spend_end_btn_rect,
                            border_radius=5,
                        )
                        self.window.blit(
                            _end_s,
                            _end_s.get_rect(center=self.pp_spend_end_btn_rect.center),
                        )

                        # 提示浮窗（悬浮在"结束行动"按钮正上方）
                        if self.pp_summon_target_prov is None:
                            _hint2 = f"PP行动：当前PP {_pp_total}　左键伤兵→回血　右键地块→召唤"
                        else:
                            _pn = getattr(self.pp_summon_target_prov, "name", "?")
                            _hint2 = f"召唤地点：{_pn}　当前PP：{_pp_total}"
                        _ft = self.tooltip_font
                        _h2s = _ft.render(_hint2, True, pg.Color("#E0FFFF"))
                        _pad_x, _pad_y = 10, 6
                        _fw = _h2s.get_width() + _pad_x * 2
                        _fh = _h2s.get_height() + _pad_y * 2
                        # 浮窗定位：按钮正上方，左对齐按钮左边
                        _fx = _end_bx
                        _fy = _end_by - _fh - 6
                        _frect = pg.Rect(_fx, _fy, _fw, _fh)
                        # 半透明深色背景
                        _fbg = pg.Surface((_fw, _fh), pg.SRCALPHA)
                        _fbg.fill((15, 25, 45, 210))
                        self.window.blit(_fbg, _frect.topleft)
                        pg.draw.rect(
                            self.window, pg.Color("#00FFCC"), _frect, 1, border_radius=5
                        )
                        self.window.blit(_h2s, (_fx + _pad_x, _fy + _pad_y))

                        # ---- 召唤子面板由 _render_pp_summon_panel() 在最顶层绘制 ----
                        self.pp_summon_btns = []  # 数据由顶层方法填充

                    elif _pp_total >= 1 and not self.pending_post_move_attack:
                        # ---- 尚未激活：显示"使用政治点数"入口按钮 ----
                        _pp_s = self._pp_btn_surf
                        _pp_bw = _pp_s.get_width() + 20
                        _pp_bh = _pp_s.get_height() + 10
                        _pp_bx = 20
                        _pp_by = self.screen_height - _pp_bh - 20
                        self.pp_btn_rect = pg.Rect(_pp_bx, _pp_by, _pp_bw, _pp_bh)
                        _pp_col = (
                            pg.Color("#DAA520")
                            if self.pp_btn_rect.collidepoint(pg.mouse.get_pos())
                            else pg.Color("#B8860B")
                        )
                        pg.draw.rect(
                            self.window, _pp_col, self.pp_btn_rect, border_radius=5
                        )
                        self.window.blit(
                            _pp_s, _pp_s.get_rect(center=self.pp_btn_rect.center)
                        )
                        # 旁边显示当前PP数值
                        _ppv_s = self.combat_ui_font.render(
                            f"({_pp_total}PP)", True, pg.Color("#FFD700")
                        )
                        self.window.blit(
                            _ppv_s,
                            (
                                _pp_bx + _pp_bw + 5,
                                _pp_by + (_pp_bh - _ppv_s.get_height()) // 2,
                            ),
                        )

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

                # 第1行：战斗结果位于顶部区域上三分之一
                start_y = max(2, top_area_height // 6 - total_text_h // 2)

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

            # 卡牌 tooltip 始终在卡牌面板最顶层绘制（不受江东止啼条件限制；事件卡覆盖层激活时跳过）
            if not self.event_card_overlay:
                self.card_panel.draw_tooltip(self.window)

        # 8.3 召唤子面板（PP系统）：绘制在最顶层，覆盖卡牌等UI
        self._render_pp_summon_panel()

        # 8.5 事件卡覆盖层（最顶层，覆盖一切）
        self._render_event_card_overlay()

        # 9. 画鼠标悬停提示 (Tooltip)：事件卡覆盖层激活时跳过
        if not self.event_card_overlay:
            self._draw_hover_tooltip()
            self._draw_evt_info_tooltip()

    def _render_pp_summon_panel(self) -> None:
        """绘制PP召唤子面板（居中覆盖层），并填充 self.pp_summon_btns。
        在 _render_gameplay 末尾、事件卡覆盖层之前调用，保证显示在最顶层。"""
        if not (
            self.pp_spend_mode
            and self.pp_summon_target_prov is not None
            and self.player_country
        ):
            return

        _pp_total = self._get_total_pp(self.player_country)
        _top_h = int(self.screen_height * 0.15)

        _panel_w = int(self.screen_width * 0.55)
        _btn_h = int(self.screen_height * 0.055)
        _btn_gap = 8
        _cols = 3
        _btn_w = (_panel_w - (_cols + 1) * _btn_gap) // _cols
        _panel_h = _btn_h * 2 + _btn_gap * 3 + 36
        _panel_x = (self.screen_width - _panel_w) // 2
        _panel_y = _top_h + 12

        pg.draw.rect(
            self.window,
            pg.Color(20, 20, 40, 220),
            pg.Rect(_panel_x, _panel_y, _panel_w, _panel_h),
            border_radius=8,
        )
        pg.draw.rect(
            self.window,
            pg.Color("#00FFCC"),
            pg.Rect(_panel_x, _panel_y, _panel_w, _panel_h),
            2,
            border_radius=8,
        )

        _unit_defs = [
            ("infantry", "步兵"),
            ("cavalry", "骑兵"),
            ("archer", "弓兵"),
        ]
        _hp_defs = [(1, 1), (2, 2)]
        _mouse = pg.mouse.get_pos()

        self.pp_summon_btns = []
        for ui, (utype, uname) in enumerate(_unit_defs):
            col = ui % _cols
            for hi, (hp_val, pp_cost) in enumerate(_hp_defs):
                _bx2 = _panel_x + _btn_gap + col * (_btn_w + _btn_gap)
                _by2 = _panel_y + 8 + hi * (_btn_h + _btn_gap)
                _br2 = pg.Rect(_bx2, _by2, _btn_w, _btn_h)
                _can = _pp_total >= pp_cost
                _hover = _br2.collidepoint(_mouse)
                if not _can:
                    _bc2 = pg.Color("#444444")
                elif _hover:
                    _bc2 = pg.Color("#208850")
                else:
                    _bc2 = pg.Color("#145530")
                pg.draw.rect(self.window, _bc2, _br2, border_radius=4)
                _label = f"{uname} {hp_val}血 ({pp_cost}PP)"
                _ls = self.combat_ui_font.render(
                    _label,
                    True,
                    pg.Color("white") if _can else pg.Color("#888888"),
                )
                self.window.blit(_ls, _ls.get_rect(center=_br2.center))
                self.pp_summon_btns.append(
                    {
                        "rect": _br2,
                        "unit_type": utype,
                        "hp": hp_val,
                        "cost": pp_cost,
                        "enabled": _can,
                    }
                )

        # 取消按钮
        _cancel_w = int(_panel_w * 0.25)
        _cancel_x = _panel_x + (_panel_w - _cancel_w) // 2
        _cancel_y = _panel_y + 8 + 2 * (_btn_h + _btn_gap)
        _cancel_r = pg.Rect(_cancel_x, _cancel_y, _cancel_w, _btn_h)
        _hover_cancel = _cancel_r.collidepoint(_mouse)
        pg.draw.rect(
            self.window,
            pg.Color("#883322") if _hover_cancel else pg.Color("#552211"),
            _cancel_r,
            border_radius=4,
        )
        _cs = self.combat_ui_font.render("取消召唤", True, pg.Color("white"))
        self.window.blit(_cs, _cs.get_rect(center=_cancel_r.center))
        self.pp_summon_btns.append(
            {
                "rect": _cancel_r,
                "unit_type": None,
                "hp": 0,
                "cost": 0,
                "enabled": True,
            }
        )

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
        self.evt_info_btns = {}

        # 先计算统一面板尺寸
        content_specs = {}
        panel_w = 0
        panel_h = 0
        for country in self.turn_order:
            stats = self.country_stats.get(country, {})
            temp_pp = self.evt_temp_pp.get(country, 0)
            pp_display = stats.get("political_points", 0)
            pp_text = (
                f"政治点数：{pp_display}(+{temp_pp}临)"
                if temp_pp > 0
                else f"政治点数：{pp_display}"
            )
            lines = [
                self.country_labels.get(country, country),
                f"民心点数：{stats.get('people_support', 0)}",
                pp_text,
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

            # 右上角"！"信息按钮
            _btn_r = 9
            _btn_cx = rect.right - _btn_r - 5
            _btn_cy = rect.top + _btn_r + 5
            _btn_rect = pg.Rect(
                _btn_cx - _btn_r, _btn_cy - _btn_r, _btn_r * 2, _btn_r * 2
            )
            _mouse = pg.mouse.get_pos()
            _has_cards = bool(self.evt_applied_this_round.get(country))
            _hovered_btn = _btn_rect.collidepoint(_mouse)
            if _has_cards:
                _btn_bg = pg.Color("#ffaa00") if _hovered_btn else pg.Color("#c87800")
            else:
                _btn_bg = pg.Color("#cccccc") if _hovered_btn else pg.Color("#aaaaaa")
            pg.draw.circle(self.window, _btn_bg, (_btn_cx, _btn_cy), _btn_r)
            pg.draw.circle(
                self.window, pg.Color(60, 60, 60), (_btn_cx, _btn_cy), _btn_r, 1
            )
            _excl_surf = body_font.render("!", True, pg.Color("white"))
            self.window.blit(_excl_surf, _excl_surf.get_rect(center=(_btn_cx, _btn_cy)))
            self.evt_info_btns[country] = _btn_rect

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

    def _draw_evt_info_tooltip(self) -> None:
        """当鼠标悬停于国家"！"按钮时，绘制本回合已生效事件卡的多行浮窗。"""
        if self.state != GameState.PLAYING:
            return
        mouse_pos = pg.mouse.get_pos()
        hovered_country: str | None = None
        for country, btn_rect in self.evt_info_btns.items():
            if btn_rect.collidepoint(mouse_pos):
                hovered_country = country
                break
        if hovered_country is None:
            return

        cards = self.evt_applied_this_round.get(hovered_country, [])
        font_title = self.country_stat_font
        font_body = self.tooltip_font
        country_name = self.country_labels.get(hovered_country, hovered_country)

        max_content_w = 260
        padding = 10
        line_gap = 3

        def _wrap(text: str, font: pg.font.Font, max_w: int) -> List[str]:
            lines: List[str] = []
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
            return lines or [""]

        # 构建行列表：(text, font, color)
        all_lines: List[Tuple[str, pg.font.Font, pg.Color]] = []
        header = f"【本回合生效事件卡 · {country_name}】"
        all_lines.append((header, font_title, pg.Color("#333333")))

        if not cards:
            all_lines.append(
                ("（本回合尚无已生效事件卡）", font_body, pg.Color("#888888"))
            )
        else:
            for i, (name, desc) in enumerate(cards):
                if i > 0:
                    all_lines.append(("", font_body, pg.Color("white")))  # 间隔
                all_lines.append((f"▸ {name}", font_title, pg.Color("#b06800")))
                for dline in _wrap(desc, font_body, max_content_w - padding * 2):
                    all_lines.append((dline, font_body, pg.Color("#444444")))

        # 计算面板尺寸
        actual_w = max_content_w
        total_h = padding
        for text, font, color in all_lines:
            w = font.size(text)[0] + padding * 2
            if w > actual_w:
                actual_w = w
            total_h += 3 if text == "" else font.get_height() + line_gap
        total_h += padding

        # 定位：靠近按钮，避免超出屏幕
        hbtn = self.evt_info_btns[hovered_country]
        tx = hbtn.right + 6
        ty = hbtn.top
        if tx + actual_w > self.screen_width - 5:
            tx = hbtn.left - actual_w - 6
        if ty + total_h > self.screen_height - 5:
            ty = self.screen_height - total_h - 5
        ty = max(5, ty)

        # 绘制背景
        bg_surf = pg.Surface((actual_w, total_h), pg.SRCALPHA)
        bg_surf.fill((255, 252, 225, 235))
        self.window.blit(bg_surf, (tx, ty))
        pg.draw.rect(
            self.window,
            pg.Color("#c8a040"),
            pg.Rect(tx, ty, actual_w, total_h),
            1,
            border_radius=6,
        )

        # 绘制文字
        cy = ty + padding
        for text, font, color in all_lines:
            if text == "":
                cy += 3
                continue
            surf = font.render(text, True, color)
            self.window.blit(surf, (tx + padding, cy))
            cy += font.get_height() + line_gap

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

        labels = ["重开一局", "退出游戏", "当前各国分数"]
        actions = ["RESTART", "EXIT", "SCORE"]

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

            btn_color = (
                pg.Color("#1a5276") if action == "SCORE" else pg.Color("#444444")
            )
            self.control_btns.append(
                {
                    "rect": rect,
                    "surface": surf,
                    "text_pos": (x + 10, y + 5),
                    "action": action,
                    "bg_color": btn_color,
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

    # ====================================================================
    # 事件卡系统 — 抽卡、效果应用、渲染
    # ====================================================================

    def _can_draw_event_card(self, country: str) -> bool:
        """判断 country 当前是否可以消耗 1 政治点数抽取事件卡"""
        if self.state != GameState.PLAYING:
            return False
        if self.turn_game_finished:
            return False
        if self.major_round_choice_pending:
            return False
        if self.show_combat_ui:
            return False
        if self.pending_post_move_attack:
            return False
        if self.selecting_evt_target or self.event_card_overlay:
            return False
        stats = self.country_stats.get(country, {})
        # 临时政治点数可用于抽卡
        total_pp = int(stats.get("political_points", 0)) + self.evt_temp_pp.get(
            country, 0
        )
        return total_pp >= 1

    def _spend_pp(self, country: str, amount: int = 1) -> bool:
        """消耗政治点数（优先消耗临时 PP，再消耗普通 PP）"""
        stats = self.country_stats.setdefault(
            country, {"people_support": 0, "political_points": 0}
        )
        pp = int(stats.get("political_points", 0))
        temp = self.evt_temp_pp.get(country, 0)
        total = pp + temp
        if total < amount:
            return False
        # 优先消耗临时 PP
        if temp >= amount:
            self.evt_temp_pp[country] = temp - amount
        else:
            # 临时 PP 不够，先全部用完，再从普通 PP 扣除
            remaining = amount - temp
            self.evt_temp_pp[country] = 0
            stats["political_points"] = pp - remaining
        return True

    def _trigger_draw_event_card(self, country: str) -> None:
        """尝试让 country 消耗 1 政治点数抽取一张事件卡"""
        if not self._can_draw_event_card(country):
            if self.info_panel:
                self.info_panel.show_message("政治点数不足或当前不可抽卡")
            return
        if not self._spend_pp(country, 1):
            return
        card = self.event_card_deck.draw(country)
        if not card:
            if self.info_panel:
                self.info_panel.show_message("事件卡牌堆已空")
            return

        # "不懈于内"安全抽卡模式：若负效果则无效
        is_negative = self._is_negative_event(card, country)
        safe_draw = self.evt_draw_again_safe
        self.evt_draw_again_safe = False  # 消耗一次

        if safe_draw and is_negative:
            # 抽到了负效果卡，无效，但仍消耗了抽卡机会（放入弃牌堆已完成）
            if self.info_panel:
                self.info_panel.show_message(
                    f"「不懈于内」：抽到「{card.name}」但效果无效", duration=3.0
                )
            return

        # 展示覆盖层
        self.event_card_overlay = {"card": card, "drawer": country, "safe": safe_draw}

    def _is_negative_event(self, card, country: str) -> bool:
        """判定事件卡对抽卡方 country 是否为负面效果（用于'不懈于内'）"""
        et = card.effect_type
        ev = card.effect_value
        # 解析实际目标国（PUBLIC 卡作用于 drawer，其余作用于其所属国）
        tc = country if card.target_country == "DRAWER" else card.deck
        if tc == country and et in ("pp", "morale") and ev < 0:
            return True
        # 特定负效果旗帜（仅当影响抽卡方时算负面）
        negative_flags = {
            "flag_xingluo": "SHU",
            "flag_hu_recruit": "WEI",
            "flag_hefei": "WU",
        }
        flag_country = negative_flags.get(et)
        if flag_country and flag_country == country:
            return True
        return False

    def _confirm_event_card(self) -> None:
        """玩家点击了「确认」，执行事件卡效果"""
        if not self.event_card_overlay:
            return
        card: EventCardDef = self.event_card_overlay["card"]
        drawer: str = self.event_card_overlay["drawer"]
        # 记录本张牌是否为「不懈于内」的免费第二次抽取（不消耗 PP）
        is_free_draw: bool = self.event_card_overlay.get("free_draw", False)
        self.event_card_overlay = None
        self.evt_overlay_ok_btn = None

        self._apply_event_card(card, drawer)

        # ── 若 _apply_event_card 期间又设置了新的覆盖层（draw_again_safe 的
        #    免费第二张牌），则跳过本次 PP 阶段检查，等第二张牌确认后再评估。
        if self.event_card_overlay:
            return

        if not card.needs_target:
            # 免费第二张牌（不懈于内）：不消耗 PP，但仍按实际 PP 决定阶段
            # 普通牌：效果执行后按实际 PP 决定阶段
            _current_pp: int = int(
                self.country_stats.get(drawer, {}).get("political_points", 0)
            ) + self.evt_temp_pp.get(drawer, 0)
            if _current_pp >= 1:
                if not self.evt_draw_phase and drawer == self.player_country:
                    self._enter_evt_draw_phase_if_needed()
            else:
                self._exit_evt_draw_phase()

    def _apply_event_card(self, card, drawer: str) -> None:
        """执行事件卡效果"""
        et = card.effect_type
        ev = card.effect_value

        # 确定目标国家
        tc = card.target_country
        if tc == "DRAWER":
            tc = drawer

        def add_pp(c: str, n: int) -> None:
            stats = self.country_stats.setdefault(
                c, {"people_support": 0, "political_points": 0}
            )
            stats["political_points"] = int(stats.get("political_points", 0)) + n

        def add_morale(c: str, n: int) -> None:
            stats = self.country_stats.setdefault(
                c, {"people_support": 0, "political_points": 0}
            )
            stats["people_support"] = int(stats.get("people_support", 0)) + n
            # 民心等级提升后，检查是否达成"天下归心"胜利条件
            self._check_tianxia_guixin_victory()

        msg = f"「{card.name}」：{card.description}"

        # 记录本小回合该国已生效事件卡（老迈昏聩无效化的卡除外）
        if not (card.id == "evt_jiangdong_cai" and self.evt_laomaikuai_active):
            # "ALL" 目标国（如奖率三军）对每个国家都显示
            _record_countries = self.turn_order if tc == "ALL" else [tc]
            for _rc in _record_countries:
                self.evt_applied_this_round.setdefault(_rc, []).append(
                    (card.name, card.description)
                )

        if et == "pp":
            # 老迈昏聩：若下次抽到"江东才俊"则无效
            if card.id == "evt_jiangdong_cai" and self.evt_laomaikuai_active:
                self.evt_laomaikuai_active = False
                if self.info_panel:
                    self.info_panel.show_message(
                        f"「老迈昏聩」使「{card.name}」效果无效", duration=3.0
                    )
                return
            add_pp(tc, ev)

        elif et == "morale":
            add_morale(tc, ev)

        elif et == "pp_temp":
            self.evt_temp_pp[tc] = self.evt_temp_pp.get(tc, 0) + ev
            msg = f"「{card.name}」：获得 {ev} 点临时政治点数（本小回合内有效）"
            # 若抽卡阶段已因 PP 耗尽而退出，临时 PP 注入后应重新进入抽卡阶段
            if not self.evt_draw_phase and tc == self.player_country:
                self._enter_evt_draw_phase_if_needed()

        elif et == "flag_xingluo":
            add_pp(tc, ev)
            self.evt_xingluo_active = True

        elif et == "conditional_lonzhong":
            # 荆州（ID=35）是否属于蜀汉
            jingzhou = self.map_manager.get_by_id(35)
            if jingzhou and jingzhou.country == "SHU":
                self.evt_lonzhong_skill += 1
                if self.evt_xingluo_active:
                    add_pp("SHU", 1)
                    self.evt_xingluo_active = False
                msg = f"「{card.name}」：荆州属于蜀汉！蜀汉获得进攻东吴骰点+1（累计 {self.evt_lonzhong_skill}）"
            else:
                _xingluo_fired = self.evt_xingluo_active
                if self.evt_xingluo_active:
                    add_pp("SHU", 1)
                    self.evt_xingluo_active = False
                if _xingluo_fired:
                    msg = f"「{card.name}」：荆州不属于蜀汉，无效（但「星落秋风」补偿触发，蜀汉获得+1政治点数）"
                else:
                    msg = f"「{card.name}」：荆州不属于蜀汉，无效"

        elif et == "conditional_jingzhu":
            jingzhou = self.map_manager.get_by_id(35)
            if jingzhou and jingzhou.country == "WU":
                self.evt_jingzhu_skill += 1
                msg = f"「{card.name}」：荆州属于东吴！东吴获得进攻蜀汉骰点+1（累计 {self.evt_jingzhu_skill}）"
            else:
                msg = f"「{card.name}」：荆州不属于东吴，无效"

        elif et == "conditional_ruzhong":
            hanzhong = self.map_manager.get_by_id(17)
            if hanzhong and hanzhong.country == "WEI":
                add_pp("WEI", ev)
                msg = f"「{card.name}」：汉中属于曹魏！曹魏政治点数+{ev}"
            else:
                msg = f"「{card.name}」：汉中不属于曹魏，无效"

        elif et == "draw_again_safe":
            self.evt_draw_again_safe = True
            msg = f"「{card.name}」：额外免费抽一张，若为负效果则无效"
            # 立即触发免费再抽一张（不消耗 PP）
            next_card = self.event_card_deck.draw(drawer)
            if next_card:
                ni = self._is_negative_event(next_card, drawer)
                if ni:
                    self.evt_draw_again_safe = False
                    msg += (
                        f"\n再抽到「{next_card.name}」，为负效果——已被「不懈于内」免除"
                    )
                else:
                    self.evt_draw_again_safe = False
                    self.event_card_overlay = {
                        "card": next_card,
                        "drawer": drawer,
                        "safe": False,
                        "free_draw": True,  # 不消耗政治点的免费第二次抽取
                    }
                    if self.info_panel:
                        self.info_panel.show_message(msg, duration=2.0)
                    return
            else:
                msg += "\n（牌堆已空，未能再次抽卡）"

        elif et == "evt_skill_yishen":
            self.evt_yishen_skill = True
            msg = (
                f"「{card.name}」：蜀汉持有「一身是胆」（下次被进攻低于1:1时自动触发）"
            )

        elif et == "flag_liukang":
            self.evt_flag_liukang = True

        elif et == "flag_hefei":
            self.evt_flag_hefei = True

        elif et == "flag_she_hushu":
            self.evt_flag_she_hushu = True

        elif et == "flag_hu_recruit":
            self.evt_flag_hu_recruit = True

        elif et == "flag_wuwei":
            add_pp("WU", ev)
            self.evt_flag_wuwei = True

        elif et == "flag_all_attack":
            self.evt_flag_all_attack = True

        elif et == "flag_laomaikuai":
            self.evt_laomaikuai_active = True

        elif et == "flag_wuzi":
            self.evt_wuzi_rounds = 5
            self.evt_wuzi_bonus = min(3, self.evt_wuzi_bonus + 1)
            msg = f"「{card.name}」：曹魏进攻骰点+{self.evt_wuzi_bonus}（剩余 {self.evt_wuzi_rounds} 小回合）"

        elif et in (
            "unit_mp_plus",
            "unit_dice_perm_def_minus",
            "unit_atk_plus",
            "unit_dice_bonus",
        ):
            # 目标选择方 = 卡牌所属国（tc），而非抽卡方
            self.selecting_evt_target = True
            self.pending_evt_card_id = card.id
            self.pending_evt_drawer = tc  # tc 已经是解析后的实际目标国
            # 若目标国为 AI，立即自动选择，不需玩家操作
            if tc != self.human_country:
                self._ai_auto_select_evt_target(tc)
                return
            if self.info_panel:
                self.info_panel.show_message(
                    f"「{card.name}」：请点击目标单位（{self.country_labels.get(tc, tc)}己方）",
                    duration=-1,
                )
            return

        elif et == "province_def_plus":
            # 目标选择方 = 卡牌所属国（tc）
            self.selecting_evt_target = True
            self.pending_evt_card_id = card.id
            self.pending_evt_drawer = tc
            # 若目标国为 AI，立即自动选择
            if tc != self.human_country:
                self._ai_auto_select_evt_target(tc)
                return
            if self.info_panel:
                self.info_panel.show_message(
                    f"「{card.name}」：请点击目标地块（{self.country_labels.get(tc, tc)}己方部队）",
                    duration=-1,
                )
            return

        if self.info_panel:
            self.info_panel.show_message(msg, duration=4.0)

    def _ai_auto_select_evt_target(self, selector_country: str) -> None:
        """AI 立即为 needs_target 事件卡自动选择目标，不等待玩家点击"""
        if not self.pending_evt_card_id:
            return
        card_def = self.event_card_deck.get_definition(self.pending_evt_card_id)
        if not card_def:
            self.selecting_evt_target = False
            self.pending_evt_card_id = None
            self.pending_evt_drawer = None
            return

        if card_def.target_type == "unit":
            # 优先选边境有部队的省份，次选任意己方有部队省份
            border_provs = self._ai_get_border_provinces(selector_country)
            border_ids = {p.province_id for p in border_provs}
            chosen_prov = None
            for prov in self.map_manager.provinces:
                if prov.country == selector_country and prov.units:
                    if prov.province_id in border_ids:
                        chosen_prov = prov
                        break
            if chosen_prov is None:
                for prov in self.map_manager.provinces:
                    if prov.country == selector_country and prov.units:
                        chosen_prov = prov
                        break
            if chosen_prov:
                self._apply_evt_target_unit(chosen_prov.province_id, 0)
            else:
                self.selecting_evt_target = False
                self.pending_evt_card_id = None
                self.pending_evt_drawer = None
                self._check_evt_draw_phase_pp()

        elif card_def.target_type == "province":
            chosen_prov = max(
                (
                    p
                    for p in self.map_manager.provinces
                    if p.country == selector_country and p.units
                ),
                key=lambda p: len(p.units),
                default=None,
            )
            if chosen_prov:
                self._apply_evt_target_province(chosen_prov.province_id)
            else:
                self.selecting_evt_target = False
                self.pending_evt_card_id = None
                self.pending_evt_drawer = None
                self._check_evt_draw_phase_pp()

    def _apply_evt_target_unit(self, prov_id: int, slot: int) -> None:
        """完成需要点击单位的事件卡效果"""
        card_id = self.pending_evt_card_id
        drawer = self.pending_evt_drawer
        self.selecting_evt_target = False
        self.pending_evt_card_id = None
        self.pending_evt_drawer = None

        prov = self.map_manager.get_by_id(prov_id)
        if not prov or slot >= len(prov.units):
            if self.info_panel:
                self.info_panel.show_message("目标无效，事件卡取消")
            return
        unit = prov.units[slot]
        card = self.event_card_deck.get_definition(card_id)

        if card_id == "evt_wangshen":  # 忘身于外：单位本大回合 MP+1
            unit.mp += card.effect_value
            if self.info_panel:
                self.info_panel.show_message(
                    f"「{card.name}」：{unit.unit_type} 本大回合行动力+{card.effect_value}"
                )

        elif card_id == "evt_yuda":  # 愿打愿挨：本大回合骰点+1，永久防御-1
            unit.temp_dice_bonus += 1
            unit.defense_bonus = getattr(unit, "defense_bonus", 0) - 1
            if self.info_panel:
                self.info_panel.show_message(
                    f"「{card.name}」：本回合骰点+1，永久防御-1"
                )

        elif card_id == "evt_xiedie":  # 挟帝发令：永久攻击+1
            unit.attack_bonus = getattr(unit, "attack_bonus", 0) + card.effect_value
            if self.info_panel:
                self.info_panel.show_message(
                    f"「{card.name}」：{unit.unit_type} 永久攻击力+{card.effect_value}"
                )

        elif card_id == "evt_libing":  # 厉兵秣马：本大回合骰点+1
            unit.temp_dice_bonus += card.effect_value
            if self.info_panel:
                self.info_panel.show_message(
                    f"「{card.name}」：{unit.unit_type} 本大回合骰点+{card.effect_value}"
                )

        # 目标选择完成，检查是否退出抽卡阶段
        self._check_evt_draw_phase_pp()

    def _apply_evt_target_province(self, prov_id: int) -> None:
        """完成需要点击地块的事件卡效果（江东铁壁）"""
        card_id = self.pending_evt_card_id
        self.selecting_evt_target = False
        self.pending_evt_card_id = None
        self.pending_evt_drawer = None

        card = self.event_card_deck.get_definition(card_id)
        prov = self.map_manager.get_by_id(prov_id)
        if not prov or not prov.units:
            if self.info_panel:
                self.info_panel.show_message("该地块无己方部队，事件卡取消")
            return

        for unit in prov.units:
            unit.defense_bonus = getattr(unit, "defense_bonus", 0) + card.effect_value
        if self.info_panel:
            self.info_panel.show_message(
                f"「{card.name}」：{prov.name} 上 {len(prov.units)} 个单位永久防御+{card.effect_value}"
            )
        # 目标选择完成，检查是否退出抽卡阶段
        self._check_evt_draw_phase_pp()

    # ====================================================================
    # 事件卡覆盖层渲染
    # ====================================================================

    def _render_event_card_overlay(self) -> None:
        """绘制事件卡展示面板（模态覆盖层）"""
        if not self.event_card_overlay:
            return
        card = self.event_card_overlay["card"]
        drawer = self.event_card_overlay["drawer"]

        font_title = self.country_stat_title_font
        font_body = self.country_stat_font

        # ---- 预渲染所有文本，用于计算动态高度 ----
        title_h = font_title.get_height()
        body_h = font_body.get_height()

        # 描述文字按面板宽度分行（约 24 字/行）
        panel_w = max(520, int(self.screen_width * 0.38))
        chunk_size = 24
        desc_lines: list[str] = []
        raw = card.description
        while raw:
            desc_lines.append(raw[:chunk_size])
            raw = raw[chunk_size:]

        # 各区域高度
        padding = 16
        bar_h = title_h + padding  # 顶部国家色条高度（自适应字体）
        card_name_h = title_h + padding  # 卡牌名称区
        desc_total_h = len(desc_lines) * (body_h + 4) + padding
        btn_section_h = body_h + padding * 3  # 确认按钮区

        panel_h = bar_h + card_name_h + desc_total_h + btn_section_h
        panel_x = (self.screen_width - panel_w) // 2
        panel_y = (self.screen_height - panel_h) // 2

        # 半透明背景遮罩
        overlay = pg.Surface((self.screen_width, self.screen_height), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.window.blit(overlay, (0, 0))

        # 卡牌面板底色
        panel_rect = pg.Rect(panel_x, panel_y, panel_w, panel_h)
        pg.draw.rect(self.window, pg.Color("#FFF8E7"), panel_rect, border_radius=12)
        pg.draw.rect(
            self.window, pg.Color("#8B4513"), panel_rect, width=3, border_radius=12
        )

        # ---- 顶部国家颜色标签条 ----
        # 公共卡（deck=="PUBLIC"）始终显示抽取方；其余显示实际生效国
        display_country = drawer if card.deck == "PUBLIC" else card.target_country
        country_color = self.country_button_colors.get(
            display_country, pg.Color("gray")
        )
        tag_rect = pg.Rect(panel_x, panel_y, panel_w, bar_h)
        pg.draw.rect(self.window, country_color, tag_rect, border_radius=12)
        pg.draw.rect(
            self.window,
            country_color,
            pg.Rect(panel_x, panel_y + bar_h // 2, panel_w, bar_h // 2),
        )

        drawer_label = (
            f"{self.country_labels.get(display_country, display_country)} — 事件卡"
        )
        tag_surf = font_title.render(drawer_label, True, pg.Color("white"))
        self.window.blit(
            tag_surf,
            tag_surf.get_rect(center=(panel_x + panel_w // 2, panel_y + bar_h // 2)),
        )

        # ---- 卡牌名称 ----
        cur_y = panel_y + bar_h + padding // 2
        name_surf = font_title.render(card.name, True, pg.Color("#4B2800"))
        self.window.blit(
            name_surf, name_surf.get_rect(centerx=panel_x + panel_w // 2, top=cur_y)
        )
        cur_y += title_h + padding

        # ---- 分隔线 ----
        pg.draw.line(
            self.window,
            pg.Color("#C8A87A"),
            (panel_x + 24, cur_y - padding // 2),
            (panel_x + panel_w - 24, cur_y - padding // 2),
            1,
        )

        # ---- 描述文字 ----
        for dl in desc_lines:
            ds = font_body.render(dl, True, pg.Color("#333333"))
            self.window.blit(ds, ds.get_rect(centerx=panel_x + panel_w // 2, top=cur_y))
            cur_y += body_h + 4

        # ---- 确认按钮 ----
        btn_w = max(140, font_body.size("确认生效")[0] + 40)
        btn_h = body_h + padding
        btn_x = panel_x + (panel_w - btn_w) // 2
        btn_y = panel_y + panel_h - btn_h - padding
        btn_rect = pg.Rect(btn_x, btn_y, btn_w, btn_h)
        self.evt_overlay_ok_btn = btn_rect

        btn_color = pg.Color("#8B4513")
        if btn_rect.collidepoint(pg.mouse.get_pos()):
            btn_color = pg.Color("#A0522D")
        pg.draw.rect(self.window, btn_color, btn_rect, border_radius=8)
        ok_surf = font_body.render("确认生效", True, pg.Color("white"))
        self.window.blit(ok_surf, ok_surf.get_rect(center=btn_rect.center))

    # ====================================================================
    # 事件卡抽取阶段管理
    # ====================================================================

    def _enter_evt_draw_phase_if_needed(self) -> None:
        """若当前为人类玩家且有政治点数，进入事件卡抽取阶段"""
        if not self.player_country:
            return
        if self.major_round_choice_pending:
            return
        # AI 回合不进入抽卡阶段
        if self.human_country is not None and self.player_country != self.human_country:
            return
        stats = self.country_stats.get(self.player_country, {})
        pp = int(stats.get("political_points", 0)) + self.evt_temp_pp.get(
            self.player_country, 0
        )
        if pp >= 1:
            self.evt_draw_phase = True
            label = self.country_labels.get(self.player_country, self.player_country)
            if self.info_panel:
                self.info_panel.show_message(
                    f"【事件卡阶段】{label} 请选择：抽取事件卡 或 跳过"
                )

    def _exit_evt_draw_phase(self) -> None:
        """退出事件卡抽取阶段，进入正常行动阶段"""
        self.evt_draw_phase = False
        self.evt_skip_draw_btn_rect = None
        if self.info_panel:
            self.info_panel.show_properties("")

    def _check_evt_draw_phase_pp(self) -> None:
        """确认/目标完成后，若 PP 耗尽则自动退出抽卡阶段"""
        if not self.evt_draw_phase:
            return
        if not self.player_country:
            self.evt_draw_phase = False
            return
        stats = self.country_stats.get(self.player_country, {})
        pp = int(stats.get("political_points", 0)) + self.evt_temp_pp.get(
            self.player_country, 0
        )
        if pp < 1:
            self._exit_evt_draw_phase()
            if self.info_panel:
                self.info_panel.show_message("政治点数耗尽，进入行动阶段", duration=2.0)

    def _render_draw_event_btn(self) -> None:
        """事件卡抽取阶段按钮组：「抽事件卡」+ 「跳过」；等待目标选择时显示提示"""
        if self.state != GameState.PLAYING:
            self.draw_event_btn_rect = None
            self.evt_skip_draw_btn_rect = None
            return
        if self.turn_game_finished or not self.player_country:
            self.draw_event_btn_rect = None
            self.evt_skip_draw_btn_rect = None
            return
        # 仅在事件卡抽取阶段显示按钮
        if not self.evt_draw_phase:
            self.draw_event_btn_rect = None
            self.evt_skip_draw_btn_rect = None
            return

        # 若正在等待玩家点选事件卡目标，隐藏抽卡/跳过按钮，显示「请选择生效目标」提示
        if self.selecting_evt_target:
            self.draw_event_btn_rect = None
            self.evt_skip_draw_btn_rect = None
            font = self.combat_ui_font
            top_area_h = int(self.screen_height * 0.15)
            tag_x = self.country_tag_pos[0]
            hint_surf = font.render("▶ 请选择生效目标", True, pg.Color("#FFD700"))
            hint_y = (top_area_h - hint_surf.get_height()) // 2
            hint_x = tag_x - hint_surf.get_width() - 20
            # 半透明背景衬底
            bg = pg.Surface(
                (hint_surf.get_width() + 16, hint_surf.get_height() + 8), pg.SRCALPHA
            )
            bg.fill((0, 0, 0, 120))
            self.window.blit(bg, (hint_x - 8, hint_y - 4))
            self.window.blit(hint_surf, (hint_x, hint_y))
            return

        font = self.combat_ui_font
        top_area_h = int(self.screen_height * 0.15)
        tag_x = self.country_tag_pos[0]
        mouse_pos = pg.mouse.get_pos()

        # 以「跳过」按钮为锚点，紧贴国家标签左侧
        skip_label = "跳过抽卡"
        skip_surf = font.render(skip_label, True, pg.Color("white"))
        btn_h = skip_surf.get_height() + 10
        btn_y = (top_area_h - btn_h) // 2
        skip_w = skip_surf.get_width() + 20
        skip_x = tag_x - skip_w - 10
        skip_rect = pg.Rect(skip_x, btn_y, skip_w, btn_h)
        self.evt_skip_draw_btn_rect = skip_rect
        skip_color = (
            pg.Color("#2E6E30")
            if not skip_rect.collidepoint(mouse_pos)
            else pg.Color("#3D9140")
        )
        pg.draw.rect(self.window, skip_color, skip_rect, border_radius=6)
        self.window.blit(skip_surf, skip_surf.get_rect(center=skip_rect.center))

        # 「抽事件卡」按钮：仅在 PP >= 1 时显示，位于跳过按钮左侧
        if self._can_draw_event_card(self.player_country):
            draw_label = "抽事件卡(-1PP)"
            draw_surf = font.render(draw_label, True, pg.Color("white"))
            draw_w = draw_surf.get_width() + 20
            draw_x = skip_x - draw_w - 10
            draw_rect = pg.Rect(draw_x, btn_y, draw_w, btn_h)
            self.draw_event_btn_rect = draw_rect
            draw_color = (
                pg.Color("#6B4226")
                if not draw_rect.collidepoint(mouse_pos)
                else pg.Color("#8B5E3C")
            )
            pg.draw.rect(self.window, draw_color, draw_rect, border_radius=6)
            self.window.blit(draw_surf, draw_surf.get_rect(center=draw_rect.center))
        else:
            self.draw_event_btn_rect = None
            draw_x = skip_x

        # 阶段提示文字
        phase_surf = font.render("▶ 事件卡阶段", True, pg.Color("#FFD700"))
        left_edge = (
            self.draw_event_btn_rect.left if self.draw_event_btn_rect else draw_x
        )
        phase_x = left_edge - phase_surf.get_width() - 14
        phase_y = btn_y + (btn_h - phase_surf.get_height()) // 2
        self.window.blit(phase_surf, (phase_x, phase_y))

    def _tag_w_cache(self) -> int:
        """返回国家标签宽度（粗略估算）"""
        if self.player_country and self.player_country in self.country_tag_surfaces:
            return self.country_tag_surfaces[self.player_country].get_width()
        return 60
