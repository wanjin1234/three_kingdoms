"""
信息面板模块。
负责在屏幕右侧显示游戏反馈、错误提示和战斗骰子。
"""
from __future__ import annotations

import time
from typing import Callable, Tuple

import pygame as pg


class BasePanel:
    """面板基类，提供通用的背景绘制和文字换行功能"""
    def __init__(self, rect: pg.Rect, font: pg.font.Font, font_path: str | None = None, base_font_size: int = 20) -> None:
        self.rect = rect
        self.font = font
        self.font_path = font_path
        self.base_font_size = base_font_size
        self._font_cache = {} # size -> Font

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

    def draw_background_and_border(self, surface: pg.Surface, draw_top_border: bool = True) -> int:
        """绘制白底黑框，返回内容区域的起始 Y 坐标"""
        # 1. 填充背景
        pg.draw.rect(surface, pg.Color("white"), self.rect)
        # 2. 绘制完整边框
        pg.draw.rect(surface, pg.Color("black"), self.rect, width=2)
        
        # 3. 如果不需要顶部边框，用白色矩形覆盖掉
        if not draw_top_border:
            # 覆盖区域：x从+2开始，y从top开始，宽度-4，高度2
            # 这样保留了左右两侧的垂直边框的连接处
            cover_rect = pg.Rect(
                self.rect.left + 2, 
                self.rect.top, 
                self.rect.width - 4, 
                2
            )
            pg.draw.rect(surface, pg.Color("white"), cover_rect)
            
        return self.rect.y + 20

    def _layout_text(self, text: str, font: pg.font.Font, color: pg.Color) -> Tuple[list[str], list[pg.Color], int]:
        """
        根据给定字体计算文字排版。
        返回 (lines, colors, total_height)
        """
        if not text:
            return [], [], 0
            
        lines = []
        line_colors = []
        max_width = self.rect.width - 20
        font_height = font.get_height()
        
        paragraphs = text.replace('\r', '').split('\n')
        total_height = 0

        for paragraph in paragraphs:
            para_color = pg.Color("red") if ("血0" in paragraph or "血-" in paragraph) else color

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

    def _render_rich_text_line(self, surface: pg.Surface, line: str, font: pg.font.Font, y: int, default_color: pg.Color) -> None:
        """
        渲染包含简易颜色标记的一行文字。
        标记格式： "|#RRGGBB|文本"
        例如: "[|#FF0000|红色文字|#000000|]黑色文字"  (需修正 Split 逻辑)
        """
        # 注意: split('|') 会把 "|#fff|text" 分成 ["", "#fff", "text"]
        parts = line.split('|')
        segments = []
        current_color = default_color
        
        total_width = 0
        
        for part in parts:
            if not part: continue
            
            # 检测是否是颜色代码
            if part.startswith('#') and len(part) == 7:
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
            # 垂直居中对齐稍微调整可以忽略
            surface.blit(surf, (x, y))
            x += surf.get_width()

    def draw_text_wrapped(self, surface: pg.Surface, text: str, color: pg.Color, start_y: int, max_height: int | None = None) -> int:
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
        plain_text = re.sub(r'\|#[A-Fa-f0-9]{6}\|', '', text).replace('|', '')
        
        current_font = self.font
        # 使用去标记后的纯文本进行排版计算
        lines_layout, line_colors_layout, total_h = self._layout_text(plain_text, current_font, color)

        # 自适应字体大小逻辑
        if max_height is not None and self.font_path:
            size = self.base_font_size
            min_size = 10
            while total_h > max_height and size > min_size:
                size -= 2
                current_font = self._get_font(size)
                lines_layout, line_colors_layout, total_h = self._layout_text(plain_text, current_font, color)

        # 渲染
        y = start_y
        font_height = current_font.get_height()
        
        # 这里需要重新按换行符分割原始带标记的文本
        # 注意：这假设 _layout_text 没有因为宽度强行把一行很长的富文本切断
        # 如果切断了，这里的对应关系会乱。
        # 鉴于当前需求只用来显示简短的单位属性，我们假设每段都不会自动折行。
        original_paragraphs = text.replace('\r', '').split('\n')
        
        # 我们遍历 logic lines, 但实际上我们需要渲染 original paragraphs
        # 如果 original_paragraphs 比 layed out lines 少，说明发生了自动换行。
        # 这里为了安全起见，如果检测到含有颜色标记，就不使用自动换行，直接截断或者强制单行
        # 或者仅仅对含有标记的行特殊处理
        
        for para in original_paragraphs:
            if not para:
                y += font_height // 2
                continue
                
            if '|#' in para:
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
    def draw(self, surface: pg.Surface) -> None:
        # 去掉顶部边框，避免与上方 InfoPanel 的底部边框重叠变粗
        content_y = self.draw_background_and_border(surface, draw_top_border=False)
        self.draw_text_wrapped(surface, "卡牌面板", pg.Color("black"), content_y)


