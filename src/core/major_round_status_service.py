from __future__ import annotations


class MajorRoundStatusService:
    """大回合事件展示记录维护服务。"""

    def remove_from_major_round(self, app, card_name: str, country: str | None = None) -> None:
        targets = [country] if country else list(app.evt_applied_major_round.keys())
        for c in targets:
            if c in app.evt_applied_major_round:
                app.evt_applied_major_round[c] = [
                    (n, d) for n, d in app.evt_applied_major_round[c] if n != card_name
                ]

    def refresh_session_skill_display(self, app) -> None:
        for skill_name in ("隆中定计", "一身是胆", "星落秋风"):
            self.remove_from_major_round(app, skill_name, "SHU")

        if app.evt_lonzhong_skill > 0:
            app.evt_applied_major_round.setdefault("SHU", []).append(
                ("隆中定计", f"蜀汉进攻东吴骰点+1（剩余 {app.evt_lonzhong_skill} 次）")
            )
        if app.evt_yishen_skill > 0:
            app.evt_applied_major_round.setdefault("SHU", []).append(
                (
                    "一身是胆",
                    f"被进攻低于1:1时自动触发（剩余 {app.evt_yishen_skill} 次）",
                )
            )
        if app.evt_xingluo_active:
            app.evt_applied_major_round.setdefault("SHU", []).append(
                ("星落秋风", "下次抽到「隆中定计」时蜀汉额外+1政治点数")
            )
