from __future__ import annotations

from typing import Callable


class PlayingCommandService:
    """执行 PLAYING 状态下输入服务返回的命令列表。"""

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
                    right_click_context = (
                        app.playing_input_args_service.build_right_click_context(
                            app,
                            on_block_message=on_show_message,
                        )
                    )
                    app.playing_input_service.handle_right_click_with_context(
                        pos=payload,
                        context=right_click_context,
                    )
