from __future__ import annotations

import pygame as pg

from src.map.geometry import hex_vertices
from src.core.view_models import GameplayViewModel


class GameplayRenderService:
    @staticmethod
    def build_round_text(
        major_round: int, minor_round: int, country_label: str = ""
    ) -> str:
        round_text = f"回合 {major_round}-{minor_round}"
        if country_label:
            round_text = f"{round_text} · {country_label}"
        return round_text

    def render_gameplay(
        self,
        app,
        view_model: GameplayViewModel | None = None,
    ) -> None:
        self = app
        self.window.fill(pg.Color("white"))

        # 1. 画背景图片（左上角对齐屏幕，50% 透明度）
        bg_surface = self.bg_image.copy()
        bg_surface.set_alpha(128)
        self.window.blit(bg_surface, (0, 0))

        # 2. 画地图底层（格子+地形）
        self.map_manager.draw(self.window)

        # 2. 画所有兵种单位
        for province in self.map_manager.provinces:
            center = (
                province.center_cache
                if province.center_cache
                else province.compute_center(self.hex_side)
            )
            self.unit_renderer.draw_units(self.window, center, province.units)

        # 2.5 给移动/招募的单位图标加彩色边框，颜色跟随对应国家
        # 出发格：只框住实际移动的那几个槽位（原始位置）
        for _src_id, _src_c in self.move_src_provs.items():
            _sp = self.map_manager.get_by_id(_src_id)
            if not _sp:
                continue
            _sc = (
                _sp.center_cache
                if _sp.center_cache
                else _sp.compute_center(self.hex_side)
            )
            _col = self.country_button_colors.get(_src_c, pg.Color("white"))
            _slots = self.move_src_slots.get(_src_id, [0])
            _all_rects = self.unit_renderer.selection_rects(_sc, 3)
            for _i in _slots:
                if _i < len(_all_rects):
                    _fr = _all_rects[_i].inflate(4, 4)
        # 目的格/招募格：只框住实际移入/招募的那几个槽位
        for _dst_id, _dst_c in self.move_dst_provs.items():
            _dp = self.map_manager.get_by_id(_dst_id)
            if not _dp:
                continue
            _dc = (
                _dp.center_cache
                if _dp.center_cache
                else _dp.compute_center(self.hex_side)
            )
            _col = self.country_button_colors.get(_dst_c, pg.Color("white"))
            _slots = self.move_dst_slots.get(_dst_id)
            if _slots is None:
                # 兼容旧数据：框住所有单位
                _slots = list(range(len(_dp.units)))
            if not _slots or not _dp.units:
                continue
            _all_rects = self.unit_renderer.selection_rects(_dc, len(_dp.units))
            for _i in _slots:
                if _i < len(_all_rects):
                    _fr = _all_rects[_i].inflate(6, 6)
                    pg.draw.rect(self.window, _col, _fr, 4)
                    pg.draw.rect(self.window, pg.Color("white"), _fr.inflate(-4, -4), 1)

        # 2.6 画当前战斗目标的金色描边 Hex Outline
        if self.combat_target:
            # 安全获取 Province 对象
            target_prov = self.combat_target
            # 计算中心点
            c = (
                target_prov.center_cache
                if target_prov.center_cache
                else target_prov.compute_center(self.hex_side)
            )
            # 计算六边形顶点
            vertices = hex_vertices(c, self.hex_side)

            # 使用金色画笔画线，宽度为4
            pg.draw.lines(self.window, pg.Color("gold"), True, vertices, 4)

        # 3. 画河流和阻挡线
        # 河流使用双层绘制：先画所有深蓝色描边，再画所有浅蓝色河流
        river_light_blue = pg.Color(173, 216, 230)  # 浅蓝色
        river_dark_blue = pg.Color(30, 80, 120)  # 深蓝色描边

        # 第一步：画所有河流的深蓝色描边
        for polyline in self.yangtze_polylines:
            self._draw_smooth_polyline(river_dark_blue, polyline, 28)  # 深蓝色描边
        self._draw_smooth_polyline(river_dark_blue, self.yellow_river_polyline, 28)

        # 第二步：画所有河流的浅蓝色主体
        for polyline in self.yangtze_polylines:
            self._draw_smooth_polyline(river_light_blue, polyline, 20)  # 浅蓝色河流
        self._draw_smooth_polyline(river_light_blue, self.yellow_river_polyline, 20)

        # 画阻挡线：双层绘制，先画黑色描边，再画紫色主体
        self._draw_smooth_polyline(
            pg.Color("black"), self.ban_line_polyline, 28
        )  # 黑色描边
        self._draw_smooth_polyline(
            pg.Color(120, 0, 120), self.ban_line_polyline, 20
        )  # 紫色主体

        # 3.5 画功能按钮
        for btn in getattr(self, "control_btns", []):
            # 简单的悬停效果
            color = btn["bg_color"]
            if btn["rect"].collidepoint(self._get_logical_mouse_pos()):
                color = pg.Color("#666666")  # Lighter gray
            # 音量按钮激活时高亮
            if btn["action"] == "VOLUME" and self.volume_slider_visible:
                color = pg.Color("#52b788")
            # 帮助按钮激活时高亮
            if btn["action"] == "HELP" and self.help_overlay_visible:
                color = pg.Color("#e07b39")

            if btn.get("shape") == "circle":
                r = btn["rect"]
                cx, cy = r.centerx, r.centery
                radius = min(r.width, r.height) // 2
                pg.draw.circle(self.window, color, (cx, cy), radius)
                pg.draw.circle(self.window, btn["border_color"], (cx, cy), radius, 2)
                # 喀叭图标（纯 pygame 基本图形）
                if btn["action"] == "VOLUME":
                    self._draw_speaker_icon(cx, cy, radius)
                # 帮助按钮：绘制 "?" 字符
                elif btn["action"] == "HELP":
                    _q_font = self._font("msyh.ttc", max(12, int(radius * 1.1)))
                    _q_surf = _q_font.render("?", True, pg.Color("white"))
                    _q_rect = _q_surf.get_rect(center=(cx, cy))
                    self.window.blit(_q_surf, _q_rect)
            else:
                pg.draw.rect(self.window, color, btn["rect"], border_radius=5)
                pg.draw.rect(
                    self.window, btn["border_color"], btn["rect"], 2, border_radius=5
                )
                self.window.blit(btn["surface"], btn["text_pos"])

        # 3.6 音量滑块浮窗
        if self.volume_slider_visible and self._vol_slider_rect:
            self._render_volume_slider()

        # 4. 右下角显示回合信息（避开功能按钮）
        vm = view_model or GameplayViewModel(
            major_round=self.major_round,
            minor_round=self.minor_round,
            player_country=self.player_country,
            country_labels=self.country_labels,
        )
        country_label = (
            vm.country_labels.get(vm.player_country, "") if vm.player_country else ""
        )
        round_text = GameplayRenderService.build_round_text(
            vm.major_round,
            vm.minor_round,
            country_label,
        )
        round_surf = self.round_counter_font.render(round_text, True, pg.Color("black"))

        # 默认贴右下角
        round_rect = round_surf.get_rect(
            bottomright=(self.screen_width - 20, self.screen_height - 12)
        )

        # 若与右下角按钮重叠，则上移到按钮上方
        control_rects = [btn["rect"] for btn in getattr(self, "control_btns", [])]
        if control_rects and any(round_rect.colliderect(r) for r in control_rects):
            top_y = min(r.top for r in control_rects)
            round_rect.bottom = max(20, top_y - 8)

        # 轻微底衬，提高可读性
        bg_rect = round_rect.inflate(12, 6)
        pg.draw.rect(self.window, pg.Color(255, 255, 255, 180), bg_rect, border_radius=6)
        self.window.blit(round_surf, round_rect)

        # 4.5 常态显示三国“民心/政治点数”
        self._draw_country_stats_overlay()

        # 4.6 绘制「抽事件卡」按钮
        self._render_draw_event_btn()

        # 5. 画当前玩家国家标签
        if self.player_country:
            tag_surface = self.country_tag_surfaces[self.player_country]
            self.window.blit(tag_surface, self.country_tag_pos)

            # --- 画战斗UI (攻防比 + 投骰子) ---
            if self.show_combat_ui:
                # 使用跟 InfoPanel 一样的字体
                font = self.combat_ui_font

                # 先清空防守按钮矩形，按可用性重建
                self.defense_jiangdong_btn_rect = None
                self.defense_jiangdong_skip_btn_rect = None
                self.defense_hold_btn_rect = None
                self.defense_hold_skip_btn_rect = None

                # 1. 投骰子按钮
                btn_text = "投骰子"
                btn_surf = font.render(btn_text, True, pg.Color("white"))

                # 按钮背景尺寸
                btn_w = btn_surf.get_width() + 20
                btn_h = btn_surf.get_height() + 10

                # 位置：在国家标签左侧 30px 处，且在 TOP 15% 区域内垂直居中
                top_area_height = int(self.screen_height * 0.15)

                tag_x = self.country_tag_pos[0]
                btn_x = tag_x - btn_w - 30
                btn_y = (top_area_height - btn_h) // 2

                self.combat_btn_rect = pg.Rect(btn_x, btn_y, btn_w, btn_h)

                # 悬停变色逻辑
                btn_color = pg.Color("blue")
                if self.combat_btn_rect.collidepoint(self._get_logical_mouse_pos()):
                    btn_color = pg.Color("#4169E1")  # RoyalBlue (Lighter than Blue)

                # 画按钮背景
                pg.draw.rect(self.window, btn_color, self.combat_btn_rect, border_radius=5)
                # 画文字
                text_rect = btn_surf.get_rect(center=self.combat_btn_rect.center)
                self.window.blit(btn_surf, text_rect)

                # 2. 攻防比文字
                ratio_str = f"攻防比 {self.combat_ratio_val:.1f}"
                ratio_surf = font.render(ratio_str, True, pg.Color("black"))

                ratio_x = btn_x - ratio_surf.get_width() - 30
                ratio_y = btn_y + (btn_h - ratio_surf.get_height()) // 2

                self.window.blit(ratio_surf, (ratio_x, ratio_y))

                # 3. 防守方决策按钮（样式参考投骰子按钮）
                option_right_x = ratio_x - 20
                row_gap = 8
                show_hold = (
                    self.waiting_defender_response
                    and self.defender_can_hold_position
                    and not self.defender_hold_decided
                )

                if show_hold:
                    title = "防守方即时决策"
                    title_surf = font.render(title, True, pg.Color("black"))
                    title_y = btn_y - title_surf.get_height() - 6
                    self.window.blit(
                        title_surf,
                        (option_right_x - title_surf.get_width(), title_y),
                    )

                next_col_right = option_right_x

                # 列2：DR改D1DG（上下两行、统一宽度）
                if show_hold:
                    hold_yes_txt = "防守方选择：DR改D1DG"
                    hold_no_txt = "保持正常DR"
                    hold_yes_surf = font.render(hold_yes_txt, True, pg.Color("white"))
                    hold_no_surf = font.render(hold_no_txt, True, pg.Color("white"))
                    hold_col_w = (
                        max(hold_yes_surf.get_width(), hold_no_surf.get_width()) + 20
                    )

                    hold_yes_rect = pg.Rect(
                        next_col_right - hold_col_w, btn_y, hold_col_w, btn_h
                    )
                    hold_no_rect = pg.Rect(
                        next_col_right - hold_col_w,
                        btn_y + btn_h + row_gap,
                        hold_col_w,
                        btn_h,
                    )
                    self.defense_hold_btn_rect = hold_yes_rect
                    self.defense_hold_skip_btn_rect = hold_no_rect

                    hold_yes_color = pg.Color("#8B0000")
                    if hold_yes_rect.collidepoint(self._get_logical_mouse_pos()):
                        hold_yes_color = pg.Color("#A52A2A")
                    hold_no_color = pg.Color("#4B4B4B")
                    if hold_no_rect.collidepoint(self._get_logical_mouse_pos()):
                        hold_no_color = pg.Color("#666666")

                    pg.draw.rect(self.window, hold_yes_color, hold_yes_rect, border_radius=5)
                    pg.draw.rect(self.window, hold_no_color, hold_no_rect, border_radius=5)
                    self.window.blit(
                        hold_yes_surf,
                        hold_yes_surf.get_rect(center=hold_yes_rect.center),
                    )
                    self.window.blit(
                        hold_no_surf, hold_no_surf.get_rect(center=hold_no_rect.center)
                    )

            # --- 检查是否需要显示“解除混乱”按钮 ---
            # 条件：1. 没有进入战斗准备 (show_combat_ui is False)
            #      2. 选中的单位中，【恰好】只有一个单位处于混乱状态
            #      3. (隐含) combat_target 为 None (show_combat_ui False 已经涵盖了大部分情况，双重保险)
            else:
                self.recover_btn_rect = None  # Reset
                self.no_attack_btn_rect = None

                # 移动后攻击选择窗口：显示“不攻击”按钮
                if self.pending_post_move_attack and self.pending_attacker:
                    btn_surf = self._no_attack_btn_surf
                    btn_w = btn_surf.get_width() + 22
                    btn_h = btn_surf.get_height() + 10

                    top_area_height = int(self.screen_height * 0.15)
                    tag_x = self.country_tag_pos[0]
                    btn_x = tag_x - btn_w - 30
                    btn_y = (top_area_height - btn_h) // 2

                    self.no_attack_btn_rect = pg.Rect(btn_x, btn_y, btn_w, btn_h)

                    btn_color = pg.Color("#555555")
                    if self.no_attack_btn_rect.collidepoint(self._get_logical_mouse_pos()):
                        btn_color = pg.Color("#6f6f6f")

                    pg.draw.rect(self.window, btn_color, self.no_attack_btn_rect, border_radius=5)
                    text_rect = btn_surf.get_rect(center=self.no_attack_btn_rect.center)
                    self.window.blit(btn_surf, text_rect)

                # 正常情况下才绘制“解除混乱”按钮
                confused_list = []
                if not self.pending_post_move_attack:
                    for pid, slot in self.selected_units:
                        prov = self.map_manager.get_by_id(pid)
                        if prov and slot < len(prov.units):
                            u = prov.units[slot]
                            if u.is_confused:
                                confused_list.append(u)

                if (not self.pending_post_move_attack) and len(confused_list) == 1:
                    # 绘制解除混乱按钮
                    btn_surf = self._recover_btn_surf

                    btn_w = btn_surf.get_width() + 20
                    btn_h = btn_surf.get_height() + 10

                    top_area_height = int(self.screen_height * 0.15)
                    tag_x = self.country_tag_pos[0]
                    # 和 combat button 相同的位置逻辑：Tag 左侧 30px
                    btn_x = tag_x - btn_w - 30
                    btn_y = (top_area_height - btn_h) // 2

                    self.recover_btn_rect = pg.Rect(btn_x, btn_y, btn_w, btn_h)

                    # 悬停变色逻辑
                    btn_color = pg.Color("purple")
                    if self.recover_btn_rect.collidepoint(self._get_logical_mouse_pos()):
                        btn_color = pg.Color("#BA55D3")  # MediumOrchid (Lighter Purple)

                    # 按照要求，按钮颜色为紫色
                    pg.draw.rect(self.window, btn_color, self.recover_btn_rect, border_radius=5)

                    text_rect = btn_surf.get_rect(center=self.recover_btn_rect.center)
                    self.window.blit(btn_surf, text_rect)

                # --- 民心等级效果按钮（2-4级）---
                self.morale_lv2_btn_rect = None
                self.morale_lv3_btn_rect = None
                self.morale_lv4_btn_rect = None
                if (
                    self.player_country
                    and not self.pending_post_move_attack
                    and not self.morale_free_move_mode
                    and not self.morale_bonus_mp_mode
                    and not self.morale_cure_mode
                ):
                    _m_support = self._get_people_support_level(self.player_country)
                    _top_h = int(self.screen_height * 0.15)
                    _tag_x = self.country_tag_pos[0]
                    _right_x = _tag_x - 30  # 从 Tag 左侧30px 处开始向左堆叠

                    # 4级：军容严整（按钮：橙色）
                    if self.morale_lv4_pending.get(self.player_country):
                        _s = self._morale_lv4_btn_surf
                        _bw = _s.get_width() + 20
                        _bh = _s.get_height() + 10
                        _bx = _right_x - _bw
                        _by = _top_h * 5 // 6 - _bh // 2  # 第3行：下三分之一
                        self.morale_lv4_btn_rect = pg.Rect(_bx, _by, _bw, _bh)
                        _bc = (
                            pg.Color("#FF8C00")
                            if not self.morale_lv4_btn_rect.collidepoint(self._get_logical_mouse_pos())
                            else pg.Color("#FFA500")
                        )
                        pg.draw.rect(self.window, _bc, self.morale_lv4_btn_rect, border_radius=5)
                        self.window.blit(_s, _s.get_rect(center=self.morale_lv4_btn_rect.center))
                        _right_x = _bx - 10

                    # 3级：老乡指路（按钮：蓝色）
                    if (
                        _m_support >= 3
                        and self.morale_lv3_used.get(self.player_country, 0)
                        != self.major_round
                    ):
                        _s = self._morale_lv3_btn_surf
                        _bw = _s.get_width() + 20
                        _bh = _s.get_height() + 10
                        _bx = _right_x - _bw
                        _by = _top_h * 5 // 6 - _bh // 2  # 第3行：下三分之一
                        self.morale_lv3_btn_rect = pg.Rect(_bx, _by, _bw, _bh)
                        _bc = (
                            pg.Color("#1E90FF")
                            if not self.morale_lv3_btn_rect.collidepoint(self._get_logical_mouse_pos())
                            else pg.Color("#87CEEB")
                        )
                        pg.draw.rect(self.window, _bc, self.morale_lv3_btn_rect, border_radius=5)
                        self.window.blit(_s, _s.get_rect(center=self.morale_lv3_btn_rect.center))
                        _right_x = _bx - 10

                    # 2级：令行禁止（按钮：绿色）
                    if (
                        _m_support >= 2
                        and self.morale_lv2_used.get(self.player_country, 0)
                        != self.major_round
                    ):
                        _s = self._morale_lv2_btn_surf
                        _bw = _s.get_width() + 20
                        _bh = _s.get_height() + 10
                        _bx = _right_x - _bw
                        _by = _top_h * 5 // 6 - _bh // 2  # 第3行：下三分之一
                        self.morale_lv2_btn_rect = pg.Rect(_bx, _by, _bw, _bh)
                        _bc = (
                            pg.Color("#2E8B57")
                            if not self.morale_lv2_btn_rect.collidepoint(self._get_logical_mouse_pos())
                            else pg.Color("#3CB371")
                        )
                        pg.draw.rect(self.window, _bc, self.morale_lv2_btn_rect, border_radius=5)
                        self.window.blit(_s, _s.get_rect(center=self.morale_lv2_btn_rect.center))

                    # --- 民心按鈕 Hover 浮窗 ---
                    _morale_tt_text = None
                    _morale_tt_anchor = None
                    _mx, _my = self._get_logical_mouse_pos()
                    if self.morale_lv4_btn_rect and self.morale_lv4_btn_rect.collidepoint(_mx, _my):
                        _morale_tt_text = "大回合结束时：解除本国一个混乱的己方单位"
                        _morale_tt_anchor = self.morale_lv4_btn_rect
                    elif self.morale_lv3_btn_rect and self.morale_lv3_btn_rect.collidepoint(_mx, _my):
                        _morale_tt_text = "每大回合：选择一个己方单位，获得+1行动力"
                        _morale_tt_anchor = self.morale_lv3_btn_rect
                    elif self.morale_lv2_btn_rect and self.morale_lv2_btn_rect.collidepoint(_mx, _my):
                        _morale_tt_text = "每大回合：免费移动一个己方单位至相邻己方格子"
                        _morale_tt_anchor = self.morale_lv2_btn_rect
                    if _morale_tt_text and _morale_tt_anchor:
                        _ft = self.morale_tt_font
                        _tts = _ft.render(_morale_tt_text, True, pg.Color("#E0FFFF"))
                        _pad_x, _pad_y = 10, 6
                        _fw = _tts.get_width() + _pad_x * 2
                        _fh = _tts.get_height() + _pad_y * 2
                        # X: 左对齐按钮，但确保不超出屏幕右边界
                        _fx = min(_morale_tt_anchor.left, self.screen_width - _fw - 6)
                        _fx = max(0, _fx)
                        _fy = max(0, _morale_tt_anchor.top - _fh - 6)
                        _frect = pg.Rect(_fx, _fy, _fw, _fh)
                        _fbg = pg.Surface((_fw, _fh), pg.SRCALPHA)
                        _fbg.fill((15, 25, 45, 210))
                        self.window.blit(_fbg, _frect.topleft)
                        pg.draw.rect(self.window, pg.Color("#00FFCC"), _frect, 1, border_radius=5)
                        self.window.blit(_tts, (_fx + _pad_x, _fy + _pad_y))

                # 当前处于某个民心效果模式时，顶部显示提示文字
                if self.morale_free_move_mode or self.morale_bonus_mp_mode or self.morale_cure_mode:
                    _top_h = int(self.screen_height * 0.15)
                    _tag_x = self.country_tag_pos[0]
                    if self.morale_free_move_mode:
                        _hint = "令行禁止：请右键选择相邻己方格（仅1格）"
                    elif self.morale_bonus_mp_mode:
                        _hint = "老乡指路：请左键点击一个己方单位"
                    else:
                        _hint = "军容严整：请左键点击一个混乱的己方单位"
                    _hint_surf = self.combat_ui_font.render(_hint, True, pg.Color("#FFD700"))
                    _hint_rect = _hint_surf.get_rect(
                        right=_tag_x - 30,
                        centery=_top_h * 5 // 6,  # 第3行
                    )
                    self.window.blit(_hint_surf, _hint_rect)

                # --- PP行动按钮 / PP模式渲染 ---
                self.pp_btn_rect = None
                self.pp_spend_end_btn_rect = None
                _top_h = int(self.screen_height * 0.15)
                _no_other_mode = (
                    not self.morale_free_move_mode
                    and not self.morale_bonus_mp_mode
                    and not self.morale_cure_mode
                )

                if _no_other_mode and self.player_country:
                    _pp_total = self._get_total_pp(self.player_country)

                    if self.pp_spend_mode:
                        # ---- 模式已激活：左侧显示"结束行动"按钮 + 当前PP + 提示 ----
                        _end_s = self._pp_end_btn_surf
                        _end_bw = _end_s.get_width() + 20
                        _end_bh = _end_s.get_height() + 10
                        _end_bx = 20
                        _end_by = self.screen_height - _end_bh - 20
                        self.pp_spend_end_btn_rect = pg.Rect(_end_bx, _end_by, _end_bw, _end_bh)
                        _end_c = (
                            pg.Color("#888888")
                            if self.pp_spend_end_btn_rect.collidepoint(self._get_logical_mouse_pos())
                            else pg.Color("#555555")
                        )
                        pg.draw.rect(self.window, _end_c, self.pp_spend_end_btn_rect, border_radius=5)
                        self.window.blit(_end_s, _end_s.get_rect(center=self.pp_spend_end_btn_rect.center))

                        # 提示浮窗（悬浮在"结束行动"按钮正上方）
                        if self.pp_summon_target_prov is None:
                            _hint2 = f"PP行动：当前PP {_pp_total}　左键伤兵→回血　右键地块→召唤"
                        else:
                            _pn = getattr(self.pp_summon_target_prov, "name", "?")
                            _hint2 = f"召唤地点：{_pn}　当前PP：{_pp_total}"
                        _ft = self.tooltip_font
                        _h2s = _ft.render(_hint2, True, pg.Color("#E0FFFF"))
                        _pad_x, _pad_y = 10, 6
                        _fw = _h2s.get_width() + _pad_x * 2
                        _fh = _h2s.get_height() + _pad_y * 2
                        # 浮窗定位：按钮正上方，左对齐按钮左边
                        _fx = _end_bx
                        _fy = _end_by - _fh - 6
                        _frect = pg.Rect(_fx, _fy, _fw, _fh)
                        # 半透明深色背景
                        _fbg = pg.Surface((_fw, _fh), pg.SRCALPHA)
                        _fbg.fill((15, 25, 45, 210))
                        self.window.blit(_fbg, _frect.topleft)
                        pg.draw.rect(self.window, pg.Color("#00FFCC"), _frect, 1, border_radius=5)
                        self.window.blit(_h2s, (_fx + _pad_x, _fy + _pad_y))

                        # ---- 召唤子面板由 _render_pp_summon_panel() 在最顶层绘制 ----
                        self.pp_summon_btns = []  # 数据由顶层方法填充

                    elif _pp_total >= 1 and not self.pending_post_move_attack:
                        # ---- 尚未激活：显示"使用政治点数"入口按钮 ----
                        _pp_s = self._pp_btn_surf
                        _pp_bw = _pp_s.get_width() + 20
                        _pp_bh = _pp_s.get_height() + 10
                        _pp_bx = 20
                        _pp_by = self.screen_height - _pp_bh - 20
                        self.pp_btn_rect = pg.Rect(_pp_bx, _pp_by, _pp_bw, _pp_bh)
                        _pp_col = (
                            pg.Color("#DAA520")
                            if self.pp_btn_rect.collidepoint(self._get_logical_mouse_pos())
                            else pg.Color("#B8860B")
                        )
                        pg.draw.rect(self.window, _pp_col, self.pp_btn_rect, border_radius=5)
                        self.window.blit(_pp_s, _pp_s.get_rect(center=self.pp_btn_rect.center))
                        # 旁边显示当前PP数值
                        _ppv_s = self.combat_ui_font.render(f"({_pp_total}PP)", True, pg.Color("#FFD700"))
                        self.window.blit(
                            _ppv_s,
                            (
                                _pp_bx + _pp_bw + 5,
                                _pp_by + (_pp_bh - _ppv_s.get_height()) // 2,
                            ),
                        )

            # --- 画战斗结果 (Top UI 第1行：顶部区域上三分之一) ---
            # timer != 0 时显示; combat_result_title 始终为单行
            if self.combat_result_title and self.combat_result_timer != 0:
                font = self.combat_ui_font
                top_area_height = int(self.screen_height * 0.15)
                tag_x = self.country_tag_pos[0]
                y_center = top_area_height // 6
                parts = self.combat_result_title.split(" · ")
                current_right_x = tag_x - 30
                for i, part in enumerate(reversed(parts)):
                    color = pg.Color("blue") if "骰" in part else pg.Color("black")
                    surf = font.render(part, True, color)
                    w = surf.get_width()
                    self.window.blit(surf, (current_right_x - w, y_center - surf.get_height() // 2))
                    current_right_x -= w
                    if i < len(parts) - 1:
                        current_right_x -= 5
                        sep_surf = font.render("·", True, pg.Color("black"))
                        self.window.blit(
                            sep_surf,
                            (
                                current_right_x - sep_surf.get_width(),
                                y_center - sep_surf.get_height() // 2,
                            ),
                        )
                        current_right_x -= sep_surf.get_width() + 5

        # 6. 画选中框（覆盖在最上层）
        self.selection_overlay.draw(
            surface=self.window,
            selections=self.selected_units,
            province_lookup=self.map_manager.get_by_id,
            rect_provider=self.unit_renderer.selection_rects,
            hex_side=self.hex_side,
        )

        # 7. 画右侧信息面板 (UI)
        if self.info_panel:
            self.info_panel.draw(self.window)

        # 8.0 战斗判定表按鈕（右下角，按鈕本体低层渲染，不遮卡牌）
        _ct_s = self._combat_table_btn_surf
        _ct_bw = _ct_s.get_width() + 20
        _ct_bh = _ct_s.get_height() + 10
        _ct_bx = self.screen_width - _ct_bw - 20
        # 动态计算Y坐标：确保始终在回合信息块（round_rect）和底部功能按钮上方，
        # 适配不同纵横比的屏幕，避免硬编码偏移量导致的重叠。
        _ct_floor = round_rect.top - 8  # 贴在回合信息块正上方
        _ct_by = max(10, _ct_floor - _ct_bh)
        self.combat_table_btn_rect = pg.Rect(_ct_bx, _ct_by, _ct_bw, _ct_bh)
        _mx, _my = self._get_logical_mouse_pos()
        _ct_hovered = self.combat_table_btn_rect.collidepoint(_mx, _my)
        _ct_col = pg.Color("#4A6FA5") if not _ct_hovered else pg.Color("#6B9FD4")
        pg.draw.rect(self.window, _ct_col, self.combat_table_btn_rect, border_radius=5)
        self.window.blit(_ct_s, _ct_s.get_rect(center=self.combat_table_btn_rect.center))
        # 浮窗表格在 8.4 节高层渲染，第一次记录坐标供后用

        # 8. 绘制卡牌面板（卡牌不占用回合动作次数）
        self.skip_jiangdong_card_btn_rect = None
        if self.card_panel:
            self.card_panel.draw(self.window)

            # 江东止啼“不使用”按钮：放在卡牌区域（叠加在江东止啼卡牌位置）
            show_jiangdong_skip = (
                self.show_combat_ui
                and self.waiting_defender_response
                and self.defender_can_use_jiangdong
                and not self.defender_jiangdong_decided
            )
            if show_jiangdong_skip:
                jd_rect = self.card_panel.card_rects.get("card_jiangdong_zhiti")
                if jd_rect:
                    overlay_h = max(20, int(jd_rect.height * 0.33))
                    btn_rect = pg.Rect(
                        jd_rect.left + 4,
                        jd_rect.bottom - overlay_h - 4,
                        jd_rect.width - 8,
                        overlay_h,
                    )
                    self.skip_jiangdong_card_btn_rect = btn_rect

                    btn_color = pg.Color("#4B4B4B")
                    if btn_rect.collidepoint(self._get_logical_mouse_pos()):
                        btn_color = pg.Color("#666666")

                    pg.draw.rect(self.window, btn_color, btn_rect, border_radius=6)
                    skip_surf = self.tooltip_font.render("不使用江东止啼", True, pg.Color("white"))
                    self.window.blit(skip_surf, skip_surf.get_rect(center=btn_rect.center))

            # 卡牌 tooltip 始终在卡牌面板最顶层绘制（不受江东止啼条件限制；事件卡覆盖层激活时跳过）
            if not self.event_card_overlay:
                self.card_panel.draw_tooltip(self.window)

        # 8.3 召唤子面板（PP系统）：绘制在最顶层，覆盖卡牌等UI
        self._render_pp_summon_panel()

        # 8.4 战斗判定表浮窗表格（高层，覆盖卡牌面板）
        if self.combat_table_btn_rect and self.combat_table_btn_rect.collidepoint(
            self._get_logical_mouse_pos()
        ):
            _ct_bx = self.combat_table_btn_rect.left
            _ct_by = self.combat_table_btn_rect.top
            _tt_ft = self.morale_tt_font
            _ct_headers = ["骰点", "1:2", "1:1", "2:1", "3:1", "4:1", "5:1"]
            _ct_rows = [
                ["1", "攻损2", "攻损1", "攻损1", "无效", "无效", "防乱"],
                ["2", "攻损1", "攻乱", "双乱", "防乱", "防乱", "防乱"],
                ["3", "攻乱", "双乱", "无效", "防乱", "防退", "防退"],
                ["4", "攻乱", "无效", "防乱", "防退", "防退", "防退"],
                ["5", "无效", "防乱", "防退", "防退", "防损1", "防损1"],
                ["6", "防乱", "防退", "防损1", "防损1", "防损1", "防损1退"],
            ]
            _all_rows = [_ct_headers] + _ct_rows
            _col_widths = []
            for _ci in range(7):
                _max_w = max(_tt_ft.size(_all_rows[_ri][_ci])[0] for _ri in range(7))
                _col_widths.append(_max_w + 14)
            _row_h = _tt_ft.get_height() + 8
            _tbl_w = sum(_col_widths) + 2
            _tbl_h = len(_all_rows) * _row_h + 2
            _tbl_x = max(0, min(_ct_bx, self.screen_width - _tbl_w - 4))
            _tbl_y = max(0, _ct_by - _tbl_h - 6)
            _tbl_bg = pg.Surface((_tbl_w, _tbl_h), pg.SRCALPHA)
            _tbl_bg.fill((12, 20, 40, 220))
            self.window.blit(_tbl_bg, (_tbl_x, _tbl_y))
            pg.draw.rect(
                self.window,
                pg.Color("#00FFCC"),
                pg.Rect(_tbl_x, _tbl_y, _tbl_w, _tbl_h),
                1,
                border_radius=4,
            )
            _cx_start = _tbl_x + 1
            _cy = _tbl_y + 1
            for _ri, _row_data in enumerate(_all_rows):
                _is_header = _ri == 0
                _cx = _cx_start
                if _is_header:
                    _hdr_bg = pg.Surface((sum(_col_widths), _row_h), pg.SRCALPHA)
                    _hdr_bg.fill((30, 60, 100, 180))
                    self.window.blit(_hdr_bg, (_cx, _cy))
                for _ci, _cell in enumerate(_row_data):
                    _tc = pg.Color("#FFD700") if _is_header else pg.Color("#E0FFFF")
                    if not _is_header and _ci > 0:
                        if _cell in ("攻损2", "攻损1", "攻乱", "双乱"):
                            _tc = pg.Color("#FF8080")
                        elif _cell in ("防退", "防损1", "防损1退"):
                            _tc = pg.Color("#80FF80")
                        elif _cell == "防乱":
                            _tc = pg.Color("#AAFFCC")
                        elif _cell == "无效":
                            _tc = pg.Color("#888888")
                    _cell_surf = _tt_ft.render(_cell, True, _tc)
                    _cell_rect = _cell_surf.get_rect(
                        centerx=_cx + _col_widths[_ci] // 2, centery=_cy + _row_h // 2
                    )
                    self.window.blit(_cell_surf, _cell_rect)
                    if _ci < 6:
                        pg.draw.line(
                            self.window,
                            pg.Color("#334466"),
                            (_cx + _col_widths[_ci], _cy),
                            (_cx + _col_widths[_ci], _cy + _row_h),
                        )
                    _cx += _col_widths[_ci]
                if _ri < len(_all_rows) - 1:
                    pg.draw.line(
                        self.window,
                        pg.Color("#334466"),
                        (_cx_start, _cy + _row_h),
                        (_cx_start + sum(_col_widths), _cy + _row_h),
                    )
                _cy += _row_h

        # 8.5 事件卡覆盖层（最顶层，覆盖一切）
        self._render_event_card_overlay()

        # 9. 画鼠标悬停提示 (Tooltip)：事件卡覆盖层激活时跳过
        if not self.event_card_overlay:
            self._draw_hover_tooltip()
            self._draw_evt_info_tooltip()

        # 9.5 游戏规则PDF覆盖层（始终位于最顶层）
        self._render_help_overlay()
