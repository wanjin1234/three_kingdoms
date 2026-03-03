# 架构改造阶段 3（渲染 / 规则解耦）

## 目标

1. 引入只读视图模型（`GameplayViewModel` / `MainSceneViewModel`）
2. 渲染服务消费视图模型，减少直接依赖规则对象
3. 输入链路先行命令化（键盘路径）

## 三轮落地

### 第1轮：视图模型落地

- 新增 [src/core/view_models.py](../src/core/view_models.py)
  - `MainSceneViewModel`
  - `GameplayViewModel`
- `GameApp` 增加：
  - `_build_main_scene_view_model()`
  - `_build_gameplay_view_model()`

### 第2轮：渲染消费视图模型

- `ScreenRenderService.render_main_scene()` 接收 `MainSceneViewModel`
- `GameplayRenderService.render_gameplay()` 接收 `GameplayViewModel`
- `GameApp._render()` / `_render_gameplay()` 改为显式传入视图模型

### 第3轮：输入命令化（键盘）

- `PlayingInputService` 新增 `build_keydown_commands()`
- `GameApp._handle_playing_event()` 中键盘路径改为：
  - 输入服务只产生命令
  - `GameApp._execute_playing_input_commands()` 执行命令

### 第3轮补完：输入命令化（右键）

- `PlayingInputService` 新增 `build_right_click_commands()`
- `GameApp._handle_playing_event()` 右键路径改为：
  - 输入服务只产生命令（阻断提示 / 右键行为分发）
  - `GameApp._execute_playing_input_commands()` 统一执行

## 验证

- 定向最小回归：`test_playing_input_service_minimal` / `test_screen_render_service_minimal` / `test_gameapp_integration_minimal` 通过
- 全量最小回归：`test_*_minimal.py` 通过
- 全局错误检查：无错误
