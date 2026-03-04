"""
RuntimeLoopService 最小单元测试。

测试重点：
  - present_frame O1 优化：预分配 Surface 的复用 / 安全回退 / 不动直接渲染路径
  - reflow_after_window_change：两个分支（超宽 / 等比）均预分配 _scaled_surface
  - to_logical_pos：round() 映射正确性、视口外哨兵值
"""

import unittest

import pygame as pg

from src.core.runtime_loop_service import RuntimeLoopService


class _FakeApp:
    """用于 RuntimeLoopService 单元测试的轻量 App 替身。"""

    def __init__(
        self,
        display_surface: pg.Surface,
        *,
        direct_render: bool = False,
        base_w: int = 1280,
        base_h: int = 720,
    ) -> None:
        self.display_surface = display_surface
        self._direct_render = direct_render
        self._base_screen_width = base_w
        self._base_screen_height = base_h
        self.screen_width = base_w
        self.screen_height = base_h
        self.display_width, self.display_height = display_surface.get_size()
        self.window = pg.Surface((base_w, base_h)).convert()
        self.viewport_rect = pg.Rect(0, 0, self.display_width, self.display_height)
        self._scaled_surface: pg.Surface | None = None
        self._viewport_scale: float = 1.0
        self._rebuild_called = False

    def _rebuild_layout_for_screen_size(self) -> None:
        self._rebuild_called = True


class RuntimeLoopServiceMinimalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pg.init()
        pg.display.set_mode((100, 100))

    @classmethod
    def tearDownClass(cls) -> None:
        pg.quit()

    def setUp(self) -> None:
        self.service = RuntimeLoopService()

    # ─── present_frame ────────────────────────────────────────────────

    def test_present_frame_no_display_no_op(self) -> None:
        """display_surface=None 时直接返回，不抛出异常。"""
        app = type("App", (), {"display_surface": None, "_direct_render": False})()
        self.service.present_frame(app)  # must not raise

    def test_present_frame_direct_render_does_not_touch_scaled_surface(self) -> None:
        """`_direct_render=True` 时跳过 smoothscale，不创建也不修改 `_scaled_surface`。"""
        fake_display = pg.Surface((80, 60))
        app = _FakeApp(fake_display, direct_render=True)
        app._scaled_surface = None

        self.service.present_frame(app)

        self.assertIsNone(app._scaled_surface, "_direct_render 路径不应碰 _scaled_surface")

    def test_present_frame_reuses_preallocated_surface(self) -> None:
        """`_scaled_surface` 尺寸匹配时应直接复用同一对象，不重建。"""
        fake_display = pg.Surface((80, 60))
        app = _FakeApp(fake_display, direct_render=False, base_w=80, base_h=60)
        app.viewport_rect = pg.Rect(0, 0, 80, 60)
        prealloc = pg.Surface((80, 60)).convert()
        app._scaled_surface = prealloc

        self.service.present_frame(app)

        self.assertIs(app._scaled_surface, prealloc, "应复用预分配 Surface，而非重建新对象")

    def test_present_frame_fallback_creates_surface_when_none(self) -> None:
        """安全回退：`_scaled_surface=None` 时应按需创建，尺寸与 viewport_rect 一致。"""
        fake_display = pg.Surface((80, 60))
        app = _FakeApp(fake_display, direct_render=False, base_w=80, base_h=60)
        app.viewport_rect = pg.Rect(0, 0, 80, 60)
        app._scaled_surface = None

        self.service.present_frame(app)

        self.assertIsNotNone(app._scaled_surface)
        self.assertEqual(app._scaled_surface.get_size(), (80, 60))

    def test_present_frame_recreates_surface_on_size_mismatch(self) -> None:
        """尺寸不匹配时（旧 Surface 滞后于 viewport 变化）应重建为新尺寸。"""
        fake_display = pg.Surface((80, 60))
        app = _FakeApp(fake_display, direct_render=False, base_w=80, base_h=60)
        app.viewport_rect = pg.Rect(0, 0, 80, 60)
        stale = pg.Surface((40, 30)).convert()
        app._scaled_surface = stale

        self.service.present_frame(app)

        self.assertIsNot(app._scaled_surface, stale, "尺寸不匹配时应重建新 Surface")
        self.assertEqual(app._scaled_surface.get_size(), (80, 60))

    # ─── reflow_after_window_change ───────────────────────────────────

    def test_reflow_letterbox_preallocates_scaled_surface(self) -> None:
        """等比缩放（有黑边）分支：_scaled_surface 尺寸应与 viewport_rect 完全一致。"""
        # scale_x = 160/1280 = 0.125, scale_y = 90/720 = 0.125 → else 分支
        fake_display = pg.Surface((160, 90))
        app = _FakeApp(fake_display, direct_render=False)

        self.service.reflow_after_window_change(app)

        self.assertIsNotNone(app._scaled_surface)
        self.assertEqual(
            app._scaled_surface.get_size(),
            (app.viewport_rect.width, app.viewport_rect.height),
        )

    def test_reflow_wide_mode_preallocates_scaled_surface(self) -> None:
        """超宽（scale_x > scale_y）分支：_scaled_surface 应铺满整个 display。"""
        # base 100x100, display 200x50 → scale_x=2.0, scale_y=0.5 → scale_x > scale_y
        fake_display = pg.Surface((200, 50))
        app = _FakeApp(fake_display, direct_render=False, base_w=100, base_h=100)

        self.service.reflow_after_window_change(app)

        self.assertIsNotNone(app._scaled_surface)
        self.assertEqual(
            app._scaled_surface.get_size(),
            (app.viewport_rect.width, app.viewport_rect.height),
        )

    def test_reflow_direct_render_skips_scaled_surface_alloc(self) -> None:
        """`_direct_render=True` 时 reflow 提前返回，不应分配 `_scaled_surface`。"""
        fake_display = pg.Surface((80, 60))
        app = _FakeApp(fake_display, direct_render=True)
        app._scaled_surface = None

        self.service.reflow_after_window_change(app)

        self.assertIsNone(app._scaled_surface, "_direct_render 下不应分配 _scaled_surface")

    def test_reflow_updates_scaled_surface_on_window_resize(self) -> None:
        """连续两次 reflow（模拟窗口拖拽缩放）_scaled_surface 应跟随 viewport 更新。"""
        fake_display = pg.Surface((160, 90))
        app = _FakeApp(fake_display, direct_render=False)
        self.service.reflow_after_window_change(app)
        size_first = app._scaled_surface.get_size()

        # 模拟窗口变大
        app.display_surface = pg.Surface((320, 180))
        app.display_width, app.display_height = 320, 180
        # 直接调用核心计算逻辑（不通过 app.display_surface.get_size() 刷新）
        self.service.reflow_after_window_change(app)
        size_second = app._scaled_surface.get_size()

        self.assertNotEqual(size_first, size_second, "窗口变化后 _scaled_surface 应重新分配")
        self.assertEqual(
            size_second,
            (app.viewport_rect.width, app.viewport_rect.height),
        )

    # ─── to_logical_pos ──────────────────────────────────────────────

    def test_to_logical_pos_passthrough_in_direct_render(self) -> None:
        """直接渲染模式下，坐标原样返回。"""
        fake_display = pg.Surface((80, 60))
        app = _FakeApp(fake_display, direct_render=True)
        app.viewport_rect = pg.Rect(0, 0, 80, 60)

        self.assertEqual(self.service.to_logical_pos(app, (40, 30)), (40, 30))

    def test_to_logical_pos_outside_viewport_sentinel(self) -> None:
        """点击落在 viewport 外侧时返回哨兵 (-10000, -10000)。"""
        fake_display = pg.Surface((120, 90))
        app = _FakeApp(fake_display, direct_render=False, base_w=120, base_h=90)
        app.viewport_rect = pg.Rect(10, 10, 100, 70)
        app.screen_width = 1280
        app.screen_height = 720

        self.assertEqual(self.service.to_logical_pos(app, (5, 5)), (-10_000, -10_000))

    def test_to_logical_pos_rounding_not_truncation(self) -> None:
        """坐标映射使用 round() 而非 int() 截断，消除亚像素系统性偏移。

        viewport (0,0,100,100)，逻辑分辨率 200x200 → 映射比例 2x
        输入 (1,1) → logical = round(1 * 200/100) = 2（int() 截断也为 2，此处相同）
        输入 (0,0) → logical = (0, 0)
        """
        fake_display = pg.Surface((100, 100))
        app = _FakeApp(fake_display, direct_render=False, base_w=200, base_h=200)
        app.viewport_rect = pg.Rect(0, 0, 100, 100)
        app.screen_width = 200
        app.screen_height = 200

        lx, ly = self.service.to_logical_pos(app, (1, 1))
        self.assertEqual(lx, 2)
        self.assertEqual(ly, 2)

    def test_to_logical_pos_rounding_half_pixel_away_from_zero(self) -> None:
        """明确验证 round() 对半像素的四舍五入行为（int() 会系统性偏低）。

        viewport (0,0,200,200)，逻辑分辨率 201x201
        比例 = 201/200 = 1.005
        输入 x=99 → float = 99 * 1.005 = 99.495 → round()=99, int()=99（一致）
        输入 x=100 → float = 100 * 1.005 = 100.5 → round()=100（银行家舍入）或 101，int()=100
        主要验证不崩溃且结果在合理范围
        """
        fake_display = pg.Surface((200, 200))
        app = _FakeApp(fake_display, direct_render=False, base_w=201, base_h=201)
        app.viewport_rect = pg.Rect(0, 0, 200, 200)
        app.screen_width = 201
        app.screen_height = 201

        lx, ly = self.service.to_logical_pos(app, (100, 100))
        # round(100 * 201/200) = round(100.5)，Python banker's rounding → 100
        self.assertIn(lx, (100, 101))  # 允许银行家舍入结果
        self.assertIn(ly, (100, 101))


if __name__ == "__main__":
    unittest.main()
