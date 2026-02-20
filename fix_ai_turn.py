with open("src/core/app.py", encoding="utf-8") as f:
    content = f.read()

# Locate start and end of _run_ai_turn
start_marker = '    def _run_ai_turn(self) -> None:\n        """AI \u884c\u52a8\uff1a\u81ea\u52a8\u5b8c\u6210\u5927\u56de\u5408\u52a0\u70b9\u9009\u62e9 + \u79fb\u52a8/\u653b\u51fb\uff0c\u7136\u540e\u7ed3\u675f\u672c\u56fd\u56de\u5408\u3002'
end_marker = "    def _ai_pick_attack_target(self, province, unit_state):"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx)
if start_idx == -1 or end_idx == -1:
    print(f"ERROR: markers not found (start={start_idx}, end={end_idx})")
    exit(1)

print(f"Replacing _run_ai_turn, block_len={end_idx - start_idx}")

new_method = '''    def _run_ai_turn(self) -> None:
        """AI \u884c\u52a8\uff1a\u81ea\u52a8\u5b8c\u6210\u5927\u56de\u5408\u52a0\u70b9\u9009\u62e9 + \u79fb\u52a8/\u653b\u51fb\uff0c\u7136\u540e\u7ed3\u675f\u672c\u56fd\u56de\u5408\u3002
        \u7b56\u7565\uff1a\u5148\u5c06\u6240\u6709\u5185\u9646\u90e8\u961f\u6574\u7701\u8c03\u5f80\u8fb9\u5883\uff0c\u5168\u90e8\u5230\u4f4d\u540e\u518d\u53d1\u52a8\u8fdb\u653b\u3002
        \u540c\u65f6\u4f1a\u62bd\u53d6\u4e8b\u4ef6\u5361\u3001\u4f7f\u7528\u9526\u56ca\u5361\u3001\u62db\u52df\u90e8\u961f\u3001\u89e3\u9664\u6df7\u4e71\u3002"""
        if self.turn_game_finished:
            return
        country = self.player_country
        if country is None or country == self.human_country:
            return

        # --- \u6c11\u5fc3\u7b49\u7ea7\u6548\u679c\uff08AI\u81ea\u52a8\u5904\u7406\uff09---
        _ai_support = self._get_people_support_level(country)

        # \u6c11\u5fc32\u7ea7\uff08\u4ee4\u884c\u7981\u6b62\uff09\uff1a\u6bcf\u5927\u56de\u5408\u514d\u8d39\u79fb\u52a81\u683c
        if (
            _ai_support >= 2
            and self.morale_lv2_used.get(country, 0) != self.major_round
        ):
            border_provs_lv2 = self._ai_get_border_provinces(country)
            for _bp in border_provs_lv2:
                if not _bp.units:
                    continue
                _dest = self._ai_pick_move_target(_bp, _bp.units[0], border_provs_lv2)
                if (
                    _dest
                    and self.map_manager.find_path_cost(
                        _bp.province_id, _dest.province_id
                    )
                    == 1
                ):
                    self.morale_free_move_mode = True
                    self.selected_units = [(_bp.province_id, 0)]
                    self._handle_movement(_dest)
                    break
            self.morale_lv2_used[country] = self.major_round
            self.morale_free_move_mode = False

        # \u6c11\u5fc33\u7ea7\uff08\u8001\u4e61\u6307\u8def\uff09\uff1a\u6bcf\u5927\u56de\u5408\u7ed9\u4e00\u4e2a\u8fb9\u5883\u5355\u4f4d+1\u884c\u52a8\u529b
        if (
            _ai_support >= 3
            and self.morale_lv3_used.get(country, 0) != self.major_round
        ):
            _border_p3 = self._ai_get_border_provinces(country)
            for _bp3 in _border_p3:
                if _bp3.units:
                    _bp3.units[0].mp += 1
                    self.morale_lv3_used[country] = self.major_round
                    break
            else:
                self.morale_lv3_used[country] = self.major_round

        # \u6c11\u5fc34\u7ea7\uff08\u519b\u5bb9\u4e25\u6574\uff09\uff1a\u5927\u56de\u5408\u7ed3\u675f\u65f6\u89e3\u9664\u6df7\u4e71 - \u5728 _advance_country_turn \u4e2d\u5904\u7406

        # --- \u9636\u63690\uff1a\u5904\u7406\u4e8b\u4ef6\u5361\u76ee\u6807\u9009\u62e9\uff08needs_target \u7c7b\u5361\u724c\u7684 AI \u81ea\u52a8\u9009\u62e9\uff09 ---
        if self.selecting_evt_target and self.pending_evt_card_id:
            card_def = self.event_card_deck.get_definition(self.pending_evt_card_id)
            if card_def:
                if card_def.target_type == "unit":
                    chosen_prov = None
                    chosen_slot = 0
                    border_provs = self._ai_get_border_provinces(country)
                    border_ids = {p.province_id for p in border_provs}
                    for prov in self.map_manager.provinces:
                        if prov.country == country and prov.units:
                            if prov.province_id in border_ids:
                                chosen_prov = prov
                                break
                    if chosen_prov is None:
                        for prov in self.map_manager.provinces:
                            if prov.country == country and prov.units:
                                chosen_prov = prov
                                break
                    if chosen_prov:
                        self._apply_evt_target_unit(
                            chosen_prov.province_id, chosen_slot
                        )
                    else:
                        self.selecting_evt_target = False
                        self.pending_evt_card_id = None
                        self.pending_evt_drawer = None
                        self._check_evt_draw_phase_pp()
                elif card_def.target_type == "province":
                    chosen_prov = max(
                        (
                            p
                            for p in self.map_manager.provinces
                            if p.country == country and p.units
                        ),
                        key=lambda p: len(p.units),
                        default=None,
                    )
                    if chosen_prov:
                        self._apply_evt_target_province(chosen_prov.province_id)
                    else:
                        self.selecting_evt_target = False
                        self.pending_evt_card_id = None
                        self.pending_evt_drawer = None
                        self._check_evt_draw_phase_pp()
            else:
                # \u627e\u4e0d\u5230\u5361\u5b9a\u4e49\uff0c\u6e05\u9664
                self.selecting_evt_target = False
                self.pending_evt_card_id = None
                self.pending_evt_drawer = None
            # \u76ee\u6807\u9009\u62e9\u5b8c\u6bd5\uff0c\u672c\u5e27 AI \u884c\u52a8\u7ed3\u675f\uff0c\u7b49\u5f85\u4e0b\u4e00\u5e27\u6b63\u5e38\u884c\u52a8
            return

        # --- \u9636\u63691\uff1a\u5927\u56de\u5408\u52a0\u70b9\uff08\u5982\u679c\u8fd8\u672a\u9009\u62e9\uff09 ---
        if self.major_round_choice_pending:
            for c in list(self.turn_order):
                # \u53ea\u4ee3\u66ff AI \u56fd\u5bb6\u81ea\u52a8\u9009\u62e9\uff0c\u73a9\u5bb6\u56fd\u5bb6\u5fc5\u987b\u7b49\u73a9\u5bb6\u624b\u52a8\u70b9\u51fb
                if c == self.human_country:
                    continue
                if not self.major_round_choice_done.get(c, False):
                    # \u667a\u80fd\u9009\u62e9\uff1aPP\u4e3a0\u65f6\u52a0\u653f\u6cbb\u70b9\u6570\u589e\u52a0\u62bd\u5361\u673a\u4f1a\uff0c\u5426\u5219\u52a0\u6c11\u5fc3
                    _ai_pp_now = self._get_total_pp(c)
                    _choice = "politics" if _ai_pp_now == 0 else "support"
                    self._apply_major_round_choice(c, _choice)
            # \u82e5\u73a9\u5bb6\u8fd8\u672a\u9009\u62e9\uff0c\u7b49\u5f85\u73a9\u5bb6\u64cd\u4f5c\uff0c\u6682\u4e0d\u7ee7\u7eed AI \u884c\u52a8
            if self.major_round_choice_pending:
                self._ai_turn_timer = pg.time.get_ticks() + 300
                return

        # --- \u9636\u63691.5\uff1a\u4e8b\u4ef6\u5361\u62bd\u53d6\uff08AI \u4e3b\u52a8\u6d88\u8017 PP \u62bd\u5361\uff0c\u6700\u591a3\u6b21\uff09 ---
        _evt_loop = 0
        while _evt_loop < 3 and self._can_draw_event_card(country):
            _evt_loop += 1
            self._trigger_draw_event_card(country)
            # \u81ea\u52a8\u786e\u8ba4\u4e8b\u4ef6\u5361\u8986\u76d6\u5c42
            if self.event_card_overlay:
                _overlay_drawer = self.event_card_overlay.get("drawer", country)
                if _overlay_drawer != self.human_country:
                    self._confirm_event_card()
            # \u82e5\u89e6\u53d1\u4e86\u9700\u8981\u76ee\u6807\u9009\u62e9\uff0c\u7acb\u5373\u5904\u7406
            if self.selecting_evt_target and self.pending_evt_card_id:
                self._ai_auto_select_evt_target(country)
            # \u82e5\u4ecd\u6709\u8986\u76d6\u5c42\u6216\u76ee\u6807\u9009\u62e9\uff0c\u4e0b\u4e00\u5e27\u7ee7\u7eed
            if self.event_card_overlay or self.selecting_evt_target:
                self._ai_turn_timer = pg.time.get_ticks() + 200
                return

        # \u2015\u2015 \u9884\u8ba1\u7b97\u8fb9\u5883\u7701\u96c6\u5408 \u2015\u2015
        border_provs = self._ai_get_border_provinces(country)
        border_ids = {p.province_id for p in border_provs}

        # \u6536\u96c6\u6240\u6709\u5df1\u65b9\u6709\u884c\u52a8\u529b\u7684\u5355\u4f4d\uff0c\u6309\u7701\u5206\u7ec4
        # inland_by_prov: { province_id: (province, [(slot_idx, unit_state), ...]) }
        # border_by_prov: same structure
        inland_by_prov: dict = {}
        border_by_prov: dict = {}

        for province in self.map_manager.provinces:
            if province.country != country:
                continue
            for slot_idx, unit_state in enumerate(province.units):
                if unit_state.mp <= 0:
                    continue
                key = province.province_id
                if key in border_ids:
                    if key not in border_by_prov:
                        border_by_prov[key] = (province, [])
                    border_by_prov[key][1].append((slot_idx, unit_state))
                else:
                    if key not in inland_by_prov:
                        inland_by_prov[key] = (province, [])
                    inland_by_prov[key][1].append((slot_idx, unit_state))

        # \u5e73\u94fa\u7684\u8fb9\u5883\u5355\u4f4d\u5217\u8868\uff08\u4f9b\u653b\u51fb\u903b\u8f91\u4f7f\u7528\uff09
        border_units = [
            (prov, slot_idx, unit_state)
            for prov, slots in border_by_prov.values()
            for slot_idx, unit_state in slots
        ]

        action_taken = False

        # \u8ba1\u7b97\u672c\u56fd\u7684\u4e3b\u8981\u5a01\u80c1\u65b9
        _main_threat = self._ai_get_main_threat_country(country)

        def _border_threat_key(item):
            """\u4f18\u5148\u9009\u4e0e\u4e3b\u5a01\u80c1\u56fd\u76f8\u90bb\u7684\u8fb9\u5883\u7701"""
            prov, _, _ = item
            p_c = prov.center_cache or prov.compute_center(self.hex_side)
            unit_stride = SQRT3 * self.hex_side
            for ep in self.map_manager.provinces:
                if ep.country == _main_threat:
                    ec = ep.center_cache or ep.compute_center(self.hex_side)
                    if dist(p_c, ec) <= unit_stride * 1.1:
                        return 0
            return 1

        border_units.sort(key=_border_threat_key)

        # \u2015\u2015 \u8f85\u52a9\uff1a\u8ba1\u7b97\u7701\u5230\u76ee\u6807\u7684\u8def\u5f84\u4ee3\u4ef7 \u2015\u2015
        def _calc_path_cost(src_prov, tgt_prov, lead_unit):
            src_eff = self.card_effect_manager.get_effect(str(src_prov.province_id))
            ign = bool(getattr(lead_unit, "temp_terrain_immunity", False))
            if src_eff and src_eff.terrain_immunity:
                ign = True
            if ign:
                return self._find_path_cost_ignore_mountain(
                    src_prov.province_id, tgt_prov.province_id
                )
            return self.map_manager.find_path_cost(
                src_prov.province_id, tgt_prov.province_id
            )

        # --- \u9636\u63692\uff1a\u5185\u9646\u5355\u4f4d\u6574\u7701\u5411\u8fb9\u5883\u7ebf\u79fb\u52a8 ---
        if inland_by_prov:
            def _inland_prov_priority(item):
                province, _ = item
                p_c = province.center_cache or province.compute_center(self.hex_side)
                if not border_provs:
                    return float("inf")
                return min(
                    dist(p_c, bp.center_cache or bp.compute_center(self.hex_side))
                    for bp in border_provs
                )

            sorted_inland = sorted(inland_by_prov.values(), key=_inland_prov_priority)

            for province, slots in sorted_inland:
                lead_unit = slots[0][1]
                dest = self._ai_pick_move_target(province, lead_unit, border_provs)
                if dest is None:
                    continue
                pc = _calc_path_cost(province, dest, lead_unit)
                if pc > 100:
                    continue
                # \u53ea\u9009\u884c\u52a8\u529b\u8db3\u591f\u7684\u5355\u4f4d\uff0c\u6574\u7701\u4e00\u6b21\u79fb\u52a8
                valid_slots = [(idx, u) for idx, u in slots if u.mp >= pc]
                if not valid_slots:
                    continue
                self.selected_units = [(province.province_id, idx) for idx, _ in valid_slots]
                self._handle_movement(dest)
                if self.player_country != country:
                    return  # \u79fb\u52a8\u6210\u529f\uff0c\u56de\u5408\u5df2\u63a8\u8fdb

        # --- \u9636\u63692.5\uff1a\u8fdb\u653b\u524d\u6fc0\u6d3b\u8fdb\u653b\u9526\u56ca\u5361 ---
        _cm = self.card_managers.get(country)
        if _cm:
            for _card in list(_cm.get_available_cards()):
                if _card.category == "offensive" and _card.id in (
                    "card_zhenjing_huaxia_shu",
                    "card_huoshao_lianying",
                ):
                    if self.card_effect_manager.activate_offensive_card(_card.id):
                        _cm.use_card(_card.id)
                        action_taken = True

        # --- \u9636\u63693\uff1a\u6240\u6709\u5355\u4f4d\u5747\u5df2\u5728\u8fb9\u5883\uff08\u6216\u5185\u9646\u65e0\u6cd5\u79fb\u52a8\uff09\uff0c\u53d1\u52a8\u653b\u51fb ---
        for province, slot_idx, unit_state in border_units:
            if self._has_attackable_target_for_unit(province, unit_state):
                target = self._ai_pick_attack_target(province, unit_state)
                if target is not None:
                    if self._ai_execute_combat(province, slot_idx, target):
                        # _execute_combat \u5df2\u8c03\u7528 _finish_country_action\uff0c\u76f4\u63a5\u8fd4\u56de
                        return

        # --- \u9636\u63694\uff1a\u65e0\u6cd5\u653b\u51fb\uff0c\u8fb9\u5883\u7701\u6574\u4f53\u5411\u654c\u7701\u538b\u8fdb ---
        for prov_id, (province, slots) in border_by_prov.items():
            lead_unit = slots[0][1]
            dest = self._ai_pick_move_target(province, lead_unit, None)
            if dest is None:
                continue
            pc = _calc_path_cost(province, dest, lead_unit)
            if pc > 100:
                continue
            valid_slots = [(idx, u) for idx, u in slots if u.mp >= pc]
            if not valid_slots:
                continue
            self.selected_units = [(province.province_id, idx) for idx, _ in valid_slots]
            self._handle_movement(dest)
            if self.player_country != country:
                return  # \u79fb\u52a8\u6210\u529f\uff0c\u56de\u5408\u5df2\u63a8\u8fdb

        # --- \u9636\u63694.3\uff1a\u4f7f\u7528\u589e\u76ca/\u53ec\u5524\u9526\u56ca\u5361\uff08\u6574\u7701\u52a0\u6210\u8fb9\u5883\u6709\u90e8\u961f\u7684\u683c\u5b50\uff09 ---
        if _cm:
            _border_ids_set = {p.province_id for p in self._ai_get_border_provinces(country)}
            for _card in list(_cm.get_available_cards()):
                if _card.category in ("buff", "summon"):
                    # \u4f18\u5148\u9009\u6709\u90e8\u961f\u7684\u8fb9\u5883\u683c\u5b50\uff0c\u6b21\u9009\u4efb\u610f\u5df1\u65b9\u7a7a\u683c\uff08\u7528\u4e8e\u53ec\u5524\uff09
                    _tgt = None
                    for _rp in self.map_manager.provinces:
                        if _rp.country == country and _rp.units:
                            if _rp.province_id in _border_ids_set:
                                _tgt = _rp
                                break
                    if _tgt is None:
                        for _rp in self.map_manager.provinces:
                            if (
                                _rp.country == country
                                and len(_rp.units) < self.MAX_UNIT_STACK
                            ):
                                _tgt = _rp
                                break
                    if _tgt is not None:
                        if self._apply_card_to_province(_card.id, _tgt.province_id):
                            action_taken = True

        # --- \u9636\u63694.5\uff1a\u79fb\u52a8/\u653b\u51fb\u90fd\u65e0\u6cd5\u8fdb\u884c\u65f6\uff0c\u624d\u8003\u8651\u4f7f\u7528\u653f\u6cbb\u70b9\u6570\uff08PP\uff09 ---
        # \u6cbb\u75c7\u4f18\u5148\uff0c\u5176\u6b21\u624d\u62db\u52df\u65b0\u5175\uff1b\u4e0d\u62a2\u5360\u79fb\u52a8/\u653b\u51fb\u673a\u4f1a
        _ai_pp_used = False
        if self._pp_can_use(country):
            # 1) \u6cbb\u75c7\u4f24\u5175
            for _prov in self.map_manager.provinces:
                if _prov.country != country:
                    continue
                for _u in _prov.units:
                    if _u.hp < 2:
                        _cost = self._get_pp_heal_cost(_u)
                        if self._get_total_pp(country) >= _cost:
                            self._spend_pp(country, _cost)
                            _u.hp += 1
                            _ai_pp_used = True
            # 2) \u6709\u5269\u4f59PP\u5219\u62db\u52df\u65b0\u5175\u5230\u8fb9\u5883\u7701
            _can_recruit = not (
                getattr(self, "evt_flag_hu_recruit", False) and country == "WEI"
            )
            if _can_recruit and self._get_total_pp(country) >= 1:
                _recruit_target = None
                _border_pset = {
                    p.province_id for p in self._ai_get_border_provinces(country)
                }
                for _rp in self.map_manager.provinces:
                    if _rp.country == country and len(_rp.units) < self.MAX_UNIT_STACK:
                        if _rp.province_id in _border_pset:
                            _recruit_target = _rp
                            break
                if _recruit_target is None:
                    for _rp in self.map_manager.provinces:
                        if (
                            _rp.country == country
                            and len(_rp.units) < self.MAX_UNIT_STACK
                        ):
                            _recruit_target = _rp
                            break
                if _recruit_target is not None:
                    _pp_left = self._get_total_pp(country)
                    if _pp_left >= 2:
                        new_u = UnitState("infantry")
                        new_u.hp = 2
                        self._spend_pp(country, 2)
                    else:
                        new_u = UnitState("infantry")
                        new_u.hp = 1
                        self._spend_pp(country, 1)
                    _recruit_target.units.append(new_u)
                    _ai_pp_used = True
            if _ai_pp_used:
                action_taken = True

        # --- \u9636\u63694.7\uff1a\u4e3b\u52a8\u89e3\u9664\u6df7\u4e71\u5355\u4f4d\uff08\u6d88\u8017\u672c\u56de\u5408\u884c\u52a8\uff09 ---
        if self._has_confused_units_for_country(country):
            # \u627e\u7b2c\u4e00\u4e2a\u6df7\u4e71\u5355\u4f4d\u5e76\u89e3\u9664\uff08\u4e0e\u73a9\u5bb6\u64cd\u4f5c\u7b49\u4ef7\uff09
            for _prov in self.map_manager.provinces:
                if _prov.country != country:
                    continue
                for _u in _prov.units:
                    if _u.is_confused:
                        _u.is_confused = False
                        self._finish_country_action(
                            f"AI({country})\u89e3\u9664\u6df7\u4e71", keep_info_message=True
                        )
                        return

        # --- \u9636\u63695\uff1a\u7ed3\u675f\u672c\u56fd\u56de\u5408 ---
        self._finish_country_action(
            f"AI({country})\u884c\u52a8", keep_info_message=action_taken
        )

'''

new_content = content[:start_idx] + new_method + content[end_idx:]

with open("src/core/app.py", encoding="utf-8", mode="w") as f:
    f.write(new_content)

print(f"SUCCESS: _run_ai_turn replaced, new method={len(new_method)} chars")
