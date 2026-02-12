"""
信息面板模块。
负责在屏幕右侧显示游戏反馈、错误提示和战斗骰子。
"""
from __future__ import annotations

import time
from typing import Callable, Tuple

import pygame as pg

class InfoPanel:
    def __init__(self, rect: pg.Rect, font: pg.font.Font) -> None:
        self.rect = rect
        self.font = font
        self._message: str | None = None
        self._message_end_time: float = 0.0
        
        # 战斗相关状态
        self.show_dice_button = False
        self.combat_ratio: float = 0.0
        self.dice_result: int | None = None
        self.combat_result_text: str | None = None
        
        # 按钮区域 (相对坐标还是绝对坐标？用绝对坐标方便点击检测)
        self.button_rect = pg.Rect(rect.x + 20, rect.y + 100, 120, 40)
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
        # 1. 绘制背景 (可选，暂时透明或半透明)
        # pg.draw.rect(surface, pg.Color(240, 240, 240), self.rect)
        
        # 2. 绘制临时消息
        current_time = time.time()
        if self._message and current_time < self._message_end_time:
            text_surf = self.font.render(self._message, True, pg.Color("red"))
            # 居中显示在面板顶部
            text_rect = text_surf.get_rect(midtop=(self.rect.centerx, self.rect.y + 20))
            surface.blit(text_surf, text_rect)
            return # 如果有紧急消息，优先显示消息，不显示别的

        # 3. 绘制战斗UI
        if self.show_dice_button:
            # 显示攻防比
            ratio_text = f"攻防比: {self.combat_ratio:.1f}"
            ratio_surf = self.font.render(ratio_text, True, pg.Color("black"))
            surface.blit(ratio_surf, (self.rect.x + 20, self.rect.y + 50))
            
            # 绘制按钮
            pg.draw.rect(surface, pg.Color("blue"), self.button_rect)
            btn_text = self.font.render("投骰子", True, pg.Color("white"))
            btn_text_rect = btn_text.get_rect(center=self.button_rect.center)
            surface.blit(btn_text, btn_text_rect)

        # 4. 绘制战斗结果
        if self.dice_result is not None:
            result_str = f"骰子: {self.dice_result} -> {self.combat_result_text}"
            res_surf = self.font.render(result_str, True, pg.Color("blue"))
            surface.blit(res_surf, (self.rect.x + 20, self.rect.y + 150))
