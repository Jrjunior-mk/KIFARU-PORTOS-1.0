/** Port process simulation tab: existing port versus SmartPort (POST /port/simulate). Everything is MODELLED. */
import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { port as portApi } from '../api/endpoints';
import type { PortSimIn, PortSimKpis, PortSimOut } from '../api/types';
import { Badge, Card, ErrorBanner, Field, Notice, Skeleton, Stat, Table } from '../components/ui';
import { useMutation } from '../hooks/useQuery';
import { chartTheme, useDarkMode } from '../lib/chart';
import { fmtNum } from '../lib/format';
import { fmtBench } from '../lib/port';

export const PORT_SIM_DEFAULTS: PortSimIn = {
  trucks_per_day: 8000, hours: 24, gates_in: 4, gates_out: 4, gate_service_existing_s: 240, gate_service_smart_s: 60,
  loading_equipment: 30, loading_minutes_container: 20, loading_minutes_bulk: 30, loading_minutes_general: 25,
  weighbridges: 2, weigh_service_existing_s: 300, weigh_service_smart_s: 90,
  clearance_desks: 6, clearance_minutes: 15, hold_prob_existing: 0.15, hold_prob_smart: 0.05, hold_minutes: 45,
  appointment_smoothing: true, peak_factor: 1.5, inland_distance_km: 480, inland_speed_kmh: 45, stop_prob: 0.3, stop_minutes: 40, seed: 1, reps: 3,
};

const KPI_ROWS: { key: keyof PortSimKpis; label: string; unit: string; lowerIsBetter: boolean }[] = [
  { key: 'avg_wait_min', label: 'Average truck waiting time', unit: 'min', lowerIsBetter: true },
  { key: 'avg_queue_len', label: 'Average queue length', unit: 'trucks', lowerIsBetter: true },
  { key: 'max_queue_len', label: 'Maximum queue length', unit: 'trucks', lowerIsBetter: true },
  { key: 'avg_processing_min', label: 'Truck processing time', unit: 'min', lowerIsBetter: true },
  { key: 'weigh_service_min', label: 'Weighbridge service time', unit: 'min', lowerIsBetter: true },
  { key: 'throughput_per_hour', label: 'Truck throughput', unit: '/h', lowerIsBetter: false },
  { key: 'avg_dwell_h', label: 'Port dwell time (mean)', unit: 'h', lowerIsBetter: true },
  { key: 'p90_dwell_h', label: 'Port dwell time (P90)', unit: 'h', lowerIsBetter: true },
  { key: 'avg_transit_h', label: 'Transit time to destination', unit: 'h', lowerIsBetter: true },
  { key: 'gate_in_utilisation', label: 'Gate-in utilisation', unit: '', lowerIsBetter: true },
  { key: 'weigh_utilisation', label: 'Weighbridge utilisation', unit: '', lowerIsBetter: true },
];

export default function PortSim() {
  const [form, setForm] = useState<PortSimIn>(PORT_SIM_DEFAULTS);
  const run = useMutation((b: PortSimIn) => portApi.simulate(b));
  const num = (k: keyof PortSimIn, label: string, step = 1, min = 0) => (
    <Field key={k} label={label}>{(id) => <input id={id} type="number" step={step} min={min} className="input py-1" value={form[k] as number} onChange={(e) => setForm({ ...form, [k]: Number(e.target.value) })} />}</Field>
  );
  return (
    <div className="space-y-4">
      <Notice tone="warn">Discrete-event model of the port visit (gate-in, yard, loading, weighing, final clearance, gate-out) plus inland transit. Defaults are engineering assumptions calibrated so the existing policy reproduces the published 2023 truck turnaround; they are not measurements.</Notice>
      <div className="grid gap-4 xl:grid-cols-[22rem_1fr]">
        <Card title="Assumptions" subtitle="POST /port/simulate" actions={<button className="btn-primary text-xs" disabled={run.busy} onClick={() => void run.run(form)}>{run.busy ? 'Running…' : 'Run both policies'}</button>}>
          <div className="space-y-3">
            <div className="section-title">Demand</div>
            <div className="grid grid-cols-2 gap-2">{num('trucks_per_day', 'Trucks / day', 100)}{num('hours', 'Hours simulated', 1, 1)}{num('peak_factor', 'Peak factor', 0.1)}{num('reps', 'Replications', 1, 1)}</div>
            <label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 rounded text-brand-600" checked={form.appointment_smoothing} onChange={(e) => setForm({ ...form, appointment_smoothing: e.target.checked })} />Appointment smoothing (SmartPort)</label>
            <div className="section-title">Gates</div>
            <div className="grid grid-cols-2 gap-2">{num('gates_in', 'Gate-in lanes')}{num('gates_out', 'Gate-out lanes')}{num('gate_service_existing_s', 'Existing gate service (s)', 10)}{num('gate_service_smart_s', 'SmartPort gate service (s)', 10)}</div>
            <div className="section-title">Yard and loading</div>
            <div className="grid grid-cols-2 gap-2">{num('loading_equipment', 'Loading equipment')}{num('loading_minutes_container', 'Container load (min)')}{num('loading_minutes_bulk', 'Bulk load (min)')}{num('loading_minutes_general', 'General load (min)')}</div>
            <div className="section-title">Weighing</div>
            <div className="grid grid-cols-2 gap-2">{num('weighbridges', 'Weighbridges')}{num('weigh_service_existing_s', 'Static weighing (s)', 10)}{num('weigh_service_smart_s', 'Gate-out node (s)', 10)}</div>
            <div className="section-title">Clearance</div>
            <div className="grid grid-cols-2 gap-2">{num('clearance_desks', 'Clearance desks')}{num('clearance_minutes', 'Clearance (min)')}{num('hold_prob_existing', 'Hold share, existing', 0.01)}{num('hold_prob_smart', 'Hold share, SmartPort', 0.01)}{num('hold_minutes', 'Hold duration (min)')}</div>
            <div className="section-title">Inland transit</div>
            <div className="grid grid-cols-2 gap-2">{num('inland_distance_km', 'Distance (km)', 10)}{num('inland_speed_kmh', 'Speed (km/h)')}{num('stop_prob', 'Stop probability', 0.05)}{num('stop_minutes', 'Stop (min)')}{num('seed', 'Seed')}</div>
          </div>
        </Card>
        <div className="space-y-4">
          <ErrorBanner error={run.error} />
          {run.result ? <SimResults r={run.result} /> : !run.busy ? <Card><p className="text-sm text-ink-600 dark:text-slate-300">Set the assumptions and run both policies to compare the existing port process with SmartPort.</p></Card> : <Card><Skeleton lines={8} /></Card>}
        </div>
      </div>
    </div>
  );
}

