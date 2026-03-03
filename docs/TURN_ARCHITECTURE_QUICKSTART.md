# 回合系统协作速查（1页版）

> 给新成员的快速上手说明：先看这页，再看详细文档。

详细版见：`docs/TURN_ARCHITECTURE_GUIDE.md`

---

## 1. 先记住三层

### 规则层

- 文件：`src/core/turn_service.py`
- 负责：回合计数、加点规则、结束判定
- 不负责：UI、`pygame`、消息提示

### 运行时副作用层

- 文件：`src/core/turn_runtime_coordinator.py`
- 负责：切换前清理、大回合重置、延迟失效标记清理
- 不负责：规则推导

### 展示分发层

- 文件：`src/core/turn_presentation_coordinator.py`
- 负责：面板刷新、结束提示、AI 计时调度
- 不负责：规则计算

`GameApp` 负责把三层串起来，不要再把复杂细节塞回去。

## 1.5 P2 新增：AI 服务层

- 文件：`src/core/ai_service.py`
- 负责：AI 行动主流程与目标选择、边境评估、召唤/战斗执行
- `GameApp` 仅保留委托入口，不再承载主要 AI 细节

---

## 2. 改动该放哪？（最快判断）

- “第几回合 / 该不该结束 / 加点怎么选” → `TurnService`
- “这个状态什么时候清掉” → `TurnRuntimeCoordinator`
- “切回合后界面怎么更新、AI 何时触发” → `TurnPresentationCoordinator`
- “调用顺序与流程编排” → `GameApp`

---

## 3. 新功能最小流程

1. 先确定归属层。
2. 只改该层文件（必要时再改 `app.py` 调用）。
3. 写最小测试（至少正常 + 边界各 1 条）。
4. 跑测试：
   - `python -m unittest discover -s tests -p "test_*_minimal.py"`
5. 确认通过再提交。

---

## 4. 当前关键测试文件

- `tests/test_turn_service_minimal.py`
- `tests/test_turn_runtime_coordinator_minimal.py`
- `tests/test_turn_presentation_coordinator_minimal.py`

---

## 5. PR 自检（精简版）

- [ ] 逻辑放对层了吗？
- [ ] 是否新增/更新最小测试？
- [ ] `test_*_minimal.py` 全通过了吗？
- [ ] 是否避免把复杂逻辑重新塞回 `GameApp`？

---

## 6. 常见坑

1. **规则写进展示层**：会导致行为分散、难测。
2. **副作用散落在 `app.py`**：后续继续膨胀。
3. **只改代码不补测试**：回归风险高。
4. **先改编排顺序再改规则**：容易定位困难，建议分两个提交。

---

## 7. 推荐协作顺序

- 先改 `TurnService`（规则）
- 再改 `TurnRuntimeCoordinator`（状态）
- 再改 `TurnPresentationCoordinator`（展示）
- 最后微调 `GameApp` 编排

这样冲突最少，排错最快。
