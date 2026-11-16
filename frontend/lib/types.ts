export interface Config {
  name: string;
  profile: string;
  capacity: number;
  power: number;
  efficiency: number;
  min_soc: number;
  max_soc: number;
  initial_soc: number;
  reserve: number;
  solar_scale: number;
  demand_scale: number;
  tariff_scale: number;
  night_shift: boolean;
  islandable: boolean;
  outage_start: number;
  outage_hours: number;
  critical_fraction: number;
  carbon_factor: number;
  demand_charge: number;
}
export interface Factory {
  id: number;
  name: string;
  config: Config;
}
export interface Dataset {
  id: number;
  name: string;
  source: string;
  count: number;
  metadata: { profile?: string; minutes?: number };
}
export interface Row {
  timestamp: string;
  demand_kw: number;
  solar_kw: number;
  grid_import_kw: number;
  grid_export_kw: number;
  charge_kw: number;
  discharge_kw: number;
  energy_kwh: number;
  soc: number;
  curtailed_kw: number;
  unserved_kw: number;
  critical_unserved_kw: number;
  grid_available: boolean;
  loss_kw: number;
  cost: number;
  reason: string;
}
export interface Dispatch {
  metrics: Record<string, number>;
  rows: Row[];
  interval_hours: number;
}
export interface Forecast {
  metrics: Record<string, { mae: number; rmse: number; smape: number }>;
  assumptions: string;
  test: {
    timestamp: string;
    actual: number;
    forecast: number;
    baseline: number;
  }[];
  future: { timestamp: string; demand_kw: number; solar_kw: number }[];
  errors_by_hour: { hour: number; absolute_error: number }[];
}
export interface Result {
  baseline?: Record<string, Dispatch>;
  modified?: Record<string, Dispatch>;
  difference?: Record<string, number>;
  input_kind?: string;
  error?: string;
}
export interface Run {
  id: number;
  kind: string;
  status: string;
  result: Result & Partial<Forecast>;
  request: { dataset_id: number };
}
export interface Simulation {
  id: number;
  run_id: number;
  cursor: number;
  count: number;
  playing: boolean;
  speed: number;
  current: Row;
}
