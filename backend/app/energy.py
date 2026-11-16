"""AC-bus dispatch. Power kW, stored energy kWh, tariffs USD/kWh."""

from typing import Literal
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import lil_matrix

PROFILES = {
    "small": (110, 100, 200),
    "medium": (450, 400, 800),
    "warehouse": (170, 600, 500),
}


class Config(BaseModel):
    model_config = {"extra": "forbid", "allow_inf_nan": False}
    name: str = Field(default="Small manufacturing", min_length=1, max_length=100)
    profile: Literal["small", "medium", "warehouse"] = "small"
    capacity: float = Field(200, ge=0, le=20000)
    power: float = Field(80, ge=0, le=10000)
    efficiency: float = Field(0.95, ge=0.5, le=1)
    min_soc: float = Field(0.1, ge=0, le=0.8)
    max_soc: float = Field(0.9, ge=0.2, le=1)
    initial_soc: float = Field(0.5, ge=0, le=1)
    reserve: float = Field(0.2, ge=0, le=0.9)
    solar_scale: float = Field(1, ge=0, le=5)
    demand_scale: float = Field(1, ge=0.1, le=5)
    tariff_scale: float = Field(1, ge=0.1, le=5)
    night_shift: bool = False
    islandable: bool = True
    outage_start: int = Field(-1, ge=-1)
    outage_hours: int = Field(4, ge=1, le=168)
    critical_fraction: float = Field(0.65, ge=0.1, le=1)
    carbon_factor: float = Field(0.4, ge=0, le=2)
    demand_charge: float = Field(0, ge=0, le=100)

    @model_validator(mode="after")
    def bounds(self):
        if not self.min_soc <= self.reserve <= self.initial_soc <= self.max_soc:
            raise ValueError("Require min_soc <= reserve <= initial_soc <= max_soc")
        return self


