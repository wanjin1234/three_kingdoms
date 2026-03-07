from __future__ import annotations

from typing import Tuple

import pygame as pg


class HelpOverlayRenderService:
    """帮助/规则书覆盖层渲染与缓存服务。"""

    def load_help_rule_thread(self, app) -> None:
        """后台线程：依次读取 rule_1.png – rule_13.png，存为原始像素列表。"""
        surfaces, failed = app.help_rule_load_service.load_help_rule_surfaces(
            pdf_path=app.settings.rules_pdf
        )
        if failed:
            app._help_rule_load_failed = True
            app._help_rule_loading = False
            app._help_scaled_slide_cache_key = None
            app._help_scaled_slide_cache_surface = None
            return
        app._help_rule_surfaces = surfaces
        app._help_rule_loading = False
        app._help_scaled_slide_cache_key = None
        app._help_scaled_slide_cache_surface = None

    def start_help_rule_load(self, app) -> None:
        """启动后台线程加载规则图片（若尚未加载）。"""
        started = app.help_rule_load_service.start_help_rule_load(
            has_surfaces=bool(app._help_rule_surfaces),
            is_loading=app._help_rule_loading,
            load_target=lambda: self.load_help_rule_thread(app),
        )
        if started:
            app._help_rule_loading = True

    def _get_help_overlay_mask(self, app) -> pg.Surface:
        """返回帮助覆盖层半透明遮罩（按窗口尺寸缓存）。"""
        key = (app.screen_width, app.screen_height, 190)
        if app._help_mask_cache_surface is None or app._help_mask_cache_key != key:
            app._help_mask_cache_surface = pg.Surface(
                (app.screen_width, app.screen_height),
                pg.SRCALPHA,
            )
            app._help_mask_cache_surface.fill((0, 0, 0, 190))
            app._help_mask_cache_key = key
        return app._help_mask_cache_surface

    def _get_help_scaled_slide(
        self,
        app,
        slide_surf: pg.Surface,
        page: int,
        target_size: Tuple[int, int],
    ) -> pg.Surface:
        """返回帮助页缩放结果（按页码与目标尺寸缓存）。"""
        dw, dh = target_size
        sw, sh = slide_surf.get_width(), slide_surf.get_height()
        key = (page, dw, dh, sw, sh, id(slide_surf))
        if (
            app._help_scaled_slide_cache_surface is None
            or app._help_scaled_slide_cache_key != key
        ):
            app._help_scaled_slide_cache_surface = pg.transform.smoothscale(
                slide_surf,
                (dw, dh),
            )
            app._help_scaled_slide_cache_key = key
        return app._help_scaled_slide_cache_surface

    def render_help_overlay(self, app) -> None:
        """渲染游戏规则图片覆盖层（单页显示 + 左右翻页按钮）。"""
        if not app.help_overlay_visible:
            return

        # 触发后台加载（不阻塞）
        if not app._help_rule_surfaces and not app._help_rule_loading:
            self.start_help_rule_load(app)

        # 半透明暗色背景遮罩（缓存）
        mask = self._get_help_overlay_mask(app)
        app.window.blit(mask, (0, 0))

        # 内容面板
        margin_y = 50
        nav_w = 72  # 左右导航按钮宽度
        content_h = app.screen_height - margin_y * 2
        max_content_w = app.screen_width - margin_y * 2

        # 有内容时：根据第一页宽高比算出刚好包住图片的面板宽度，避免两侧空白过多
        if app._help_rule_surfaces:
            _s = app._help_rule_surfaces[0]
            _sw, _sh = _s.get_width(), _s.get_height()
            _img_h = content_h - 44  # 去掉底部页码区高度
            _ideal_img_w = int(_img_h * _sw / max(_sh, 1))
            _ideal_w = _ideal_img_w + nav_w * 2 + 16  # 加导航按钮和少量内边距
            content_w = min(max_content_w, max(_ideal_w, 400))
        else:
            content_w = max_content_w

        content_x = (app.screen_width - content_w) // 2
        content_y = margin_y
        content_rect = pg.Rect(content_x, content_y, content_w, content_h)
        app._help_overlay_content_rect = content_rect

        pg.draw.rect(app.window, pg.Color("#1a1a1a"), content_rect, border_radius=10)
        pg.draw.rect(app.window, pg.Color("#5a3a1a"), content_rect, 3, border_radius=10)

        # --- 加载中 / 失败 ---
        if not app._help_rule_surfaces:
            info_font = app._font("msyh.ttc", 22)
            if app._help_rule_load_failed:
                msg = "无法加载规则图片（assets/graphics/rule/ 目录不存在）"
                err = info_font.render(msg, True, pg.Color("#cc4444"))
                app.window.blit(err, err.get_rect(center=content_rect.center))
            else:
                app._help_load_anim_frame += 1
                dots = "●" * ((app._help_load_anim_frame // 12) % 4)
                loading = info_font.render(f"正在加载规则{dots}", True, pg.Color("#f5f0e8"))
                app.window.blit(loading, loading.get_rect(center=content_rect.center))
            hint_font = app._font("msyh.ttc", 20)
            hint = hint_font.render("ESC 或点击外部关闭", True, pg.Color("#888888"))
            app.window.blit(
                hint,
                (
                    content_x + content_w - hint.get_width() - 16,
                    content_y + content_h - hint.get_height() - 6,
                ),
            )
            return

        total_pages = len(app._help_rule_surfaces)
        app.help_current_page = max(0, min(app.help_current_page, total_pages - 1))
        slide_surf = app._help_rule_surfaces[app.help_current_page]

        # 图片显示区（去掉左右导航按钮占用宽度）
        img_area_x = content_x + nav_w
        img_area_y = content_y + 8
        img_area_w = content_w - nav_w * 2
        img_area_h = content_h - 44  # 留底部页码区

        # 等比缩放至显示区，再乘以缩放倍数
        sw, sh = slide_surf.get_width(), slide_surf.get_height()
        base_scale = min(img_area_w / max(sw, 1), img_area_h / max(sh, 1))
        zoom = getattr(app, "help_zoom_factor", 1.0)
        scale = base_scale * zoom
        dw, dh = max(1, int(sw * scale)), max(1, int(sh * scale))
        scaled_slide = self._get_help_scaled_slide(app, slide_surf, app.help_current_page, (dw, dh))
        blit_x = img_area_x + (img_area_w - dw) // 2
        blit_y = img_area_y + (img_area_h - dh) // 2
        # 裁剪到内容区域，防止放大后溢出面板边界
        img_clip = pg.Rect(img_area_x, img_area_y, img_area_w, img_area_h)
        app.window.set_clip(img_clip)
        app.window.blit(scaled_slide, (blit_x, blit_y))
        app.window.set_clip(None)

        # 页码文字（底部居中）
        page_font = app._font("msyh.ttc", 18)
        page_surf = page_font.render(
            f"{app.help_current_page + 1} / {total_pages}",
            True,
            pg.Color("#f5f0e8"),
        )
        app.window.blit(
            page_surf,
            page_surf.get_rect(centerx=content_rect.centerx, bottom=content_rect.bottom - 8),
        )

        # ESC 提示 + 缩放操作说明
        hint_font = app._font("msyh.ttc", 24)
        hint = hint_font.render("ESC 或点击外部关闭", True, pg.Color("#666666"))
        app.window.blit(hint, (content_x + content_w - hint.get_width() - 16, content_y + 6))
        zoom_val = getattr(app, "help_zoom_factor", 1.0)
        zoom_color = pg.Color("#f5c842") if abs(zoom_val - 1.0) > 0.01 else pg.Color("#555555")
        zoom_hint = hint_font.render(
            f"Ctrl+滚轮缩放  {int(zoom_val * 100)}%", True, zoom_color
        )
        app.window.blit(zoom_hint, (content_x + 12, content_y + 6))

        # 左右导航按钮
        btn_h = 100
        btn_cy = content_y + content_h // 2
        prev_rect = pg.Rect(content_x + 6, btn_cy - btn_h // 2, nav_w - 12, btn_h)
        next_rect = pg.Rect(
            content_x + content_w - nav_w + 6,
            btn_cy - btn_h // 2,
            nav_w - 12,
            btn_h,
        )
        app._help_prev_btn = prev_rect
        app._help_next_btn = next_rect

        prev_active = app.help_current_page > 0
        next_active = app.help_current_page < total_pages - 1
        _ah = 14  # 三角形半高（像素）

        prev_color = pg.Color("#5a3a1a") if prev_active else pg.Color("#3a3a3a")
        pg.draw.rect(app.window, prev_color, prev_rect, border_radius=8)
        _arrow_col = pg.Color("#f5f0e8") if prev_active else pg.Color("#555555")
        _cx, _cy = prev_rect.centerx, prev_rect.centery
        pg.draw.polygon(app.window, _arrow_col, [
            (_cx + _ah, _cy - _ah), (_cx + _ah, _cy + _ah), (_cx - _ah, _cy)
        ])

        next_color = pg.Color("#5a3a1a") if next_active else pg.Color("#3a3a3a")
        pg.draw.rect(app.window, next_color, next_rect, border_radius=8)
        _arrow_col = pg.Color("#f5f0e8") if next_active else pg.Color("#555555")
        _cx, _cy = next_rect.centerx, next_rect.centery
        pg.draw.polygon(app.window, _arrow_col, [
            (_cx - _ah, _cy - _ah), (_cx - _ah, _cy + _ah), (_cx + _ah, _cy)
        ])
