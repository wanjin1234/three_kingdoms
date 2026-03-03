# 回合系统重构协作文档（P1）

> 适用范围：当前仓库回合逻辑重构成果（P1 阶段）。
> 目标读者：协作开发成员、评审同学、后续接手维护者。

速查版见：`docs/TURN_ARCHITECTURE_QUICKSTART.md`

---

## 1. 背景与目标

在重构前，`GameApp` 同时承担：

- 回合规则计算
- 回合切换副作用清理
- UI/消息分发与 AI 调度

这会导致以下问题：

1. 单文件体量过大，改动风险高。
2. 规则与表现耦合，难以单元测试。
3. 协作冲突频繁（多人同时改 `app.py`）。

### P1 重构目标

- 不改变玩法规则（行为等价）。
- 将“规则计算 / 运行时副作用 / 展示分发”拆开。
- 保持 `GameApp` 作为编排层，减少其业务细节。
- 用最小测试保护关键行为，支撑后续 P2/P3 拆分。

---

## 2. 当前模块分层

### 2.1 规则层（纯逻辑）

文件：`src/core/turn_service.py`

核心职责：

- 回合推进计数（国家索引、大回合/小回合）
- 大回合加点策略选择（AI 默认策略）
- 大回合加点状态计算与完成判定
- 国家公共属性默认结构初始化

关键接口：

- `TurnService.advance_turn()`
- `TurnService.apply_major_round_choice()`
- `TurnService.all_major_round_choices_done()`

特性：

- 不依赖 `pygame`
- 不处理 UI
- 易单测、可复用

---

### 2.2 运行时副作用层（状态清理与重置）

文件：`src/core/turn_runtime_coordinator.py`

核心职责：

- 回合切换前动作态清理（选择、临时标记）
- 跨大回合时单位临时属性重置
- 回合开始时“延迟失效事件”清理
- 移动高亮按国家回收

关键接口：

- `TurnRuntimeCoordinator.prepare_turn_switch()`
- `TurnRuntimeCoordinator.apply_major_round_rollover()`
- `TurnRuntimeCoordinator.on_country_turn_start()`

特性：

- 聚焦状态副作用，不做规则判定
- 通过调用 `GameApp` 已有回调完成必要联动

---

### 2.3 展示分发层（UI/消息/调度）

文件：`src/core/turn_presentation_coordinator.py`

核心职责：

- 对局结束时 UI、消息、得分画面触发
- 新行动国激活后的卡牌面板更新
- 事件抽卡阶段入口触发
- AI 延迟执行时间调度

关键接口：

- `TurnPresentationCoordinator.handle_game_finished()`
- `TurnPresentationCoordinator.on_country_activated()`

特性：

- 明确属于“表现层协调”，不承担规则计算

---

### 2.4 编排层

文件：`src/core/app.py`

当前职责建议：

- 作为总控制器（Orchestrator）
- 按顺序调用：规则层 -> 副作用层 -> 展示层
- 保持“少算、多调度”的风格

---

## 3. 回合切换主流程（现状）

入口方法：`GameApp._advance_country_turn()`

高层流程：

1. `turn_runtime.prepare_turn_switch()`
2. `turn_service.advance_turn()` 得到推进结果
3. 若对局结束 -> `turn_presentation.handle_game_finished()`
4. 若完成小回合 -> `_end_full_round()`
5. 若进入新大回合 -> `turn_runtime.apply_major_round_rollover()`
6. 设置 `player_country`
7. `turn_runtime.on_country_turn_start()`
8. `turn_presentation.on_country_activated()`

好处：

- 每一步语义明确，便于排查问题。
- 协作时可按层拆任务，减少冲突。

---

## 4. 协作开发边界（重要）

为避免多人改同一逻辑引发回归，建议按边界提交：

### A 组（规则）

只改：`turn_service.py` 及其测试

禁止：

- 直接改 UI
- 直接调用 `pygame` API

### B 组（运行时清理）

只改：`turn_runtime_coordinator.py` 及其测试

