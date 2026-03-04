import unittest

from src.core.app_contexts import AIAutoSelectEventTargetContext, AIBorderProvincesContext
from src.core.ai_service import AIService


class _Prov:
    def __init__(self, pid: int, country: str, units: int, terrain: str = "plain") -> None:
        self.province_id = pid
        self.country = country
        self.units = [object() for _ in range(units)]
        self.terrain = terrain
        self.center_cache = (pid * 10, pid * 10)

    def compute_center(self, hex_side):
        return self.center_cache


class _Map:
    def __init__(self, provs, adjacency, river_edges=None) -> None:
        self.provinces = provs
        self._adjacency = adjacency
        self._river_crossing_edges = river_edges or {}
        self._by_id = {p.province_id: p for p in provs}

    def get_by_id(self, pid):
        return self._by_id.get(pid)


class _App:
    def __init__(self, map_manager) -> None:
        self.map_manager = map_manager
        self.hex_side = 10


class AIServiceMinimalTests(unittest.TestCase):
    def test_get_main_threat_country(self) -> None:
        provs = [
            _Prov(1, "SHU", 1),
            _Prov(2, "WEI", 3),
            _Prov(3, "WU", 1),
        ]
        adjacency = {
            1: [2, 3],
            2: [1],
            3: [1],
        }
        app = _App(_Map(provs, adjacency))
        svc = AIService()

        threat = svc.get_main_threat_country(app, "SHU")
        self.assertEqual(threat, "WEI")

    def test_border_defense_score_city_empty_with_river(self) -> None:
        city = _Prov(1, "SHU", 0, terrain="city")
        enemy = _Prov(2, "WEI", 1)
        adjacency = {1: [2], 2: [1]}
        river_edges = {(1, 2): True}

        app = _App(_Map([city, enemy], adjacency, river_edges))
        svc = AIService()

        score = svc.border_defense_score(app, city)
        # city 4 + river 1 + empty bonus 3
        self.assertEqual(score, 8.0)

    def test_get_border_provinces_with_context(self) -> None:
        provs = [
            _Prov(1, "SHU", 1),
            _Prov(2, "WEI", 2),
            _Prov(3, "SHU", 1),
        ]
        adjacency = {1: [2], 2: [1], 3: []}
        map_obj = _Map(provs, adjacency)
        svc = AIService()

        context = AIBorderProvincesContext(map_manager=map_obj, hex_side=10)
        result = svc.get_border_provinces_with_context(context, "SHU")

        self.assertEqual([p.province_id for p in result], [1])

    def test_auto_select_evt_target_with_context_unit_target(self) -> None:
        svc = AIService()
        state = {
            "pending": "evt_x",
            "cleared": 0,
            "unit_apply": [],
            "prov_apply": [],
            "check": 0,
        }

        target_prov = type("_P", (), {"province_id": 7, "country": "SHU", "units": [object()]})()
        context = AIAutoSelectEventTargetContext(
            get_pending_evt_card_id=lambda: state["pending"],
            get_event_card_definition=lambda _cid: type("_CardDef", (), {"target_type": "unit"})(),
            clear_pending_evt_target_state=lambda: state.__setitem__("cleared", state["cleared"] + 1),
            get_border_provinces=lambda _country: [target_prov],
            get_provinces=lambda: [target_prov],
            apply_evt_target_unit=lambda pid, slot: state["unit_apply"].append((pid, slot)),
            apply_evt_target_province=lambda pid: state["prov_apply"].append(pid),
            check_evt_draw_phase_pp=lambda: state.__setitem__("check", state["check"] + 1),
        )

        svc.auto_select_evt_target_with_context(context, "SHU")

        self.assertEqual(state["unit_apply"], [(7, 0)])
        self.assertEqual(state["prov_apply"], [])
        self.assertEqual(state["cleared"], 0)
        self.assertEqual(state["check"], 0)

    def test_auto_select_evt_target_with_context_no_valid_target_clears_pending(self) -> None:
        svc = AIService()
        state = {
            "pending": "evt_x",
            "cleared": 0,
            "unit_apply": [],
            "check": 0,
        }

        empty_prov = type("_P", (), {"province_id": 8, "country": "SHU", "units": []})()
        context = AIAutoSelectEventTargetContext(
            get_pending_evt_card_id=lambda: state["pending"],
            get_event_card_definition=lambda _cid: type("_CardDef", (), {"target_type": "province"})(),
            clear_pending_evt_target_state=lambda: state.__setitem__("cleared", state["cleared"] + 1),
            get_border_provinces=lambda _country: [],
            get_provinces=lambda: [empty_prov],
            apply_evt_target_unit=lambda pid, slot: state["unit_apply"].append((pid, slot)),
            apply_evt_target_province=lambda _pid: None,
            check_evt_draw_phase_pp=lambda: state.__setitem__("check", state["check"] + 1),
        )

        svc.auto_select_evt_target_with_context(context, "SHU")

        self.assertEqual(state["unit_apply"], [])
        self.assertEqual(state["cleared"], 1)
        self.assertEqual(state["check"], 1)


if __name__ == "__main__":
    unittest.main()
