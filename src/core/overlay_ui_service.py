from __future__ import annotations

from typing import List, Sequence, Tuple

import pygame as pg

MAX_UNIT_STACK = 3


class OverlayUIService:
    """PP召唤面板与悬停提示渲染服务。"""

    def render_pp_summon_panel(self, app) -> None:
        self = app
        if not (
            self.pp_spend_mode
            and self.pp_summon_target_prov is not None
            and self.player_country
        ):
            return

        _pp_total = self._get_total_pp(self.player_country)
        _top_h = int(self.screen_height * 0.15)

        _panel_w = int(self.screen_width * 0.55)
        _btn_h = int(self.screen_height * 0.055)
        _btn_gap = 8
        _cols = 3
        _btn_w = (_panel_w - (_cols + 1) * _btn_gap) // _cols
        _panel_h = _btn_h * 2 + _btn_gap * 3 + 36
        _panel_x = (self.screen_width - _panel_w) // 2
        _panel_y = _top_h + 12

        pg.draw.rect(
            self.window,
            pg.Color(20, 20, 40, 220),
            pg.Rect(_panel_x, _panel_y, _panel_w, _panel_h),
            border_radius=8,
        )
        pg.draw.rect(
            self.window,
            pg.Color("#00FFCC"),
            pg.Rect(_panel_x, _panel_y, _panel_w, _panel_h),
            2,
            border_radius=8,
        )

        _unit_defs = [
            ("infantry", "步兵"),
            ("cavalry", "骑兵"),
            ("archer", "弓兵"),
        ]
        _hp_defs = [(1, 1), (2, 2)]
        _mouse = self._get_logical_mouse_pos()

        self.pp_summon_btns = []
        for ui, (utype, uname) in enumerate(_unit_defs):
            col = ui % _cols
            for hi, (hp_val, pp_cost) in enumerate(_hp_defs):
                _bx2 = _panel_x + _btn_gap + col * (_btn_w + _btn_gap)
                _by2 = _panel_y + 8 + hi * (_btn_h + _btn_gap)
                _br2 = pg.Rect(_bx2, _by2, _btn_w, _btn_h)
                _can = _pp_total >= pp_cost
                _hover = _br2.collidepoint(_mouse)
                if not _can:
                    _bc2 = pg.Color("#444444")
                elif _hover:
                    _bc2 = pg.Color("#208850")
                else:
                    _bc2 = pg.Color("#145530")
                pg.draw.rect(self.window, _bc2, _br2, border_radius=4)
                _label = f"{uname} {hp_val}血 ({pp_cost}PP)"
                _ls = self.combat_ui_font.render(
                    _label,
                    True,
                    pg.Color("white") if _can else pg.Color("#888888"),
                )
                self.window.blit(_ls, _ls.get_rect(center=_br2.center))
                self.pp_summon_btns.append(
                    {
                        "rect": _br2,
                        "unit_type": utype,
                        "hp": hp_val,
                        "cost": pp_cost,
                        "enabled": _can,
                    }
                )

        _cancel_w = int(_panel_w * 0.25)
        _cancel_x = _panel_x + (_panel_w - _cancel_w) // 2
        _cancel_y = _panel_y + 8 + 2 * (_btn_h + _btn_gap)
        _cancel_r = pg.Rect(_cancel_x, _cancel_y, _cancel_w, _btn_h)
        _hover_cancel = _cancel_r.collidepoint(_mouse)
        pg.draw.rect(
            self.window,
            pg.Color("#883322") if _hover_cancel else pg.Color("#552211"),
            _cancel_r,
            border_radius=4,
        )
        _cs = self.combat_ui_font.render("取消召唤", True, pg.Color("white"))
        self.window.blit(_cs, _cs.get_rect(center=_cancel_r.center))
        self.pp_summon_btns.append(
            {
                "rect": _cancel_r,
                "unit_type": None,
                "hp": 0,
                "cost": 0,
                "enabled": True,
            }
        )

    def draw_hover_tooltip(self, app) -> None:
        self = app
        if self.state != type(self.state).PLAYING:
            return

        mouse_pos = self._get_logical_mouse_pos()
        if not self.window.get_rect().collidepoint(mouse_pos):
            return

        tooltip_parts: List[Tuple[str, pg.Color, bool, bool]] = []

        hovered_unit = self._get_unit_slot_at(mouse_pos)
        if hovered_unit:
            pid, slot = hovered_unit
            prov = self.map_manager.get_by_id(pid)
            if prov and slot < len(prov.units):
                u_type = prov.units[slot].unit_type
                t_name = OverlayUIService.get_display_name(u_type)
                if t_name:
                    tooltip_parts.append((t_name, pg.Color("black"), False, False))

        if not tooltip_parts:
            if self._is_hovering_ban_line(mouse_pos):
                tooltip_parts.append(("禁行", pg.Color("black"), False, False))
            elif self._is_hovering_river(mouse_pos):
                tooltip_parts.append(("河流", pg.Color("black"), False, False))
                tooltip_parts.append(
                    (
                        " 跨河移动行动力消耗+1；进攻跨河部队攻击力-1",
                        pg.Color("#555555"),
                        False,
                        False,
                    )
                )

        if not tooltip_parts:
            hovered_prov = self._get_province_at(mouse_pos)
            if hovered_prov:
                p_name = hovered_prov.name
                city_name_map = {
                    "Liangzhou": "凉州",
                    "Chengdu": "成都",
                    "Hanzhong": "汉中",
                    "Changan": "长安",
                    "Jingzhou": "荆州",
                    "Xiangyang": "襄阳",
                    "Luoyang": "洛阳",
                    "Wuchang": "武昌",
                    "Changsha": "长沙",
                    "Youzhou": "幽州",
                    "Hefei": "合肥",
                    "Jianye": "建业",
                }

                if (
                    p_name
                    and not p_name.startswith("Tile")
                    and not p_name.startswith("Border")
                ):
                    base_name = city_name_map.get(p_name, p_name)
                else:
                    t_key = hovered_prov.terrain.lower() if hovered_prov.terrain else "plain"
                    base_name = OverlayUIService.get_display_name(t_key)

                if base_name:
                    terrain_lower = (hovered_prov.terrain or "").lower()
                    is_city = terrain_lower == "city"
                    is_mountain = terrain_lower in ("hill", "mountain", "hills", "mountains")
                    if is_city:
                        tooltip_parts.append((base_name, pg.Color("#D4AF37"), True, True))
                        tooltip_parts.append(
                            (
                                " 进攻此格，攻防比向左移动一列",
                                pg.Color("#555555"),
                                False,
                                False,
                            )
                        )
                    else:
                        tooltip_parts.append((base_name, pg.Color("black"), False, False))
                        if is_mountain:
                            tooltip_parts.append(
                                (
                                    " 行动力消耗+1；进攻此格部队攻击力-1",
                                    pg.Color("#555555"),
                                    False,
                                    False,
                                )
                            )

                if hovered_prov.country:
                    country_cn = self.country_labels.get(hovered_prov.country, hovered_prov.country)
                    c_color = self.kingdom_repository.get_color(hovered_prov.country)
                    if not c_color:
                        c_color = self.country_button_colors.get(hovered_prov.country, pg.Color("black"))
                    tooltip_parts.append((f"({country_cn})", c_color, True, True))

        if tooltip_parts:
            if tooltip_parts == self._last_tooltip_data and self._cached_tooltip_surface:
                final_surf = self._cached_tooltip_surface
            else:
                font_regular = self.tooltip_font
                font_bold = self.tooltip_bold_font

                rendered_surfaces = []
                total_w = 0
                max_h = 0

                shadow_offset = (1, 1)
                shadow_color = pg.Color("black")

                for text, color, is_bold, has_shadow in tooltip_parts:
                    font = font_bold if is_bold else font_regular
                    fg_surf = font.render(text, True, color)

                    if has_shadow:
                        shadow_surf = font.render(text, True, shadow_color)
                        w = fg_surf.get_width() + abs(shadow_offset[0])
                        h = fg_surf.get_height() + abs(shadow_offset[1])
                        container = pg.Surface((w, h), pg.SRCALPHA)
                        container.blit(shadow_surf, shadow_offset)
                        container.blit(fg_surf, (0, 0))
                        s = container
                    else:
                        s = fg_surf

                    rendered_surfaces.append(s)
                    total_w += s.get_width()
                    max_h = max(max_h, s.get_height())

                final_surf = pg.Surface((total_w, max_h), pg.SRCALPHA)
                current_x = 0
                for s in rendered_surfaces:
                    y_offset = (max_h - s.get_height()) // 2
                    final_surf.blit(s, (current_x, y_offset))
                    current_x += s.get_width()

                self._last_tooltip_data = tooltip_parts
                self._cached_tooltip_surface = final_surf

            x, y = mouse_pos
            x += 15
            y += 15
            rect = final_surf.get_rect(topleft=(x, y))

            if rect.right > self.screen_width:
                rect.right = mouse_pos[0] - 5
            if rect.bottom > self.screen_height:
                rect.bottom = mouse_pos[1] - 5

            bg_rect = rect.inflate(10, 6)
            pg.draw.rect(self.window, pg.Color("white"), bg_rect, border_radius=3)
            pg.draw.rect(self.window, pg.Color("black"), bg_rect, 1, border_radius=3)

            self.window.blit(final_surf, rect)

    @staticmethod
    def get_display_name(key: str) -> str | None:
        mapping = {
            "city": "城市",
            "hill": "山地",
            "mountain": "山地",
            "mountains": "山地",
            "hills": "山地",
            "plain": "平原",
            "infantry": "步兵",
            "cavalry": "骑兵",
            "archer": "弓兵",
            "HUBAO_cavalry": "虎豹骑",
            "WUDANG_archer": "无当飞军",
            "JIEFAN_infantry": "解烦兵",
        }

        if key in mapping:
            return mapping[key]

        key_lower = key.lower()
        if "infantry" in key_lower:
            return "步兵"
        if "cavalry" in key_lower:
            return "骑兵"
        if "archer" in key_lower:
            return "弓兵"

        return None
