"""
控制台服务：抽离 `GameApp` 中的控制台命令与输入处理逻辑。
"""

from __future__ import annotations

import logging
from typing import Any

import pygame as pg

logger = logging.getLogger(__name__)


class ConsoleService:
    """控制台交互与命令执行服务。"""

    def toggle_console(self, app: Any) -> None:
        """切换控制台显示状态。"""
        app.console_visible = not app.console_visible
        if app.console_visible:
            app.console_input = ""
            app.console_message = ""

    def handle_console_event(self, app: Any, event: pg.event.Event) -> None:
        """控制台输入事件处理。"""
        if event.type != pg.KEYDOWN:
            return
        if event.key == pg.K_ESCAPE:
            app.console_visible = False
            app.console_input = ""
        elif event.key in (pg.K_RETURN, pg.K_KP_ENTER):
            cmd = app.console_input.strip().lower()
            self.process_console_command(app, cmd)
            app.console_input = ""
            app.console_visible = False
        elif event.key == pg.K_BACKSPACE:
            app.console_input = app.console_input[:-1]
        else:
            ch = event.unicode
            if ch and ch.isprintable():
                app.console_input += ch

    def process_console_command(self, app: Any, cmd: str) -> None:
        """解析并执行控制台命令（cmd 已统一转为小写）。"""
        logger.info("控制台命令：%s", cmd)
        if cmd == "observe":
            self.enable_observe_mode(app)
        elif cmd.startswith("tag "):
            target = cmd[4:].strip()
            self.tag_command(app, target)
        else:
            app.console_message = f"未知命令: {cmd}"
            logger.info("未知控制台命令: %s", cmd)

    def enable_observe_mode(self, app: Any) -> None:
        """激活观察者模式：所有国家均由 AI 接管。"""
        if app.state != type(app.state).PLAYING:
            app.console_message = "请先进入游戏再使用 observe"
            return
        if app.human_country == "OBSERVE":
            app.console_message = "已处于观察者模式"
            return

        app.human_country = "OBSERVE"
        logger.info("已激活观察者模式，所有国家由 AI 接管")
        if app.player_country and not app.turn_game_finished and app._ai_turn_timer is None:
            app._ai_turn_timer = pg.time.get_ticks() + 600
        if app.info_panel:
            app.info_panel.show_message("已进入观察者模式：三国均由 AI 接管", duration=3.0)
        app.console_message = "观察者模式已激活"

    def tag_command(self, app: Any, target: str) -> None:
        """tag 指令：切换玩家控制国家（shu/wu/wei）。"""
        mapping = {"shu": "SHU", "wu": "WU", "wei": "WEI"}
        if target not in mapping:
            app.console_message = "用法: tag shu / tag wu / tag wei"
            return
        if app.state != type(app.state).PLAYING:
            app.console_message = "请先进入游戏再使用 tag"
            return

        new_country = mapping[target]
        label = app.country_labels.get(new_country, new_country)
        old_human = app.human_country
        app.human_country = new_country
        logger.info("控制台切换玩家国家: %s -> %s", old_human, new_country)

        if app.player_country == new_country:
            app._ai_turn_timer = None
            if app.info_panel:
                app.info_panel.show_message(
                    f"已切换：现在控制{label}（当前正是{label}回合）", duration=3.0
                )
        else:
            if app._ai_turn_timer is None and not app.turn_game_finished:
                app._ai_turn_timer = pg.time.get_ticks() + 600
            if app.info_panel:
                app.info_panel.show_message(f"已切换：现在控制{label}", duration=3.0)
        app.console_message = f"已切换至{label}"
