# 性能优化待办（暂停前记录）

更新时间：2026-03-04
状态：暂停中，后续继续

## P1（优先）

1. 背景半透明改为缓存，避免每帧 `copy + set_alpha`
   - 现状位置：`src/core/gameplay_render_service.py` 的 `render_gameplay()`
   - 关键代码：`bg_surface = self.bg_image.copy()` + `bg_surface.set_alpha(128)`
   - 目标：在分辨率/背景资源变化时预生成 `bg_image_alpha`，每帧直接 `blit`

2. 鼠标逻辑坐标改为帧内一次计算
   - 现状位置：`src/core/gameplay_render_service.py` 的 `render_gameplay()`
   - 问题：`self._get_logical_mouse_pos()` 在同一帧内多次调用
   - 目标：函数开头缓存 `mouse_pos`，后续悬停/按钮判定统一复用

3. 帮助覆盖层缩放与UI资源缓存
   - 现状位置：`src/core/app.py` 的 `_render_help_overlay()`
   - 问题：每帧 `smoothscale`、重复创建遮罩与字体
   - 目标：按 `(page, viewport)` 缓存缩放结果；遮罩与常用字体复用

4. 分数屏静态布局缓存
   - 现状位置：`src/core/app.py` 的 `_render_score_screen()`
   - 问题：每帧重复字体初始化、换行计算、文本排版
   - 目标：当 `show_score_screen` 内容未变化时，复用预渲染 Surface

## P2（次优先）

5. 河流/禁线预渲染图层
   - 现状位置：`src/core/gameplay_render_service.py` 的河流与禁线绘制段
   - 问题：每帧重复多次粗线绘制
   - 目标：在资产构建阶段预渲染 `river_layer`，运行时直接贴图

## 回归要求（继续时执行）

- 错误检查：改动文件无错误
- 定向回归：`tests.test_gameapp_integration_minimal`
- 全量回归：`python -m unittest discover -s tests -p "test_*_minimal.py"`
- 如涉及缓存：补最小测试验证“缓存命中/尺寸变化失效”
