# Measured case studies

Executed on Windows 11, Python 3.13.3, seed 42. Each case uses the last 24 hourly intervals of the 56-day synthetic dataset (2026-03-01 UTC, a Sunday), default tariffs, one-way efficiency 0.95, reserve 20%, initial SOC 50%, maximum SOC 90%, no outage and no peak charge. These are reproducible scenario measurements, not real industrial savings claims.

| Factory | Solar / battery | No battery | Rule-based | Optimized | Optimized savings |
|---|---|---:|---:|---:|---:|
| Small manufacturing | 100 kW / 200 kWh | $104.53 | $82.32 | $71.44 | $33.09 |
| Medium industrial | 400 kW / 800 kWh | $431.33 | $342.47 | $298.52 | $132.82 |
| Solar-rich warehouse | 600 kW / 500 kWh | $26.37 | −$24.34 | −$45.72 | $72.09 |

## Small manufacturing

Optimized grid imports were 490.76 kWh versus 617.47 kWh without a battery. Solar retained rose from 72.90% to 94.96%. Optimized peak import was 102.61 kW versus 49.72 kW without storage: minimizing energy expenditure alone does not minimize grid peak. The rule controller increased imports to 631.84 kWh because tariff arbitrage incurred losses without improving retained solar.

## Medium industrial

Optimized energy expenditure was $298.52, compared with $342.47 under rule-based control. Imports were 2,028.10 kWh; AC throughput was 1,627.83 kWh, or 1.017 equivalent cycles under the documented throughput definition. Zero unserved energy was recorded. This scaled profile demonstrates that the solver can account for efficiency and exploit daytime surplus beyond fixed price rules.

## Solar-rich warehouse

Export credits produced a negative net energy cost. Optimized imports fell from 870.56 to 549.20 kWh. The site still exported substantial surplus, with 30.06% retained solar. A negative cost is tariff-dependent and does not imply a battery investment pays back; capex and financing are outside this model.

## Forecasts and runtime

| Profile | Naive MAE | Boosting MAE | Boosting RMSE | Boosting sMAPE | Three dispatches | Full forecast workflow |
|---|---:|---:|---:|---:|---:|---:|
| Small | 3.168 kW | 2.397 kW | 2.948 kW | 4.343% | 0.026 s | 1.114 s |
| Medium | 12.958 kW | 9.804 kW | 12.059 kW | 4.343% | 0.047 s | 1.121 s |
| Warehouse | 4.895 kW | 3.704 kW | 4.555 kW | 4.343% | 0.046 s | 1.263 s |

These are single local wall-clock measurements, not latency guarantees or load tests. Similar relative errors reflect deliberately scaled synthetic demand profiles. Reproduce exact metrics and fresh timings with `python scripts/benchmark.py`; CPU, dependency and operating-system differences affect runtime and may introduce minor numerical differences.
