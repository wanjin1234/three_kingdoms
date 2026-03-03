"""
事件卡服务：抽离 `GameApp` 中的事件卡流程逻辑。

该模块保留现有规则与行为，`GameApp` 仅做委托调用。
"""

from __future__ import annotations

import logging
import os
from typing import Any

import pygame as pg

logger = logging.getLogger(__name__)


class EventCardService:
    """事件卡系统服务。"""

    def can_draw_event_card(self, app: Any, country: str) -> bool:
        """判断 country 当前是否可以消耗 1 政治点数抽取事件卡。"""
        if app.state != type(app.state).PLAYING:
            return False
        if app.turn_game_finished:
            return False
        if app.major_round_choice_pending:
            return False
        if app.show_combat_ui:
            return False
        if app.pending_post_move_attack:
            return False
        if app.selecting_evt_target or app.event_card_overlay:
            return False
        stats = app.country_stats.get(country, {})
        total_pp = int(stats.get("political_points", 0)) + app.evt_temp_pp.get(country, 0)
        return total_pp >= 1

    def spend_pp(self, app: Any, country: str, amount: int = 1) -> bool:
        """消耗政治点数（优先消耗临时 PP，再消耗普通 PP）。"""
        stats = app.country_stats.setdefault(
            country, {"people_support": 0, "political_points": 0}
        )
        pp = int(stats.get("political_points", 0))
        temp = app.evt_temp_pp.get(country, 0)
        total = pp + temp
        if total < amount:
            return False
        if temp >= amount:
            app.evt_temp_pp[country] = temp - amount
        else:
            remaining = amount - temp
            app.evt_temp_pp[country] = 0
            stats["political_points"] = pp - remaining
        return True

    def trigger_draw_event_card(self, app: Any, country: str) -> None:
        """尝试让 country 消耗 1 政治点数抽取一张事件卡。"""
        if not self.can_draw_event_card(app, country):
            if app.info_panel:
                app.info_panel.show_message("政治点数不足或当前不可抽卡")
            return
        if not self.spend_pp(app, country, 1):
            return
        card = app.event_card_deck.draw(country)
        if not card:
            if app.info_panel:
                app.info_panel.show_message("事件卡牌堆已空")
            return

        is_negative = self.is_negative_event(app, card, country)
        safe_draw = app.evt_draw_again_safe
        app.evt_draw_again_safe = False

        if safe_draw and is_negative:
            if app.info_panel:
                app.info_panel.show_message(
                    f"「不懈于内」：抽到「{card.name}」但效果无效", duration=3.0
                )
            return

        app.event_card_overlay = {"card": card, "drawer": country, "safe": safe_draw}

    def is_negative_event(self, app: Any, card, country: str) -> bool:
        """判定事件卡对抽卡方 country 是否为负面效果（用于'不懈于内'）。"""
        et = card.effect_type
        ev = card.effect_value
        tc = country if card.target_country == "DRAWER" else card.deck
        if tc == country and et in ("pp", "morale") and ev < 0:
            return True
        negative_flags = {
            "flag_xingluo": "SHU",
            "flag_hu_recruit": "WEI",
            "flag_hefei": "WU",
        }
        flag_country = negative_flags.get(et)
        if flag_country and flag_country == country:
            return True
        return False

    def confirm_event_card(self, app: Any) -> None:
        """玩家点击了「确认」，执行事件卡效果。"""
        if not app.event_card_overlay:
            return
        card = app.event_card_overlay["card"]
        drawer: str = app.event_card_overlay["drawer"]
        is_free_draw: bool = app.event_card_overlay.get("free_draw", False)
        actual_actor: str = app.event_card_overlay.get("actual_actor", drawer)
        app.event_card_overlay = None
        app.evt_overlay_ok_btn = None

        self.apply_event_card(app, card, drawer)

        if app.event_card_overlay:
            return

        if not card.needs_target:
            pp_country = actual_actor if is_free_draw else drawer
            current_pp = int(app.country_stats.get(pp_country, {}).get("political_points", 0)) + app.evt_temp_pp.get(pp_country, 0)
            if current_pp >= 1:
                if not app.evt_draw_phase and pp_country == app.player_country:
                    self.enter_evt_draw_phase_if_needed(app)
            else:
                self.exit_evt_draw_phase(app)

        if (
            app.human_country is not None
            and app.selecting_evt_target
            and app.pending_evt_card_id
            and app.pending_evt_drawer != app.human_country
        ):
            app.ai_service.auto_select_evt_target(app, app.pending_evt_drawer)

        ai_actor = actual_actor if is_free_draw else drawer
        if (
            app.human_country is not None
            and ai_actor != app.human_country
            and not app.event_card_overlay
            and not app.selecting_evt_target
        ):
            app._ai_turn_timer = pg.time.get_ticks() + 400

    def apply_event_card(self, app: Any, card, drawer: str) -> None:
        """执行事件卡效果。"""
        et = card.effect_type
        ev = card.effect_value

        tc = card.target_country
        if tc == "DRAWER":
            tc = drawer

        def add_pp(c: str, n: int) -> None:
            stats = app.country_stats.setdefault(
                c, {"people_support": 0, "political_points": 0}
            )
            stats["political_points"] = int(stats.get("political_points", 0)) + n

        def add_morale(c: str, n: int) -> None:
            stats = app.country_stats.setdefault(
                c, {"people_support": 0, "political_points": 0}
            )
            stats["people_support"] = int(stats.get("people_support", 0)) + n
            app._check_tianxia_guixin_victory()

        msg = f"「{card.name}」：{card.description}"

        if not (card.id == "evt_jiangdong_cai" and app.evt_laomaikuai_active):
            record_countries = app.turn_order if tc == "ALL" else [tc]
            for rc in record_countries:
                app.evt_applied_this_round.setdefault(rc, []).append(
                    (card.name, card.description)
                )

        if et == "pp":
            if card.id == "evt_jiangdong_cai" and app.evt_laomaikuai_active:
                app.evt_laomaikuai_active = False
                app._remove_from_major_round("老迈昏聩", "WU")
                if app.info_panel:
                    app.info_panel.show_message(
                        f"「老迈昏聩」使「{card.name}」效果无效", duration=3.0
                    )
                return
            add_pp(tc, ev)

        elif et == "morale":
            add_morale(tc, ev)

        elif et == "pp_temp":
            app.evt_temp_pp[tc] = app.evt_temp_pp.get(tc, 0) + ev
            msg = f"「{card.name}」：获得 {ev} 点临时政治点数（本小回合内有效）"
            if not app.evt_draw_phase and tc == app.player_country:
                self.enter_evt_draw_phase_if_needed(app)

        elif et == "flag_xingluo":
            add_pp(tc, ev)
            app.evt_xingluo_active = True
            app._refresh_session_skill_display()

        elif et == "conditional_lonzhong":
            app.evt_lonzhong_skill += 1
            if app.evt_xingluo_active:
                add_pp("SHU", 1)
                app.evt_xingluo_active = False
                msg = f"「{card.name}」：蜀汉获得「隆中定计」触发机会（累计 {app.evt_lonzhong_skill} 次，进攻东吴时+1骰点）；「星落秋风」补偿触发，额外+1政治点数"
            else:
                msg = f"「{card.name}」：蜀汉获得「隆中定计」触发机会（累计 {app.evt_lonzhong_skill} 次，进攻东吴时+1骰点）"
            app._refresh_session_skill_display()

        elif et == "conditional_jingzhu":
            jingzhou = app.map_manager.get_by_id(35)
            if jingzhou and jingzhou.country == "WU":
                app.evt_jingzhu_skill += 1
                app.evt_applied_major_round.setdefault(tc, []).append(
                    (card.name, card.description)
                )
                msg = f"「{card.name}」：荆州属于东吴！东吴获得进攻蜀汉骰点+1（累计 {app.evt_jingzhu_skill}）"
            else:
                msg = f"「{card.name}」：荆州不属于东吴，无效"

        elif et == "conditional_ruzhong":
            hanzhong = app.map_manager.get_by_id(17)
            if hanzhong and hanzhong.country == "WEI":
                add_pp("WEI", ev)
                msg = f"「{card.name}」：汉中属于曹魏！曹魏政治点数+{ev}"
            else:
                msg = f"「{card.name}」：汉中不属于曹魏，无效"

        elif et == "draw_again_safe":
            app.evt_draw_again_safe = True
            msg = f"「{card.name}」：额外免费抽一张，若为负效果则无效"
            next_card = app.event_card_deck.draw(tc)
            if next_card:
                ni = self.is_negative_event(app, next_card, tc)
                if ni:
                    app.evt_draw_again_safe = False
                    msg += f"\n再抽到「{next_card.name}」，为负效果——已被「不懈于内」免除"
                else:
                    app.evt_draw_again_safe = False
                    app.event_card_overlay = {
                        "card": next_card,
                        "drawer": tc,
                        "safe": False,
                        "free_draw": True,
                        "actual_actor": drawer,
                    }
                    if app.info_panel:
                        app.info_panel.show_message(msg, duration=2.0)
                    return
            else:
                msg += "\n（牌堆已空，未能再次抽卡）"

        elif et == "evt_skill_yishen":
            app.evt_yishen_skill += 1
            msg = f"「{card.name}」：蜀汉获得「一身是胆」触发机会（累计 {app.evt_yishen_skill} 次，被进攻低于1:1时自动触发）"
            app._refresh_session_skill_display()

        elif et == "flag_liukang":
            app.evt_flag_liukang = True
            app.evt_flag_liukang_drawer = drawer
            for rc in app.turn_order:
                app.evt_applied_major_round.setdefault(rc, []).append(
                    (card.name, card.description)
                )

        elif et == "flag_hefei":
            app.evt_flag_hefei = True
            r = app.turn_order if tc == "ALL" else [tc]
            for rc in r:
                app.evt_applied_major_round.setdefault(rc, []).append(
                    (card.name, card.description)
                )

        elif et == "flag_she_hushu":
            app.evt_flag_she_hushu = True
            r = app.turn_order if tc == "ALL" else [tc]
            for rc in r:
                app.evt_applied_major_round.setdefault(rc, []).append(
                    (card.name, card.description)
                )

        elif et == "flag_hu_recruit":
            app.evt_flag_hu_recruit = True
            r = app.turn_order if tc == "ALL" else [tc]
            for rc in r:
                app.evt_applied_major_round.setdefault(rc, []).append(
                    (card.name, card.description)
                )

        elif et == "flag_wuwei":
            add_pp("WU", ev)
            app.evt_flag_wuwei = True
            app.evt_flag_wuwei_drawer = drawer
            for rc in app.turn_order:
                app.evt_applied_major_round.setdefault(rc, []).append(
                    (card.name, card.description)
                )

        elif et == "flag_all_attack":
            app.evt_flag_all_attack = True
            app.evt_all_attack_drawer = drawer
            for rc in app.turn_order:
                app.evt_applied_major_round.setdefault(rc, []).append(
                    (card.name, card.description)
                )

        elif et == "flag_laomaikuai":
            app.evt_laomaikuai_active = True
            app.evt_applied_major_round.setdefault(tc, []).append(
                (card.name, card.description)
            )

        elif et == "flag_wuzi":
            app.evt_wuzi_rounds = 5
            app.evt_wuzi_bonus = min(3, app.evt_wuzi_bonus + 1)
            r = app.turn_order if tc == "ALL" else [tc]
            for rc in r:
                app.evt_applied_major_round.setdefault(rc, []).append(
                    (card.name, card.description)
                )
            msg = f"「{card.name}」：曹魏进攻骰点+{app.evt_wuzi_bonus}（剩余 {app.evt_wuzi_rounds} 小回合）"

        elif et in (
            "unit_mp_plus",
            "unit_dice_perm_def_minus",
            "unit_atk_plus",
            "unit_dice_bonus",
        ):
            app.selecting_evt_target = True
            app.pending_evt_card_id = card.id
            app.pending_evt_drawer = tc
            if tc != app.human_country:
                app.ai_service.auto_select_evt_target(app, tc)
                return
            if app.info_panel:
                app.info_panel.show_message(
                    f"「{card.name}」：请点击目标单位（{app.country_labels.get(tc, tc)}己方）",
                    duration=-1,
                )
            return

        elif et == "province_def_plus":
            app.selecting_evt_target = True
            app.pending_evt_card_id = card.id
            app.pending_evt_drawer = tc
            if tc != app.human_country:
                app.ai_service.auto_select_evt_target(app, tc)
                return
            if app.info_panel:
                app.info_panel.show_message(
                    f"「{card.name}」：请点击目标地块（{app.country_labels.get(tc, tc)}己方部队）",
                    duration=-1,
                )
            return

        if app.info_panel:
            app.info_panel.show_message(msg, duration=4.0)

    def apply_evt_target_unit(self, app: Any, prov_id: int, slot: int) -> None:
        """完成需要点击单位的事件卡效果。"""
        card_id = app.pending_evt_card_id
        app.selecting_evt_target = False
        app.pending_evt_card_id = None
        app.pending_evt_drawer = None

        prov = app.map_manager.get_by_id(prov_id)
        if not prov or slot >= len(prov.units):
            if app.info_panel:
                app.info_panel.show_message("目标无效，事件卡取消")
            return
        unit = prov.units[slot]
        card = app.event_card_deck.get_definition(card_id)

        if card_id == "evt_wangshen":
            unit.major_mp_bonus = getattr(unit, "major_mp_bonus", 0) + card.effect_value
            unit.mp += card.effect_value
            if app.info_panel:
                app.info_panel.show_message(
                    f"「{card.name}」：{unit.unit_type} 本大回合行动力+{card.effect_value}"
                )

        elif card_id == "evt_yuda":
            unit.temp_dice_bonus += 1
            unit.defense_bonus = getattr(unit, "defense_bonus", 0) - 1
            if app.info_panel:
                app.info_panel.show_message("「{card.name}」：本回合骰点+1，永久防御-1")

        elif card_id == "evt_xiedie":
            unit.attack_bonus = getattr(unit, "attack_bonus", 0) + card.effect_value
            if app.info_panel:
                app.info_panel.show_message(
                    f"「{card.name}」：{unit.unit_type} 永久攻击力+{card.effect_value}"
                )

        elif card_id == "evt_libing":
            unit.temp_dice_bonus += card.effect_value
            if app.info_panel:
                app.info_panel.show_message(
                    f"「{card.name}」：{unit.unit_type} 本大回合骰点+{card.effect_value}"
                )

        self.check_evt_draw_phase_pp(app)
        if (
            app.player_country
            and app.human_country is not None
            and app.player_country != app.human_country
            and app._ai_turn_timer is None
            and not app.turn_game_finished
        ):
            app._ai_turn_timer = pg.time.get_ticks() + 400

    def apply_evt_target_province(self, app: Any, prov_id: int) -> None:
        """完成需要点击地块的事件卡效果（江东铁壁）。"""
        card_id = app.pending_evt_card_id
        app.selecting_evt_target = False
        app.pending_evt_card_id = None
        app.pending_evt_drawer = None

        card = app.event_card_deck.get_definition(card_id)
        prov = app.map_manager.get_by_id(prov_id)
        if not prov or not prov.units:
            if app.info_panel:
                app.info_panel.show_message("该地块无己方部队，事件卡取消")
            return

        for unit in prov.units:
            unit.defense_bonus = getattr(unit, "defense_bonus", 0) + card.effect_value
        if app.info_panel:
            app.info_panel.show_message(
                f"「{card.name}」：{prov.name} 上 {len(prov.units)} 个单位永久防御+{card.effect_value}"
            )

        self.check_evt_draw_phase_pp(app)
        if (
            app.player_country
            and app.human_country is not None
            and app.player_country != app.human_country
            and app._ai_turn_timer is None
            and not app.turn_game_finished
        ):
            app._ai_turn_timer = pg.time.get_ticks() + 400

    def enter_evt_draw_phase_if_needed(self, app: Any) -> None:
        """若当前为人类玩家且有政治点数，进入事件卡抽取阶段。"""
        if not app.player_country:
            return
        if app.major_round_choice_pending:
            return
        if app.human_country is not None and app.player_country != app.human_country:
            return
        stats = app.country_stats.get(app.player_country, {})
        pp = int(stats.get("political_points", 0)) + app.evt_temp_pp.get(app.player_country, 0)
        if pp >= 1:
            app.evt_draw_phase = True
            label = app.country_labels.get(app.player_country, app.player_country)
            if app.info_panel:
                app.info_panel.show_message(f"【事件卡阶段】{label} 请选择：抽取事件卡 或 跳过")

    def exit_evt_draw_phase(self, app: Any) -> None:
        """退出事件卡抽取阶段，进入正常行动阶段。"""
        app.evt_draw_phase = False
        app.evt_skip_draw_btn_rect = None
        if app.info_panel:
            app.info_panel.show_properties("")

    def check_evt_draw_phase_pp(self, app: Any) -> None:
        """确认/目标完成后，若 PP 耗尽则自动退出抽卡阶段。"""
        if not app.evt_draw_phase:
            return
        if not app.player_country:
            app.evt_draw_phase = False
            return
        stats = app.country_stats.get(app.player_country, {})
        pp = int(stats.get("political_points", 0)) + app.evt_temp_pp.get(app.player_country, 0)
        if pp < 1:
            self.exit_evt_draw_phase(app)
            if app.info_panel:
                app.info_panel.show_message("政治点数耗尽，进入行动阶段", duration=2.0)

    def get_event_card_image(self, app: Any, card_name: str):
        """按卡牌名称加载 card/ 目录下图片并缓存。"""
        if card_name in app._event_card_image_cache:
            return app._event_card_image_cache[card_name]

        card_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "card",
        )
        surf = None
        for ext in (".png", ".jpg", ".jpeg"):
            path = os.path.join(card_dir, card_name + ext)
            if os.path.isfile(path):
                try:
                    surf = pg.image.load(path).convert_alpha()
                except Exception as exc:
                    logger.warning("事件卡图片加载失败 %s: %s", path, exc)
                break

        app._event_card_image_cache[card_name] = surf
        return surf

    def render_event_card_overlay(self, app: Any) -> None:
        """绘制事件卡展示面板（模态覆盖层）。"""
        if not app.event_card_overlay:
            return
        card = app.event_card_overlay["card"]
        drawer = app.event_card_overlay["drawer"]

        font_title = app.country_stat_title_font
        font_body = app.country_stat_font

        title_h = font_title.get_height()
        body_h = font_body.get_height()
        padding = 16

        card_img = self.get_event_card_image(app, card.name)
        panel_w = max(520, int(app.screen_width * 0.40))

        img_area_h = 0
        img_surf_scaled = None
        if card_img is not None:
            iw, ih = card_img.get_width(), card_img.get_height()
            max_img_w = panel_w - padding * 2
            max_img_h = int(app.screen_height * 0.35)
            scale = min(max_img_w / max(iw, 1), max_img_h / max(ih, 1))
            dw, dh = max(1, int(iw * scale)), max(1, int(ih * scale))
            img_surf_scaled = pg.transform.smoothscale(card_img, (dw, dh))
            img_area_h = dh + padding

        chunk_size = 24
        desc_lines: list[str] = []
        raw = card.description
        while raw:
            desc_lines.append(raw[:chunk_size])
            raw = raw[chunk_size:]

        bar_h = title_h + padding
        name_h = title_h + padding
        desc_h = len(desc_lines) * (body_h + 4) + padding
        btn_h_total = body_h + padding * 3

        panel_h = bar_h + name_h + img_area_h + desc_h + btn_h_total
        panel_x = (app.screen_width - panel_w) // 2
        panel_y = max(padding, (app.screen_height - panel_h) // 2)

        overlay = pg.Surface((app.screen_width, app.screen_height), pg.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        app.window.blit(overlay, (0, 0))

        drawer_name = app.country_labels.get(drawer, drawer)
        drawer_color = app.country_button_colors.get(drawer, pg.Color("white"))
        announce_surf = font_title.render(
            f"{drawer_name}  抽取了事件卡", True, drawer_color
        )
        shadow_surf = font_title.render(
            f"{drawer_name}  抽取了事件卡", True, pg.Color(0, 0, 0, 180)
        )
        ax = (app.screen_width - announce_surf.get_width()) // 2
        ay = panel_y - title_h - padding - 4
        app.window.blit(shadow_surf, (ax + 2, ay + 2))
        app.window.blit(announce_surf, (ax, ay))

        panel_rect = pg.Rect(panel_x, panel_y, panel_w, panel_h)
        pg.draw.rect(app.window, pg.Color("#FFF8E7"), panel_rect, border_radius=12)
        pg.draw.rect(app.window, pg.Color("#8B4513"), panel_rect, width=3, border_radius=12)

        display_country = drawer if card.deck == "PUBLIC" else card.target_country
        country_color = app.country_button_colors.get(display_country, pg.Color("gray"))
        tag_rect = pg.Rect(panel_x, panel_y, panel_w, bar_h)
        pg.draw.rect(app.window, country_color, tag_rect, border_radius=12)
        pg.draw.rect(
            app.window,
            country_color,
            pg.Rect(panel_x, panel_y + bar_h // 2, panel_w, bar_h // 2),
        )
        drawer_label = f"{app.country_labels.get(display_country, display_country)} — 事件卡"
        tag_surf = font_title.render(drawer_label, True, pg.Color("white"))
        app.window.blit(
            tag_surf,
            tag_surf.get_rect(center=(panel_x + panel_w // 2, panel_y + bar_h // 2)),
        )

        cur_y = panel_y + bar_h + padding // 2
        name_surf = font_title.render(card.name, True, pg.Color("#4B2800"))
        app.window.blit(
            name_surf, name_surf.get_rect(centerx=panel_x + panel_w // 2, top=cur_y)
        )
        cur_y += title_h + padding

        pg.draw.line(
            app.window,
            pg.Color("#C8A87A"),
            (panel_x + 24, cur_y - padding // 2),
            (panel_x + panel_w - 24, cur_y - padding // 2),
            1,
        )

        if img_surf_scaled is not None:
            img_x = panel_x + (panel_w - img_surf_scaled.get_width()) // 2
            app.window.blit(img_surf_scaled, (img_x, cur_y))
            cur_y += img_surf_scaled.get_height() + padding
            pg.draw.line(
                app.window,
                pg.Color("#C8A87A"),
                (panel_x + 24, cur_y - padding // 2),
                (panel_x + panel_w - 24, cur_y - padding // 2),
                1,
            )

        for dl in desc_lines:
            ds = font_body.render(dl, True, pg.Color("#333333"))
            app.window.blit(ds, ds.get_rect(centerx=panel_x + panel_w // 2, top=cur_y))
            cur_y += body_h + 4

        btn_w = max(140, font_body.size("确认生效")[0] + 40)
        btn_h = body_h + padding
        btn_x = panel_x + (panel_w - btn_w) // 2
        btn_y = panel_y + panel_h - btn_h - padding
        btn_rect = pg.Rect(btn_x, btn_y, btn_w, btn_h)
        app.evt_overlay_ok_btn = btn_rect

        btn_color = pg.Color("#8B4513")
        if btn_rect.collidepoint(app._get_logical_mouse_pos()):
            btn_color = pg.Color("#A0522D")
        pg.draw.rect(app.window, btn_color, btn_rect, border_radius=8)
        ok_surf = font_body.render("确认生效", True, pg.Color("white"))
        app.window.blit(ok_surf, ok_surf.get_rect(center=btn_rect.center))

    def render_draw_event_btn(self, app: Any) -> None:
        """事件卡抽取阶段按钮组渲染。"""
        if app.state != type(app.state).PLAYING:
            app.draw_event_btn_rect = None
            app.evt_skip_draw_btn_rect = None
            return
        if app.turn_game_finished or not app.player_country:
            app.draw_event_btn_rect = None
            app.evt_skip_draw_btn_rect = None
            return
        if not app.evt_draw_phase:
            app.draw_event_btn_rect = None
            app.evt_skip_draw_btn_rect = None
            return

        if app.selecting_evt_target:
            app.draw_event_btn_rect = None
            app.evt_skip_draw_btn_rect = None
            font = app.combat_ui_font
            top_area_h = int(app.screen_height * 0.15)
            tag_x = app.country_tag_pos[0]
            hint_surf = font.render("▶ 请选择生效目标", True, pg.Color("#FFD700"))
            hint_h = hint_surf.get_height()
            hint_y = top_area_h // 2 - hint_h // 2
            hint_x = tag_x - hint_surf.get_width() - 20
            bg = pg.Surface((hint_surf.get_width() + 16, hint_h + 8), pg.SRCALPHA)
            bg.fill((0, 0, 0, 120))
            app.window.blit(bg, (hint_x - 8, hint_y - 4))
            app.window.blit(hint_surf, (hint_x, hint_y))
            return

        font = app.combat_ui_font
        top_area_h = int(app.screen_height * 0.15)
        tag_x = app.country_tag_pos[0]
        mouse_pos = app._get_logical_mouse_pos()

        skip_label = "跳过抽卡"
        skip_surf = font.render(skip_label, True, pg.Color("white"))
        btn_h = skip_surf.get_height() + 10
        btn_y = top_area_h // 2 - btn_h // 2
        skip_w = skip_surf.get_width() + 20
        skip_x = tag_x - skip_w - 10
        skip_rect = pg.Rect(skip_x, btn_y, skip_w, btn_h)
        app.evt_skip_draw_btn_rect = skip_rect
        skip_color = pg.Color("#2E6E30") if not skip_rect.collidepoint(mouse_pos) else pg.Color("#3D9140")
        pg.draw.rect(app.window, skip_color, skip_rect, border_radius=6)
        app.window.blit(skip_surf, skip_surf.get_rect(center=skip_rect.center))

        if self.can_draw_event_card(app, app.player_country):
            draw_label = "抽事件卡(-1PP)"
            draw_surf = font.render(draw_label, True, pg.Color("white"))
            draw_w = draw_surf.get_width() + 20
            draw_x = skip_x - draw_w - 10
            draw_rect = pg.Rect(draw_x, btn_y, draw_w, btn_h)
            app.draw_event_btn_rect = draw_rect
            draw_color = pg.Color("#6B4226") if not draw_rect.collidepoint(mouse_pos) else pg.Color("#8B5E3C")
            pg.draw.rect(app.window, draw_color, draw_rect, border_radius=6)
            app.window.blit(draw_surf, draw_surf.get_rect(center=draw_rect.center))
        else:
            app.draw_event_btn_rect = None
            draw_x = skip_x

        phase_surf = font.render("▶ 事件卡阶段", True, pg.Color("#FFD700"))
        left_edge = app.draw_event_btn_rect.left if app.draw_event_btn_rect else draw_x
        phase_x = left_edge - phase_surf.get_width() - 14
        phase_y = btn_y + (btn_h - phase_surf.get_height()) // 2
        app.window.blit(phase_surf, (phase_x, phase_y))
