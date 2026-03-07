"""
信息面板模块。
负责在屏幕右侧显示游戏反馈、错误提示和战斗骰子。
"""

from __future__ import annotations

import os
import time
from typing import Callable, Dict, List, Tuple

import pygame as pg


class BasePanel:
    """面板基类，提供通用的背景绘制和文字换行功能"""

    def __init__(
        self,
        rect: pg.Rect,
        font: pg.font.Font,
        font_path: str | None = None,
        base_font_size: int = 20,
        cards_dir: str | None = None,
    ) -> None:
        self.rect = rect
        self.font = font
        self.font_path = font_path
        self.base_font_size = base_font_size
        self._font_cache = {}  # size -> Font

    def _get_font(self, size: int) -> pg.font.Font:
        if size >= self.base_font_size or self.font_path is None:
            return self.font
        if size not in self._font_cache:
            try:
                self._font_cache[size] = pg.font.Font(self.font_path, size)
            except:
                # 降级处理
                self._font_cache[size] = pg.font.SysFont("arial", size)
        return self._font_cache[size]

    def draw_background_and_border(
        self, surface: pg.Surface, draw_top_border: bool = True
    ) -> int:
        """绘制白底黑框，返回内容区域的起始 Y 坐标"""
        # 1. 填充背景
        pg.draw.rect(surface, pg.Color("white"), self.rect)
        # 2. 绘制完整边框
        pg.draw.rect(surface, pg.Color("black"), self.rect, width=2)

        # 3. 如果不需要顶部边框，用白色矩形覆盖掉
        if not draw_top_border:
            # 覆盖区域：x 从 +2 开始，y 从 top 开始，宽度 -4，高度 2
            # 这样保留了左右两侧的垂直边框的连接处
            cover_rect = pg.Rect(
                self.rect.left + 2, self.rect.top, self.rect.width - 4, 2
            )
            pg.draw.rect(surface, pg.Color("white"), cover_rect)

        return self.rect.y + 20

    def _layout_text(
        self, text: str, font: pg.font.Font, color: pg.Color
    ) -> Tuple[list[str], list[pg.Color], int]:
        """
        根据给定字体计算文字排版。
        返回 (lines, colors, total_height)
        """
        if not text:
            return [], [], 0

        lines = []
        line_colors = []
        max_width = self.rect.width - 10
        font_height = font.get_height()

        paragraphs = text.replace("\r", "").split("\n")
        total_height = 0

        for paragraph in paragraphs:
            para_color = (
                pg.Color("red")
                if ("血 0" in paragraph or "血-" in paragraph)
                else color
            )

            if not paragraph:
                lines.append("")
                line_colors.append(para_color)
                total_height += font_height // 2
                continue

            current_line = ""
            for char in paragraph:
                test_line = current_line + char
                w, h = font.size(test_line)
                if w > max_width:
                    if not current_line:
                        lines.append(char)
                        line_colors.append(para_color)
                        total_height += font_height + 5
                        current_line = ""
                    else:
                        lines.append(current_line)
                        line_colors.append(para_color)
                        total_height += font_height + 5
                        current_line = char
                else:
                    current_line = test_line
            if current_line:
                lines.append(current_line)
                line_colors.append(para_color)
                total_height += font_height + 5

        # 修正最后一个行距
        if total_height > 0:
            total_height -= 5

        return lines, line_colors, total_height

    def _render_rich_text_line(
        self,
        surface: pg.Surface,
        line: str,
        font: pg.font.Font,
        y: int,
        default_color: pg.Color,
    ) -> None:
        """
        渲染包含简易颜色标记的一行文字。
        标记格式："|#RRGGBB|文本"
        支持制表符\t对齐：遇到\t时跳转到固定 X 坐标
        例如："|#FF0000|红色文字|#000000|]\t黑色文字"
        """
        # 检查是否包含制表符
        if "\t" in line:
            # 按制表符分割
            tab_parts = line.split("\t")

            # 定义制表位：标签从 left+10 开始，属性从左边起 55% 处开始（自适应，防止右溢出）
            label_x = self.rect.left + 10
            attr_x = self.rect.left + int(self.rect.width * 0.55)

            # 渲染第一部分（制表符之前）- 标签，从左边固定位置开始
            if tab_parts:
                first_part = tab_parts[0]
                parts = first_part.split("|")
                current_color = default_color

                x = label_x

                for part in parts:
                    if not part:
                        continue

                    # 检测是否是颜色代码
                    if part.startswith("#") and len(part) == 7:
                        try:
                            current_color = pg.Color(part)
                            continue
                        except:
                            pass

                    # 普通文本，渲染之
                    try:
                        surf = font.render(part, True, current_color)
                        surface.blit(surf, (x, y))
                        x += surf.get_width()
                    except Exception as e:
                        print(f"Render error: {e}")

            # 渲染制表符后的部分（如果有），从固定位置开始
            if len(tab_parts) > 1:
                for tab_idx, tab_part in enumerate(tab_parts[1:], 1):
                    parts = tab_part.split("|")
                    current_color = default_color

                    x = attr_x

                    for part in parts:
                        if not part:
                            continue

                        if part.startswith("#") and len(part) == 7:
                            try:
                                current_color = pg.Color(part)
                                continue
                            except:
                                pass

                        try:
                            surf = font.render(part, True, current_color)
                            surface.blit(surf, (x, y))
                            x += surf.get_width()
                        except Exception as e:
                            print(f"Render error: {e}")
        else:
            # 没有制表符，使用原来的居中渲染逻辑
            parts = line.split("|")
            segments = []
            current_color = default_color

            total_width = 0

            for part in parts:
                if not part:
                    continue

                # 检测是否是颜色代码
                if part.startswith("#") and len(part) == 7:
                    try:
                        current_color = pg.Color(part)
                        continue
                    except:
                        pass

                # 普通文本，渲染之
                try:
                    surf = font.render(part, True, current_color)
                    segments.append(surf)
                    total_width += surf.get_width()
                except Exception as e:
                    print(f"Render error: {e}")

            # 居中绘制
            x = self.rect.centerx - total_width // 2
            for surf in segments:
                surface.blit(surf, (x, y))
                x += surf.get_width()

    def draw_text_wrapped(
        self,
        surface: pg.Surface,
        text: str,
        color: pg.Color,
        start_y: int,
        max_height: int | None = None,
    ) -> int:
        """
        绘制水平居中且自动换行的文本。
        支持简单的富文本颜色标记（仅限单行内）。
        如果提供了 max_height，会尝试缩小字体以适应高度。
        返回文本结束后的 Y 坐标。
        """
        if not text:
            return start_y

        # 为了计算布局高度，我们需要先去除颜色标记，当做普通文本估算
        # 这是一个简化的处理：假设富文本不会导致额外的换行问题
        # (因为目前只用于单位名称变色，通常都在第一行且很短)
        plain_text = ""
        import re

        # 去除 |#XXXXXX| 标记
        plain_text = re.sub(r"\|#[A-Fa-f0-9]{6}\|", "", text).replace("|", "")

        current_font = self.font
        # 使用去标记后的纯文本进行排版计算
        lines_layout, line_colors_layout, total_h = self._layout_text(
            plain_text, current_font, color
        )

        # 自适应字体大小逻辑
        if max_height is not None and self.font_path:
            size = self.base_font_size
            min_size = 10
            while total_h > max_height and size > min_size:
                size -= 2
                current_font = self._get_font(size)
                lines_layout, line_colors_layout, total_h = self._layout_text(
                    plain_text, current_font, color
                )

        # 渲染
        y = start_y
        font_height = current_font.get_height()

        # 这里需要重新按换行符分割原始带标记的文本
        # 注意：这假设 _layout_text 没有因为宽度强行把一行很长的富文本切断
        # 如果切断了，这里的对应关系会乱。
        # 鉴于当前需求只用来显示简短的单位属性，我们假设每段都不会自动折行。
        original_paragraphs = text.replace("\r", "").split("\n")

        # 我们遍历 logic lines, 但实际上我们需要渲染 original paragraphs
        # 如果 original_paragraphs 比 layed out lines 少，说明发生了自动换行。
        # 这里为了安全起见，如果检测到含有颜色标记，就不使用自动换行，直接截断或者强制单行
        # 或者仅仅对含有标记的行特殊处理

        for para in original_paragraphs:
            if not para:
                y += font_height // 2
                continue

            if "|#" in para:
                # 富文本行
                self._render_rich_text_line(surface, para, current_font, y, color)
                y += font_height + 5
            else:
                # 普通行，可能需要自动换行
                # 复用 _layout_text 的逻辑比较复杂，这里简化处理：
                # 如果是普通行，直接调用原来的逻辑渲染每一行
                # 为了保持字体一致，我们重新 layout 这一小段
                sub_lines, sub_colors, _ = self._layout_text(para, current_font, color)
                for i, line in enumerate(sub_lines):
                    surf = current_font.render(line, True, sub_colors[i])
                    rect = surf.get_rect(midtop=(self.rect.centerx, y))
                    surface.blit(surf, rect)
                    y += font_height + 5

        return y