def synthetic(profile="small", days=56, minutes=60, seed=42):
    if profile not in PROFILES or minutes not in (15, 60) or not 1 <= days <= 366:
        raise ValueError("Invalid profile, duration or resolution")
    rng = np.random.default_rng(seed)
    t = pd.date_range(
        "2026-01-05", periods=days * 24 * 60 // minutes, freq=f"{minutes}min", tz="UTC"
    )
    h = t.hour.to_numpy() + t.minute.to_numpy() / 60
    base, solar, _ = PROFILES[profile]
    shift = ((h >= 7) & (h < 19) & (t.dayofweek.to_numpy() < 5)).astype(float)
    cloud = np.repeat(rng.uniform(0.45, 1, days), 24 * 60 // minutes)
    temp = 24 + 7 * np.sin((h - 8) * np.pi / 12) + rng.normal(0, 0.6, len(t))
    production = base * (0.25 + 0.65 * shift)
    hvac = base * (0.08 + 0.012 * np.maximum(temp - 22, 0))
    flexible = base * (0.05 + 0.08 * shift)
    demand = np.maximum(
        0, production + hvac + flexible + rng.normal(0, base * 0.025, len(t))
    )
    return pd.DataFrame(
        dict(
            timestamp=t.astype(str),
            demand_kw=demand,
            solar_kw=solar * np.maximum(0, np.sin((h - 6) * np.pi / 12)) * cloud,
            import_price=np.where(
                (h >= 17) & (h < 22), 0.30, np.where((h < 6), 0.09, 0.16)
            ),
            export_price=np.full(len(t), 0.04),
            temperature=temp,
            shift=shift,
            production_kw=production,
            hvac_kw=hvac,
            flexible_kw=flexible,
        )
    )


def prepare(frame, cfg):
    f = frame.copy().reset_index(drop=True)
    f.demand_kw *= cfg.demand_scale
    if cfg.night_shift:
        hours = pd.to_datetime(f.timestamp, utc=True).dt.hour
        f.loc[(hours < 7) | (hours >= 19), "demand_kw"] += (
            PROFILES[cfg.profile][0] * 0.45
        )
    f.solar_kw *= cfg.solar_scale
    f.import_price *= cfg.tariff_scale
    f.export_price *= cfg.tariff_scale
    return f


def dispatch(frame, cfg: Config, mode="optimized"):
    f = prepare(frame, cfg)
    n = len(f)
    dt = (
        pd.to_datetime(f.timestamp.iloc[1]) - pd.to_datetime(f.timestamp.iloc[0])
    ).total_seconds() / 3600
    demand, solar = f.demand_kw.to_numpy(), f.solar_kw.to_numpy().copy()
    buy, sell = f.import_price.to_numpy(), f.export_price.to_numpy()
    grid = np.ones(n, dtype=bool)
    if cfg.outage_start >= 0:
        grid[
            int(cfg.outage_start / dt) : int((cfg.outage_start + cfg.outage_hours) / dt)
        ] = False
    if not cfg.islandable:
        solar[~grid] = 0
    cap = cfg.capacity if mode != "none" else 0
    power = cfg.power if cap else 0
    emin, emax, initial = cap * cfg.reserve, cap * cfg.max_soc, cap * cfg.initial_soc
    # Variables per timestep: import, export, charge, discharge, energy, curtail,
    # noncritical unserved, critical unserved, charge binary, import binary; plus peak.
    width, size = 10, n * 10 + 1
    cost = np.zeros(size)
    lo = np.zeros(size)
    hi = np.full(size, np.inf)
    integrality = np.zeros(size)
    matrix = lil_matrix((n * 5 + 1, size))
    lower = []
    upper = []
    big = float(max(demand.max() + power, solar.max() + power, 1))
    for i in range(n):
        j = i * width
        cost[j : j + 4] = [buy[i] * dt, -sell[i] * dt, 0.002 * dt, 0.002 * dt]
        cost[j + 6 : j + 8] = [100 * dt, 10000 * dt]
        hi[j : j + 2] = big if grid[i] else 0
        hi[j + 2 : j + 4] = power
        lo[j + 4], hi[j + 4] = emin, emax
        hi[j + 5] = solar[i]
        hi[j + 6 : j + 8] = (
            [demand[i] * (1 - cfg.critical_fraction), demand[i] * cfg.critical_fraction]
            if not grid[i]
            else [0, 0]
        )
        hi[j + 8 : j + 10] = 1
        integrality[j + 8 : j + 10] = 1
        r = i * 5
        for k, v in {0: 1, 1: -1, 2: -1, 3: 1, 5: -1, 6: 1, 7: 1}.items():
            matrix[r, j + k] = v
        lower.append(demand[i] - solar[i])
        upper.append(demand[i] - solar[i])
        matrix[r + 1, j + 4] = 1
        matrix[r + 1, j + 2] = -dt * cfg.efficiency
        matrix[r + 1, j + 3] = dt / cfg.efficiency
        if i:
            matrix[r + 1, j - 6] = -1
        lower.append(initial if i == 0 else 0)
        upper.append(lower[-1])
        matrix[r + 2, j + 2] = 1
        matrix[r + 2, j + 8] = -power
        lower.append(-np.inf)
        upper.append(0)
        matrix[r + 3, j + 3] = 1
        matrix[r + 3, j + 8] = power
        lower.append(-np.inf)
        upper.append(power)
        matrix[r + 4, j] = 1
        matrix[r + 4, -1] = -1
        lower.append(-np.inf)
        upper.append(0)
    # Separate grid import/export exclusivity constraints.
    extra = lil_matrix((2 * n, size))
    for i in range(n):
        j = i * 10
        extra[2 * i, j] = 1
        extra[2 * i, j + 9] = -big
        extra[2 * i + 1, j + 1] = 1
        extra[2 * i + 1, j + 9] = big
    from scipy.sparse import vstack

    matrix[-1, (n - 1) * 10 + 4] = 1
    lower.append(initial)
    upper.append(initial)
    cost[-1] = cfg.demand_charge
    if mode == "optimized" or mode == "none":
        result = milp(
            cost,
            integrality=integrality,
            bounds=Bounds(lo, hi),
            constraints=[
                LinearConstraint(matrix.tocsr(), lower, upper),
                LinearConstraint(
                    extra.tocsr(), np.full(2 * n, -np.inf), np.tile([0, big], n)
                ),
            ],
            options={"time_limit": 60, "mip_rel_gap": 1e-7},
        )
        if not result.success:
            raise ValueError(f"Dispatch did not solve: {result.message}")
        x = result.x[:-1].reshape(n, 10)
    else:
        x = np.zeros((n, 10))
        energy = initial
        for i in range(n):
            net = demand[i] - solar[i]
            c = d = 0.0
            # Keep sufficient time to restore starting energy by the horizon end.
            restore = (
                grid[i]
                and (initial - energy) > max(0, n - i - 1) * power * dt * cfg.efficiency
            )
            if restore or net < 0 or (buy[i] <= np.quantile(buy, 0.25) and grid[i]):
                c = min(
                    power,
                    (emax - energy) / (dt * cfg.efficiency),
                    (
                        max(0, -net)
                        if not grid[i]
                        else (max(0, -net) if net < 0 and not restore else power)
                    ),
                )
                c = (
                    min(c, max(0, (initial - energy) / (dt * cfg.efficiency)))
                    if restore
                    else c
                )
            elif not grid[i] or buy[i] >= np.quantile(buy, 0.8):
                d = min(power, (energy - emin) * cfg.efficiency / dt, max(0, net))
            energy += dt * (c * cfg.efficiency - d / cfg.efficiency)
            residual = net + c - d
            imp = max(0, residual) if grid[i] else 0
            exp = max(0, -residual) if grid[i] else 0
            unserved = max(0, residual) if not grid[i] else 0
            non = min(unserved, demand[i] * (1 - cfg.critical_fraction))
            x[i, :8] = [
                imp,
                exp,
                c,
                d,
                energy,
                max(0, -residual) if not grid[i] else 0,
                non,
                unserved - non,
            ]
    rows = []
    for i, v in enumerate(x):
        imp, exp, c, d, e, curt, non, critical = v[:8]
        reason = (
            "Critical load prioritized during outage"
            if not grid[i]
            else (
                "Charging from solar surplus"
                if c > 1e-5 and solar[i] > demand[i]
                else (
                    "Charging under tariff and terminal-energy constraints"
                    if c > 1e-5
                    else (
                        "Discharging to offset grid purchases"
                        if d > 1e-5
                        else "Battery idle within operating constraints"
                    )
                )
            )
        )
        rows.append(
            dict(
                timestamp=str(f.timestamp.iloc[i]),
                demand_kw=float(demand[i]),
                solar_kw=float(solar[i]),
                grid_import_kw=float(imp),
                grid_export_kw=float(exp),
                charge_kw=float(c),
                discharge_kw=float(d),
                energy_kwh=float(e),
                soc=float(e / cap if cap else 0),
                curtailed_kw=float(curt),
                unserved_kw=float(non + critical),
                critical_unserved_kw=float(critical),
                grid_available=bool(grid[i]),
                loss_kw=float(c * (1 - cfg.efficiency) + d * (1 / cfg.efficiency - 1)),
                import_price=float(buy[i]),
                cost=float(dt * (imp * buy[i] - exp * sell[i])),
                reason=reason,
            )
        )
    a = pd.DataFrame(rows)
    energy_cost = float(a.cost.sum())
    peak = float(a.grid_import_kw.max())
    # Terminal asset credit makes heuristic inventory differences explicit.
    terminal_adjustment = float((initial - x[-1, 4]) * buy.min() / cfg.efficiency)
    metrics = dict(
        cost=energy_cost + peak * cfg.demand_charge + terminal_adjustment,
        energy_cost=energy_cost,
        terminal_adjustment=terminal_adjustment,
        demand_charge=peak * cfg.demand_charge,
        grid_kwh=float(a.grid_import_kw.sum() * dt),
        peak_kw=peak,
        solar_self_consumption=float(
            max(
                0,
                1
                - (a.grid_export_kw.sum() + a.curtailed_kw.sum())
                / max(a.solar_kw.sum(), 1e-9),
            )
        ),
        throughput_kwh=float((a.charge_kw + a.discharge_kw).sum() * dt),
        cycles=(
            float((a.charge_kw + a.discharge_kw).sum() * dt / (2 * cap)) if cap else 0
        ),
        unserved_kwh=float(a.unserved_kw.sum() * dt),
        critical_unserved_kwh=float(a.critical_unserved_kw.sum() * dt),
        carbon_kg=float(a.grid_import_kw.sum() * dt * cfg.carbon_factor),
    )
    return dict(mode=mode, interval_hours=dt, metrics=metrics, rows=rows)


def compare(frame, cfg):
    results = {m: dispatch(frame, cfg, m) for m in ("none", "rule", "optimized")}
    for v in results.values():
        v["metrics"]["savings"] = (
            results["none"]["metrics"]["cost"] - v["metrics"]["cost"]
        )
    return results
