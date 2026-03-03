# 架构改造阶段 4（App 物理瘦身与编排收口）

## 目标

- 继续降低 [src/core/app.py](../src/core/app.py) 的实现密度
- 把初始化/资产构建与命令执行细节下沉到服务层
- 收敛状态写入口，减少分散字段直写

## 本轮 4 轮落地

### 第1轮：初始化/资产构建拆分

- 新增 [src/core/asset_build_service.py](../src/core/asset_build_service.py)
- `GameApp._build_mode_select_assets()` 改为委托服务
- `GameApp._build_loading_assets()` 改为委托服务
- `GameApp._build_choosing_assets()` 改为委托服务
- `GameApp._build_play_assets()` 改为委托服务

### 第2轮：命令执行编排下沉

- 新增 [src/core/playing_command_service.py](../src/core/playing_command_service.py)
- `GameApp._execute_playing_input_commands()` 改为委托 `PlayingCommandService.execute()`

### 第3轮：状态写入口收口

- `GameApp` 新增统一写入口：
  - `_set_help_overlay_visible()`
  - `_reset_morale_modes()`
  - `_set_pp_summon_target_prov()`
  - `_clear_pp_summon_btns()`
  - `_set_pp_spend_mode()`
- `PlayingCommandService` 通过上述入口修改状态

### 第4轮：收尾与验证

- 增补服务委托相关最小集成测试：
  - `test_asset_build_methods_delegate_to_service`
  - `test_execute_playing_input_commands_delegates_to_service`
- 继续保留阶段3深度模拟操作测试

## 验证

- 定向最小回归：`tests.test_gameapp_integration_minimal` + 输入/渲染相关 minimal 通过
- 全量最小回归：`test_*_minimal.py` 通过
- 错误检查：无错误
