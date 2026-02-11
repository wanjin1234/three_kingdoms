import os

import pygame as pg


class Unit:
    """管理部队单位"""

    def __init__(self, move, attack, defend, unit_type, distance, country):
        self.move = move
        self.attack = attack
        self.defend = defend
        self.type = unit_type
        self.distance = distance
        self.country = country


# 定义部队类型
# 普通步兵、骑兵、弓兵所属势力未定，默认设为None
infantry = Unit(2, 3, 3, "infantry", 1, None)
cavalry = Unit(3, 3, 2, "cavalry", 1, None)
archer = Unit(2, 4, 2, "archer", 2, None)
JIEFAN_infantry = Unit(2, 4, 4, "JIEFAN_infantry", 1, "WU")
HUBAO_cavalry = Unit(4, 4, 3, "HUBAO_cavalry", 1, "WEI")
WUDANG_archer = Unit(2, 4, 3, "WUDANG_archer", 2, "SHU")

# 加载并画出图标
pictures_path = os.path.join(os.path.dirname(__file__), "pictures")


def lattice_draw_pos(lattice_pos, d):
    """
    获取该格子哪些地方能画,返回一个列表,列表为可以画的位置坐标
    lattice_pos:格子的中心点坐标
    """
    center_x, center_y = lattice_pos
    draw_pos = [
        (center_x, int(center_y - 0.5 * d)),
        (center_x, int(center_y + 0.5 * d)),
        (int(center_x - 0.5 * d), int(center_y + 0.5 * d)),
    ]
    return draw_pos


def draw_unit_icon(surface, unit_type, d, pos):
    """根据格子上单位的数量和格子所在的位置画出单位图标
    参数：
    surface:要画的屏幕
    unit_type:部队种类(含数量,如1个infantry为infantry_1,2个为infantry_2)
    d:格子的边长
    pos:画的位置
    """
    infantry_image_1 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "infantry_icon.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    infantry_image_2 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "infantry_icon_2.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    infantry_image_3 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "infantry_icon_3.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    cavalry_image_1 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "cavalry_icon.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    cavalry_image_2 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "cavalry_icon_2.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    cavalry_image_3 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "cavalry_icon_3.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    archer_image_1 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "archer_icon.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    archer_image_2 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "archer_icon_2.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    archer_image_3 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "archer_icon_3.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    JIEFAN_infantry_image_1 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "JIEFAN_infantry_icon.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    JIEFAN_infantry_image_2 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "JIEFAN_infantry_icon_2.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    JIEFAN_infantry_image_3 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "JIEFAN_infantry_icon_3.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    HUBAO_cavalry_image_1 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "HUBAO_cavalry_icon.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    HUBAO_cavalry_image_2 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "HUBAO_cavalry_icon_2.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    HUBAO_cavalry_image_3 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "HUBAO_cavalry_icon_3.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    WUDANG_archer_image_1 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "WUDANG_archer_icon.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    WUDANG_archer_image_2 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "WUDANG_archer_icon_2.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )
    WUDANG_archer_image_3 = pg.transform.scale(
        pg.image.load(os.path.join(pictures_path, "WUDANG_archer_icon_3.jpg")),
        (int(0.7 * d), int(0.7 * d)),
    )

    if unit_type == "infantry_1":
        surface.blit(infantry_image_1, pos)
    elif unit_type == "infantry_2":
        surface.blit(infantry_image_2, pos)
    elif unit_type == "infantry_3":
        surface.blit(infantry_image_3, pos)
    elif unit_type == "cavalry_1":
        surface.blit(cavalry_image_1, pos)
    elif unit_type == "cavalry_2":
        surface.blit(cavalry_image_2, pos)
    elif unit_type == "cavalry_3":
        surface.blit(cavalry_image_3, pos)
    elif unit_type == "archer_1":
        surface.blit(archer_image_1, pos)
    elif unit_type == "archer_2":
        surface.blit(archer_image_2, pos)
    elif unit_type == "archer_3":
        surface.blit(archer_image_3, pos)
    elif unit_type == "JIEFAN_infantry_1":
        surface.blit(JIEFAN_infantry_image_1, pos)
    elif unit_type == "JIEFAN_infantry_2":
        surface.blit(JIEFAN_infantry_image_2, pos)
    elif unit_type == "JIEFAN_infantry_3":
        surface.blit(JIEFAN_infantry_image_3, pos)
    elif unit_type == "HUBAO_cavalry_1":
        surface.blit(HUBAO_cavalry_image_1, pos)
    elif unit_type == "HUBAO_cavalry_2":
        surface.blit(HUBAO_cavalry_image_2, pos)
    elif unit_type == "HUBAO_cavalry_3":
        surface.blit(HUBAO_cavalry_image_3, pos)
    elif unit_type == "WUDANG_archer_1":
        surface.blit(WUDANG_archer_image_1, pos)
    elif unit_type == "WUDANG_archer_2":
        surface.blit(WUDANG_archer_image_2, pos)
    elif unit_type == "WUDANG_archer_3":
        surface.blit(WUDANG_archer_image_3, pos)
