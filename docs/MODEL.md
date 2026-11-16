# Energy model and optimization

## Units and interval convention

Power is interval-average **kW**, energy is **kWh**, prices are **USD/kWh**, and timestamps are the start of a UTC interval. A row's stored energy/SOC is measured at the **end** of that interval. Supported interval lengths Δ are 1 hour and 0.25 hour.

At the AC bus:

```text
import + available_solar + discharge
  = (demand − unserved) + charge + export + curtailment
```

Battery charge is AC input and discharge is AC output. Conversion losses are therefore already inside the battery state transition and must not be counted twice at the AC bus:

```text
E[t] = E[t−1] + Δ × (η × charge[t] − discharge[t] / η)
loss[t] = (1−η) × charge[t] + (1/η−1) × discharge[t]
```

Equivalently, import + solar + withdrawal from battery stored energy equals served demand + stored-energy addition + export + curtailment + losses. `efficiency` is one-way efficiency; round-trip efficiency is its square. The reserve is a hard operating floor even during outages.

## Mathematical dispatch

The horizon objective is:

```text
min Σ Δ × (buy[t] × import[t] − sell[t] × export[t]
           + 0.002 × (charge[t] + discharge[t])
           + 100 × noncritical_unserved[t] + 10000 × critical_unserved[t])
    + horizon_peak_charge × peak_import
```

Subject to bus balance, battery state transitions, reserve/max energy, charge/discharge power limits, nonnegative flows, available solar curtailment limits, unserved-load bounds, and `peak_import ≥ import[t]`. Binary mode variables prohibit simultaneous charge/discharge and simultaneous import/export. SciPy `milp` invokes HiGHS; this is a mixed-integer linear model, not an unconstrained price heuristic.

Initial energy is `capacity × initial_soc`; optimized terminal energy must equal initial energy. The 0.002 USD/kWh throughput term is a dispatch tie-breaker / wear proxy, **not** a claimed real battery aging cost. Displayed electricity costs exclude that proxy and unserved-load penalty, but expose physical unserved energy separately. Optional peak charges apply once to this modeled horizon; they are not a reconstruction of a monthly utility bill.

Grid outages set both import and export bounds to zero. Solar remains available only when `islandable` is true. Unserved load is prohibited when the grid is available. During an outage critical unserved load receives 100× the penalty of noncritical unserved load. Prioritization is horizon-wide, so storage can be conserved for later critical load.

Dispatch uses either a retrospective historical replay (perfect knowledge of the selected recorded interval) or an explicitly selected completed forecast. These are planning schedules, not a closed-loop controller tested against future forecast error. Flexible load is modeled as a demand component; this release does not reschedule production jobs.

## Comparisons and inventory fairness

- **No battery:** capacity and power are zero; the same solar, tariffs, loads and outage apply.
- **Rule-based:** charge from surplus or low-price periods; discharge in high-price periods or outages; begin restoring starting energy when remaining charging windows become scarce.
- **Optimized:** solve the full constrained horizon with exact terminal energy equality.

When the rule controller cannot finish at its initial inventory (for example an outage at the end), its reported cost includes `(initial_energy − final_energy) × minimum_import_price / η`. This replacement-value adjustment is disclosed separately as `terminal_adjustment`. It is an approximation, not an assertion that rule and optimized dispatch always finish at identical inventory.

Savings = no-battery reported cost − strategy reported cost. Negative costs are possible from export credits. No percentage is hardcoded. An energy-only objective can increase peak import and does not guarantee carbon reduction; enable the peak term to explore that tradeoff.

Solar retained = max(0, 1 − (exports + curtailment)/available_solar). This is a site-level proxy: battery energy is not source-tagged, so it is not a precise renewable provenance ledger. Carbon = grid-import kWh × disclosed scenario factor (default 0.4 kg CO₂/kWh), with no export credit. Equivalent cycles = AC charge-plus-discharge throughput / (2 × rated capacity).

## Data assumptions and bounds

Seeded profiles use production schedules, HVAC temperature response, flexible loads, bounded noise, a daylight solar curve and daily cloud attenuation. No measured site data is implied. UTC shift schedules are deliberate; imports are normalized to UTC, and the user should account for plant-local shift alignment. Missing readings and timestamp gaps are rejected rather than silently filled. Outliers above 10× the 75th percentile (minimum 1 kW) are rejected or explicitly clipped with a recorded warning.

The model omits ramp rates, voltage, reactive power, frequency, degradation physics, inverter start-up, grid connection ratings and protection coordination. It cannot certify real-world islanding or safety.
