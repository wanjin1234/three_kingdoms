from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class RightClickContext:
    """右键处理所需的最小上下文契约。"""

    major_round_choice_pending: bool
    evt_draw_phase: bool
    selecting_evt_target: bool
    on_block_message: Callable[[str], None] | None

    pp_spend_mode: bool
    pp_summon_target_prov: object | None
    get_province_at: Callable
    player_country: str | None
    evt_flag_hu_recruit: bool
    on_set_pp_summon_target_prov: Callable[[object | None], None]
    selected_units: list
    card_effect_manager: object
    on_get_people_support_level: Callable[[str], int]
    is_fort_or_city: Callable[[object], bool]
    morale_free_move_mode: bool
    combat_target: object | None
    on_cancel_combat_preview: Callable[[], None]
    on_handle_combat: Callable[[object], None]
    pending_post_move_attack: bool
    on_handle_movement: Callable[[object], None]
    on_show_message: Callable[[str], None] | None


@dataclass(frozen=True)
class LeftClickContext:
    """左键处理的输入上下文契约。"""

    payload: dict


@dataclass(frozen=True)
class StartMajorRoundChoiceContext:
    """大回合加点阶段启动契约。"""

    turn_order: list[str]
    human_country: str | None
    begin_major_round_choice: Callable[[], tuple[bool, dict]]
    choose_major_round_bonus: Callable[[int], str]
    get_total_pp: Callable[[str], int]
    on_apply_major_round_choice: Callable[[str, str], None]
    on_set_major_round_choice_state: Callable[[bool, dict], None]
    on_set_country_stat_choice_btns: Callable[[dict], None]


@dataclass(frozen=True)
class ApplyMajorRoundChoiceContext:
    """单个国家应用大回合加点选择契约。"""

    major_round_choice_pending: bool
    country_stats: dict
    major_round_choice_done: dict
    major_round: int
    apply_major_round_choice: Callable[..., bool]
    all_major_round_choices_done: Callable[[dict], bool]
    on_set_major_round_choice_pending: Callable[[bool], None]
    on_check_tianxia_guixin_victory: Callable[[], None]
    on_show_message: Callable[[str], None] | None
    on_enter_evt_draw_phase_if_needed: Callable[[], None]


@dataclass(frozen=True)
class EndFullRoundContext:
    """小回合结束收尾契约。"""

    on_clear_turn_effects: Callable[[], None]
    on_replenish_action_points: Callable[[], None]
    on_set_gexu_guard_active: Callable[[bool], None]
    on_clear_jingnang_applied: Callable[[], None]


@dataclass(frozen=True)
class CardApplyEffectContext:
    """卡牌效果应用收尾契约。"""

    use_card: Callable[[str], None]
    player_country: str | None
    append_jingnang_applied: Callable[[str, str, str], None]
    show_message: Callable[..., None]
    on_update_card_panel: Callable[[], None]


@dataclass(frozen=True)
class CardCancelSelectionContext:
    """取消卡牌目标选择契约。"""

    on_set_selecting_card_target: Callable[[bool], None]
    on_set_selected_card_for_effect: Callable[[str | None], None]
    show_message: Callable[..., None]


@dataclass(frozen=True)
class EventConfirmContext:
    """事件卡确认生效流程契约。"""

    get_event_card_overlay: Callable[[], dict | None]
    clear_event_card_overlay: Callable[[], None]
    apply_event_card: Callable[[object, str], None]
    is_event_card_overlay_active: Callable[[], bool]
    is_evt_draw_phase_active: Callable[[], bool]
    get_player_country: Callable[[], str | None]
    get_country_total_pp: Callable[[str], int]
    enter_evt_draw_phase_if_needed: Callable[[], None]
    exit_evt_draw_phase: Callable[[], None]
    get_human_country: Callable[[], str | None]
    is_selecting_evt_target: Callable[[], bool]
    get_pending_evt_card_id: Callable[[], str | None]
    get_pending_evt_drawer: Callable[[], str | None]
    ai_auto_select_evt_target: Callable[[str], None]
    get_ai_turn_timer: Callable[[], int | None]
    is_turn_game_finished: Callable[[], bool]
    set_ai_turn_timer: Callable[[int], None]


