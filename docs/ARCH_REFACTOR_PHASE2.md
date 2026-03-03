# 架构改造阶段 2（服务契约化）

## 目标

把服务从“接收整个 `GameApp` 并直接取字段”逐步改为“显式参数/返回值契约”，降低耦合并提升可测试性。

## 本轮落地范围

- `VolumeUIService`
  - `draw_speaker_icon()` 改为显式 `window` 参数
  - `update_volume_from_y()` 重构为纯计算 `calculate_volume_from_y()`
  - `render_volume_slider()` 改为显式参数契约
- `MapBoundsService`
  - `get_map_bounds_rect()` 改为显式 `provinces/hex_side/screen_size` 契约
- `PolylineRenderService`
  - `draw_smooth_polyline()` 改为显式 `window` 参数契约
- `HelpRuleLoadService`
  - 新增纯加载函数 `load_help_rule_surfaces()`
  - `start_help_rule_load()` 改为显式状态参数并返回 `started`
- `ProvinceQueryService`
  - `get_unit_slot_at()` 改为显式 `provinces/unit_renderer/hex_side/pos` 契约
  - `get_province_at()` 改为显式 `provinces/hex_side/pos` 契约
- `SelectionService`
  - `handle_selection_click()` 改为显式输入 + `on_add_selection` 回调契约
- `PlayingInputService`（局部）
  - `handle_volume_slider_click()` 改为显式状态 + 回调契约
  - `should_block_right_click()` 改为显式状态 + 可选消息回调
  - `handle_mouse_motion()` 改为显式状态 + 回调契约
  - `handle_left_button_up()` 改为显式回调契约
  - `handle_unit_selection_click()` 改为显式状态 + 回调契约
  - `handle_card_panel_click()` 改为显式状态 + 回调契约
  - `handle_info_panel_click()` 改为显式参数契约
  - `handle_card_target_click()` 改为显式状态 + 回调契约
  - `handle_major_round_choice_click()` 改为显式状态 + 回调契约
  - `handle_evt_draw_phase_click()` 改为显式状态 + 回调契约
  - `handle_draw_event_button_click()` 改为显式状态 + 回调契约
  - `handle_help_overlay_wheel()` 改为显式状态 + 回调契约
  - `handle_help_overlay_click()` 改为显式状态 + 回调契约
  - `handle_keydown()` 改为显式状态 + 回调契约
  - `handle_control_button_click()` 改为显式状态 + 回调契约
  - `handle_recover_click()` 改为显式状态 + 回调契约
  - `handle_no_attack_click()` 改为显式状态 + 回调契约
  - `handle_game_right_click()` 改为显式状态 + 回调契约
  - `handle_evt_target_click()` 改为显式状态 + 回调契约
  - `handle_morale_click()` 改为显式状态 + 回调契约
  - `handle_combat_ui_click()` 改为显式状态 + 回调契约
  - `handle_pp_click()` 改为显式状态 + 回调契约

## App 侧配套

- `GameApp` 对上述服务调用已全部改为显式参数。
- 业务副作用（如 `volume_level` 赋值、`mixer` 同步、帮助加载状态写回）回收到 `GameApp` 编排层。

## 阶段2收口归并（3轮）

- 第1轮：输入入口归并
  - `PlayingInputService` 新增三聚合入口：`handle_keyboard_input()`、`handle_left_click()`、`handle_right_click()`。
- 第2轮：左键按业务域归并
  - 拆分为 `_handle_left_click_global_ui()`、`_handle_left_click_combat_and_event()`、`_handle_left_click_panels_and_selection()`。
- 第3轮：调用侧收敛
  - `GameApp._handle_playing_event()` 收敛为三入口路由，统一消息回调，减少分散分支。

## 价值

- 服务更接近“纯函数/纯渲染函数”
- 单测可不依赖完整 `GameApp` 构造
- 后续阶段可进一步用 `Protocol` 替代散字段访问
