import io
import hashlib
import numpy as np
import pandas as pd


def ingest(content: bytes, timezone="UTC", unit="kW", outliers="reject"):
    if len(content) > 5_000_000:
        raise ValueError("CSV maximum size is 5 MB")
    f = pd.read_csv(io.BytesIO(content))
    required = ["timestamp", "demand_kw", "solar_kw", "import_price", "export_price"]
    if not set(required) <= set(f.columns):
        raise ValueError(f"Required columns: {required}")
    if not 48 <= len(f) <= 35136:
        raise ValueError("Require 48 to 35136 readings")
    t = pd.to_datetime(f.timestamp, errors="raise")
    if t.dt.tz is None:
        t = t.dt.tz_localize(timezone, ambiguous="raise", nonexistent="raise")
    t = t.dt.tz_convert("UTC")
    if t.duplicated().any() or not t.is_monotonic_increasing:
        raise ValueError("Timestamps must be unique and ascending")
    delta = t.diff().dropna().dt.total_seconds()
    if delta.nunique() != 1 or delta.iloc[0] not in (900, 3600):
        raise ValueError(
            "Missing timestamps or unsupported interval; use regular 15-minute or hourly readings"
        )
    f = f[required].copy()
    f.timestamp = t.astype(str)
    for col in required[1:]:
        f[col] = pd.to_numeric(f[col], errors="raise")
        if not np.isfinite(f[col]).all() or (f[col] < 0).any():
            raise ValueError(f"Missing, negative or nonfinite values in {col}")
    if unit not in ("kW", "W", "MW"):
        raise ValueError("Units must be kW, W or MW")
    f[["demand_kw", "solar_kw"]] *= {"kW": 1, "W": 0.001, "MW": 1000}[unit]
    warnings = []
    for col in ("demand_kw", "solar_kw"):
        threshold = max(1, float(f[col].quantile(0.75)) * 10)
        bad = f[col] > threshold
        if bad.any():
            if outliers != "clip":
                raise ValueError(f"Outliers in {col}; explicitly select clip to cap")
            f.loc[bad, col] = threshold
            warnings.append(f"Clipped {int(bad.sum())} {col} values at {threshold} kW")
    if (f.export_price > f.import_price).any():
        raise ValueError("Export prices must not exceed import prices")
    return f, dict(
        source="imported",
        sha256=hashlib.sha256(content).hexdigest(),
        warnings=warnings,
        timezone="UTC",
        unit="kW",
    )