class InfoPanel(BasePanel):
    def __init__(self, rect: pg.Rect, font: pg.font.Font, font_path: str | None = None, base_font_size: int = 20) -> None:
        super().__init__(rect, font, font_path, base_font_size)


        self._message: str | None = None
        self._message_end_time: float = 0.0
        
        # 战斗相关状态
        self.dice_result: int | None = None
        self.combat_result_text: str | None = None
        self._combat_attacker_info: str | None = None
        self._combat_enemy_info: str | None = None

    def show_properties(self, props: str) -> None:
        """显示选中单位/格子的属性列表"""
        self._message = props
        self._message_end_time = float("inf") # 永久显示，直到被覆盖
        # 清除战斗状态但保留消息
        self.dice_result = None
        self.combat_result_text = None
        self._combat_attacker_info = None
        self._combat_enemy_info = None # 清除之前的敌方预览

    def show_message(self, text: str, duration: float = 2.0) -> None:
        """显示一条临时消息"""
        self._message = text
        self._message_end_time = time.time() + duration

    def show_combat_details(self, attacker_info: str, defender_info: str) -> None:
        """显示战斗双方详情"""
        self._combat_attacker_info = attacker_info
        self._combat_enemy_info = defender_info
        self.dice_result = None
        self.combat_result_text = None
        # 清除选中的单位信息，避免重叠
        self._message = None 

    def show_combat_result(self, dice: int | None, result_text: str | None, detail_msg: str = "") -> None:
        """显示战斗结果详请（只显示详情，不显示标题）"""
        self.dice_result = dice
        self.combat_result_text = result_text
        self._combat_attacker_info = None
        self._combat_enemy_info = None
        
        # 详细战报显示在消息区域
        self._message = detail_msg
        self._message_end_time = float("inf")


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
            2
        )
        return line_y + 10

    def draw(self, surface: pg.Surface) -> None:
        """绘制面板"""
        # 1. 绘制背景和边框
        content_y = self.draw_background_and_border(surface)
        
        # 2. 优先绘制战斗结果标题（如果有）
        if self.combat_result_text:
            parts = self.combat_result_text.split(" · ")
            total_w = 0
            widths = []
            sep_w, _ = self.font.size(" · ")
            
            # 同样按照两端加空格的方式绘制
            for i, part in enumerate(parts):
                w, h = self.font.size(part)
                widths.append(w)
                total_w += w
                if i < len(parts) - 1:
                    total_w += sep_w
            
            x = self.rect.centerx - total_w // 2
            
            for i, part in enumerate(parts):
                # 判读是否是骰子部分 (根据是否包含数字且位置在中间？或者根据内容)
                # 简单判读：包含 "骰" 字
                color = pg.Color("blue") if "骰" in part else pg.Color("black")
                surf = self.font.render(part, True, color)
                surface.blit(surf, (x, content_y))
                x += widths[i]
                
                if i < len(parts) - 1:
                    # 绘制分隔符
                    sep_surf = self.font.render(" · ", True, pg.Color("black"))
                    surface.blit(sep_surf, (x, content_y))
                    x += sep_w
            
            content_y += self.font.get_height() + 10

        # 3. 绘制临时消息 (或者属性列表/战报详情)
        current_time = time.time()
        # 如果还在显示时间内，或者是永久消息(inf)
        if self._message and (self._message_end_time > current_time or self._message_end_time == float("inf")):
            # 计算剩余可用高度，留出一点底部边距
            available_h = self.rect.bottom - content_y - 10
            # 如果没有战斗UI，那整个面板都可以用来显示文字
            last_y = self.draw_text_wrapped(surface, self._message, pg.Color("black"), content_y, max_height=available_h)
            content_y = last_y + 10 

        # 4. 绘制战斗详情 (两个部分：攻击者 -> --- -> 防守者)
        # Part 1: 攻击者
        if self._combat_attacker_info:
            content_y = self.draw_text_wrapped(surface, self._combat_attacker_info, pg.Color("black"), content_y)
            content_y = self._draw_separator(surface, content_y)
            
        # Part 2: 防守者
        if self._combat_enemy_info:
            content_y = self.draw_text_wrapped(surface, self._combat_enemy_info, pg.Color("black"), content_y)
            # content_y = self._draw_separator(surface, content_y) # 底部不需要分隔符了

        # 4. 绘制战斗结果 (现已合并到 message 中显示详细版，这里保留简单骰子显示)
        # if self.dice_result is not None:
        #    result_str = f"骰子: {self.dice_result} -> {self.combat_result_text}"
        #    self.draw_text_wrapped(surface, result_str, pg.Color("blue"), content_y)