function SimResults({ r }: { r: PortSimOut }) {
  const dark = useDarkMode();
  const t = chartTheme(dark);
  const ex = r.scenarios.existing, sm = r.scenarios.smartport;
  const chart = [
    { kpi: 'Waiting (min)', existing: ex.avg_wait_min, smartport: sm.avg_wait_min },
    { kpi: 'Processing (min)', existing: ex.avg_processing_min, smartport: sm.avg_processing_min },
    { kpi: 'Dwell (h)', existing: ex.avg_dwell_h, smartport: sm.avg_dwell_h },
    { kpi: 'Transit (h)', existing: ex.avg_transit_h, smartport: sm.avg_transit_h },
  ];
  const pct = (a: number, b: number) => (a ? ((b - a) / a) * 100 : 0);
  return (
    <>
      <Card title="Existing port versus SmartPort" subtitle="Means over the replications; change is SmartPort relative to existing" actions={<Badge tone="violet">{r.label}</Badge>}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Dwell time, existing" value={`${fmtNum(ex.avg_dwell_h, 2)} h`} hint={bench(r, 'truck_turnaround')} />
          <Stat label="Dwell time, SmartPort" value={`${fmtNum(sm.avg_dwell_h, 2)} h`} tone="teal" delta={`${fmtNum(pct(ex.avg_dwell_h, sm.avg_dwell_h), 0)} %`} deltaTone={sm.avg_dwell_h < ex.avg_dwell_h ? 'up' : 'down'} />
          <Stat label="Waiting, existing" value={`${fmtNum(ex.avg_wait_min, 1)} min`} />
          <Stat label="Waiting, SmartPort" value={`${fmtNum(sm.avg_wait_min, 1)} min`} tone="teal" delta={`${fmtNum(pct(ex.avg_wait_min, sm.avg_wait_min), 0)} %`} deltaTone={sm.avg_wait_min < ex.avg_wait_min ? 'up' : 'down'} />
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chart} margin={{ top: 8, right: 8, left: -12, bottom: 0 }} barGap={2}>
            <CartesianGrid stroke={t.grid} vertical={false} /><XAxis dataKey="kpi" tick={{ fontSize: 11, fill: t.text }} stroke={t.axis} /><YAxis tick={{ fontSize: 11, fill: t.text }} stroke={t.axis} />
            <Tooltip contentStyle={t.tooltip} formatter={(v: number) => fmtNum(v, 2)} /><Legend wrapperStyle={{ fontSize: 11 }} />
            <Bar dataKey="existing" name="existing port operations" fill="#64748b" radius={[4, 4, 0, 0]} />
            <Bar dataKey="smartport" name="SmartPort (modelled)" fill="#0d9488" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
        <Table head={['KPI', 'Existing', 'SmartPort', 'Change']} dense>
          {KPI_ROWS.map((k) => {
            const a = ex[k.key], b = sm[k.key];
            const d = pct(a, b);
            const good = k.lowerIsBetter ? d < 0 : d > 0;
            const f = (v: number) => (k.unit === '' ? `${fmtNum(v * 100, 0)} %` : `${fmtNum(v, k.unit === 'trucks' ? 1 : 2)} ${k.unit}`);
            return <tr key={k.key} className="tr"><td className="td">{k.label}</td><td className="td tabular-nums">{f(a)}</td><td className="td tabular-nums font-medium">{f(b)}</td><td className={`td tabular-nums ${good ? 'text-green-700 dark:text-green-300' : d === 0 ? '' : 'text-amber-700 dark:text-amber-300'}`}>{d > 0 ? '+' : ''}{fmtNum(d, 0)} %</td></tr>;
          })}
        </Table>
        {r.calibration_note && <p className="mt-2 text-xs text-ink-600 dark:text-slate-300"><span className="font-medium">Calibration:</span> {r.calibration_note}</p>}
        {r.benchmarks.length > 0 && <div className="mt-2 flex flex-wrap gap-1 text-[11px]">{r.benchmarks.map((b) => <span key={b.key} className="chip">{b.label}: {fmtBench(b.value, b.unit)} <Badge tone={b.classification === 'published' ? 'blue' : 'amber'}>{b.classification}</Badge></span>)}</div>}
        <details className="mt-3 text-xs text-ink-600 dark:text-slate-300"><summary className="cursor-pointer">Assumptions used by the model</summary><ul className="mt-1 list-inside list-disc">{r.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></details>
      </Card>
    </>
  );
}

function bench(r: PortSimOut, key: string): string | undefined {
  const b = r.benchmarks.find((x) => x.key.includes(key));
  return b ? `${b.label}: ${fmtBench(b.value, b.unit)}` : undefined;
}
