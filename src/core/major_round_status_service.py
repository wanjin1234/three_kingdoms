from __future__ import annotations

from src.core.app_contexts import (
    RefreshSessionSkillDisplayContext,
    RemoveMajorRoundContext,
)


class MajorRoundStatusService:
    """大回合事件展示记录维护服务。"""

    def remove_from_major_round_with_context(
        self,
        context: RemoveMajorRoundContext,
        card_name: str,
        country: str | None = None,
    ) -> None:
        targets = [country] if country else context.get_major_round_countries()
        for c in targets:
            context.filter_out_card_for_country(c, card_name)

    def refresh_session_skill_display_with_context(
        self,
        context: RefreshSessionSkillDisplayContext,
    ) -> None:
        for skill_name in ("隆中定计", "一身是胆", "星落秋风"):
            context.on_remove_from_major_round(skill_name, "SHU")

        lonzhong_skill = context.get_evt_lonzhong_skill()
        if lonzhong_skill > 0:
            context.append_major_round_record(
                "SHU",
                "隆中定计",
                f"蜀汉进攻东吴骰点+1（剩余 {lonzhong_skill} 次）",
            )
        yishen_skill = context.get_evt_yishen_skill()
        if yishen_skill > 0:
            context.append_major_round_record(
                "SHU",
                "一身是胆",
                f"被进攻低于1:1时自动触发（剩余 {yishen_skill} 次）",
            )
        if context.is_evt_xingluo_active():
            context.append_major_round_record(
                "SHU",
                "星落秋风",
                "下次抽到「隆中定计」时蜀汉额外+1政治点数",
            )
