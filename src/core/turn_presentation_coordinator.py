"""
回合展示协调器：抽离 `GameApp` 回合切换后的 UI/消息与调度逻辑。

该模块不包含规则计算，只负责界面相关状态分发。
"""

from __future__ import annotations

from typing import Any

import pygame as pg


class TurnPresentationCoordinator:
    """回合展示与调度协调器。"""

    def handle_game_finished(self, app: Any) -> None:
        """处理对局结束时的 UI 与消息分发。"""
        app.turn_game_finished = True
        app.player_country = None
        app.card_manager = None

        if app.card_panel:
            app.card_panel.set_available_cards([])
        if app.info_panel:
            app.info_panel.show_message("对局结束：已完成5个大回合（每回合6个小回合）")

        app._show_score_screen("game_over")

    def on_country_activated(self, app: Any) -> None:
        """处理切换到新行动国后的 UI 与调度逻辑。"""
        app.card_manager = app.card_managers[app.player_country]
        app._update_card_panel()

        # 进入事件卡抽取阶段（若为人类玩家且有政治点数）
        app._enter_evt_draw_phase_if_needed()

        # 若当前轮到的是 AI 国家，延迟触发 AI 行动
        if (
            app.human_country is not None
            and app.player_country != app.human_country
            and not app.turn_game_finished
        ):
            # 判断上一个行动的国家：若上家是人类玩家，则为"第一台电脑"（等1秒）；
            # 若上家也是 AI，则为"第二台电脑"（等2秒，给玩家更多时间阅读上一台电脑的行动结果）
            turn_order = list(app.turn_order)
            prev_idx = (app.turn_index - 1) % len(turn_order)
            prev_country = turn_order[prev_idx]
            if prev_country == app.human_country:
                delay_ms = 1000   # 人类刚操作完，第一台电脑等1秒
            else:
                delay_ms = 2000   # 第一台电脑操作完，第二台电脑等2秒
            app._ai_turn_timer = pg.time.get_ticks() + delay_ms
        else:
            app._ai_turn_timer = None
