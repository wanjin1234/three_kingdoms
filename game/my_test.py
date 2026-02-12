from math import sqrt

import pygame as pg

pg.init()
screen_Info = pg.display.Info()
window_Width = screen_Info.current_w
window_Height = screen_Info.current_h
d = window_Height * 2 / (19 * sqrt(3))

# ========== 优化1：重构选中状态存储 ==========
# 使用(lattice对象, 单位索引)替代坐标元组，减少绘制计算量
selected_units = set()  # 改为set更高效
# 添加一个事件标志，避免每帧重复处理
click_processed_this_frame = False


def unit_choose_check(surface, lattice_to_check):
    """优化后的选中检测函数"""
    global selected_units, click_processed_this_frame

    keys = pg.key.get_pressed()
    mouse_buttons = pg.mouse.get_pressed()

    # ========== 优化2：事件驱动点击检测 ==========
    # 只处理新点击事件，避免每帧重复检测
    for event in pg.event.get(pg.MOUSEBUTTONDOWN):
        if event.button == 1 and not click_processed_this_frame:
            click_processed_this_frame = True
            mouse_x, mouse_y = event.pos
            center_x, center_y = lattice_to_check.pos

            # 非SHIFT点击：清除所有选中（如果没点到单位）
            if not (keys[pg.K_LSHIFT] or keys[pg.K_RSHIFT]):
                unit_clicked = False
                if lattice_to_check.unit:
                    unit_clicked = check_unit_click(lattice_to_check, mouse_x, mouse_y)

                if not unit_clicked:
                    # 清除所有选中
                    selected_units = set()
                return

            # SHIFT+点击：选择/取消选择
            if lattice_to_check.unit:
                process_unit_selection(lattice_to_check, mouse_x, mouse_y)

    # ========== 优化3：按需绘制 ==========
    # 只绘制当前格子上的选中单位
    draw_selected_units_for_lattice(surface, lattice_to_check)

    # ESC键清除所有选中
    if keys[pg.K_ESCAPE]:
        selected_units = set()


def check_unit_click(lattice, x, y):
    """检查点是否在格子内的任何单位上"""
    center_x, center_y = lattice.pos
    unit_num = len(lattice.unit)

    # 通用碰撞检测算法
    for i in range(unit_num):
        pos = get_unit_position(lattice, i)
        icon_rect = pg.Rect(pos[0], pos[1], 0.6 * d, 0.6 * d)
        if icon_rect.collidepoint(x, y):
            return True
    return False


def process_unit_selection(lattice, x, y):
    """处理单位选中/取消选中逻辑"""
    center_x, center_y = lattice.pos
    unit_num = len(lattice.unit)

    for i in range(unit_num):
        pos = get_unit_position(lattice, i)
        icon_rect = pg.Rect(pos[0], pos[1], 0.6 * d, 0.6 * d)

        if icon_rect.collidepoint(x, y):
            unit_id = (id(lattice), i)  # 使用格子ID和索引作为唯一标识

            if unit_id in selected_units:
                selected_units.remove(unit_id)
            else:
                selected_units.add(unit_id)
            return True  # 已处理点击

    return False


def get_unit_position(lattice, unit_index):
    """获取单位位置坐标（优化版本）"""
    center_x, center_y = lattice.pos

    if unit_index == 0:
        return (center_x, int(center_y - 0.6 * d))
    elif unit_index == 1:
        return (center_x, center_y)
    elif unit_index == 2:
        return (int(center_x - 0.6 * d), center_y)
    # 添加更多位置支持...
    return (center_x, center_y)  # 默认位置


def draw_selected_units_for_lattice(surface, lattice):
    """只绘制当前格子上的选中单位"""
    lattice_id = id(lattice)

    for unit_id in selected_units:
        if unit_id[0] == lattice_id:  # 检查是否属于当前格子
            unit_index = unit_id[1]
            pos = get_unit_position(lattice, unit_index)
            pg.draw.rect(surface, "yellow", (pos[0], pos[1], 0.6 * d, 0.6 * d), 3)


def reset_click_state():
    """重置点击状态，每帧结束时调用"""
    global click_processed_this_frame
    click_processed_this_frame = False
