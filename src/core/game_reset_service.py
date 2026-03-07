from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class GameResetService:
    """对局重置服务，负责将游戏状态恢复到新对局的初始状态。"""

    def restart_game(
        self,
        app,
        *,
        map_manager_cls,
        card_manager_cls,
        event_card_deck_cls,
        game_state,
        yangtze_points_1,
        yangtze_points_2,
        yellow_river_points,
        ban_line_points,
    ) -> None:
        app.map_manager = map_manager_cls(
            definition_file=app.settings.map_definition_file,
            terrain_graphics_dir=app.settings.map_graphics_dir,
            color_resolver=app.kingdom_repository.get_color,
            river_polylines=(
                yangtze_points_1,
                yangtze_points_2,
                yellow_river_points,
            ),
            ban_polylines=(ban_line_points,),
        )
        app.map_manager.set_hex_side(app.hex_side)

        app._replenish_action_points()

        app.clear_selection()
        app.show_combat_ui = False
        app.combat_result_title = None
        if app.info_panel:
            app.info_panel.show_properties("")

        app.card_managers = {
            country: card_manager_cls(app.card_repository, country)
            for country in app.turn_order
        }
        app.card_manager = None
        app.card_effect_manager.clear_all_effects()
        app.selecting_card_target = False
        app.selected_card_for_effect = None
        if app.card_panel:
            app.card_panel.set_available_cards([])

        app.pending_post_move_attack = False
        app.pending_attacker = None

        app.player_country = None
        app.human_country = None
        app.turn_index = 0
        app.major_round = 1
        app.minor_round = 1
        app.turn_game_finished = False
        app.country_stats = app.turn_service.create_country_stats()

        from settings import SETTINGS as settings_module

        app.event_card_deck = event_card_deck_cls(settings_module.event_cards_file)
        app.event_card_overlay = None
        app.evt_overlay_ok_btn = None
        app.selecting_evt_target = False
        app.pending_evt_card_id = None
        app.pending_evt_drawer = None
        app.evt_flag_liukang = False
        app.evt_flag_liukang_drawer = ""
        app.evt_flag_she_hushu = False
        app.evt_flag_hu_recruit = False
        app.evt_flag_wuwei = False
        app.evt_flag_wuwei_drawer = ""
        app.evt_temp_pp = {}
        app.evt_flag_hefei = False
        app.evt_flag_all_attack = False
        app.evt_all_attack_drawer = ""
        app.gexu_guard_active = False
        app.jingnang_applied = {}
        app.evt_applied_this_round = {}
        app.evt_applied_major_round = {}
        app.jingnang_applied_major = {}
        app.evt_wuzi_rounds = 0
        app.evt_wuzi_bonus = 0
        app.evt_xingluo_active = False
        app.evt_laomaikuai_active = False
        app.evt_lonzhong_skill = 0
        app.evt_jingzhu_skill = 0
        app.evt_yishen_skill = 0
        app.evt_draw_again_safe = False
        app.evt_draw_phase = False
        app.evt_skip_draw_btn_rect = None

        app.morale_lv2_used = {}
        app.morale_lv3_used = {}
        app.morale_lv4_pending = {}
        app.morale_free_move_mode = False
        app.morale_bonus_mp_mode = False
        app.morale_cure_mode = False

        app.pp_spend_mode = False
        app.pp_summon_target_prov = None
        app.pp_summon_btns = []

        app.state = game_state.MODE_SELECT
        if app.music_manager:
            app.music_manager.play_menu()
        logger.info("Game restarted.")
