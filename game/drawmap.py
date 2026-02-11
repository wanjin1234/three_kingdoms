import os
from math import sqrt

import pygame as pg

pictures_path = os.path.join(os.path.dirname(__file__), "pictures")


def draw_hexagon(surface, color, center, side_length, width=0):
    """
    绘制边朝上的正六边形
    参数:
        surface: pygame绘制表面
        color: 六边形颜色 (RGB元组)
        center: 中心坐标 (x, y)
        side_length: 边长 (像素)
    返回: 六边形顶点坐标列表
    """
    center_x, center_y = center
    pg.draw.polygon(
        surface,
        color,
        (
            (int(center_x + side_length), int(center_y)),
            (
                int(center_x + 0.5 * side_length),
                int(center_y + 0.5 * sqrt(3) * side_length),
            ),
            (
                int(center_x - 0.5 * side_length),
                int(center_y + 0.5 * sqrt(3) * side_length),
            ),
            (int(center_x - side_length), int(center_y)),
            (
                int(center_x - 0.5 * side_length),
                int(center_y - 0.5 * sqrt(3) * side_length),
            ),
            (
                int(center_x + 0.5 * side_length),
                int(center_y - 0.5 * sqrt(3) * side_length),
            ),
        ),
        width,
    )


def draw_terrain_icon(surface, center, side_length, terrain):
    """在六边形中添加地形图标"""
    center_x, center_y = center
    if terrain == "plain":
        pass
    elif terrain == "city":
        city_icon = pg.image.load(os.path.join(pictures_path, "city_icon.jpg"))
        city_icon = pg.transform.scale(
            city_icon, (int(side_length * 0.5), int(side_length * 0.5))
        )
        surface.blit(
            city_icon,
            (int(center_x - 0.5 * side_length), int(center_y - 0.5 * side_length)),
        )
    elif terrain == "hill":
        hill_icon = pg.image.load(os.path.join(pictures_path, "hill_icon.jpg"))
        hill_icon = pg.transform.scale(
            hill_icon, (int(side_length * 0.5), int(side_length * 0.5))
        )
        surface.blit(
            hill_icon,
            (int(center_x - 0.5 * side_length), int(center_y - 0.5 * side_length)),
        )