class CardPanel(BasePanel):
    """卡牌面板"""

    CARD_IMAGES = {
        "威震华夏": "威震华夏.jpg",
        "七擒七纵": "七擒七纵.jpg",
        "空城妙计": "空城妙计.jpg",
        "火烧连营": "火烧连营.jpg",
        "白衣渡江": "白衣渡江.jpg",
        "刮目相看": "刮目相看.jpg",
        "偷渡阴平": "偷渡阴平.jpg",
        "割须弃袍": "割须弃袍.jpg",
        "江东止啼": "江东止啼.jpg",
    }

    def __init__(
        self,
        rect: pg.Rect,
        font: pg.font.Font,
        font_path: str | None = None,
        base_font_size: int = 20,
        cards_dir: str | None = None,
        allow_jiangdong_selection: bool = False,
    ) -> None:
        super().__init__(rect, font, font_path, base_font_size)
        self.available_cards = []
        self.selected_card_id: str | None = None
        self.card_rects: Dict[str, pg.Rect] = {}
        self.card_id_at_mouse: str | None = None
        self.mouse_pos: Tuple[int, int] = (0, 0)
        self._card_font_size = base_font_size
        self.tooltip_font = None
        self.cards_dir = cards_dir
        self._card_images: Dict[str, pg.Surface] = {}
        self.allow_jiangdong_selection = allow_jiangdong_selection
        self._card_available: Dict[str, bool] = {}

    def set_available_cards(self, cards: List) -> None:
        """设置可用卡牌列表"""
        self.available_cards = cards
        self.selected_card_id = None
        # 保存每张卡牌的可用状态
        self._card_available = {}
        for card in cards:
            self._card_available[card.id] = self._is_card_available(card.id)

    def _is_card_available(self, card_id: str) -> bool:
        """检查卡牌是否可用"""
        # 江东止啼仅在 allow_jiangdong_selection 为 True 时可用
        if card_id == "card_jiangdong_zhiti":
            return self.allow_jiangdong_selection
        return True

    def _get_card_image(self, card_name: str) -> pg.Surface | None:
        """获取卡牌图片，如果已加载则直接返回，否则加载并缓存"""
        if card_name in self._card_images:
            return self._card_images[card_name]

        if not self.cards_dir:
            return None

        image_filename = self.CARD_IMAGES.get(card_name)
        if not image_filename:
            return None

        image_path = os.path.join(self.cards_dir, image_filename)
        try:
            image = pg.image.load(image_path).convert_alpha()
            self._card_images[card_name] = image
            return image
        except Exception as e:
            print(f"加载卡牌图片失败 {image_filename}: {e}")
            return None

    def select_card(self, card_id: str) -> None:
        """选中一张卡牌"""
        # 检查卡牌是否存在于可用卡牌列表中
        for card in self.available_cards:
            if card.id == card_id:
                self.selected_card_id = card_id
                return
        # 如果卡牌还未绘制，也允许选择（用于交互）
        if card_id in self.card_rects or any(
            card.id == card_id for card in self.available_cards
        ):
            self.selected_card_id = card_id

    def deselect_card(self) -> None:
        """取消选中"""
        self.selected_card_id = None

    def get_card_at(self, pos: Tuple[int, int]) -> str | None:
        """获取在指定位置的卡牌 ID"""
        for card_id, rect in self.card_rects.items():
            if rect.collidepoint(pos):
                return card_id
        return None

    def get_selected_card(self) -> str | None:
        """获取当前选中的卡牌 ID"""
        return self.selected_card_id

    def handle_mouse_motion(self, pos: Tuple[int, int]) -> None:
        """处理鼠标移动"""
        self.mouse_pos = pos
        self.card_id_at_mouse = self.get_card_at(pos)

    def _draw_tooltip(self, surface: pg.Surface) -> None:
        """绘制鼠标悬停的卡牌描述浮窗"""
        if not self.card_id_at_mouse:
            return

        # 找到鼠标所在的卡牌
        card_def = None
        for card in self.available_cards:
            if card.id == self.card_id_at_mouse:
                card_def = card
                break

        if not card_def:
            return

        # 初始化 tooltip 字体（仅一次）
        if self.tooltip_font is None:
            tooltip_size = int(
                self.base_font_size * 0.8
            )  # 浮窗字体为 base_font_size 的 80%
            if self.font_path:
                try:
                    self.tooltip_font = pg.font.Font(self.font_path, tooltip_size)
                except:
                    self.tooltip_font = pg.font.SysFont("arial", tooltip_size)
            else:
                self.tooltip_font = pg.font.SysFont("arial", tooltip_size)

        # 准备 tooltip 内容
        description = card_def.description

        # 将长文本换行到合适宽度
        lines = []
        current_line = ""
        max_line_width = 220  # 增加最大宽度
        for char in description:
            test_line = current_line + char
            line_width = self.tooltip_font.size(test_line)[0]
            if line_width > max_line_width:
                if current_line:
                    lines.append(current_line)
                current_line = char
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)

        # 计算浮窗大小
        padding = 10  # 增加内间距
        line_height = self.tooltip_font.get_height() + 3  # 增加行间距
        # 加入卡牌名称和分隔线的高度
        tooltip_height = (
            self.tooltip_font.get_height()
            + 4
            + len(lines) * line_height
            + padding * 2
            + 4
        )

        max_line_width = (
            max(self.tooltip_font.size(line)[0] for line in lines) if lines else 100
        )
        # 确保足够宽度显示卡牌名称
        name_width = self.tooltip_font.size(card_def.name)[0]
        tooltip_width = max(max_line_width, name_width) + padding * 2

        # 确保浮窗在屏幕内
        tooltip_x = self.mouse_pos[0] + 10
        tooltip_y = self.mouse_pos[1] + 10

        # 防止浮窗超出屏幕右边
        if tooltip_x + tooltip_width > surface.get_width():
            tooltip_x = self.mouse_pos[0] - tooltip_width - 10

        # 防止浮窗超出屏幕下边
        if tooltip_y + tooltip_height > surface.get_height():
            tooltip_y = self.mouse_pos[1] - tooltip_height - 10

        tooltip_rect = pg.Rect(tooltip_x, tooltip_y, tooltip_width, tooltip_height)

        # 绘制浮窗背景和边框
        pg.draw.rect(surface, pg.Color("lightyellow"), tooltip_rect)
        pg.draw.rect(surface, pg.Color("black"), tooltip_rect, width=1)

        # 绘制卡牌名称（加粗）
        name_surf = self.tooltip_font.render(card_def.name, True, pg.Color("darkred"))
        surface.blit(name_surf, (tooltip_x + padding, tooltip_y + padding))

        # 绘制分隔线
        sep_y = tooltip_y + padding + self.tooltip_font.get_height() + 2
        pg.draw.line(
            surface,
            pg.Color("black"),
            (tooltip_x + padding, sep_y),
            (tooltip_x + tooltip_width - padding, sep_y),
            1,
        )

        # 绘制描述文本
        text_y = sep_y + 4
        for line in lines:
            line_surf = self.tooltip_font.render(line, True, pg.Color("black"))
            surface.blit(line_surf, (tooltip_x + padding, text_y))
            text_y += line_height

    def draw_tooltip(self, surface: pg.Surface) -> None:
        """对外暴露：绘制卡牌 tooltip（用于控制图层顺序）"""
        self._draw_tooltip(surface)

    def draw(self, surface: pg.Surface) -> None:
        # 绘制完整边框（InfoPanel 已无边框，无需去掉顶部）
        content_y = self.draw_background_and_border(surface, draw_top_border=True)

        # 绘制卡牌标题
        title_font = self._get_font(self.base_font_size)  # 与卡牌名称字体保持一致
        title_surf = title_font.render("锦囊卡", True, pg.Color("black"))
        title_rect = title_surf.get_rect(topleft=(self.rect.left + 10, content_y))
        surface.blit(title_surf, title_rect)
        content_y = title_rect.bottom + 8

        # 清空卡牌矩形缓存
        self.card_rects.clear()

        if not self.available_cards:
            # 没有可用卡牌
            no_card_font = self._get_font(12)
            no_card_surf = no_card_font.render("暂无可用锦囊卡", True, pg.Color("gray"))
            no_card_rect = no_card_surf.get_rect(
                center=(self.rect.centerx, content_y + 20)
            )
            surface.blit(no_card_surf, no_card_rect)
        else:
            # 绘制卡牌按钮：3 列并排，瘦高比例（3:4）
            card_font = self._get_font(self._card_font_size)
            cols = 3
            gap = 8
            card_count = len(self.available_cards)
            rows = max(1, (card_count + cols - 1) // cols)

            inner_x = self.rect.left + 10
            inner_w = self.rect.width - 20
            inner_h = self.rect.bottom - 10 - content_y

            # 卡牌采用瘦高比例：宽度：高度 = 3:4
            aspect_ratio = 0.75  # 宽高比
            max_card_w = (inner_w - gap * (cols - 1)) // cols
            max_card_h = (
                (inner_h - gap * (rows - 1)) // rows if rows > 0 else max_card_w
            )

            # 根据最大高度计算宽度（保持瘦高比例）
            card_height = max_card_h
            card_width = int(card_height * aspect_ratio)

            # 确保宽度不超过限制
            if card_width > max_card_w:
                card_width = max_card_w
                card_height = int(card_width / aspect_ratio)

            # 计算网格布局
            grid_w = cols * card_width + gap * (cols - 1)
            grid_x = inner_x + max(0, (inner_w - grid_w) // 2)

            for i, card in enumerate(self.available_cards):
                row = i // cols
                col = i % cols
                card_x = grid_x + col * (card_width + gap)
                card_y = content_y + row * (card_height + gap)

                # 检查是否超出面板范围
                if card_y + card_height > self.rect.bottom - 10:
                    break

                # 创建卡牌矩形（瘦高）
                card_rect = pg.Rect(card_x, card_y, card_width, card_height)
                self.card_rects[card.id] = card_rect

                # 获取卡牌图片
                card_image = self._get_card_image(card.name)

                # 判断是否选中
                is_selected = card.id == self.selected_card_id
                is_hover = card.id == self.card_id_at_mouse

                # 检查卡牌是否可用（江东止啼在非防守状态下不可用）
                is_available = self._is_card_available(card.id)

                # 不可用的卡牌不能被选中
                if not is_available:
                    is_selected = False
                    is_hover = False

                if card_image:
                    # 获取卡牌图片并保持原比例缩放
                    img_w, img_h = card_image.get_size()
                    img_aspect = img_w / img_h
                    rect_aspect = card_width / card_height

                    if img_aspect > rect_aspect:
                        # 图片更宽，按宽度缩放
                        new_w = card_width
                        new_h = int(card_width / img_aspect)
                    else:
                        # 图片更高，按高度缩放
                        new_h = card_height
                        new_w = int(card_height * img_aspect)

                    scaled_image = pg.transform.smoothscale(card_image, (new_w, new_h))

                    # 居中绘制图片
                    image_x = card_x + (card_width - new_w) // 2
                    image_y = card_y + (card_height - new_h) // 2
                    surface.blit(scaled_image, (image_x, image_y))

                    # 绘制边框特效
                    if is_selected:
                        # 选中：金色发光边框（多层边框模拟发光）
                        for offset in range(3, 0, -1):
                            glow_rect = pg.Rect(
                                card_x - offset,
                                card_y - offset,
                                card_width + offset * 2,
                                card_height + offset * 2,
                            )
                            glow_color = pg.Color(255, 215, 0, 100)  # 金色半透明
                            pg.draw.rect(
                                surface, glow_color, glow_rect, width=2, border_radius=8
                            )
                        # 内层实线边框
                        pg.draw.rect(
                            surface,
                            pg.Color("gold"),
                            card_rect,
                            width=3,
                            border_radius=6,
                        )
                    elif is_hover:
                        # 悬停：蓝色/白色高亮边框
                        pg.draw.rect(
                            surface,
                            pg.Color(100, 180, 255),
                            card_rect,
                            width=3,
                            border_radius=6,
                        )
                    else:
                        # 默认：细边框
                        pg.draw.rect(
                            surface,
                            pg.Color(80, 80, 80),
                            card_rect,
                            width=1,
                            border_radius=6,
                        )

                    # 在图片底部叠加半透明背景（用于显示文字）
                    text_bg_height = int(card_height * 0.25)
                    overlay_rect = pg.Rect(
                        card_rect.left,
                        card_rect.bottom - text_bg_height,
                        card_width,
                        text_bg_height,
                    )
                    overlay_surface = pg.Surface(
                        (card_width, text_bg_height), pg.SRCALPHA
                    )
                    overlay_surface.fill((0, 0, 0, 180))
                    surface.blit(overlay_surface, overlay_rect)

                    # 绘制卡牌名称（白色文字，在半透明背景上）
                    text_color = pg.Color("white")
                    # 字体大小根据卡牌宽度动态调整
                    name_font_size = max(10, int(card_width * 0.35))
                    name_font = self._get_font(name_font_size)
                    card_name_surf = name_font.render(card.name, True, text_color)
                    name_width = card_name_surf.get_width()
                    name_height = card_name_surf.get_height()

                    # 留边距预留（两侧各留 4 像素）
                    margin = 4
                    container_width = card_width - margin * 2

                    # 如果文字超出框外，使用省略号
                    if name_width > container_width:
                        # 截断名称直到能够显示
                        display_name = card.name
                        dot_num = 1
                        while (
                            name_font.size(display_name + "•" * dot_num)[0]
                            > container_width
                            and len(display_name) > 1
                        ):
                            display_name = display_name[:-1]
                        card_name_surf = name_font.render(
                            display_name + "•" * dot_num, True, text_color
                        )
                        name_width = card_name_surf.get_width()

                    # 水平居中，垂直在半透明背景区域内居中
                    name_x = card_rect.left + (card_width - name_width) // 2
                    # 文字绘制在半透明背景的垂直中心位置
                    name_y = (
                        card_rect.bottom
                        - text_bg_height
                        + (text_bg_height - name_height) // 2
                    )

                    surface.blit(card_name_surf, (name_x, name_y))

                    # 为不可用的卡牌添加灰色遮罩
                    if not is_available:
                        # 绘制半透明灰色遮罩，表示卡牌不可用
                        overlay = pg.Surface((card_width, card_height), pg.SRCALPHA)
                        overlay.fill((100, 100, 100, 150))  # 半透明灰色
                        surface.blit(overlay, (card_x, card_y))

                        # 绘制"不可用"文字
                        unavailable_font = self._get_font(
                            max(8, int(card_width * 0.25))
                        )
                        unavailable_surf = unavailable_font.render(
                            "不可用", True, pg.Color("white")
                        )
                        unavailable_rect = unavailable_surf.get_rect(
                            center=(card_rect.centerx, card_rect.centery)
                        )
                        surface.blit(unavailable_surf, unavailable_rect)
                else:
                    # 无图片：使用原来的纯色按钮逻辑作为降级处理
                    if is_selected:
                        # 选中：金色强调
                        bg_color = pg.Color(255, 246, 204)
                        border_color = pg.Color("gold")
                        border_width = 2
                        text_color = pg.Color("black")
                    elif is_hover:
                        # 悬停：蓝灰按钮
                        bg_color = pg.Color(220, 232, 245)
                        border_color = pg.Color(60, 90, 130)
                        border_width = 2
                        text_color = pg.Color("black")
                    else:
                        # 默认：浅灰按钮
                        bg_color = pg.Color(238, 238, 238)
                        border_color = pg.Color(90, 90, 90)
                        border_width = 1
                        text_color = pg.Color("black")

                    # 按钮阴影
                    shadow_rect = card_rect.move(1, 1)
                    pg.draw.rect(
                        surface, pg.Color(180, 180, 180), shadow_rect, border_radius=6
                    )

                    pg.draw.rect(surface, bg_color, card_rect, border_radius=6)
                    pg.draw.rect(
                        surface,
                        border_color,
                        card_rect,
                        width=border_width,
                        border_radius=6,
                    )

                    # 绘制卡牌名称，确保完全框内
                    # 字体大小根据卡牌宽度动态调整
                    name_font_size = max(10, int(card_width * 0.35))
                    name_font = self._get_font(name_font_size)
                    card_name_surf = name_font.render(card.name, True, text_color)
                    name_width = card_name_surf.get_width()
                    name_height = card_name_surf.get_height()

                    # 留边距预留（两侧各留 4 像素）
                    margin = 4
                    container_width = card_width - margin * 2

                    # 如果文字超出框外，使用省略号
                    if name_width > container_width:
                        # 截断名称直到能够显示
                        display_name = card.name
                        dot_num = 1
                        while (
                            name_font.size(display_name + "•" * dot_num)[0]
                            > container_width
                            and len(display_name) > 1
                        ):
                            display_name = display_name[:-1]
                        card_name_surf = name_font.render(
                            display_name + "•" * dot_num, True, text_color
                        )
                        name_width = card_name_surf.get_width()

                    # 水平居中、垂直居中
                    name_x = card_rect.left + (card_width - name_width) // 2
                    name_y = card_rect.top + (card_height - name_height) // 2

                    # 确保文字完全在框内（额外边距 3 像素）
                    name_x = max(card_rect.left + margin, name_x)
                    name_x = min(card_rect.right - name_width - margin, name_x)
                    name_y = max(card_rect.top + 3, name_y)  # 上方留 3 像素
                    name_y = min(
                        card_rect.bottom - name_height - 3, name_y
                    )  # 下方留 3 像素

                    surface.blit(card_name_surf, (name_x, name_y))

                    # 为不可用的卡牌添加灰色遮罩
                    if not is_available:
                        # 绘制半透明灰色遮罩，表示卡牌不可用
                        overlay = pg.Surface((card_width, card_height), pg.SRCALPHA)
                        overlay.fill((100, 100, 100, 150))  # 半透明灰色
                        surface.blit(overlay, (card_x, card_y))

                        # 绘制"不可用"文字
                        unavailable_font = self._get_font(
                            max(8, int(card_width * 0.25))
                        )
                        unavailable_surf = unavailable_font.render(
                            "不可用", True, pg.Color("white")
                        )
                        unavailable_rect = unavailable_surf.get_rect(
                            center=(card_rect.centerx, card_rect.centery)
                        )
                        surface.blit(unavailable_surf, unavailable_rect)

        # tooltip 由上层渲染流程统一控制图层顺序


class InfoPanel(BasePanel):
    def __init__(
        self,
        rect: pg.Rect,
        font: pg.font.Font,
        font_path: str | None = None,
        base_font_size: int = 20,
    ) -> None:
        super().__init__(rect, font, font_path, base_font_size)

        self._message: str | None = None
        self._message_end_time: float = 0.0
        # True 表示当前内容来自 show_properties（选中属性/行动结果），False 表示来自 show_message（临时通知）
        self._is_properties_display: bool = False

        # 战斗相关状态
        self.dice_result: int | None = None
        self.combat_result_text: str | None = None

        # 右侧状态栏卷轴装饰图（可选）
        self.status_image: pg.Surface | None = None
        self._combat_attacker_info: str | None = None
        self._combat_enemy_info: str | None = None

    def show_properties(self, props: str) -> None:
        """显示选中单位/格子的属性列表（永久显示，可被 clear_if_properties 清除）"""
        self._message = props
        self._message_end_time = float("inf")  # 永久显示，直到被覆盖
        self._is_properties_display = True
        # 清除战斗状态但保留消息
        self.dice_result = None
        self.combat_result_text = None
        self._combat_attacker_info = None
        self._combat_enemy_info = None  # 清除之前的敌方预览

    def show_message(self, text: str, duration: float = 2.0) -> None:
        """显示一条临时消息（有时限，不被 clear_if_properties 清除）"""
        self._message = text
        self._message_end_time = time.time() + duration
        self._is_properties_display = False

    def clear_if_properties(self) -> None:
        """仅当当前显示内容来自 show_properties 时才清除，临时行动消息（show_message）不受影响。"""
        if self._is_properties_display:
            self._message = None
            self._message_end_time = 0.0
            self._is_properties_display = False

    def show_combat_details(self, attacker_info: str, defender_info: str) -> None:
        """显示战斗双方详情"""
        self._combat_attacker_info = attacker_info
        self._combat_enemy_info = defender_info
        self.dice_result = None
        self.combat_result_text = None
        # 清除选中的单位信息，避免重叠
        self._message = None
        self._is_properties_display = False

    def show_combat_result(
        self, dice: int | None, result_text: str | None, detail_msg: str = ""
    ) -> None:
        """显示战斗结果详请（只显示详情，不显示标题）"""
        self.dice_result = dice
        self.combat_result_text = result_text
        self._combat_attacker_info = None
        self._combat_enemy_info = None

        # 详细战报显示在消息区域（永久保留，不被 clear_if_properties 清除）
        self._message = detail_msg
        self._message_end_time = float("inf")
        self._is_properties_display = False

    def reset_combat_state(self) -> None:
        """重置战斗面板"""
        self.dice_result = None
        self.combat_result_text = None
        self._combat_attacker_info = None
        self._combat_enemy_info = None

    def handle_click(self, pos: Tuple[int, int]) -> bool:
        """
        处理点击事件。
        """
        # 现在面板本身没有按钮了，返回 False (如果有其他交互需求再加)
        return False

    def _draw_separator(self, surface: pg.Surface, y: int) -> int:
        """绘制一条横贯面板的分割线"""
        line_y = y + 5
        pg.draw.line(
            surface,
            pg.Color("black"),
            (self.rect.left + 5, line_y),
            (self.rect.right - 5, line_y),
            2,
        )
        return line_y + 10

    def draw(self, surface: pg.Surface) -> None:
        """绘制面板"""
        orig_rect = self.rect

        # 1. 绘制白色背景（整个面板）
        pg.draw.rect(surface, pg.Color("white"), orig_rect)

        # 2. 若有卷轴装饰图，直接 blit（已在资产构建时缩放至面板宽×高，上下左右对齐）
        if self.status_image is not None:
            surface.blit(self.status_image, (orig_rect.left, orig_rect.top))

        # 4. 将 self.rect 临时切换到卷轴内部文字区域，使所有文字绘制函数自动限制宽度
        if self.status_image is not None:
            h_margin = int(orig_rect.height * 0.15)  # 上下留15%给卷轴轴头装饰
            w_margin = int(orig_rect.width * 0.17)  # 左右留17%给卷轴侧边装饰
            self.rect = pg.Rect(
                orig_rect.left + w_margin,
                orig_rect.top + h_margin,
                orig_rect.width - 2 * w_margin,
                orig_rect.height - 2 * h_margin,
            )
        content_y = self.rect.top

        try:
            # 5. 优先绘制战斗结果标题（如果有）
            if self.combat_result_text:
                parts = self.combat_result_text.split(" · ")
                total_w = 0
                widths = []
                sep_w, _ = self.font.size(" · ")

                for i, part in enumerate(parts):
                    w, h = self.font.size(part)
                    widths.append(w)
                    total_w += w
                    if i < len(parts) - 1:
                        total_w += sep_w

                x = self.rect.centerx - total_w // 2

                for i, part in enumerate(parts):
                    color = pg.Color("blue") if "骰" in part else pg.Color("black")
                    surf = self.font.render(part, True, color)
                    surface.blit(surf, (x, content_y))
                    x += widths[i]

                    if i < len(parts) - 1:
                        sep_surf = self.font.render(" · ", True, pg.Color("black"))
                        surface.blit(sep_surf, (x, content_y))
                        x += sep_w

                content_y += self.font.get_height() + 10

            # 6. 绘制临时消息 (或者属性列表/战报详情)
            current_time = time.time()
            if self._message and (
                self._message_end_time > current_time
                or self._message_end_time == float("inf")
            ):
                available_h = self.rect.bottom - content_y - 10
                last_y = self.draw_text_wrapped(
                    surface,
                    self._message,
                    pg.Color("black"),
                    content_y,
                    max_height=available_h,
                )
                content_y = last_y + 10

            # 7. 绘制战斗详情 (两个部分：攻击者 -> --- -> 防守者)
            if self._combat_attacker_info or self._combat_enemy_info:
                atk_line_count = len(
                    [
                        l
                        for l in (self._combat_attacker_info or "").split("\n")
                        if l.strip()
                    ]
                )
                def_line_count = len(
                    [
                        l
                        for l in (self._combat_enemy_info or "").split("\n")
                        if l.strip()
                    ]
                )
                total_units = atk_line_count + def_line_count

                atk_max_h = None
                def_max_h = None
                if total_units > 9:
                    _SEP_H = 15  # 分割线占用高度约15px
                    available_h = max(0, self.rect.bottom - content_y - 10)
                    usable_h = max(0, available_h - _SEP_H)
                    if atk_line_count > 0:
                        atk_max_h = max(1, int(usable_h * atk_line_count / total_units))
                    if def_line_count > 0:
                        def_max_h = max(1, int(usable_h * def_line_count / total_units))

                if self._combat_attacker_info:
                    content_y = self.draw_text_wrapped(
                        surface,
                        self._combat_attacker_info,
                        pg.Color("black"),
                        content_y,
                        max_height=atk_max_h,
                    )
                    content_y = self._draw_separator(surface, content_y)

                if self._combat_enemy_info:
                    content_y = self.draw_text_wrapped(
                        surface,
                        self._combat_enemy_info,
                        pg.Color("black"),
                        content_y,
                        max_height=def_max_h,
                    )

        # 绘制战斗结果 (现已合并到 message 中显示详细版)
        # if self.dice_result is not None:
        #    result_str = f"骰子：{self.dice_result} -> {self.combat_result_text}"
        #    self.draw_text_wrapped(surface, result_str, pg.Color("blue"), content_y)
        finally:
            self.rect = orig_rect
