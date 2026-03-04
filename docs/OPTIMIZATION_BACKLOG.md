# 性能优化待办（暂停前记录）

更新时间：2026-03-04
状态：R1-R5 已完成，进入收尾

## 已完成（2026-03-04）

- ✅ R1：背景半透明缓存 + 鼠标逻辑坐标帧内一次计算
- ✅ R2：河流/禁线预渲染缓存图层
- ✅ R3：字体对象缓存（`(filename, size)`）
- ✅ R4：帮助覆盖层遮罩与缩放结果缓存
- ✅ R5：分数屏静态布局缓存
- ✅ R6：统一回归（`test_*_minimal.py` 全量通过）
- ✅ P1-1：帮助覆盖层彻底下沉到 `HelpOverlayRenderService`
- ✅ P1-2：分数屏彻底下沉到 `ScoreScreenService`
- ✅ P2-1：开局/大回合流程下沉到 `TurnStartOrchestrationService`
- ✅ P2-2：会话技能显示维护下沉到 `MajorRoundStatusService`

## P1（优先）

1. [已完成] 背景半透明改为缓存，避免每帧 `copy + set_alpha`
   - 现状位置：`src/core/gameplay_render_service.py` 的 `render_gameplay()`
   - 关键代码：`bg_surface = self.bg_image.copy()` + `bg_surface.set_alpha(128)`
   - 目标：在分辨率/背景资源变化时预生成 `bg_image_alpha`，每帧直接 `blit`

2. [已完成] 河流/禁线预渲染图层
   - 现状位置：`src/core/gameplay_render_service.py` 的河流与禁线绘制段
   - 问题：每帧重复多次粗线绘制
   - 目标：在资产构建阶段预渲染 `river_layer`（可含 ban line），运行时直接贴图

3. [已完成] 鼠标逻辑坐标改为帧内一次计算
   - 现状位置：`src/core/gameplay_render_service.py` 的 `render_gameplay()`
   - 问题：`self._get_logical_mouse_pos()` 在同一帧内多次调用
   - 目标：函数开头缓存 `mouse_pos`，后续悬停/按钮判定统一复用

4. [已完成] 字体对象缓存（基础优化）
   - 现状位置：`src/core/ui_render_helper_service.py` 的 `font()` / `render_text()`
   - 问题：频繁创建 `pg.font.Font` 对象，增加 CPU 与分配开销
   - 目标：按 `(filename, size)` 建立字体缓存；全局复用，尺寸变化时按 key 自动区分

## P2（次优先）

5. [已完成] 帮助覆盖层缩放与UI资源缓存
   - 现状位置：`src/core/app.py` 的 `_render_help_overlay()`
   - 问题：每帧 `smoothscale`、重复创建遮罩与字体
   - 目标：按 `(page, viewport)` 缩放缓存；遮罩与常用字体复用

## P3（可延后）

6. [已完成] 分数屏静态布局缓存
   - 现状位置：`src/core/app.py` 的 `_render_score_screen()`
   - 问题：每帧重复字体初始化、换行计算、文本排版
   - 目标：当 `show_score_screen` 内容未变化时，复用预渲染 Surface

## 回归要求（继续时执行）

- 错误检查：改动文件无错误
- 定向回归：`tests.test_gameapp_integration_minimal`
- 全量回归：`python -m unittest discover -s tests -p "test_*_minimal.py"`
- 如涉及缓存：补最小测试验证“缓存命中/尺寸变化失效”

## 后续可选（非性能刚需）

- 继续清理 `app.py` 中历史代理方法，按域做接口分组（结构优化，非性能瓶颈）。