@dataclass(frozen=True)
class EventTargetApplyContext:
    """事件卡目标应用（单位/地块）流程契约。"""

    get_pending_evt_card_id: Callable[[], str | None]
    clear_pending_evt_target_state: Callable[[], None]
    get_province_by_id: Callable[[int], object | None]
    get_event_card_definition: Callable[[str], object | None]
    show_message: Callable[..., None] | None
    check_evt_draw_phase_pp: Callable[[], None]
    get_player_country: Callable[[], str | None]
    get_human_country: Callable[[], str | None]
    get_ai_turn_timer: Callable[[], int | None]
    is_turn_game_finished: Callable[[], bool]
    set_ai_turn_timer: Callable[[int], None]


@dataclass(frozen=True)
class EventDrawPhaseContext:
    """事件卡抽卡阶段入口/退出/校验流程契约。"""

    get_player_country: Callable[[], str | None]
    get_human_country: Callable[[], str | None]
    is_major_round_choice_pending: Callable[[], bool]
    get_country_total_pp: Callable[[str], int]
    set_evt_draw_phase: Callable[[bool], None]
    get_evt_draw_phase: Callable[[], bool]
    set_evt_skip_draw_btn_rect: Callable[[object | None], None]
    show_message: Callable[..., None] | None
    show_properties: Callable[[str], None] | None
    get_country_label: Callable[[str], str]


@dataclass(frozen=True)
class RemoveMajorRoundContext:
    """移除大回合展示记录契约。"""

    get_major_round_countries: Callable[[], list[str]]
    filter_out_card_for_country: Callable[[str, str], None]


@dataclass(frozen=True)
class RefreshSessionSkillDisplayContext:
    """刷新会话技能展示契约。"""

    on_remove_from_major_round: Callable[[str, str | None], None]
    get_evt_lonzhong_skill: Callable[[], int]
    get_evt_yishen_skill: Callable[[], int]
    is_evt_xingluo_active: Callable[[], bool]
    append_major_round_record: Callable[[str, str, str], None]


@dataclass(frozen=True)
class ClearForTurnSwitchContext:
    """切换国家前的交互状态清理契约。"""

    clear_selected_units: Callable[[], None]
    reset_combat_interaction_state: Callable[[], None]
    reset_morale_and_pp_modes: Callable[[], None]
    on_clear_combat_result_ui: Callable[[], None]
    show_properties: Callable[[str], None] | None


@dataclass(frozen=True)
class AdvanceCountryTurnContext:
    """切换到下一国家流程契约。"""

    turn_game_finished: bool
    prepare_turn_switch: Callable[[bool], None]
    advance_turn: Callable[..., object]
    on_set_turn_progression: Callable[[int, int, int], None]
    on_handle_game_finished: Callable[[], None]
    on_end_full_round: Callable[[], None]
    on_apply_major_round_rollover: Callable[[], None]
    get_turn_order: Callable[[], list[str]]
    on_set_player_country: Callable[[str], None]
    on_country_turn_start: Callable[[str], None]
    on_country_activated: Callable[[], None]


@dataclass(frozen=True)
class FinishCountryActionContext:
    """国家行动完成后的轮换契约。"""

    on_advance_country_turn: Callable[[bool], None]


@dataclass(frozen=True)
class CheckTianxiaVictoryContext:
    """天下归心胜利检查契约。"""

    check_tianxia_guixin: Callable[[], str | None]
    on_set_turn_game_finished: Callable[[bool], None]
    on_set_player_country: Callable[[str | None], None]
    on_set_card_manager: Callable[[object | None], None]
    on_clear_card_panel_available: Callable[[], None]
    score_manager_initial_recorded: bool
    on_record_initial_scores: Callable[[], None]
    on_set_score_manager_initial_recorded: Callable[[bool], None]
    get_detailed_scores: Callable[[], object]
    on_set_show_score_screen: Callable[[dict], None]
    on_show_message: Callable[[str], None] | None


@dataclass(frozen=True)
class AIAutoSelectEventTargetContext:
    """AI 自动选择事件卡目标契约。"""

    get_pending_evt_card_id: Callable[[], str | None]
    get_event_card_definition: Callable[[str], object | None]
    clear_pending_evt_target_state: Callable[[], None]
    get_border_provinces: Callable[[str], list[object]]
    get_provinces: Callable[[], list[object]]
    apply_evt_target_unit: Callable[[int, int], None]
    apply_evt_target_province: Callable[[int], None]
    check_evt_draw_phase_pp: Callable[[], None]


@dataclass(frozen=True)
class AIBorderProvincesContext:
    """AI 边境省计算契约。"""

    map_manager: object
    hex_side: int | float


@dataclass(frozen=True)
class AIRunTurnContext:
    """AI 回合执行入口契约。"""

    app: object
