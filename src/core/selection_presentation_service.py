from __future__ import annotations


class SelectionPresentationService:
    """选中单位信息展示相关服务。"""

    def get_unit_abbr(self, unit_type: str) -> str:
        """获取单位类型的单字（或特殊）简称。"""
        if unit_type == "HUBAO_cavalry":
            return "虎豹"
        if unit_type == "WUDANG_archer":
            return "无当"
        if unit_type == "JIEFAN_infantry":
            return "解烦"

        if "infantry" in unit_type:
            return "步"
        if "cavalry" in unit_type:
            return "骑"
        if "archer" in unit_type:
            return "弓"
        return unit_type[0].upper()

    def format_unit_info(
        self,
        app,
        u_state,
        prefix: str = "",
        province_id: str | None = None,
    ) -> str:
        """通用单位信息格式化。"""
        u_def = app.unit_repository.get_definition(u_state.unit_type)
        u_abbr = self.get_unit_abbr(u_state.unit_type)

        status = []
        if u_state.is_injured:
            status.append("伤")
        if u_state.is_confused:
            status.append("乱")
        status_str = f"({''.join(status)})" if status else ""

        country = u_def.country
        color_hex = "#000000"
        if country:
            c = app.kingdom_repository.get_color(country)
            color_hex = f"#{c.r:02x}{c.g:02x}{c.b:02x}"

        abbr_part = f"|{color_hex}|{u_abbr}|#000000|"
        label = f"[{prefix}{abbr_part}{status_str}]"

        actual_atk, actual_dfs = app._calculate_unit_powers(u_state, province_id)

        attrs = [
            f"血{u_state.hp}",
            f"攻{actual_atk:.1f}",
            f"防{actual_dfs:.1f}",
            f"动{u_state.mp}/{u_def.move}",
            f"射{u_def.range}",
        ]
        return f"{label} {'·'.join(attrs)}"

    def update_selection_info(self, app) -> None:
        """更新信息面板显示的选中单位属性。"""
        if not app.selected_units:
            if app.info_panel:
                app.info_panel.show_properties("")
            return

        lines = []
        for pid, idx in app.selected_units:
            prov = app.map_manager.get_by_id(pid)
            if not prov:
                continue
            u_state = prov.units[idx]
            info_str = self.format_unit_info(app, u_state, province_id=prov.province_id)
            lines.append(info_str)

        if app.info_panel:
            app.info_panel.show_properties("\n".join(lines))
