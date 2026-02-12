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
            
        lines = []
        max_width = self.rect.width - 20
        
        # 1. 先按换行符拆分段落，确保 \n 生效
        paragraphs = text.replace('\r', '').split('\n')
        
        for paragraph in paragraphs:
            # 如果是空行，插入占位符以便后面渲染时增加 Y 轴距离
            if not paragraph:
                lines.append("")
                continue

            # 2. 对每个段落进行自动换行处理
            current_line = ""
            for char in paragraph:
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
        font_height = self.font.get_height()
        
        for line in lines:
            if not line:
                # 空行，只移动 y 坐标
                y += font_height // 2 # 空行高度给一半？或者给全高
                continue
                
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
        self._combat_attacker_info: str | None = None
        self._combat_enemy_info: str | None = None
        
        # 按钮区域
        btn_width = max(120, int(rect.width * 0.6))
        btn_height = max(40, int(rect.height * 0.1))
        btn_x = rect.centerx - btn_width // 2
        btn_y = rect.y + int(rect.height * 0.3)
        
        self.button_rect = pg.Rect(btn_x, btn_y, btn_width, btn_height)
        self._on_dice_click: Callable[[], None] | None = None

    def show_properties(self, props: str) -> None:
        """显示选中单位/格子的属性列表"""
        self._message = props
        self._message_end_time = float("inf") # 永久显示，直到被覆盖
        # 清除战斗状态但保留消息
        self.show_dice_button = False
        self.dice_result = None
        self.combat_result_text = None
        self._combat_attacker_info = None
        self._combat_enemy_info = None # 清除之前的敌方预览
        self._on_dice_click = None

    def show_message(self, text: str, duration: float = 2.0) -> None:
        """显示一条临时消息"""
        self._message = text
        self._message_end_time = time.time() + duration
        # 显示消息时隐藏战斗UI，避免冲突
        # self.reset_combat_state() # 暂时注释掉，避免冲掉正在进行的战斗请求显示

    def show_combat_request(self, ratio: float, attacker_info: str, defender_info: str, on_roll: Callable[[], None]) -> None:
        """显示战斗请求（投骰子按钮）"""
        self.combat_ratio = ratio
        self._combat_attacker_info = attacker_info
        self._combat_enemy_info = defender_info
        self.show_dice_button = True
        self._on_dice_click = on_roll
        self.dice_result = None
        self.combat_result_text = None
        # 清除选中的单位信息，避免重叠
        self._message = None 

    def show_combat_result(self, dice: int, result_text: str, detail_msg: str = "") -> None:
        """显示战斗结果"""
        self.dice_result = dice
        self.combat_result_text = result_text
        self.show_dice_button = False # 隐藏按钮
        
        # 详细战报显示在消息区域（不包含标题，标题单独绘制）
        self._message = detail_msg
        self._message_end_time = float("inf")


    def reset_combat_state(self) -> None:
        """重置战斗面板"""
        self.show_dice_button = False
        self.dice_result = None
        self.combat_result_text = None
        self._on_dice_click = None
        self._combat_attacker_info = None
        self._combat_enemy_info = None

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
        # 如果还在显示时间内，或者是永久消息(inf)，且不在战斗投骰子状态（避免重叠）
        if self._message and (self._message_end_time > current_time or self._message_end_time == float("inf")) and not self.show_dice_button:
            # 如果没有战斗UI，那整个面板都可以用来显示文字
            last_y = self.draw_text_wrapped(surface, self._message, pg.Color("black"), content_y)
            content_y = last_y + 10 

        # 4. 绘制战斗UI (三个部分：攻击者 -> --- -> 防守者 -> --- -> 按钮)
        if self.show_dice_button:
            # Part 1: 攻击者
            if self._combat_attacker_info:
                content_y = self.draw_text_wrapped(surface, self._combat_attacker_info, pg.Color("black"), content_y)
                content_y = self._draw_separator(surface, content_y)
                
            # Part 2: 防守者
            if self._combat_enemy_info:
                content_y = self.draw_text_wrapped(surface, self._combat_enemy_info, pg.Color("black"), content_y)
                content_y = self._draw_separator(surface, content_y)
            
            # Part 3: 攻防比 + 投骰子按钮
            # 显示攻防比
            ratio_text = f"攻防比: {self.combat_ratio:.1f}"
            ratio_surf = self.font.render(ratio_text, True, pg.Color("blue"))
            ratio_rect = ratio_surf.get_rect(midtop=(self.rect.centerx, content_y))
            surface.blit(ratio_surf, ratio_rect)
            
            # 更新按钮位置到攻防比下方
            btn_y = ratio_rect.bottom + 10
            self.button_rect.y = btn_y
            self.button_rect.centerx = self.rect.centerx
            
            # 绘制按钮
            pg.draw.rect(surface, pg.Color("blue"), self.button_rect)
            btn_text = self.font.render("投骰子", True, pg.Color("white"))
            btn_text_rect = btn_text.get_rect(center=self.button_rect.center)
            surface.blit(btn_text, btn_text_rect)

        # 4. 绘制战斗结果 (现已合并到 message 中显示详细版，这里保留简单骰子显示)
        # if self.dice_result is not None:
        #    result_str = f"骰子: {self.dice_result} -> {self.combat_result_text}"
        #    self.draw_text_wrapped(surface, result_str, pg.Color("blue"), content_y)
