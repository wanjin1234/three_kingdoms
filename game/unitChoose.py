from math import sqrt

import pygame as pg

pg.init()
screen_Info = pg.display.Info()
window_Width = screen_Info.current_w
window_Height = screen_Info.current_h
d = window_Height * 2 / (19 * sqrt(3))
icon_size = 0.6 * d
selected_units = []


def unit_choose_check(surface, lattice_to_check):
    """检查是否通过shift+左键选中了单位兵牌
    输入为lattice类
    """
    keys = pg.key.get_pressed()
    mouse_buttons = pg.mouse.get_pressed()
    # 检查 Shift 和鼠标左键是否同时被按下,如果同时按下表示选中兵牌
    if mouse_buttons[0]:
        if keys[pg.K_LSHIFT] or keys[pg.K_RSHIFT]:  # 索引 0 表示左键
            mouse_x, mouse_y = pg.mouse.get_pos()
            center_x, center_y = lattice_to_check.pos
            if lattice_to_check.unit:
                unit_num = len(lattice_to_check.unit)
                if unit_num == 1:
                    if (
                        mouse_x >= center_x
                        and mouse_x <= int(center_x + icon_size)
                        and mouse_y >= int(center_y - icon_size)
                        and mouse_y <= center_y
                    ):
                        """pg.draw.rect(
                            surface,
                            "yellow",
                            (center_x, int(center_y - 0.6 * d), 0.6 * d, 0.6 * d),
                            5,
                        )"""
                        selected_units.append(
                            (center_x, int(center_y - icon_size), icon_size, icon_size),
                        )
                elif unit_num == 2:
                    if (
                        mouse_x >= center_x
                        and mouse_x <= int(center_x + icon_size)
                        and mouse_y >= int(center_y - icon_size)
                        and mouse_y <= center_y
                    ):
                        selected_units.append(
                            (center_x, int(center_y - icon_size), icon_size, icon_size),
                        )

                    if (
                        mouse_x >= center_x
                        and mouse_x <= int(center_x + icon_size)
                        and mouse_y >= center_y
                        and mouse_y <= int(center_y + icon_size)
                    ):
                        selected_units.append(
                            (center_x, center_y, icon_size, icon_size),
                        )

                elif unit_num == 3:
                    if (
                        mouse_x >= center_x
                        and mouse_x <= int(center_x + icon_size)
                        and mouse_y >= int(center_y - icon_size)
                        and mouse_y <= center_y
                    ):
                        selected_units.append(
                            (center_x, int(center_y - icon_size), icon_size, icon_size),
                        )
                    if (
                        mouse_x >= center_x
                        and mouse_x <= int(center_x + icon_size)
                        and mouse_y >= center_y
                        and mouse_y <= int(center_y + icon_size)
                    ):
                        selected_units.append(
                            (center_x, center_y, icon_size, icon_size),
                        )

                    if (
                        mouse_x >= center_x - icon_size
                        and mouse_x <= center_x
                        and mouse_y >= center_y
                        and mouse_y <= center_y + icon_size
                    ):
                        selected_units.append(
                            (int(center_x - icon_size), center_y, icon_size, icon_size)
                        )

    for units_to_draw in selected_units:
        pg.draw.rect(surface, "yellow", units_to_draw, 5)
    if keys[pg.K_ESCAPE]:
        selected_units.clear()
