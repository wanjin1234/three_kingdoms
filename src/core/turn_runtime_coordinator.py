"""
回合运行时协调器：抽离 `GameApp` 中与回合切换相关的状态清理和重置副作用。

该模块不处理渲染，仅协调状态字段与回调调用。
"""

from __future__ import annotations

from typing import Any


class TurnRuntimeCoordinator:
    """回合运行时副作用协调器。"""

    def prepare_turn_switch(self, app: Any, *, keep_info_message: bool = False) -> None:
        """在推进到下个国家前，先清理本国动作态与临时标记。"""
        app.pending_post_move_attack = False
        app.pending_attacker = None
        app.selecting_card_target = False
        app.selected_card_for_effect = None
        # 注意：evt_flag_liukang/wuwei/all_attack 为"持续到抽取者下次回合"效果，
        # 不在此处统一清除，而是在抽取方下次回合开始时清除
        app.evt_temp_pp = {}
        app.evt_applied_this_round = {}
        app.evt_ai_drawn_this_turn = {}
        app.selecting_evt_target = False
        app.pending_evt_card_id = None
        app.pending_evt_drawer = None

        # 五子良将递减计数
        if app.evt_wuzi_rounds > 0:
            app.evt_wuzi_rounds -= 1
            if app.evt_wuzi_rounds == 0:
                app.evt_wuzi_bonus = 0

        app._clear_for_turn_switch(keep_info_message=keep_info_message)

    def apply_major_round_rollover(self, app: Any) -> None:
        """小回合满后进入下一大回合时执行的集中清理逻辑。"""
        # 大回合结束：民心4级效果（军容严整）各国可解除一个混乱单位
        for country in list(app.turn_order):
            support_lv = app.turn_resource_service.get_people_support_level(
                app.turn_state.country_stats,
                country,
            )
            if support_lv >= 4:
                if country == app.human_country:
                    app.morale_lv4_pending[country] = True
                else:
                    app.turn_resource_service.ai_cure_confused_unit(
                        app.map_manager.provinces,
                        country,
                    )

        # 重置单位大回合临时属性
        for province in app.map_manager.provinces:
            for unit in province.units:
                unit.major_mp_bonus = 0
                unit.temp_river_immunity = False
                unit.temp_terrain_immunity = False
                unit.temp_dice_bonus = 0

        # 重置大回合级事件标记
        app.evt_flag_hefei = False
        app.evt_flag_she_hushu = False
        app.evt_flag_hu_recruit = False
        app.evt_jingzhu_skill = 0
        app.evt_laomaikuai_active = False

        # 大回合显示记录清除后重建会话级技能显示
        app.evt_applied_major_round = {}
        app.jingnang_applied_major = {}
        app._refresh_session_skill_display()

        # 大回合级格子效果清除并进入下个大回合加点阶段
        app.card_effect_manager.clear_all_effects()
        app._end_full_round()
        app._start_major_round_choice_phase()

    def on_country_turn_start(self, app: Any, *, new_country: str) -> None:
        """国家开始自己回合时，清除该国延迟到本轮才失效的标记。"""
        if app.evt_flag_liukang_drawer and new_country == app.evt_flag_liukang_drawer:
            app.evt_flag_liukang = False
            app.evt_flag_liukang_drawer = ""
            app._remove_from_major_round("联刘抗曹")

        if app.evt_flag_wuwei_drawer and new_country == app.evt_flag_wuwei_drawer:
            app.evt_flag_wuwei = False
            app.evt_flag_wuwei_drawer = ""
            app._remove_from_major_round("吴魏媾和")

        if new_country == "WEI":
            # 割须弃袍兜底：若战斗后未消耗，魏国下次回合开始时清除
            app.gexu_guard_active = False

        if app.evt_all_attack_drawer and new_country == app.evt_all_attack_drawer:
            app.evt_flag_all_attack = False
            app.evt_all_attack_drawer = ""
            app._remove_from_major_round("奖率三军")

        # 仅清除该国上一轮遗留的移动高亮
        app.move_src_provs = {k: v for k, v in app.move_src_provs.items() if v != new_country}
        app.move_dst_provs = {k: v for k, v in app.move_dst_provs.items() if v != new_country}
        app.move_src_slots = {
            k: v for k, v in app.move_src_slots.items() if k in app.move_src_provs
        }
        app.move_dst_slots = {
            k: v for k, v in app.move_dst_slots.items() if k in app.move_dst_provs
        }
