from __future__ import annotations

import pygame as pg


class ScoreScreenService:
    """分数屏展示与渲染服务。"""

    def show_score_screen(self, app, screen_type: str) -> None:
        """显示分数屏幕。"""
        record = app.score_manager.get_detailed_scores(
            app.map_manager.provinces,
            app.country_stats,
        )

        net_scores = {
            "SHU": record.shu_score - record.shu_initial,
            "WEI": record.wei_score - record.wei_initial,
            "WU": record.wu_score - record.wu_initial,
        }

        app.show_score_screen = {
            "type": screen_type,
            "record": record,
            "net_scores": net_scores,
        }
        app._score_screen_cache_key = None
        app._score_screen_cache_surface = None

        if screen_type == "game_over" and app.music_manager:
            app.music_manager.play_score()

        if screen_type == "game_over":
            tianxia_winner = app.score_manager.check_tianxia_guixin(
                app.map_manager.provinces,
                app.country_stats,
            )
            if tianxia_winner:
                app.show_score_screen["tianxia_winner"] = tianxia_winner
            else:
                winner, net = app.score_manager.get_winner_by_score(
                    app.map_manager.provinces,
                    app.country_stats,
                )
                app.show_score_screen["score_winner"] = winner
                app.show_score_screen["net_scores"] = net

    def render_score_screen(self, app) -> None:
        """渲染分数显示屏幕（白屏）。"""
        if not app.show_score_screen:
            return

        record = app.show_score_screen["record"]
        net_scores = app.show_score_screen["net_scores"]
        screen_type = app.show_score_screen["type"]

        cache_key = (
            app.screen_width,
            app.screen_height,
            screen_type,
            getattr(record, "shu_score", None),
            getattr(record, "shu_initial", None),
            net_scores.get("SHU"),
            getattr(record, "shu_people_support", None),
            tuple(getattr(record, "shu_special", []) or []),
            getattr(record, "shu_normal", None),
            getattr(record, "wei_score", None),
            getattr(record, "wei_initial", None),
            net_scores.get("WEI"),
            getattr(record, "wei_people_support", None),
            tuple(getattr(record, "wei_special", []) or []),
            getattr(record, "wei_normal", None),
            getattr(record, "wu_score", None),
            getattr(record, "wu_initial", None),
            net_scores.get("WU"),
            getattr(record, "wu_people_support", None),
            tuple(getattr(record, "wu_special", []) or []),
            getattr(record, "wu_normal", None),
            app.show_score_screen.get("tianxia_winner"),
            app.show_score_screen.get("score_winner"),
        )

        if (
            app._score_screen_cache_surface is not None
            and app._score_screen_cache_key == cache_key
            and app._score_screen_cache_surface.get_size() == app.window.get_size()
        ):
            app.window.blit(app._score_screen_cache_surface, (0, 0))
            return

        render_surface = pg.Surface((app.screen_width, app.screen_height)).convert()
        render_surface.fill(pg.Color("white"))

        title_size = int(app.screen_height * 0.05)
        body_size = int(app.screen_height * 0.035)
        small_size = int(app.screen_height * 0.025)

        title_font = app._font("msyh.ttc", title_size)
        body_font = app._font("msyh.ttc", body_size)
        small_font = app._font("msyh.ttc", small_size)

        def wrap_text(text: str, font: pg.font.Font, max_w: int) -> list[str]:
            lines: list[str] = []
            cur = ""
            for ch in text:
                test = cur + ch
                if font.size(test)[0] <= max_w:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = ch
            if cur:
                lines.append(cur)
            return lines if lines else [text]

        special_names_map = {
            "Hanzhong": "汉中",
            "Jingzhou": "荆州",
            "Chengdu": "成都",
            "Liangzhou": "凉州",
            "Youzhou": "幽州",
            "Xiangyang": "襄阳",
            "Hefei": "合肥",
            "Changan": "长安",
            "Luoyang": "洛阳",
            "Wuchang": "武昌",
            "Changsha": "长沙",
            "Jianye": "建业",
        }

        title_text = "魏国行动完毕 - 各国分数" if screen_type == "wei_turn" else "游戏结束 - 最终分数"
        title_surf = title_font.render(title_text, True, pg.Color("black"))
        title_rect = title_surf.get_rect(centerx=app.screen_width // 2, top=40)
        render_surface.blit(title_surf, title_rect)
        y_offset = title_rect.bottom + 40

        countries = [
            ("SHU", "蜀汉", pg.Color("red")),
            ("WEI", "曹魏", pg.Color("blue")),
            ("WU", "孙吴", pg.Color("green")),
        ]

        col_width = app.screen_width // 3
        box_width = col_width - 20
        inner_w = box_width - 30
        line_gap = 4
        section_gap = 12

        def calc_box_content(country):
            rows = []
            if country == "SHU":
                current, initial, net = (
                    record.shu_score,
                    record.shu_initial,
                    net_scores["SHU"],
                )
                support = record.shu_people_support
                special, normal = record.shu_special, record.shu_normal
            elif country == "WEI":
                current, initial, net = (
                    record.wei_score,
                    record.wei_initial,
                    net_scores["WEI"],
                )
                support = record.wei_people_support
                special, normal = record.wei_special, record.wei_normal
            else:
                current, initial, net = (
                    record.wu_score,
                    record.wu_initial,
                    net_scores["WU"],
                )
                support = record.wu_people_support
                special, normal = record.wu_special, record.wu_normal

            sign = "+" if net >= 0 else ""
            net_color = pg.Color("darkgreen") if net >= 0 else pg.Color("red")

            rows.append((f"当前分数：{current:.1f}", small_font, pg.Color("black")))
            rows.append((f"开局分数：{initial:.1f}", small_font, pg.Color("black")))
            rows.append((f"净得分：{sign}{net:.1f}", small_font, net_color))
            rows.append((f"民心等级：{support}", small_font, pg.Color("black")))

            if special:
                names_str = ", ".join([special_names_map.get(n, n) for n in special])
                for line in wrap_text(f"特殊地点：{names_str}", small_font, inner_w):
                    rows.append((line, small_font, pg.Color("black")))
            rows.append((f"普通地块：{normal}", small_font, pg.Color("black")))
            return rows

        all_rows = {c: calc_box_content(c) for c, _, _ in countries}

        def rows_height(rows):
            h = 0
            for _text, font, _ in rows:
                h += font.get_height() + line_gap
            return h

        name_area = body_font.get_height() + 15 + section_gap
        padding_bottom = 15
        box_height = (
            max(rows_height(rows) + name_area + padding_bottom for rows in all_rows.values())
            + 20
        )

        for i, (country, cn_name, color) in enumerate(countries):
            box_x = i * col_width + (col_width - box_width) // 2
            box_y = y_offset

            box_rect = pg.Rect(box_x, box_y, box_width, box_height)
            pg.draw.rect(render_surface, pg.Color(250, 250, 250), box_rect, border_radius=10)
            pg.draw.rect(render_surface, color, box_rect, 3, border_radius=10)

            name_surf = body_font.render(cn_name, True, color)
            name_rect = name_surf.get_rect(centerx=box_x + box_width // 2, top=box_y + 10)
            render_surface.blit(name_surf, name_rect)

            info_y = name_rect.bottom + section_gap
            for text, font, txt_color in all_rows[country]:
                surf = font.render(text, True, txt_color)
                render_surface.blit(surf, (box_x + 15, info_y))
                info_y += font.get_height() + line_gap

        if screen_type == "game_over":
            winner_y = y_offset + box_height + 40
            winner_names = {"SHU": "蜀汉", "WEI": "曹魏", "WU": "孙吴"}

            if "tianxia_winner" in app.show_score_screen:
                winner = app.show_score_screen["tianxia_winner"]
                winner_text = f"胜利：{winner_names.get(winner, winner)} 达成「天下归心」!"
                winner_surf = title_font.render(winner_text, True, pg.Color("gold"))
                render_surface.blit(
                    winner_surf,
                    winner_surf.get_rect(centerx=app.screen_width // 2, top=winner_y),
                )
            elif "score_winner" in app.show_score_screen:
                winner = app.show_score_screen["score_winner"]
                winner_text = (
                    f"胜利：{winner_names.get(winner, winner)} 获得「一代枭雄」!"
                    if winner
                    else "平局！"
                )
                winner_surf = title_font.render(winner_text, True, pg.Color("gold"))
                render_surface.blit(
                    winner_surf,
                    winner_surf.get_rect(centerx=app.screen_width // 2, top=winner_y),
                )

        hint_surf = small_font.render("按 ESC 退出", True, pg.Color("gray"))
        hint_rect = hint_surf.get_rect(centerx=app.screen_width // 2, bottom=app.screen_height - 30)
        render_surface.blit(hint_surf, hint_rect)

        app._score_screen_cache_key = cache_key
        app._score_screen_cache_surface = render_surface
        app.window.blit(render_surface, (0, 0))
