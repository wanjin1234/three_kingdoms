# 架构改造阶段 1（状态模型化）

## 目标

将高频运行态按领域分组，先建立“状态模型层”，并与原有 `GameApp` 字段并存，确保行为等价。

## 本轮落地

- 新增状态模型文件：`src/core/state_models.py`
  - `TurnState`
  - `UIState`
  - `CombatState`
  - `EventCardState`
- 在 `GameApp` 中接入状态模型实例：
  - `turn_state`
  - `ui_state`
  - `combat_state`
  - `event_card_state`
- 将部分核心读取逻辑迁移到状态模型入口（保持行为不变）：
  - `_get_people_support_level()`
  - `_get_total_pp()`

## 兼容策略

- 采用“代理视图”方式：状态模型读写直接代理 `GameApp` 原字段。
- 优点：
  - 无需一次性替换大量历史逻辑
  - 能逐步把服务调用从“散字段”收敛到“分域状态入口”

## 验收项

- 最小测试全集通过
- 新增状态模型测试通过
- 集成测试覆盖“状态模型写入 -> 原字段同步”路径通过
