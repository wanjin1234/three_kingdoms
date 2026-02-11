import os
from math import sqrt

import pygame as pg
from drawmap import draw_hexagon, draw_terrain_icon
from latticeManagement import lattice
from unitManagement import Unit, draw_unit_icon, lattice_draw_pos

pg.init()
window = pg.display.set_mode(flags=pg.NOFRAME)
clock = pg.time.Clock()  # 初始化时钟对象，限制帧率
pg.display.set_caption("三足鼎立")
# 开发全屏应用，获取物理显示器信息，便于适配不同物理显示器的电脑
screen_Info = pg.display.Info()
window_Width = screen_Info.current_w
window_Height = screen_Info.current_h
# 获取资源目录，便于跨平台引用
pictures_path = os.path.join(os.path.dirname(__file__), "pictures")
fonts_path = os.path.join(os.path.dirname(__file__), "fonts")
isRunning = True  # 游戏正在运行
isLoading = True  # 处在开始游戏界面
isChoosing = False  # 处在选择势力界面
isPlaying = False  # 处在游戏中界面
player_country = None
country_dict = {"SHU": "蜀", "WU": "吴", "WEI": "魏"}
color_dict = {"SHU": "red", "WU": "green", "WEI": "blue"}
# 格子数据
lattice_initialized = False
d = window_Height * 2 / (19 * sqrt(3))
lattice_1 = lattice("WEI", [], "plain", 0, (int(d), int(0.5 * sqrt(3) * d)), 0.5)
lattice_2 = lattice("SHU", [], "plain", 0, (int(d), int(15 * sqrt(3) / 2 * d)), 0.5)
lattice_roll_1 = [lattice_1, lattice_2]
"""第一列格子"""

lattice_3 = lattice("WEI", [], "city", 2, (int(2.5 * d), int(sqrt(3) * d)), 3)  # 凉州
lattice_4 = lattice("SHU", [], "plain", 0, (int(2.5 * d), int(6 * sqrt(3) * d)), 0.5)
lattice_5 = lattice("SHU", [], "plain", 0, (int(2.5 * d), int(7 * sqrt(3) * d)), 0.5)
lattice_6 = lattice("SHU", [], "plain", 0, (int(2.5 * d), int(8 * sqrt(3) * d)), 0.5)
lattice_roll_2 = [lattice_3, lattice_4, lattice_5, lattice_6]
"""第二列格子"""

