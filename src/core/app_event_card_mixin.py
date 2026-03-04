from __future__ import annotations

import pygame as pg

from src.core import app_context_factory


class AppEventCardMixin:
    """GameApp 事件卡相关委托与上下文入口。"""

    def _can_draw_event_card(self, country: str) -> bool:
        return self.event_card_service.can_draw_event_card(self, country)

    def _spend_pp(self, country: str, amount: int = 1) -> bool:
        return self.event_card_service.spend_pp(self, country, amount)

    def _trigger_draw_event_card(self, country: str) -> None:
        self.event_card_service.trigger_draw_event_card(self, country)

    def _is_negative_event(self, card, country: str) -> bool:
        return self.event_card_service.is_negative_event(self, card, country)

    def _confirm_event_card(self) -> None:
        self.event_card_service.confirm_event_card_with_context(
            self._build_event_confirm_context()
        )

    def _apply_event_card(self, card, drawer: str) -> None:
        self.event_card_service.apply_event_card(self, card, drawer)

    def _apply_evt_target_unit(self, prov_id: int, slot: int) -> None:
        self.event_card_service.apply_evt_target_unit_with_context(
            self._build_event_target_apply_context(),
            prov_id,
            slot,
        )

    def _apply_evt_target_province(self, prov_id: int) -> None:
        self.event_card_service.apply_evt_target_province_with_context(
            self._build_event_target_apply_context(),
            prov_id,
        )

    def _get_event_card_image(self, card_name: str) -> "pg.Surface | None":
        return self.event_card_service.get_event_card_image(self, card_name)

    def _render_event_card_overlay(self) -> None:
        self.event_card_service.render_event_card_overlay(self)

    def _enter_evt_draw_phase_if_needed(self) -> None:
        self.event_card_service.enter_evt_draw_phase_if_needed_with_context(
            self._build_event_draw_phase_context()
        )

    def _exit_evt_draw_phase(self) -> None:
        self.event_card_service.exit_evt_draw_phase_with_context(
            self._build_event_draw_phase_context()
        )

    def _check_evt_draw_phase_pp(self) -> None:
        self.event_card_service.check_evt_draw_phase_pp_with_context(
            self._build_event_draw_phase_context()
        )

    def _build_event_confirm_context(self):
        return app_context_factory.build_event_confirm_context(self)

    def _build_event_target_apply_context(self):
        return app_context_factory.build_event_target_apply_context(self)

    def _build_event_draw_phase_context(self):
        return app_context_factory.build_event_draw_phase_context(self)

    def _render_draw_event_btn(self) -> None:
        self.event_card_service.render_draw_event_btn(self)
