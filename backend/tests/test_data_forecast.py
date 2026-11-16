import pytest
import numpy as np
import pandas as pd
from app.data import ingest
from app.energy import synthetic
from app.forecast import features, predict, forecast


def test_import_normalization():
    f = synthetic(days=2)
    f[["demand_kw", "solar_kw"]] *= 1000
    result, meta = ingest(f.to_csv(index=False).encode(), unit="W")
    assert result.demand_kw.iloc[0] == pytest.approx(f.demand_kw.iloc[0] / 1000)
    assert meta["source"] == "imported" and len(meta["sha256"]) == 64


@pytest.mark.parametrize("bad", ["missing", "gap", "duplicate", "negative", "tariff"])
def test_reject_bad_data(bad):
    f = synthetic(days=3)
    if bad == "missing":
        f.loc[2, "demand_kw"] = np.nan
    if bad == "gap":
        f = f.drop(5)
    if bad == "duplicate":
        f.loc[2, "timestamp"] = f.timestamp.iloc[1]
    if bad == "negative":
        f.loc[2, "demand_kw"] = -1
    if bad == "tariff":
        f.loc[2, "export_price"] = 10
    with pytest.raises(ValueError):
        ingest(f.to_csv(index=False).encode())


def test_recursive_leakage_boundary():
    history = list(np.arange(200, dtype=float))
    times = pd.date_range("2026-01-01", periods=48, freq="h", tz="UTC")

    class Recorder:
        def __init__(self):
            self.seen = []

        def predict(self, x):
            self.seen.append(x[0])
            return [77]

    model = Recorder()
    predict(model, history, times, 24)
    assert model.seen[0][-3] == 199
    assert model.seen[1][-3] == 77
    assert model.seen[24][-2] == 77
    assert history[-1] == 199


def test_forecast_real_metrics():
    r = forecast(synthetic(days=28), 24)
    assert len(r["future"]) == 24
    assert (
        r["split"]["train_end"]
        < r["split"]["validation_end"]
        < r["split"]["test_start"]
    )
    assert r["metrics"]["gradient_boosting"]["mae"] >= 0
