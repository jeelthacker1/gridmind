"""Recursive forecasts: all lag features come from the history available at origin."""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


def features(t, history, day):
    return [
        np.sin(t.hour * np.pi / 12),
        np.cos(t.hour * np.pi / 12),
        t.dayofweek,
        int(t.dayofweek < 5 and 7 <= t.hour < 19),
        history[-1],
        history[-day],
        history[-7 * day],
    ]


def predict(model, history, times, day):
    values = list(history)
    out = []
    for t in times:
        value = (
            max(0, float(model.predict([features(t, values, day)])[0]))
            if model
            else float(values[-7 * day])
        )
        values.append(value)
        out.append(value)
    return np.asarray(out)


def score(y, p):
    return dict(
        mae=float(mean_absolute_error(y, p)),
        rmse=float(np.sqrt(mean_squared_error(y, p))),
        smape=float(
            200 * np.mean(np.abs(y - p) / np.maximum(np.abs(y) + np.abs(p), 1e-6))
        ),
    )


def forecast(frame, horizon=24):
    f = frame.copy()
    times = pd.to_datetime(f.timestamp, utc=True)
    minutes = int((times.iloc[1] - times.iloc[0]).total_seconds() / 60)
    day = 1440 // minutes
    if len(f) < 28 * day:
        raise ValueError("Forecast requires at least 28 complete days")
    y = f.demand_kw.to_numpy()
    a = int(len(y) * 0.6)
    b = int(len(y) * 0.8)
    X = np.array([features(times.iloc[i], y[:i], day) for i in range(7 * day, len(y))])
    target = y[7 * day :]
    best = None
    best_error = np.inf
    trials = []
    for leaves in (7, 15):
        model = HistGradientBoostingRegressor(
            max_iter=80, max_leaf_nodes=leaves, l2_regularization=1, random_state=42
        )
        model.fit(X[: a - 7 * day], target[: a - 7 * day])
        p = predict(model, y[:a], times.iloc[a:b], day)
        error = score(y[a:b], p)
        trials.append(dict(leaves=leaves, **error))
        if error["mae"] < best_error:
            best_error = error["mae"]
            best = leaves
    model = HistGradientBoostingRegressor(
        max_iter=80, max_leaf_nodes=best, l2_regularization=1, random_state=42
    )
    model.fit(X[: b - 7 * day], target[: b - 7 * day])
    p = predict(model, y[:b], times.iloc[b:], day)
    naive = predict(None, y[:b], times.iloc[b:], day)
    errors = (
        pd.DataFrame(
            {
                "hour": times.iloc[b:].dt.hour.to_numpy(),
                "absolute_error": np.abs(y[b:] - p),
            }
        )
        .groupby("hour")
        .mean()
        .reset_index()
    )
    metrics = {
        "gradient_boosting": score(y[b:], p),
        "seasonal_naive": score(y[b:], naive),
    }
    model.fit(X, target)
    future = pd.date_range(
        times.iloc[-1] + pd.Timedelta(minutes=minutes),
        periods=horizon * 60 // minutes,
        freq=f"{minutes}min",
    )
    pred = predict(model, y, future, day)
    base = predict(None, y, future, day)
    solar = list(f.solar_kw.to_numpy())
    future_solar = []
    for _ in future:
        solar.append(float(solar[-7 * day]))
        future_solar.append(solar[-1])
    return dict(
        metrics=metrics,
        validation_trials=trials,
        selected_leaves=best,
        split={
            "train_end": str(times.iloc[a - 1]),
            "validation_end": str(times.iloc[b - 1]),
            "test_start": str(times.iloc[b]),
        },
        assumptions="UTC calendar; recursive lag predictions; unchanged shifts; solar repeats the previous week. No future measured weather or demand is used.",
        errors_by_hour=errors.to_dict("records"),
        test=[
            dict(
                timestamp=str(t), actual=float(v), forecast=float(q), baseline=float(z)
            )
            for t, v, q, z in zip(times.iloc[b:], y[b:], p, naive)
        ],
        future=[
            dict(timestamp=str(t), demand_kw=float(q), baseline=float(z), solar_kw=s)
            for t, q, z, s in zip(future, pred, base, future_solar)
        ],
    )
