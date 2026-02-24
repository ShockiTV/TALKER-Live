"""Parametrized e2e test runner — one test per JSON scenario file."""

import pytest

from .scenario_loader import discover_scenarios, load_scenario, scenario_id


def _scenario_params():
    paths = discover_scenarios()
    return [
        pytest.param(path, id=scenario_id(path))
        for path in paths
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_path", _scenario_params())
async def test_e2e_scenario(scenario_path, e2e_harness):
    from .assertions import assert_scenario
    scenario = load_scenario(scenario_path)
    result = await e2e_harness.run(scenario)
    assert_scenario(result, scenario)
