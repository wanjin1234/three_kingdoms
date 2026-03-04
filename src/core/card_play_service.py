from __future__ import annotations

import logging

from src.game_objects.unit import UnitState


logger = logging.getLogger(__name__)
MAX_UNIT_STACK = 3


class CardPlayService:
    """锦囊卡选择、目标应用与取消流程服务。"""

    def play_selected_card(self, app) -> None:
        """打出选中的卡牌。"""
        if not app.card_panel or not app.card_manager:
            return

        selected_card_id = app.card_panel.get_selected_card()
        if not selected_card_id:
            app.info_panel.show_message("请先选择一张卡牌")
            return

        if app.card_manager.is_card_used(selected_card_id):
            app.info_panel.show_message("该卡牌已被使用")
            return

        card_def = app.card_repository.get_definition(selected_card_id)
        if not card_def:
            return

        if app.show_combat_ui and selected_card_id != "card_jiangdong_zhiti":
            app.info_panel.show_message("战斗进行中仅可使用江东止啼")
            return

        if selected_card_id == "card_jiangdong_zhiti":
            if not app.allow_jiangdong_selection:
                app.info_panel.show_message("江东止啼仅在魏国被进攻时可选择")
                return

            app.card_manager.use_card(selected_card_id)
            app.jingnang_applied.setdefault("WEI", []).append(
                (card_def.name, card_def.description or "")
            )
            app.defender_use_jiangdong = True
            app.defender_jiangdong_decided = True
            app.allow_jiangdong_selection = False
            app.info_panel.show_message("已使用江东止啼：本次进攻方骰点-2")

            if app.player_country and app.player_country in app.card_managers:
                app.card_manager = app.card_managers[app.player_country]
            app._update_card_panel()

            if (
                app.waiting_defender_response
                and app.defender_jiangdong_decided
                and app.defender_hold_decided
                and app.combat_callback
            ):
                app.waiting_defender_response = False
                app.combat_callback()
            return

        if card_def.category == "offensive":
            if selected_card_id in [
                "card_zhenjing_huaxia_shu",
                "card_huoshao_lianying",
            ]:
                if app.card_effect_manager.activate_offensive_card(selected_card_id):
                    app.card_manager.use_card(selected_card_id)
                    _jn_c = app.player_country or ""
                    app.jingnang_applied.setdefault(_jn_c, []).append(
                        (card_def.name, card_def.description or "")
                    )
                    app.info_panel.show_message(
                        f"已激活锦囊卡: {card_def.name}",
                        duration=2.0,
                    )
                    app._update_card_panel()
                    logger.info(
                        f"Offensive card activated: {card_def.name} (ID: {selected_card_id})"
                    )
                return

        needs_target = card_def.category in ["buff", "defensive", "summon"]

        if needs_target:
            app.selecting_card_target = True
            app.selected_card_for_effect = selected_card_id
            _desc = card_def.description or ""
            app.info_panel.show_message(
                f"【{card_def.name}】\n{_desc}\n请点击目标格子来应用",
                duration=-1,
            )
        else:
            self.apply_card_effect(app, selected_card_id, card_def)

    def apply_card_effect(self, app, card_id: str, card_def: object) -> None:
        """应用卡牌效果到指定目标后，完成消费与UI更新。"""
        app.card_manager.use_card(card_id)

        _jn_c = app.player_country or ""
        app.jingnang_applied.setdefault(_jn_c, []).append(
            (card_def.name, card_def.description or "")
        )

        app.info_panel.show_message(f"已使用锦囊卡: {card_def.name}", duration=2.0)
        app._update_card_panel()
        logger.info(f"Card played: {card_def.name} (ID: {card_id})")

    def apply_card_to_province(self, app, card_id: str, province_id: str) -> bool:
        """将卡牌效果应用到指定的格子。"""
        card_def = app.card_repository.get_definition(card_id)
        if not card_def:
            return False

        target_prov = app.map_manager.get_by_id(province_id)
        if not target_prov:
            app.info_panel.show_message("无效的目标格子")
            return False

        if app.card_manager.is_card_used(card_id):
            app.info_panel.show_message("该卡牌已被使用")
            return False

        if target_prov.country != app.player_country:
            app.info_panel.show_message("目标必须是己方格子")
            return False

        if card_id == "card_zhenjing_huaxia_shu":
            app.info_panel.show_message("威震华夏只能按 Enter 全局激活")
            return False

        if card_id == "card_jiangdong_zhiti":
            app.info_panel.show_message("江东止啼无需指定格子，仅在魏国被进攻时可在卡牌面板选择")
            return False

        if card_id in ("card_qilin_qishu", "card_guanmu_xiangkan"):
            if len(target_prov.units) >= MAX_UNIT_STACK:
                app.info_panel.show_message("超过堆叠数量，请重新选择格子")
                return False

        if card_id == "card_qilin_qishu" and target_prov.country != "SHU":
            app.info_panel.show_message("七擒七纵只能部署在蜀国格子")
            return False
        if card_id == "card_guanmu_xiangkan" and target_prov.country != "WU":
            app.info_panel.show_message("刮目相看只能部署在吴国格子")
            return False

        success = app.card_effect_manager.apply_card_effect(
            card_id,
            card_def.name,
            str(province_id),
            app.player_country,
        )

        if success:
            if card_id == "card_baiyue_dujiang":
                for u in target_prov.units:
                    u.temp_river_immunity = True
                    u.temp_dice_bonus = max(u.temp_dice_bonus, 1)

            if card_id == "card_touduo_yinping":
                for u in target_prov.units:
                    u.mp += 2
                    u.temp_terrain_immunity = True

            if card_id == "card_gexu_qibao":
                app.gexu_guard_active = True
                app.info_panel.show_message(
                    "割须弃袍已激活：本小回合内魏方防御最高单位受伤时免除一次伤害",
                    duration=2.5,
                )

            if card_id in (
                "card_baiyue_dujiang",
                "card_touduo_yinping",
                "card_kongcheng_mouce",
            ):
                _jn_c = app.player_country or ""
                app.jingnang_applied_major.setdefault(_jn_c, []).append(
                    (card_def.name, card_def.description or "")
                )

            if card_id == "card_qilin_qishu":
                try:
                    unit_def = app.unit_repository.get_definition("WUDANG_archer")
                    new_unit = UnitState("WUDANG_archer")
                    new_unit.mp = unit_def.move
                    target_prov.units.append(new_unit)
                    app.map_manager.invalidate_cache()
                    app.info_panel.show_message(f"在{target_prov.name}召唤了无当飞军", duration=2.0)
                except Exception:
                    logger.exception("召唤 无当飞军 失败")

            if card_id == "card_guanmu_xiangkan":
                try:
                    unit_def = app.unit_repository.get_definition("JIEFAN_infantry")
                    new_unit = UnitState("JIEFAN_infantry")
                    new_unit.mp = unit_def.move
                    target_prov.units.append(new_unit)
                    app.map_manager.invalidate_cache()
                    app.info_panel.show_message(f"在{target_prov.name}召唤了解烦兵", duration=2.0)
                except Exception:
                    logger.exception("召唤 解烦兵 失败")

            self.apply_card_effect(app, card_id, card_def)
            return True

        app.info_panel.show_message("无法应用卡牌效果")
        return False

    def cancel_card_target_selection(self, app) -> None:
        """取消卡牌目标选择。"""
        app.selecting_card_target = False
        app.selected_card_for_effect = None
        app.info_panel.show_message("已取消卡牌选择")