关注：

- 临时标记生命周期
- 大回合重置完整性

### C 组（展示与调度）

只改：`turn_presentation_coordinator.py` 及其测试

关注：

- 提示文案
- 面板刷新
- AI 触发时机

### D 组（编排与集成）

只改：`app.py` 的调用顺序与参数传递

关注：

- 先后顺序是否正确
- 异常分支是否完整（结束态、AI/human 切换）

---

## 5. 代码约定（建议执行）

1. **任何新增回合逻辑，先判断属于哪一层。**
2. 规则变化优先放 `TurnService`，不要直接塞回 `GameApp`。
3. `Coordinator` 类只协调状态和调用，不做复杂规则推导。
4. `GameApp` 方法优先保持“流程语句 + 调度调用”，少写细节。
5. 新增方法必须配套最小测试（至少 1 个正常 + 1 个边界）。

---

## 6. 测试映射（当前）

### 回合相关测试

- `tests/test_turn_service_minimal.py`
  - 策略选择
  - 大回合加点应用
  - 回合推进边界（换小回合/换大回合/结束）

- `tests/test_turn_runtime_coordinator_minimal.py`
  - 切换前清理
  - 跨大回合重置
  - 国家开始回合时延迟失效标记清理

- `tests/test_turn_presentation_coordinator_minimal.py`
  - 游戏结束分发
  - 人类/AI 回合激活差异
  - AI 计时器设置

### 全量最小测试执行

- `python -m unittest discover -s tests -p "test_*_minimal.py"`

---

## 7. 常见问题与排查

### Q1：回合切换后 UI 没更新？

优先检查：

1. `on_country_activated()` 是否被调用
2. `card_manager` 是否按 `player_country` 设置
3. `_update_card_panel()` 是否执行

### Q2：AI 不行动或提前行动？

优先检查：

1. `human_country` 与 `player_country` 比较逻辑
2. `_ai_turn_timer` 赋值时机
3. 是否处于 `turn_game_finished` 状态

### Q3：大回合效果没清干净？

优先检查：

1. `apply_major_round_rollover()` 是否触发
2. 单位临时属性是否全部重置
3. 大回合事件标记与显示记录是否同步清理

---

## 8. 后续演进建议（P2/P3）

1. 将 AI 决策进一步抽离为 `AIStrategy`（避免继续膨胀 `GameApp`）。
2. 将回合事件通知抽象为轻量事件总线（替代散落的回调调用）。
3. 建立“集成回放测试”样例（固定随机种子跑 3~5 轮，比较关键状态快照）。
4. 补充协作规范文档（提交命名、测试门槛、评审清单）。

---

## 9. 评审清单（PR Checklist）

提交任何回合相关改动前，请自检：

- [ ] 逻辑归属是否正确（规则 / 副作用 / 展示）
- [ ] 是否新增或更新对应最小测试
- [ ] 全部 `test_*_minimal.py` 是否通过
- [ ] 是否避免把新复杂逻辑塞回 `GameApp`
- [ ] 是否更新文档（如本文件或 `TESTING.md`）

---

## 10. 变更记录（P1 摘要）

- 新增 `TurnService`：抽离回合推进与加点规则。
- 新增 `TurnRuntimeCoordinator`：抽离回合副作用清理。
- 新增 `TurnPresentationCoordinator`：抽离回合展示分发。
- `GameApp` 变为主要编排层。
- 回合相关最小测试已补齐并纳入统一执行。

---

## 11. 变更记录（P2 摘要）

- 新增 `AIService`：`src/core/ai_service.py`
- `GameApp` 中 AI 相关方法已切换为服务委托（边境判断、威胁判断、目标选择、召唤、战斗执行）
- `GameApp._run_ai_turn()` 已改为由 `AIService.run_turn()` 执行主流程
- 新增 `tests/test_ai_service_minimal.py`，并纳入最小测试全集

---

如需继续协作扩展，请优先在本文件“第 4 节边界”下认领模块，再开工。