lattice_7 = lattice("WEI", [], "plain", 0, (int(4 * d), int(1.5 * sqrt(3) * d)), 0.5)
lattice_8 = lattice("WEI", [], "plain", 0, (int(4 * d), int(2.5 * sqrt(3) * d)), 0.5)
lattice_9 = lattice("SHU", [], "hill", 0, (int(4 * d), int(3.5 * sqrt(3) * d)), 0.5)
lattice_10 = lattice("SHU", [], "plain", 0, (int(4 * d), int(4.5 * sqrt(3) * d)), 0.5)
lattice_11 = lattice(
    "SHU", ["WUDANG_archer_1"], "city", 2, (int(4 * d), int(5.5 * sqrt(3) * d)), 5
)  # 成都
lattice_12 = lattice("SHU", [], "plain", 0, (int(4 * d), int(6.5 * sqrt(3) * d)), 0.5)
lattice_13 = lattice("SHU", [], "plain", 0, (int(4 * d), int(7.5 * sqrt(3) * d)), 0.5)
lattice_14 = lattice("SHU", [], "plain", 0, (int(4 * d), int(8.5 * sqrt(3) * d)), 0.5)
lattice_roll_3 = [
    lattice_7,
    lattice_8,
    lattice_9,
    lattice_10,
    lattice_11,
    lattice_12,
    lattice_13,
    lattice_14,
]
"""第三列格子"""
lattice_15 = lattice("WEI", [], "plain", 0, (int(5.5 * d), int(2 * sqrt(3) * d)), 0.5)
lattice_16 = lattice("WEI", [], "plain", 0, (int(5.5 * d), int(3 * sqrt(3) * d)), 0.5)
lattice_17 = lattice(
    "SHU", [], "city", 2, (int(5.5 * d), int(4 * sqrt(3) * d)), 3
)  # 汉中
lattice_18 = lattice("SHU", [], "plain", 0, (int(5.5 * d), int(5 * sqrt(3) * d)), 0.5)
lattice_19 = lattice("SHU", [], "plain", 0, (int(5.5 * d), int(6 * sqrt(3) * d)), 0.5)
lattice_20 = lattice("SHU", [], "plain", 0, (int(5.5 * d), int(7 * sqrt(3) * d)), 0.5)
lattice_21 = lattice("SHU", [], "plain", 0, (int(5.5 * d), int(8 * sqrt(3) * d)), 0.5)
lattice_22 = lattice("SHU", [], "plain", 0, (int(5.5 * d), int(9 * sqrt(3) * d)), 0.5)
lattice_roll_4 = [
    lattice_15,
    lattice_16,
    lattice_17,
    lattice_18,
    lattice_19,
    lattice_20,
    lattice_21,
    lattice_22,
]
"""第四列格子"""
lattice_23 = lattice("WEI", [], "plain", 0, (int(7 * d), int(1.5 * sqrt(3) * d)), 0.5)
lattice_24 = lattice("WEI", [], "plain", 0, (int(7 * d), int(2.5 * sqrt(3) * d)), 0.5)
lattice_25 = lattice(
    "WEI", None, "city", 2, (int(7 * d), int(3.5 * sqrt(3) * d)), 3
)  # 长安
lattice_26 = lattice("SHU", [], "hill", 0, (int(7 * d), int(4.5 * sqrt(3) * d)), 0.5)
lattice_27 = lattice("SHU", [], "hill", 0, (int(7 * d), int(5.5 * sqrt(3) * d)), 0.5)
lattice_28 = lattice("SHU", [], "hill", 0, (int(7 * d), int(6.5 * sqrt(3) * d)), 0.5)
lattice_29 = lattice("SHU", [], "plain", 0, (int(7 * d), int(7.5 * sqrt(3) * d)), 0.5)
lattice_30 = lattice("SHU", [], "plain", 0, (int(7 * d), int(8.5 * sqrt(3) * d)), 0.5)
lattice_roll_5 = [
    lattice_23,
    lattice_24,
    lattice_25,
    lattice_26,
    lattice_27,
    lattice_28,
    lattice_29,
    lattice_30,
]
"""第五列格子"""
lattice_31 = lattice("WEI", [], "plain", 0, (int(8.5 * d), int(sqrt(3) * d)), 0.5)
lattice_32 = lattice("WEI", [], "plain", 0, (int(8.5 * d), int(2 * sqrt(3) * d)), 0.5)
lattice_33 = lattice("WEI", [], "plain", 0, (int(8.5 * d), int(3 * sqrt(3) * d)), 0.5)
lattice_34 = lattice("WEI", [], "plain", 0, (int(8.5 * d), int(4 * sqrt(3) * d)), 0.5)
lattice_35 = lattice(
    "SHU", None, "city", 2, (int(8.5 * d), int(5 * sqrt(3) * d)), 3
)  # 荆州
lattice_36 = lattice("SHU", [], "plain", 0, (int(8.5 * d), int(6 * sqrt(3) * d)), 0.5)
lattice_37 = lattice("SHU", [], "plain", 0, (int(8.5 * d), int(7 * sqrt(3) * d)), 0.5)
lattice_38 = lattice("WU", [], "plain", 0, (int(8.5 * d), int(8 * sqrt(3) * d)), 0.5)
lattice_39 = lattice("WU", [], "plain", 0, (int(8.5 * d), int(9 * sqrt(3) * d)), 0.5)
lattice_roll_6 = [
    lattice_31,
    lattice_32,
    lattice_33,
    lattice_34,
    lattice_35,
    lattice_36,
    lattice_37,
    lattice_38,
    lattice_39,
]
"""第六列格子"""
lattice_40 = lattice("WEI", [], "hill", 0, (int(10 * d), int(0.5 * sqrt(3) * d)), 0.5)
lattice_41 = lattice("WEI", [], "hill", 0, (int(10 * d), int(1.5 * sqrt(3) * d)), 0.5)
lattice_42 = lattice("WEI", [], "plain", 0, (int(10 * d), int(2.5 * sqrt(3) * d)), 0.5)
lattice_43 = lattice("WEI", [], "plain", 0, (int(10 * d), int(3.5 * sqrt(3) * d)), 0.5)
lattice_44 = lattice(
    "WEI", [], "city", 2, (int(10 * d), int(4.5 * sqrt(3) * d)), 2
)  # 襄阳
lattice_45 = lattice("SHU", [], "plain", 0, (int(10 * d), int(5.5 * sqrt(3) * d)), 0.5)
lattice_46 = lattice(
    "SHU", None, "plain", 0, (int(10 * d), int(6.5 * sqrt(3) * d)), 0.5
)
lattice_47 = lattice("WU", [], "plain", 0, (int(10 * d), int(7.5 * sqrt(3) * d)), 0.5)
lattice_48 = lattice("WU", [], "plain", 0, (int(10 * d), int(8.5 * sqrt(3) * d)), 0.5)
lattice_roll_7 = [
    lattice_40,
    lattice_41,
    lattice_42,
    lattice_43,
    lattice_44,
    lattice_45,
    lattice_46,
    lattice_47,
    lattice_48,
]
"""第七列格子"""
lattice_49 = lattice("WEI", [], "plain", 0, (int(11.5 * d), int(sqrt(3) * d)), 0.5)
lattice_50 = lattice("WEI", [], "plain", 0, (int(11.5 * d), int(2 * sqrt(3) * d)), 0.5)
lattice_51 = lattice(
    "WEI", ["HUBAO_cavalry_1"], "city", 2, (int(11.5 * d), int(3 * sqrt(3) * d)), 5
)  # 洛阳
lattice_52 = lattice("WEI", [], "plain", 0, (int(11.5 * d), int(4 * sqrt(3) * d)), 0.5)
lattice_53 = lattice(
    "WU", [], "city", 2, (int(11.5 * d), int(5 * sqrt(3) * d)), 2
)  # 武昌
lattice_54 = lattice("WU", [], "plain", 0, (int(11.5 * d), int(6 * sqrt(3) * d)), 0.5)
lattice_55 = lattice(
    "WU", [], "city", 2, (int(11.5 * d), int(7 * sqrt(3) * d)), 2
)  # 长沙
lattice_56 = lattice("WU", [], "plain", 0, (int(11.5 * d), int(8 * sqrt(3) * d)), 0.5)
lattice_57 = lattice("WU", [], "plain", 0, (int(11.5 * d), int(9 * sqrt(3) * d)), 0.5)
lattice_roll_8 = [
    lattice_49,
    lattice_50,
    lattice_51,
    lattice_52,
    lattice_53,
    lattice_54,
    lattice_55,
    lattice_56,
    lattice_57,
]
"""第八列格子"""
lattice_58 = lattice(
    "WEI", [], "city", 2, (int(13 * d), int(0.5 * sqrt(3) * d)), 2
)  # 幽州
lattice_59 = lattice("WEI", [], "plain", 0, (int(13 * d), int(1.5 * sqrt(3) * d)), 0.5)
lattice_60 = lattice("WEI", [], "plain", 0, (int(13 * d), int(2.5 * sqrt(3) * d)), 0.5)
lattice_61 = lattice("WEI", [], "plain", 0, (int(13 * d), int(3.5 * sqrt(3) * d)), 0.5)
lattice_62 = lattice(
    "WEI", [], "city", 2, (int(13 * d), int(4.5 * sqrt(3) * d)), 2
)  # 合肥
lattice_63 = lattice("WU", [], "plain", 0, (int(13 * d), int(5.5 * sqrt(3) * d)), 0.5)
lattice_64 = lattice("WU", [], "plain", 0, (int(13 * d), int(6.5 * sqrt(3) * d)), 0.5)
lattice_65 = lattice("WU", [], "plain", 0, (int(13 * d), int(7.5 * sqrt(3) * d)), 0.5)
lattice_66 = lattice("WU", [], "plain", 0, (int(13 * d), int(8.5 * sqrt(3) * d)), 0.5)
lattice_roll_9 = [
    lattice_58,
    lattice_59,
    lattice_60,
    lattice_61,
    lattice_62,
    lattice_63,
    lattice_64,
    lattice_65,
    lattice_66,
]
"""第九列格子"""
lattice_67 = lattice("WEI", [], "plain", 0, (int(14.5 * d), int(2 * sqrt(3) * d)), 0.5)
lattice_68 = lattice("WEI", [], "plain", 0, (int(14.5 * d), int(3 * sqrt(3) * d)), 0.5)
lattice_69 = lattice("WEI", [], "plain", 0, (int(14.5 * d), int(4 * sqrt(3) * d)), 0.5)
lattice_70 = lattice("WU", [], "plain", 0, (int(14.5 * d), int(5 * sqrt(3) * d)), 0.5)
lattice_71 = lattice("WU", [], "plain", 0, (int(14.5 * d), int(6 * sqrt(3) * d)), 0.5)
lattice_72 = lattice("WU", [], "plain", 0, (int(14.5 * d), int(7 * sqrt(3) * d)), 0.5)
lattice_73 = lattice("WU", [], "plain", 0, (int(14.5 * d), int(8 * sqrt(3) * d)), 0.5)
lattice_roll_10 = [
    lattice_67,
    lattice_68,
    lattice_69,
    lattice_70,
    lattice_71,
    lattice_72,
    lattice_73,
]
"""第十列格子"""
lattice_74 = lattice("WEI", [], "plain", 0, (int(16 * d), int(1.5 * sqrt(3) * d)), 0.5)
lattice_75 = lattice(
    "WU", ["JIEFAN_infantry_2"], "city", 2, (int(16 * d), int(4.5 * sqrt(3) * d)), 5
)  # 建邺
lattice_76 = lattice("WU", [], "plain", 2, (int(16 * d), int(5.5 * sqrt(3) * d)), 0.5)
lattice_77 = lattice("WU", [], "plain", 2, (int(16 * d), int(6.5 * sqrt(3) * d)), 0.5)
lattice_78 = lattice("WU", [], "plain", 2, (int(16 * d), int(7.5 * sqrt(3) * d)), 0.5)
lattice_roll_11 = [lattice_74, lattice_75, lattice_76, lattice_77, lattice_78]
lattices = (
    lattice_roll_1
    + lattice_roll_2
    + lattice_roll_3
    + lattice_roll_4
    + lattice_roll_5
    + lattice_roll_6
    + lattice_roll_7
    + lattice_roll_8
    + lattice_roll_9
    + lattice_roll_10
    + lattice_roll_11
)
"""所有格子的集合"""
# 长江点集
yantze_river_points_1 = (
    (int(4.5 * d), int(6 * sqrt(3) * d)),
    (int(5 * d), int(5.5 * sqrt(3) * d)),
    (int(6 * d), int(5.5 * sqrt(3) * d)),
    (int(6.5 * d), int(5 * sqrt(3) * d)),
    (int(7.5 * d), int(5 * sqrt(3) * d)),
    (int(8 * d), int(5.5 * sqrt(3) * d)),
    (int(9 * d), int(5.5 * sqrt(3) * d)),
    (int(9.5 * d), int(5 * sqrt(3) * d)),
    (int(10.5 * d), int(5 * sqrt(3) * d)),
    (int(11 * d), int(4.5 * sqrt(3) * d)),
    (int(12 * d), int(4.5 * sqrt(3) * d)),
    (int(12.5 * d), int(5 * sqrt(3) * d)),
    (int(13.5 * d), int(5 * sqrt(3) * d)),
    (int(14 * d), int(4.5 * sqrt(3) * d)),
    (int(15 * d), int(4.5 * sqrt(3) * d)),
    (int(15.5 * d), int(4 * sqrt(3) * d)),
)
yantze_river_points_2 = (
    (int(10.5 * d), int(5 * sqrt(3) * d)),
    (int(11 * d), int(5.5 * sqrt(3) * d)),
    (int(10.5 * d), int(6 * sqrt(3) * d)),
    (int(11 * d), int(6.5 * sqrt(3) * d)),
    (int(10.5 * d), int(7 * sqrt(3) * d)),
)
# 黄河点集
yellow_river_points = (
    (int(9 * d), int(0.5 * sqrt(3) * d)),
    (int(9.5 * d), int(sqrt(3) * d)),
    (int(9 * d), int(1.5 * sqrt(3) * d)),
    (int(9.5 * d), int(2 * sqrt(3) * d)),
    (int(9 * d), int(2.5 * sqrt(3) * d)),
    (int(9.5 * d), int(3 * sqrt(3) * d)),
    (int(10.5 * d), int(3 * sqrt(3) * d)),
    (int(11 * d), int(2.5 * sqrt(3) * d)),
    (int(12 * d), int(2.5 * sqrt(3) * d)),
    (int(12.5 * d), int(2 * sqrt(3) * d)),
    (int(13.5 * d), int(2 * sqrt(3) * d)),
    (int(14 * d), int(1.5 * sqrt(3) * d)),
)
# 不可通行线点集
ban_line_points = (
    (int(7.5 * d), int(9 * sqrt(3) * d)),
    (int(8 * d), int(8.5 * sqrt(3) * d)),
    (int(7.5 * d), int(8 * sqrt(3) * d)),
    (int(8 * d), int(7.5 * sqrt(3) * d)),
    (int(9 * d), int(7.5 * sqrt(3) * d)),
    (int(9.5 * d), int(7 * sqrt(3) * d)),
    (int(10.5 * d), int(7 * sqrt(3) * d)),
)
while isRunning:
    clock.tick(60)
    # 统一处理事件
    mouse_clicked = False
    for ev in pg.event.get():
        if ev.type == pg.QUIT:
            isRunning = False
            break
        elif ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
            mouse_clicked = True
    # 开始游戏界面
    if isLoading:
        window.fill("white")
        # 诸葛亮图片
        start_background_image_1_path = os.path.join(
            pictures_path, "start_ZHUGELIANG.jpg"
        )
        start_background_image_1 = pg.image.load(start_background_image_1_path)
        start_background_image_1 = pg.transform.scale(
            start_background_image_1,
            (int(window_Height * 0.6), int(window_Height * 0.7)),
        )
        window.blit(
            start_background_image_1,
            (int(window_Width - window_Height * 0.65), int(window_Height * 0.2)),
        )
        # 司马懿图片
        start_background_image_2_path = os.path.join(pictures_path, "start_SIMAYI.jpg")
        start_background_image_2 = pg.image.load(start_background_image_2_path)
        start_background_image_2 = pg.transform.flip(
            pg.transform.scale(
                start_background_image_2,
                (int(window_Height * 0.5), int(window_Height * 0.625)),
            ),
            True,
            False,
        )
        window.blit(
            start_background_image_2,
            (int(window_Height * 0.03), int(window_Height) * 0.25),
        )
        # 游戏标题
        title_text = "三足鼎立"
        title_font_path = os.path.join(fonts_path, "STLITI.ttf")
        title_font = pg.font.Font(title_font_path, int(window_Width * 0.1))
        title_image = title_font.render(title_text, True, "black")
        window.blit(title_image, (int(window_Width * 0.3), 0))
        pg.draw.rect(
            window,
            "yellow",
            (
                window_Width * 0.3,
                window_Height * 0.75,
                window_Width * 0.4,
                window_Height * 0.1,
            ),
        )
        # 开始游戏按钮
        start_text = "开始游戏"
        start_font_path = os.path.join(fonts_path, "STXINGKA.ttf")
        start_font = pg.font.Font(start_font_path, int(window_Height * 0.1))
        start_image = start_font.render(start_text, True, "black")
        window.blit(
            start_image,
            (int(window_Width * 0.5 - window_Height * 0.2), int(window_Height * 0.75)),
        )
        pg.display.update()
        # 检查是否按下“开始游戏”按钮
        if mouse_clicked:
            click_position_x, click_position_y = ev.pos
            # 鼠标点击的位置在按钮区域内，则进入选择势力界面
            if (
                click_position_x >= window_Width * 0.3
                and click_position_x <= window_Width * 0.7
                and click_position_y >= window_Height * 0.75
                and click_position_y <= window_Height * 0.85
            ):
                isLoading = False
                isChoosing = True
    # 选择势力界面
    elif isChoosing:
        window.fill("white")
        # 刘备图片
        choosing_image_SHU_path = os.path.join(pictures_path, "choosing_LIUBEI.jpg")
        choosing_image_SHU = pg.transform.scale(
            pg.image.load(choosing_image_SHU_path),
            (int(window_Height * 0.3), int(window_Height * 0.3)),
        )
        window.blit(
            choosing_image_SHU,
            (int(window_Width * 0.4 - window_Height * 0.45), int(window_Height * 0.2)),
        )
        # 孙权图片
        choosing_image_WU_path = os.path.join(pictures_path, "choosing_SUNQUAN.jpg")
        choosing_image_WU = pg.transform.scale(
            pg.image.load(choosing_image_WU_path),
            (int(window_Height * 0.3), int(window_Height * 0.3)),
        )
        window.blit(
            choosing_image_WU,
            (int(window_Width * 0.5 - window_Height * 0.15), int(window_Height * 0.2)),
        )
        # 曹操图片
        choosing_image_WEI_path = os.path.join(pictures_path, "choosing_CAOCAO.jpg")
        choosing_image_WEI = pg.transform.scale(
            pg.image.load(choosing_image_WEI_path),
            (int(window_Height * 0.3), int(window_Height * 0.3)),
        )
        window.blit(
            choosing_image_WEI,
            (int(window_Width * 0.6 + window_Height * 0.15), int(window_Height * 0.2)),
        )
        # 选择势力的按钮
        choosing_key_font_path = os.path.join(fonts_path, "STLITI.ttf")
        choosing_key_font = pg.font.Font(
            choosing_key_font_path, int(window_Height * 0.1)
        )
        choosing_key_text_SHU = choosing_key_font.render("蜀", True, "black")
        choosing_key_text_WU = choosing_key_font.render("吴", True, "black")
        choosing_key_text_WEI = choosing_key_font.render("魏", True, "black")
        pg.draw.circle(
            window,
            "red",
            (int(window_Width * 0.4 - window_Height * 0.3), int(window_Height * 0.7)),
            window_Height * 0.1,
        )
        window.blit(
            choosing_key_text_SHU,
            (int(window_Width * 0.4 - window_Height * 0.35), int(window_Height * 0.65)),
        )  # 蜀按钮
        pg.draw.circle(
            window,
            "green",
            (int(window_Width * 0.5), int(window_Height * 0.7)),
            window_Height * 0.1,
        )
        window.blit(
            choosing_key_text_WU,
            (int(window_Width * 0.5 - window_Height * 0.05), int(window_Height * 0.65)),
        )  # 吴按钮
        pg.draw.circle(
            window,
            "blue",
            (int(window_Width * 0.6 + window_Height * 0.3), int(window_Height * 0.7)),
            window_Height * 0.1,
        )
        window.blit(
            choosing_key_text_WEI,
            (int(window_Width * 0.6 + window_Height * 0.25), int(window_Height * 0.65)),
        )  # 魏按钮
        # 画面标题（“选择势力”）
        choosing_title_font_path = os.path.join(fonts_path, "SIMLI.ttf")
        choosing_title_font = pg.font.Font(
            choosing_title_font_path, int(window_Height * 0.1)
        )
        choosing_title_image = choosing_title_font.render("选择势力", True, "black")
        window.blit(choosing_title_image, (window_Width * 0.5 - window_Height * 0.2, 0))
        # 判定选择哪个势力
        if mouse_clicked:
            click_position_x, click_position_y = ev.pos
            # 鼠标点击的位置在按钮区域内，则以该势力进入游戏界面
            ##蜀国势力判定
            if (click_position_x - window_Width * 0.4 + window_Height * 0.3) ** 2 + (
                click_position_y - window_Height * 0.7
            ) ** 2 <= (window_Height * 0.1) ** 2:
                player_country = "SHU"
                isChoosing = False
                isPlaying = True
            elif (click_position_x - window_Width * 0.5) ** 2 + (
                click_position_y - window_Height * 0.7
            ) ** 2 <= (window_Height * 0.1) ** 2:
                player_country = "WU"
                isChoosing = False
                isPlaying = True
            elif (click_position_x - window_Width * 0.6 - window_Height * 0.3) ** 2 + (
                click_position_y - window_Height * 0.7
            ) ** 2 <= (window_Height * 0.1) ** 2:
                player_country = "WEI"
                isChoosing = False
                isPlaying = True
        pg.display.update()
    # 游戏界面
    elif isPlaying:
        window.fill("white")
        # 右上角显示所选势力
        country_tag_font = pg.font.Font(
            os.path.join(fonts_path, "STZHONGS.ttf"), int(window_Height * 0.1)
        )
        country_tag = country_tag_font.render(
            country_dict[player_country], True, "black"
        )
        window.blit(country_tag, (int(window_Width - window_Height * 0.15), 0))
        # 画出左侧游戏地图
        for lattice_to_draw in lattices:
            draw_hexagon(
                window, color_dict[lattice_to_draw.country], lattice_to_draw.pos, d
            )
            draw_terrain_icon(window, lattice_to_draw.pos, d, lattice_to_draw.terrain)
            if lattice_to_draw.unit == None:
                pass
            else:
                for unit in lattice_to_draw.unit:
                    unit_type_num = len(
                        lattice_to_draw.unit
                    )  # 获取这个格子上有多少种兵
                    for i in range(unit_type_num):
                        draw_unit_icon(
                            window,
                            lattice_to_draw.unit[i],
                            d,
                            lattice_draw_pos(lattice_to_draw.pos, d)[i],
                        )
        pg.draw.lines(window, "black", False, ban_line_points, 20)
        pg.draw.lines(window, (173, 216, 230), False, yantze_river_points_1, 20)
        pg.draw.lines(window, (173, 216, 230), False, yantze_river_points_2, 20)
        pg.draw.lines(window, (173, 216, 230), False, yellow_river_points, 20)

        pg.display.update()
pg.quit()
