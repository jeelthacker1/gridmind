import numpy as np
import pandas as pd
import pytest
from app.energy import Config, synthetic, dispatch, compare


@pytest.mark.parametrize("minutes", [15, 60])
@pytest.mark.parametrize("mode", ["none", "rule", "optimized"])
def test_conservation_and_battery(minutes, mode):
    cfg = Config(outage_start=17)
    result = dispatch(synthetic(days=1, minutes=minutes), cfg, mode)
    dt = minutes / 60
    previous = cfg.capacity * cfg.initial_soc if mode != "none" else 0
    for r in result["rows"]:
        assert r["grid_import_kw"] + r["solar_kw"] + r["discharge_kw"] == pytest.approx(
            r["demand_kw"]
            - r["unserved_kw"]
            + r["charge_kw"]
            + r["grid_export_kw"]
            + r["curtailed_kw"],
            abs=1e-6,
        )
        assert r["energy_kwh"] == pytest.approx(
            previous
            + dt
            * (r["charge_kw"] * cfg.efficiency - r["discharge_kw"] / cfg.efficiency),
            abs=1e-6,
        )
        assert (
            r["charge_kw"] <= cfg.power + 1e-6 and r["discharge_kw"] <= cfg.power + 1e-6
        )
        assert r["charge_kw"] * r["discharge_kw"] < 1e-5
        assert r["grid_import_kw"] * r["grid_export_kw"] < 1e-5
        if mode != "none":
            assert cfg.reserve - 1e-6 <= r["soc"] <= cfg.max_soc + 1e-6
        if not r["grid_available"]:
            assert abs(r["grid_import_kw"]) + abs(r["grid_export_kw"]) < 1e-6
        previous = r["energy_kwh"]


def test_known_arbitrage():
    f = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-01-01", periods=2, freq="h", tz="UTC"
            ).astype(str),
            "demand_kw": [0, 10],
            "solar_kw": [0, 0],
            "import_price": [0.1, 0.5],
            "export_price": [0, 0],
        }
    )
    cfg = Config(
        capacity=10,
        power=10,
        efficiency=1,
        min_soc=0,
        reserve=0,
        initial_soc=0,
        max_soc=1,
    )
    r = compare(f, cfg)
    assert r["optimized"]["metrics"]["cost"] == pytest.approx(1)
    assert r["none"]["metrics"]["cost"] == pytest.approx(5)
    assert r["optimized"]["metrics"]["savings"] == pytest.approx(4)
    assert r["optimized"]["rows"][0]["charge_kw"] == pytest.approx(10)


def test_outage_priority_no_islanding():
    cfg = Config(outage_start=0, outage_hours=24, islandable=False, capacity=0)
    r = dispatch(synthetic(days=1), cfg)
    assert all(x["solar_kw"] == 0 and x["grid_import_kw"] == 0 for x in r["rows"])
    assert r["metrics"]["unserved_kwh"] == pytest.approx(
        sum(x["demand_kw"] for x in r["rows"])
    )


def test_tariff_and_terminal():
    r = dispatch(synthetic(days=1), Config())
    assert r["metrics"]["energy_cost"] == pytest.approx(
        sum(x["cost"] for x in r["rows"])
    )
    assert r["rows"][-1]["energy_kwh"] == pytest.approx(100)
    assert r["metrics"]["terminal_adjustment"] == pytest.approx(0)


def test_invalid_soc():
    with pytest.raises(ValueError):
        Config(reserve=0.8, initial_soc=0.5)
