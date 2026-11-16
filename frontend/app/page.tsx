"use client";
import { useEffect, useState, useCallback } from "react";
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  Activity,
  BatteryCharging,
  Factory as FactoryIcon,
  Sun,
  PlugZap,
  ChartNoAxesCombined,
  FlaskConical,
  Database,
  FileChartColumn,
  ArrowUpRight,
  Play,
  Pause,
  RotateCcw,
  Zap,
  LogOut,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useWorkspace, type Tab } from "@/lib/store";
import type {
  Factory,
  Dataset,
  Config,
  Run,
  Simulation,
  Forecast,
  Row,
} from "@/lib/types";

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    "/api" + path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const t = await response.text();
    throw new Error(t);
  }
  return response.json();
}
const money = (n: number = 0) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    n,
  );
const num = (n: number = 0) =>
  n.toLocaleString("en-US", { maximumFractionDigits: 1 });
const nav: [Tab, typeof Activity][] = [
  ["Control center", Activity],
  ["Forecast studio", ChartNoAxesCombined],
  ["What-if lab", FlaskConical],
  ["Data & assets", Database],
  ["Reports", FileChartColumn],
];
const scenarios: Record<string, Partial<Config>> = {
  "Tariff +25%": { tariff_scale: 1.25 },
  "Solar −40%": { solar_scale: 0.6 },
  "Double battery": { capacity: 400 },
  "Lower efficiency": { efficiency: 0.8 },
  "Production +25%": { demand_scale: 1.25 },
  "Grid outage": { outage_start: 17, outage_hours: 4 },
  "More rooftop solar": { solar_scale: 1.5 },
  "Night production": { night_shift: true },
};

