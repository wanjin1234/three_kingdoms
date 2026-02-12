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
    def __init__(self, rect: pg.Rect, font: pg.font.Font) -> None:
        self.rect = rect
        self.font = font

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

    def draw_text_wrapped(self, surface: pg.Surface, text: str, color: pg.Color, start_y: int) -> int:
        """
        绘制水平居中且自动换行的文本。
        返回文本结束后的 Y 坐标。
        """
        if not text:
            return start_y
            
        # 简单的按字符换行，适应中文
        lines = []
        current_line = ""
        max_width = self.rect.width - 20
        
        for char in text:
            test_line = current_line + char
            w, h = self.font.size(test_line)
            if w > max_width:
                if not current_line: 
                    lines.append(char)
                    current_line = ""
                else:
                    lines.append(current_line)
                    current_line = char
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
            
        y = start_y
        for line in lines:
            surf = self.font.render(line, True, color)
            rect = surf.get_rect(midtop=(self.rect.centerx, y))
            surface.blit(surf, rect)
            y += surf.get_height() + 5
            
        return y


class CardPanel(BasePanel):
    """卡牌面板"""
    def draw(self, surface: pg.Surface) -> None:
        # 去掉顶部边框，避免与上方 InfoPanel 的底部边框重叠变粗
        content_y = self.draw_background_and_border(surface, draw_top_border=False)
        self.draw_text_wrapped(surface, "卡牌面板", pg.Color("black"), content_y)


class InfoPanel(BasePanel):
    def __init__(self, rect: pg.Rect, font: pg.font.Font) -> None:
        super().__init__(rect, font)
        self._message: str | None = None
        self._message_end_time: float = 0.0
        
        # 战斗相关状态
        self.show_dice_button = False
        self.combat_ratio: float = 0.0
        self.dice_result: int | None = None
        self.combat_result_text: str | None = None
        
        # 按钮区域
        btn_width = max(120, int(rect.width * 0.6))
        btn_height = max(40, int(rect.height * 0.1))
        btn_x = rect.centerx - btn_width // 2
        btn_y = rect.y + int(rect.height * 0.3)
        
        self.button_rect = pg.Rect(btn_x, btn_y, btn_width, btn_height)
        self._on_dice_click: Callable[[], None] | None = None

    def show_message(self, text: str, duration: float = 2.0) -> None:
        """显示一条临时消息"""
        self._message = text
        self._message_end_time = time.time() + duration
        # 显示消息时隐藏战斗UI，避免冲突
        self.reset_combat_state()

    def show_combat_request(self, ratio: float, on_roll: Callable[[], None]) -> None:
        """显示战斗请求（投骰子按钮）"""
        self.combat_ratio = ratio
        self.show_dice_button = True
        self._on_dice_click = on_roll
        self.dice_result = None
        self.combat_result_text = None
        self._message = None # 清除其他消息

    def show_combat_result(self, dice: int, result_text: str) -> None:
        """显示战斗结果"""
        self.dice_result = dice
        self.combat_result_text = result_text
        self.show_dice_button = False # 隐藏按钮

    def reset_combat_state(self) -> None:
        """重置战斗面板"""
        self.show_dice_button = False
        self.dice_result = None
        self.combat_result_text = None
        self._on_dice_click = None

    def handle_click(self, pos: Tuple[int, int]) -> bool:
        """
        处理点击事件。
        如果点击了按钮，返回 True。
        """
        if self.show_dice_button and self.button_rect.collidepoint(pos):
            if self._on_dice_click:
                self._on_dice_click()
            return True
        return False

    def draw(self, surface: pg.Surface) -> None:
        """绘制面板"""
        # 1. 绘制背景和边框
        content_y = self.draw_background_and_border(surface)
        
        # 2. 绘制临时消息
        current_time = time.time()
        if self._message and current_time < self._message_end_time:
            self.draw_text_wrapped(surface, self._message, pg.Color("red"), content_y)
            # 如果有紧急消息，优先显示消息
            return

        # 3. 绘制战斗UI
        if self.show_dice_button:
            # 显示攻防比
            ratio_text = f"攻防比: {self.combat_ratio:.1f}"
            
            text_bottom_y = self.button_rect.top - 10
            ratio_surf = self.font.render(ratio_text, True, pg.Color("black"))
            ratio_rect = ratio_surf.get_rect(midbottom=(self.rect.centerx, text_bottom_y))
            surface.blit(ratio_surf, ratio_rect)
            
            # 绘制按钮
            pg.draw.rect(surface, pg.Color("blue"), self.button_rect)
            btn_text = self.font.render("投骰子", True, pg.Color("white"))
            btn_text_rect = btn_text.get_rect(center=self.button_rect.center)
            surface.blit(btn_text, btn_text_rect)

        # 4. 绘制战斗结果
        if self.dice_result is not None:
            result_str = f"骰子: {self.dice_result} -> {self.combat_result_text}"
            self.draw_text_wrapped(surface, result_str, pg.Color("blue"), content_y)
