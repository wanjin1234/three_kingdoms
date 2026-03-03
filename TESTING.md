# 最小测试（P0）

本项目当前提供了第一批“最小测试”，目标是先保护核心规则，支持后续重构。

## 覆盖范围

- 战斗判定：`tests/test_combat_minimal.py`
- 地图路径代价：`tests/test_map_manager_minimal.py`
- 事件卡牌堆：`tests/test_event_card_deck_minimal.py`
- 分数计算：`tests/test_score_manager_minimal.py`
- 回合推进服务：`tests/test_turn_service_minimal.py`
- 回合运行时协调器：`tests/test_turn_runtime_coordinator_minimal.py`
- 回合展示协调器：`tests/test_turn_presentation_coordinator_minimal.py`
- AI 服务：`tests/test_ai_service_minimal.py`
- 控制台服务：`tests/test_console_service_minimal.py`
- 战斗工具服务：`tests/test_combat_utils_service_minimal.py`
- 战斗流程服务：`tests/test_combat_flow_service_minimal.py`
- 战斗结算服务：`tests/test_combat_resolution_service_minimal.py`
- 界面渲染服务：`tests/test_screen_render_service_minimal.py`
- 游戏主战场渲染服务：`tests/test_gameplay_render_service_minimal.py`
- 覆盖层 UI 服务：`tests/test_overlay_ui_service_minimal.py`
- 单位选择服务：`tests/test_selection_service_minimal.py`
- 游戏内输入服务：`tests/test_playing_input_service_minimal.py`
- 单位移动服务：`tests/test_movement_service_minimal.py`
- 地图拾取查询服务：`tests/test_province_query_service_minimal.py`
- 国家状态叠层渲染服务：`tests/test_country_stats_overlay_service_minimal.py`
- 事件信息浮窗渲染服务：`tests/test_evt_info_tooltip_service_minimal.py`
- 音量 UI 服务：`tests/test_volume_ui_service_minimal.py`
- 折线几何渲染服务：`tests/test_polyline_render_service_minimal.py`
- 地图包围盒查询服务：`tests/test_map_bounds_service_minimal.py`
- 规则图片异步加载服务：`tests/test_help_rule_load_service_minimal.py`
- 架构阶段0关键交互冒烟：`tests/test_arch_phase0_smoke_minimal.py`
- 阶段1状态模型：`tests/test_state_models_minimal.py`
- GameApp 集成路径：`tests/test_gameapp_integration_minimal.py`

## 运行方式

在项目根目录执行：

- 运行全部最小测试：`python -m unittest discover -s tests -p "test_*_minimal.py"`
- 运行单个测试文件：`python -m unittest tests.test_combat_minimal`

## 架构改造阶段 0 基线

- 冻结与基线文档：`docs/ARCH_REFACTOR_PHASE0.md`
- 进入后续架构阶段前，至少执行一次：
  - `python -m unittest discover -s tests -p "test_*_minimal.py"`
  - 关键交互冒烟（进入对局、渲染、鼠标交互、帮助覆盖层）

> 说明：这些测试优先验证规则引擎逻辑，不包含渲染/UI 回归测试。

## 协作架构说明

- 回合系统分层与协作边界：`docs/TURN_ARCHITECTURE_GUIDE.md`
- 新成员快速上手（1页速查）：`docs/TURN_ARCHITECTURE_QUICKSTART.md`
- 架构改造阶段 0（冻结与基线）：`docs/ARCH_REFACTOR_PHASE0.md`
- 架构改造阶段 1（状态模型化）：`docs/ARCH_REFACTOR_PHASE1.md`
- 架构改造阶段 2（服务契约化）：`docs/ARCH_REFACTOR_PHASE2.md`
