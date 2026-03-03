import unittest
from types import SimpleNamespace

from src.core.combat_flow_service import CombatFlowService


class _DummyFlowService(CombatFlowService):
    def __init__(self):
        super().__init__()
        self.called = False

    def resolve_combat(self, app, col_index, attackers, target_province):
        self.called = True
        app._captured_col_index = col_index


class CombatFlowServiceMinimalTest(unittest.TestCase):
    def test_handle_combat_returns_when_precondition_false(self):
        svc = CombatFlowService()
        app = SimpleNamespace(
            combat_utils_service=SimpleNamespace(
                check_combat_preconditions=lambda _app, _target: False
            )
        )
        target = SimpleNamespace()
        svc.handle_combat(app, target)
        # 无异常即可，且不会要求 app 具备更多属性
        self.assertTrue(True)

    def test_execute_combat_calls_resolve(self):
        svc = _DummyFlowService()
        app = SimpleNamespace(
            _calculate_unit_powers=lambda _u, _pid: (2, 2),
            _get_attack_terrain_penalty=lambda _p, _t, _u: 0,
            combat_utils_service=SimpleNamespace(
                get_counter_bonus=lambda _ut, _dts: 0,
                calculate_total_defense=lambda _app, _tp: 2,
                calculate_is_flanked=lambda _app, _tp, _aps: False,
                apply_base_column_adjustment=lambda _app, _tp, ci: ci,
            ),
        )
        unit = SimpleNamespace(unit_type="infantry")
        prov = SimpleNamespace(province_id=1)
        target = SimpleNamespace(units=[], province_id=2)

        svc.execute_combat(app, [(prov, unit)], target)
        self.assertTrue(svc.called)


if __name__ == "__main__":
    unittest.main()
