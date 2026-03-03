from __future__ import annotations

import logging

MAX_UNIT_STACK = 3

logger = logging.getLogger(__name__)


class MovementService:
    """单位移动与行军拦截服务。"""

    def handle_movement(self, app, target: object) -> None:  # target: Province
        self = app
        source_ids = {pid for pid, _ in self.selected_units}
        if not source_ids:
            return
        if len(source_ids) > 1:
            self.info_panel.show_message("只能移动同一格子上的部队")
            return

        source_id = list(source_ids)[0]
        source = self.map_manager.get_by_id(source_id)
        if not source:
            return

        if source.province_id == target.province_id:
            return

        selected_indices = sorted([idx for pid, idx in self.selected_units if pid == source_id])
        if not selected_indices:
            return

        if source.province_id == target.province_id:
            self.clear_selection()
            return

        selected_unit = source.units[selected_indices[0]]
        source_effect = self.card_effect_manager.get_effect(str(source.province_id))
        if source_effect and source_effect.terrain_immunity:
            ignore_mountain = True
        else:
            ignore_mountain = all(
                bool(getattr(source.units[idx], "temp_terrain_immunity", False))
                or getattr(source.units[idx], "unit_type", "") == "WUDANG_archer"
                for idx in selected_indices
            )
        effective_mp = min(source.units[idx].mp for idx in selected_indices)

        if ignore_mountain:
            path_cost = self._find_path_cost_ignore_mountain(source.province_id, target.province_id)
        else:
            path_cost = self.map_manager.find_path_cost(source.province_id, target.province_id)

        if path_cost > 100:
            self.info_panel.show_message("无法到达")
            return

        if not self.morale_free_move_mode and path_cost > effective_mp:
            self.info_panel.show_message(f"行动力不足（需 {path_cost}，剩余 {effective_mp}）")
            return

        _intermediate_to_occupy = []
        if not self.morale_free_move_mode:
            if ignore_mountain:
                _full_path = self._find_path_ignore_mountain(source.province_id, target.province_id)
            else:
                _full_path = self.map_manager.find_path(source.province_id, target.province_id)

            if _full_path and len(_full_path) >= 2:
                if ignore_mountain:
                    _cumulative = 0
                else:
                    _src_t = (source.terrain or "").lower()
                    _cumulative = 1 if _src_t in ("hill", "mountain", "hills", "mountains") else 0
                _intercept_prov = None
                _effective_target = target
                _effective_cost = path_cost

                for _i in range(1, len(_full_path)):
                    _prev_id = _full_path[_i - 1]
                    _curr_id = _full_path[_i]
                    _sc = 1
                    if not ignore_mountain:
                        _nxt_p = self.map_manager.get_by_id(_curr_id)
                        _nxt_t = (_nxt_p.terrain or "").lower() if _nxt_p else ""
                        if _nxt_t in ("hill", "mountain", "hills", "mountains"):
                            _sc += 1
                    if self._is_river_crossing(_prev_id, _curr_id):
                        _sc += 1
                    _cumulative += _sc

                    if _cumulative > effective_mp:
                        break

                    _curr_prov = self.map_manager.get_by_id(_curr_id)
                    if _curr_prov.country != self.player_country:
                        if _curr_prov.units:
                            _intercept_prov = _curr_prov
                            break
                        _effective_target = _curr_prov
                        _effective_cost = _cumulative
                        _intermediate_to_occupy.append(_curr_prov)
                    else:
                        _effective_target = _curr_prov
                        _effective_cost = _cumulative

                if _intercept_prov is not None:
                    self._handle_combat(_intercept_prov)
                    return

                target = _effective_target
                path_cost = _effective_cost
                _intermediate_to_occupy = [
                    p for p in _intermediate_to_occupy if p.province_id != target.province_id
                ]

        if self.morale_free_move_mode:
            _lxjz_neighbors = self.map_manager._adjacency.get(source.province_id, [])
            if target.province_id not in _lxjz_neighbors:
                self.info_panel.show_message("令行禁止：只能移动到相邻格子")
                return
            if target.country != source.country:
                self.info_panel.show_message("令行禁止：只能移动到己方格子")
                return

        moving_units = []
        unit_costs = []

        for idx in selected_indices:
            unit_state = source.units[idx]
            if not self.morale_free_move_mode:
                if unit_state.mp <= 0:
                    self.info_panel.show_message("行动力为0")
                    return
                if unit_state.mp < path_cost:
                    self.info_panel.show_message(f"行动力不足(需{path_cost})")
                    return

            moving_units.append(unit_state)
            unit_costs.append(0 if self.morale_free_move_mode else path_cost)

        if len(target.units) + len(moving_units) > MAX_UNIT_STACK:
            self.info_panel.show_message("堆叠部队过多")
            return

        pre_move_can_attack = (
            len(moving_units) == 1
            and selected_unit.mp > 0
            and self._has_attackable_target_for_unit(source, selected_unit)
        )

        _orig_src_count = len(source.units)
        new_source_list = []
        moved_indices = set(selected_indices)
        for i, u in enumerate(source.units):
            if i not in moved_indices:
                new_source_list.append(u)
        source.units = new_source_list

        _moved_unit_ids: set = set()
        for u, c in zip(moving_units, unit_costs):
            if id(u) in _moved_unit_ids:
                continue
            _moved_unit_ids.add(id(u))
            u.mp -= c
            target.units.append(u)

        if moving_units:
            target.country = self.player_country
            self.map_manager.invalidate_cache()
            _n_moved = len(moving_units)
            _src_slots = list(range(_orig_src_count - _n_moved, _orig_src_count))
            _dst_start = len(target.units) - len(moving_units)
            _dst_slots = list(range(_dst_start, len(target.units)))
            self.move_src_provs[source_id] = self.player_country
            self.move_src_slots[source_id] = _src_slots
            self.move_dst_provs[target.province_id] = self.player_country
            self.move_dst_slots[target.province_id] = _dst_slots

            for _occ in _intermediate_to_occupy:
                _occ.country = self.player_country
                self.move_dst_provs[_occ.province_id] = self.player_country
                self.move_dst_slots[_occ.province_id] = []
            if _intermediate_to_occupy:
                self.map_manager.invalidate_cache()

            self._check_tianxia_guixin_victory()

        self.clear_selection()

        logger.info(f"Moved {len(moving_units)} units from {source.name} to {target.name}")

        moved_unit = moving_units[0] if moving_units else None
        post_move_can_attack = bool(
            moved_unit and moved_unit.mp > 0 and self._has_attackable_target_for_unit(target, moved_unit)
        )

        if moved_unit and pre_move_can_attack and post_move_can_attack:
            moved_slot = target.units.index(moved_unit)
            self.pending_post_move_attack = True
            self.pending_attacker = (target.province_id, moved_slot)
            self.add_selection(target.province_id, moved_slot)
            self.info_panel.show_message("请选择攻击单位或不攻击")
            return

        if self.morale_free_move_mode:
            if self.player_country:
                self.morale_lv2_used[self.player_country] = self.major_round
            self.morale_free_move_mode = False
            self.info_panel.show_message("令行禁止：移动完成，继续行动")
            return

        self._finish_country_action("移动")
