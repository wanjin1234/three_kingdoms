from __future__ import annotations

from typing import Callable


class PlayingCommandService:
    """PLAYING 输入命令执行服务（阶段4：从 GameApp 抽离执行细节）。"""

    def execute(
        self,
        *,
        app,
        commands: list[dict],
        on_show_message: Callable[[str], None] | None,
    ) -> None:
        for command in commands:
            name = command.get("name")
            payload = command.get("payload")

            if name == "set_help_overlay_visible":
                app._set_help_overlay_visible(bool(payload))
            elif name == "reset_morale_modes":
                app._reset_morale_modes()
            elif name == "show_message":
                if on_show_message:
                    on_show_message(str(payload))
            elif name == "set_pp_summon_target_prov":
                app._set_pp_summon_target_prov(payload)
            elif name == "clear_pp_summon_btns":
                app._clear_pp_summon_btns()
            elif name == "set_pp_spend_mode":
                app._set_pp_spend_mode(bool(payload))
            elif name == "cancel_card_target_selection":
                app._cancel_card_target_selection()
            elif name == "clear_selection":
                app.clear_selection()
            elif name == "play_selected_card":
                app._play_selected_card()
            elif name == "handle_game_right_click":
                if payload is not None:
                    app._handle_game_right_click(payload)