export default function Home() {
  const { tab, setTab } = useWorkspace();
  const [user, setUser] = useState<{ email: string; role: string } | null>(
      null,
    ),
    [email, setEmail] = useState("admin@gridmind.local"),
    [password, setPassword] = useState("");
  const [factories, setFactories] = useState<Factory[]>([]),
    [datasets, setDatasets] = useState<Dataset[]>([]),
    [cfg, setCfg] = useState<Config | null>(null),
    [dataset, setDataset] = useState(0);
  const [run, setRun] = useState<Run | null>(null),
    [forecast, setForecast] = useState<Run | null>(null),
    [scenario, setScenario] = useState<Run | null>(null),
    [sim, setSim] = useState<Simulation | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [horizon, setHorizon] = useState(24),
    [choice, setChoice] = useState("Tariff +25%"),
    [reportPeriod, setReportPeriod] = useState("daily");
  const [history, setHistory] = useState<
      { id: number; kind: string; status: string }[]
    >([]),
    [timezone, setTimezone] = useState("UTC"),
    [unit, setUnit] = useState("kW"),
    [outliers, setOutliers] = useState("reject");
  const [selectedNode, setSelectedNode] = useState("Factory"),
    [useForecast, setUseForecast] = useState(false);
  const canEdit = user?.role !== "viewer";
  const load = useCallback(async () => {
    const [fs, ds, hs] = await Promise.all([
      api<Factory[]>("/factories"),
      api<Dataset[]>("/datasets"),
      api<typeof history>("/runs"),
    ]);
    setFactories(fs);
    setDatasets(ds);
    setHistory(hs);
    setCfg((c) => c || fs[0]?.config);
    setDataset((d) => d || ds[0]?.id);
  }, []);
  useEffect(() => {
    api<typeof user>("/me")
      .then((u) => {
        setUser(u);
        return load();
      })
      .catch(() => {});
  }, [load]);
  useEffect(() => {
    if (!sim?.id) return;
    const s = new EventSource(`/api/simulations/${sim.id}/events`);
    s.onmessage = (e) => setSim(JSON.parse(e.data));
    s.onerror = () => setNotice("Reconnecting to simulation stream…");
    return () => s.close();
  }, [sim?.id]);
  async function act(fn: () => Promise<void>) {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  async function launch(kind: string) {
    if (!cfg) return;
    await act(async () => {
      const changes = { ...scenarios[choice] };
      if (choice === "Double battery") changes.capacity = cfg.capacity * 2;
      const created = await api<{ id: number }>("/runs", {
        kind,
        dataset_id: dataset,
        config: cfg,
        horizon,
        changes: kind === "scenario" ? changes : {},
        forecast_id: useForecast && kind !== "forecast" ? forecast?.id : null,
      });
      let item: Run;
      let polls = 0;
      do {
        item = await api<Run>(`/runs/${created.id}`);
        if (item.status === "failed") throw new Error(item.result.error);
        if (item.status !== "complete")
          await new Promise((r) => setTimeout(r, 1000));
        if (++polls > 650)
          throw new Error("Job is still running. Open it later from Reports.");
      } while (item.status !== "complete");
      if (kind === "forecast") setForecast(item);
      else if (kind === "scenario") setScenario(item);
      else {
        setRun(item);
        setSim(await api<Simulation>(`/simulations/${item.id}`, {}));
      }
      await load();
      setNotice(`Run #${item.id} completed and saved.`);
    });
  }
  async function control(action: string, value = 1) {
    if (sim)
      await act(async () =>
        setSim(
          await api<Simulation>(`/simulations/${sim.id}/control`, {
            action,
            value,
          }),
        ),
      );
  }
  const result = run?.result.baseline,
    metrics = result?.optimized.metrics,
    current = sim?.current || result?.optimized.rows[0];
  const chart =
    result?.optimized.rows.map((r) => ({
      ...r,
      time: r.timestamp.slice(11, 16),
    })) || [];
  const f = forecast?.result as Forecast | undefined;
  function selectFactory(id: number) {
    const fac = factories.find((v) => v.id === id);
    if (!fac) return;
    setCfg(fac.config);
    setDataset(
      datasets.find(
        (d) =>
          d.metadata.profile === fac.config.profile &&
          d.metadata.minutes === 60,
      )?.id || dataset,
    );
    setRun(null);
    setSim(null);
    setForecast(null);
    setScenario(null);
    setUseForecast(false);
  }
  if (!user)
    return (
      <main className="login">
        <div className="login-art">
          <div className="brand">
            <Zap /> GRIDMIND<span>ENERGY INTELLIGENCE</span>
          </div>
          <div>
            <span className="eyebrow">
              KNOW YOUR ENERGY. CONTROL YOUR IMPACT.
            </span>
            <h1>
              A smarter grid.
              <br />A stronger operation.
            </h1>
            <p>
              Your factory, solar, and storage.
              <br />
              One connected energy model.
            </p>
          </div>
          <small>Industrial Energy Intelligence & Microgrid Digital Twin</small>
        </div>
        <form
          className="login-form"
          onSubmit={(e) => {
            e.preventDefault();
            void act(async () => {
              setUser(await api("/login", { email, password }));
              await load();
            });
          }}
        >
          <span className="eyebrow">OPERATOR ACCESS</span>
          <h2>Welcome to GRIDMIND</h2>
          <p>Sign in to your local energy workspace.</p>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <Button disabled={busy} type="submit">
            {busy ? "Signing in…" : "Enter control center"}{" "}
            <ArrowUpRight size={17} />
          </Button>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <small>
            First launch: find the generated demo password in API logs.
            <br />
            Demo roles: admin, analyst, viewer @gridmind.local.
          </small>
        </form>
      </main>
    );
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <Zap /> GRIDMIND<span>ENERGY INTELLIGENCE</span>
        </div>
        <div className="workspace-label">
          WORKSPACE <span>LOCAL</span>
        </div>
        <nav>
          {nav.map(([name, Icon]) => (
            <button
              key={name}
              className={tab === name ? "active" : ""}
              onClick={() => setTab(name)}
            >
              <Icon size={19} />
              {name}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" /> Engineering sandbox
          <p>
            Reproducible data.
            <br />
            Real calculated decisions.
          </p>
          <small>Not a field control system</small>
        </div>
        <div className="user">
          <div className="avatar">{user.role[0].toUpperCase()}</div>
          <div>
            <strong>{user.role}</strong>
            <small>Local workspace</small>
          </div>
          <button
            aria-label="Sign out"
            onClick={() =>
              void act(async () => {
                await api("/logout", {});
                setUser(null);
                setSim(null);
              })
            }
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="main">
        <header>
          <div>
            <span className="breadcrumb">Workspace / </span>
            {tab}
          </div>
          <div className="header-right">
            <span className="status-dot" /> API connected{" "}
            <span className="tag">
              {datasets.find((d) => d.id === dataset)?.source || "SYNTHETIC"}{" "}
              DATA
            </span>
          </div>
        </header>
        <main className="content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">INDUSTRIAL ENERGY INTELLIGENCE</span>
              <h1>{tab}</h1>
              <p>
                {tab === "Control center"
                  ? "Every kilowatt, accounted for."
                  : tab === "Forecast studio"
                    ? "Plan ahead with measured forecasting performance."
                    : tab === "What-if lab"
                      ? "Change the conditions. Measure the consequences."
                      : tab === "Data & assets"
                        ? "Build a model that reflects your operation."
                        : "A traceable record of every energy decision."}
              </p>
            </div>
            <select
              aria-label="Factory profile"
              value={factories.find((v) => v.name === cfg?.name)?.id || ""}
              onChange={(e) => selectFactory(+e.target.value)}
            >
              {factories.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </div>
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          {notice && (
            <div role="status" className="notice">
              {notice}
            </div>
          )}
          <div className="toolbar">
            <label>
              Dataset
              <select
                aria-label="Dataset"
                value={dataset}
                onChange={(e) => {
                  setDataset(+e.target.value);
                  setForecast(null);
                  setUseForecast(false);
                }}
              >
                {datasets.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} · {v.source}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Planning horizon
              <select
                aria-label="Planning horizon"
                value={horizon}
                onChange={(e) => setHorizon(+e.target.value)}
              >
                <option value={24}>24 hours</option>
                <option value={168}>7 days</option>
              </select>
            </label>
            {forecast && (
              <label className="check">
                <input
                  type="checkbox"
                  checked={useForecast}
                  onChange={(e) => setUseForecast(e.target.checked)}
                />{" "}
                Use forecast #{forecast.id}
              </label>
            )}
            <span className="timezone">UTC · kW / kWh · USD</span>
          </div>
          {tab === "Control center" && (
            <>
              <div className="metrics">
                {[
                  ["Factory demand", current?.demand_kw, "kW", FactoryIcon],
                  ["Solar generation", current?.solar_kw, "kW", Sun],
                  ["Grid import", current?.grid_import_kw, "kW", PlugZap],
                  [
                    "Battery charge",
                    current ? current.soc * 100 : undefined,
                    "%",
                    BatteryCharging,
                  ],
                ].map(([title, value, u, Icon]) => {
                  const I = Icon as typeof Sun;
                  return (
                    <div className="metric" key={String(title)}>
                      <div>
                        {String(title)}
                        <I size={19} />
                      </div>
                      <strong>
                        {value === undefined ? "—" : num(Number(value))}
                        <small>{String(u)}</small>
                      </strong>
                      <span>
                        {current
                          ? "At " + current.timestamp.slice(11, 16) + " UTC"
                          : "Run dispatch to calculate"}
                      </span>
                    </div>
                  );
                })}
              </div>
              <div className="dashboard-grid">
                <section className="panel flow-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Microgrid digital twin</h2>
                      <p>AC bus · energy-conserving dispatch</p>
                    </div>
                    <span className="pill">
                      {sim?.playing ? "● RUNNING" : "● READY"}
                    </span>
                  </div>
                  <div className="flow">
                    <svg viewBox="0 0 600 270" aria-hidden="true">
                      <path d="M110 60 H300 V210 H490 M110 210 H300 V60 H490" />
                      <circle cx="300" cy="135" r="7" />
                    </svg>
                    {[
                      ["Solar", Sun, current?.solar_kw, "solar"],
                      ["Grid", PlugZap, current?.grid_import_kw, "grid"],
                      ["Factory", FactoryIcon, current?.demand_kw, "factory"],
                      [
                        "Battery",
                        BatteryCharging,
                        current
                          ? current.discharge_kw - current.charge_kw
                          : undefined,
                        "battery",
                      ],
                    ].map(([name, Icon, value, pos]) => {
                      const I = Icon as typeof Sun;
                      return (
                        <button
                          key={String(name)}
                          onClick={() => setSelectedNode(String(name))}
                          className={
                            "flow-node " +
                            pos +
                            (selectedNode === name ? " selected" : "")
                          }
                        >
                          <I size={27} />
                          <span>{String(name)}</span>
                          <strong>
                            {value === undefined ? "—" : num(Number(value))}{" "}
                            <small>kW</small>
                          </strong>
                        </button>
                      );
                    })}
                    <span className="bus-label">AC BUS</span>
                  </div>
                  <div className="flow-detail">
                    <span>{selectedNode}</span>
                    {selectedNode === "Battery"
                      ? `${num(current?.energy_kwh)} kWh stored · ${num(current?.loss_kw)} kW conversion loss`
                      : selectedNode === "Grid"
                        ? `${current?.grid_available === false ? "OUTAGE" : "Grid available"} · ${num(current?.grid_export_kw)} kW export`
                        : selectedNode === "Solar"
                          ? `${num(current?.curtailed_kw)} kW curtailed`
                          : `${num(current?.unserved_kw)} kW unserved`}
                  </div>
                  <div className="playback">
                    <Button
                      disabled={busy || !canEdit}
                      onClick={() => void launch("optimization")}
                    >
                      <Zap size={16} />
                      {busy ? "Calculating…" : "Optimize dispatch"}
                    </Button>
                    <button
                      aria-label={
                        sim?.playing ? "Pause simulation" : "Start simulation"
                      }
                      disabled={!sim || !canEdit}
                      onClick={() =>
                        void control(sim?.playing ? "pause" : "start")
                      }
                    >
                      {sim?.playing ? <Pause size={18} /> : <Play size={18} />}
                    </button>
                    <button
                      aria-label="Reset simulation"
                      disabled={!sim || !canEdit}
                      onClick={() => void control("reset")}
                    >
                      <RotateCcw size={17} />
                    </button>
                    <select
                      aria-label="Simulation speed"
                      value={sim?.speed || 1}
                      disabled={!sim || !canEdit}
                      onChange={(e) => void control("speed", +e.target.value)}
                    >
                      <option value={1}>1× speed</option>
                      <option value={5}>5× speed</option>
                      <option value={20}>20× speed</option>
                    </select>
                  </div>
                  {sim && (
                    <label className="timeline">
                      {sim.current.timestamp.slice(0, 16)} UTC
                      <input
                        aria-label="Simulation time"
                        type="range"
                        min={0}
                        max={sim.count - 1}
                        value={sim.cursor}
                        disabled={!canEdit}
                        onChange={(e) => void control("seek", +e.target.value)}
                      />
                    </label>
                  )}
                </section>
                <section className="panel decision">
                  <span className="eyebrow">DISPATCH INTELLIGENCE</span>
                  <h2>
                    Your next move,
                    <br />
                    grounded in data.
                  </h2>
                  <div className="decision-icon">
                    <BatteryCharging size={30} />
                  </div>
                  <h3>
                    {current?.charge_kw
                      ? "Store energy"
                      : current?.discharge_kw
                        ? "Supply the load"
                        : current
                          ? "Battery idle"
                          : "Ready to model"}
                  </h3>
                  <p>
                    {current?.reason ||
                      "Calculate a feasible battery schedule to see the current decision and its operating context."}
                  </p>
                  <div className="decision-stat">
                    <span>Modeled savings vs no battery</span>
                    <strong>{metrics ? money(metrics.savings) : "—"}</strong>
                  </div>
                  <small>
                    {run?.result.input_kind || "Historical replay"} ·{" "}
                    {cfg?.capacity} kWh battery
                  </small>
                  {current &&
                    current.grid_import_kw > (cfg?.power || 80) * 1.5 && (
                      <div className="warning">
                        Peak demand warning: import exceeds 1.5× battery power.
                      </div>
                    )}
                </section>
              </div>
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Energy through the day</h2>
                    <p>
                      Calculated power at each interval ·{" "}
                      {run ? `Run #${run.id}` : "No run yet"}
                    </p>
                  </div>
                  <span className="tag">
                    {horizon === 24 ? "24H" : "7D"} VIEW
                  </span>
                </div>
                {chart.length ? (
                  <div className="chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={chart}>
                        <defs>
                          <linearGradient
                            id="solar"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="0%"
                              stopColor="#c1db61"
                              stopOpacity={0.5}
                            />
                            <stop
                              offset="100%"
                              stopColor="#c1db61"
                              stopOpacity={0}
                            />
                          </linearGradient>
                        </defs>
                        <CartesianGrid
                          strokeDasharray="3 5"
                          vertical={false}
                          stroke="#e5eae7"
                        />
                        <XAxis
                          dataKey="time"
                          minTickGap={45}
                          tick={{ fontSize: 11 }}
                        />
                        <YAxis unit=" kW" tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Legend />
                        <Area
                          isAnimationActive={false}
                          type="monotone"
                          dataKey="solar_kw"
                          name="Solar"
                          stroke="#91ac2f"
                          fill="url(#solar)"
                        />
                        <Area
                          isAnimationActive={false}
                          type="monotone"
                          dataKey="demand_kw"
                          name="Demand"
                          stroke="#153e36"
                          fill="transparent"
                          strokeWidth={2}
                        />
                        <Area
                          isAnimationActive={false}
                          type="monotone"
                          dataKey="grid_import_kw"
                          name="Grid import"
                          stroke="#7c9dbb"
                          fill="transparent"
                          strokeWidth={2}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="empty">
                    <Activity />
                    <h3>Your energy story starts here</h3>
                    <p>
                      Choose a factory and calculate dispatch to populate the
                      live model.
                    </p>
                  </div>
                )}
              </section>
              {result && (
                <section className="panel">
                  <h2>Control strategy comparison</h2>
                  <Comparison results={result} />
                </section>
              )}
            </>
          )}
          {tab === "Forecast studio" && (
            <>
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Demand forecasting</h2>
                    <p>
                      Chronological 60 / 20 / 20 split · weekly seasonal
                      baseline · recursive gradient boosting
                    </p>
                  </div>
                  <Button
                    disabled={busy || !canEdit}
                    onClick={() => void launch("forecast")}
                  >
                    {busy ? "Training models…" : "Generate forecast"}
                  </Button>
                </div>
                {f?.metrics ? (
                  <>
                    <div className="metrics forecast-metrics">
                      {Object.entries(f.metrics).map(([name, m]) => (
                        <div className="metric" key={name}>
                          <div>{name.replaceAll("_", " ")}</div>
                          <strong>
                            {num(m.mae)}
                            <small>MAE kW</small>
                          </strong>
                          <span>
                            RMSE {num(m.rmse)} kW · sMAPE {num(m.smape)}%
                          </span>
                        </div>
                      ))}
                    </div>
                    <p className="method">{f.assumptions}</p>
                    <h3>Held-out test performance</h3>
                    <div className="chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart
                          data={f.test.map((v) => ({
                            ...v,
                            time: v.timestamp.slice(5, 16),
                          }))}
                        >
                          <CartesianGrid strokeDasharray="3 5" />
                          <XAxis dataKey="time" minTickGap={90} />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Line dataKey="actual" stroke="#153e36" dot={false} />
                          <Line
                            dataKey="forecast"
                            stroke="#8eaa39"
                            dot={false}
                          />
                          <Line
                            dataKey="baseline"
                            stroke="#9baac0"
                            dot={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    <h3>Next {horizon} hours · forecast</h3>
                    <div className="chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart
                          data={f.future.map((v) => ({
                            ...v,
                            time: v.timestamp.slice(5, 16),
                          }))}
                        >
                          <XAxis dataKey="time" minTickGap={90} />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Line
                            dataKey="demand_kw"
                            name="Forecast demand kW"
                            stroke="#153e36"
                            dot={false}
                          />
                          <Line
                            dataKey="solar_kw"
                            name="Repeated-week solar kW"
                            stroke="#95ad42"
                            dot={false}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    <details>
                      <summary>Prediction errors by UTC hour</summary>
                      <div className="error-grid">
                        {f.errors_by_hour.map((v) => (
                          <span key={v.hour}>
                            {v.hour}:00 <b>{num(v.absolute_error)} kW</b>
                          </span>
                        ))}
                      </div>
                    </details>
                  </>
                ) : (
                  <div className="empty">
                    <ChartNoAxesCombined />
                    <h3>Forecasts with an honest baseline</h3>
                    <p>
                      Train on the selected dataset and evaluate unseen periods.
                      At least 28 days of history are required.
                    </p>
                  </div>
                )}
              </section>
            </>
          )}
          {tab === "What-if lab" && (
            <>
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Stress-test your operation</h2>
                    <p>
                      Baseline and modified scenarios use the same input
                      intervals.
                    </p>
                  </div>
                  <Button
                    disabled={busy || !canEdit}
                    onClick={() => void launch("scenario")}
                  >
                    {busy ? "Comparing…" : "Run comparison"}
                  </Button>
                </div>
                <div className="scenario-options">
                  {Object.keys(scenarios).map((s) => (
                    <button
                      className={choice === s ? "chosen" : ""}
                      key={s}
                      onClick={() => setChoice(s)}
                    >
                      <FlaskConical size={18} />
                      {s}
                    </button>
                  ))}
                </div>
                {scenario?.result.difference && (
                  <>
                    <h3>
                      Computed scenario differences · modified minus baseline
                    </h3>
                    <div className="metrics">
                      {[
                        ["Energy cost", "cost", "USD"],
                        ["Peak demand", "peak_kw", "kW"],
                        ["Unserved energy", "unserved_kwh", "kWh"],
                        ["Grid emissions", "carbon_kg", "kg CO₂"],
                      ].map(([label, key, u]) => (
                        <div className="metric" key={key}>
                          <div>{label}</div>
                          <strong>
                            {num(scenario.result.difference?.[key])}
                            <small>{u}</small>
                          </strong>
                        </div>
                      ))}
                    </div>
                    <p className="method">
                      Emission factor: {cfg?.carbon_factor} kg CO₂/kWh of
                      imports. Export receives no carbon credit. Outages
                      prioritize critical loads; this is a simplified islandable
                      microgrid model.
                    </p>
                    <h3>Baseline</h3>
                    <Comparison results={scenario.result.baseline!} />
                    <h3>Modified scenario</h3>
                    <Comparison results={scenario.result.modified!} />
                  </>
                )}
              </section>
            </>
          )}
          {tab === "Data & assets" && cfg && (
            <div className="data-grid">
              <section className="panel">
                <h2>Asset configuration</h2>
                <p>Save an edited configuration as a new scenario.</p>
                <div className="form-grid">
                  <label>
                    Scenario name
                    <input
                      value={cfg.name}
                      onChange={(e) => setCfg({ ...cfg, name: e.target.value })}
                    />
                  </label>
                  {(
                    [
                      ["capacity", "Battery capacity · kWh"],
                      ["power", "Power limit · kW"],
                      ["efficiency", "One-way efficiency"],
                      ["reserve", "Reserve fraction"],
                      ["initial_soc", "Initial SOC fraction"],
                      ["max_soc", "Maximum SOC fraction"],
                      ["solar_scale", "Solar multiplier"],
                      ["demand_scale", "Demand multiplier"],
                      ["tariff_scale", "Tariff multiplier"],
                      ["critical_fraction", "Critical load fraction"],
                      ["carbon_factor", "kg CO₂ / kWh"],
                      ["demand_charge", "Horizon peak charge · USD/kW"],
                    ] as [keyof Config, string][]
                  ).map(([key, label]) => (
                    <label key={key}>
                      {label}
                      <input
                        type="number"
                        step="any"
                        value={Number(cfg[key])}
                        onChange={(e) =>
                          setCfg({ ...cfg, [key]: +e.target.value })
                        }
                      />
                    </label>
                  ))}
                </div>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={cfg.islandable}
                    onChange={(e) =>
                      setCfg({ ...cfg, islandable: e.target.checked })
                    }
                  />{" "}
                  Solar available in island mode
                </label>
                <Button
                  disabled={busy || !canEdit}
                  onClick={() =>
                    void act(async () => {
                      await api("/factories", cfg);
                      await load();
                      setNotice("Configuration saved as a new scenario.");
                    })
                  }
                >
                  Save configuration
                </Button>
              </section>
              <section className="panel">
                <h2>Dataset library</h2>
                <p>Immutable versions · synthetic and imported sources</p>
                <div className="dataset-list">
                  {datasets.map((d) => (
                    <div key={d.id}>
                      <strong>{d.name}</strong>
                      <span>
                        {d.source} · {d.count.toLocaleString()} readings
                      </span>
                      <a href={`/api/datasets/${d.id}/csv`}>
                        Download CSV <Download size={13} />
                      </a>
                    </div>
                  ))}
                </div>
                <h3>Import meter readings</h3>
                <p>
                  timestamp, demand_kw, solar_kw, import_price, export_price.
                  Regular 15-minute or hourly intervals; missing data is
                  rejected.
                </p>
                <label>
                  Source timezone
                  <input
                    value={timezone}
                    onChange={(e) => setTimezone(e.target.value)}
                  />
                </label>
                <label>
                  Power units
                  <select
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                  >
                    <option>kW</option>
                    <option>W</option>
                    <option>MW</option>
                  </select>
                </label>
                <label>
                  Outliers
                  <select
                    value={outliers}
                    onChange={(e) => setOutliers(e.target.value)}
                  >
                    <option value="reject">Reject</option>
                    <option value="clip">Clip and record warnings</option>
                  </select>
                </label>
                <input
                  aria-label="Upload CSV"
                  type="file"
                  accept=".csv"
                  disabled={!canEdit || busy}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file)
                      void act(async () => {
                        const body = new FormData();
                        body.append("file", file);
                        body.append("timezone", timezone);
                        body.append("unit", unit);
                        body.append("outliers", outliers);
                        const r = await fetch("/api/datasets/import", {
                          method: "POST",
                          body,
                        });
                        if (!r.ok) throw new Error(await r.text());
                        await load();
                        setNotice("Dataset imported and versioned.");
                      });
                  }}
                />
              </section>
            </div>
          )}
          {tab === "Reports" && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Run archive & exports</h2>
                  <p>
                    Exports are calculated from stored results, limited to each
                    run’s actual coverage.
                  </p>
                </div>
                <select
                  aria-label="Report period"
                  value={reportPeriod}
                  onChange={(e) => setReportPeriod(e.target.value)}
                >
                  {["daily", "weekly", "monthly", "forecast", "scenario"].map(
                    (p) => (
                      <option key={p}>{p}</option>
                    ),
                  )}
                </select>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Calculation</th>
                    <th>Status</th>
                    <th>Results</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((r) => (
                    <tr key={r.id}>
                      <td>#{r.id}</td>
                      <td>{r.kind}</td>
                      <td>
                        <span className="pill">{r.status}</span>
                      </td>
                      <td>
                        {r.status === "complete" && (
                          <div className="report-actions">
                            <button
                              onClick={() =>
                                void act(async () => {
                                  const item = await api<Run>(`/runs/${r.id}`);
                                  if (r.kind === "forecast") {
                                    setForecast(item);
                                    setTab("Forecast studio");
                                  } else if (r.kind === "scenario") {
                                    setScenario(item);
                                    setTab("What-if lab");
                                  } else {
                                    setRun(item);
                                    setSim(null);
                                    setTab("Control center");
                                  }
                                })
                              }
                            >
                              Inspect
                            </button>
                            <a
                              href={`/api/reports/${r.id}?format=csv&period=${reportPeriod}`}
                            >
                              CSV ↗
                            </a>
                            <a
                              href={`/api/reports/${r.id}?format=pdf&period=${reportPeriod}`}
                            >
                              PDF ↗
                            </a>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!history.length && (
                <div className="empty">
                  Run an optimization or forecast to create a report.
                </div>
              )}
            </section>
          )}
          <footer>
            <span>GRIDMIND / Industrial energy intelligence</span>
            <span>Local model · Explicit assumptions · Traceable results</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
function Comparison({
  results,
}: {
  results: NonNullable<Run["result"]["baseline"]>;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Strategy</th>
            <th>Cost</th>
            <th>Grid energy</th>
            <th>Peak</th>
            <th>Solar retained*</th>
            <th>Cycles</th>
            <th>Unserved</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(results).map(([mode, r]) => (
            <tr key={mode}>
              <td>
                <strong>
                  {mode === "none"
                    ? "No battery"
                    : mode === "rule"
                      ? "Rule-based"
                      : "Optimized"}
                </strong>
              </td>
              <td>{money(r.metrics.cost)}</td>
              <td>{num(r.metrics.grid_kwh)} kWh</td>
              <td>{num(r.metrics.peak_kw)} kW</td>
              <td>{num(r.metrics.solar_self_consumption * 100)}%</td>
              <td>{num(r.metrics.cycles)}</td>
              <td>{num(r.metrics.unserved_kwh)} kWh</td>
            </tr>
          ))}
        </tbody>
      </table>
      <small>
        *Solar retained = generation less exports and curtailment. Cost includes
        configured peak charge and disclosed terminal inventory adjustment.
      </small>
    </div>
  );
}
