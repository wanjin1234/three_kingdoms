from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TurnState:
    """回合状态视图（代理到 GameApp 字段，保持行为等价）。"""

    app: Any

    @property
    def player_country(self):
        return self.app.player_country

    @player_country.setter
    def player_country(self, value):
        self.app.player_country = value

    @property
    def human_country(self):
        return self.app.human_country

    @human_country.setter
    def human_country(self, value):
        self.app.human_country = value

    @property
    def turn_order(self):
        return self.app.turn_order

    @property
    def turn_index(self):
        return self.app.turn_index

    @turn_index.setter
    def turn_index(self, value):
        self.app.turn_index = value

    @property
    def major_round(self):
        return self.app.major_round

    @major_round.setter
    def major_round(self, value):
        self.app.major_round = value

    @property
    def minor_round(self):
        return self.app.minor_round

    @minor_round.setter
    def minor_round(self, value):
        self.app.minor_round = value

    @property
    def turn_game_finished(self):
        return self.app.turn_game_finished

    @turn_game_finished.setter
    def turn_game_finished(self, value):
        self.app.turn_game_finished = value

    @property
    def country_stats(self):
        return self.app.country_stats

    @country_stats.setter
    def country_stats(self, value):
        self.app.country_stats = value

    @property
    def major_round_choice_pending(self):
        return self.app.major_round_choice_pending

    @major_round_choice_pending.setter
    def major_round_choice_pending(self, value):
        self.app.major_round_choice_pending = value

    @property
    def major_round_choice_done(self):
        return self.app.major_round_choice_done


@dataclass
class UIState:
    """界面状态视图（代理到 GameApp 字段）。"""

    app: Any

    @property
    def selected_units(self):
        return self.app.selected_units

    @selected_units.setter
    def selected_units(self, value):
        self.app.selected_units = value

    @property
    def country_stat_choice_btns(self):
        return self.app.country_stat_choice_btns

    @property
    def evt_info_btns(self):
        return self.app.evt_info_btns

    @property
    def help_overlay_visible(self):
        return self.app.help_overlay_visible

    @help_overlay_visible.setter
    def help_overlay_visible(self, value):
        self.app.help_overlay_visible = value

    @property
    def volume_slider_visible(self):
        return self.app.volume_slider_visible

    @volume_slider_visible.setter
    def volume_slider_visible(self, value):
        self.app.volume_slider_visible = value

    @property
    def volume_level(self):
        return self.app.volume_level

    @volume_level.setter
    def volume_level(self, value):
        self.app.volume_level = value

    @property
    def pp_summon_btns(self):
        return self.app.pp_summon_btns


@dataclass
class CombatState:
    """战斗状态视图（代理到 GameApp 字段）。"""

    app: Any

    @property
    def show_combat_ui(self):
        return self.app.show_combat_ui

    @show_combat_ui.setter
    def show_combat_ui(self, value):
        self.app.show_combat_ui = value

    @property
    def combat_target(self):
        return self.app.combat_target

    @combat_target.setter
    def combat_target(self, value):
        self.app.combat_target = value

    @property
    def combat_ratio_val(self):
        return self.app.combat_ratio_val

    @combat_ratio_val.setter
    def combat_ratio_val(self, value):
        self.app.combat_ratio_val = value

    @property
    def waiting_defender_response(self):
        return self.app.waiting_defender_response

    @waiting_defender_response.setter
    def waiting_defender_response(self, value):
        self.app.waiting_defender_response = value

    @property
    def combat_result_title(self):
        return self.app.combat_result_title

    @combat_result_title.setter
    def combat_result_title(self, value):
        self.app.combat_result_title = value

    @property
    def combat_result_timer(self):
        return self.app.combat_result_timer

    @combat_result_timer.setter
    def combat_result_timer(self, value):
        self.app.combat_result_timer = value


@dataclass
class EventCardState:
    """事件卡状态视图（代理到 GameApp 字段）。"""

    app: Any

    @property
    def event_card_overlay(self):
        return self.app.event_card_overlay

    @event_card_overlay.setter
    def event_card_overlay(self, value):
        self.app.event_card_overlay = value

    @property
    def selecting_evt_target(self):
        return self.app.selecting_evt_target

    @selecting_evt_target.setter
    def selecting_evt_target(self, value):
        self.app.selecting_evt_target = value

    @property
    def pending_evt_card_id(self):
        return self.app.pending_evt_card_id

    @pending_evt_card_id.setter
    def pending_evt_card_id(self, value):
        self.app.pending_evt_card_id = value

    @property
    def pending_evt_drawer(self):
        return self.app.pending_evt_drawer

    @pending_evt_drawer.setter
    def pending_evt_drawer(self, value):
        self.app.pending_evt_drawer = value

    @property
    def evt_temp_pp(self):
        return self.app.evt_temp_pp

    @evt_temp_pp.setter
    def evt_temp_pp(self, value):
        self.app.evt_temp_pp = value

    @property
    def evt_draw_phase(self):
        return self.app.evt_draw_phase

    @evt_draw_phase.setter
    def evt_draw_phase(self, value):
        self.app.evt_draw_phase = value

    @property
    def evt_applied_this_round(self):
        return self.app.evt_applied_this_round

    @property
    def evt_applied_major_round(self):
        return self.app.evt_applied_major_round

    @property
    def jingnang_applied(self):
        return self.app.jingnang_applied

    @property
    def jingnang_applied_major(self):
        return self.app.jingnang_applied_major
