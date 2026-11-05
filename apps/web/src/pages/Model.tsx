/** RCS v2 Model Explorer: Monte Carlo of the clearance chain for three truck streams (POST /rcs/model, /rcs/model/sweep). Everything is MODELLED. */
import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { rcs as rcsApi } from '../api/endpoints';
import type { RcsModelIn, RcsModelOut, RcsSweepOut } from '../api/types';
import { Badge, Card, ErrorBanner, Field, Notice, PageHeader, Skeleton, Stat, Table } from '../components/ui';
import { useMutation } from '../hooks/useQuery';
import { chartTheme, useDarkMode } from '../lib/chart';
import { fmtNum } from '../lib/format';

export const MODEL_DEFAULTS: RcsModelIn = {
  avg_loading_pct: 85, load_spread_pct: 12, overload_prob: 0.015, token_coverage: 0.9, stream_mix: { port: 0.6, origin: 0.3, untokened: 0.1 },
  port_error_pct: 1.0, origin_error_pct: 1.0, road_error_pct: 2.5, lane_error_pct: 1.0, lane_margin_pct: 2.0, allowance_pct: 0, audit_rate: 0.03,
  port_legal_grade: false, lane_legal_grade: false, trucks_per_day: 8000, stop_minutes: 6, lane_minutes: 1.5, peak_per_hour: 500, n: 200_000, seed: 1,
};

const C = { base: '#64748b', allow: '#a855f7', road: '#0d9488', port: '#d97706', lane: '#2563eb', stat: '#dc2626' };

export default function Model() {
  const [form, setForm] = useState<RcsModelIn>(MODEL_DEFAULTS);
  const run = useMutation((b: RcsModelIn) => rcsApi.model(b));
  const sweepLoad = useMutation((b: RcsModelIn) => rcsApi.sweep({ factor: 'avg_loading_pct', values: [75, 80, 85, 90], base: b }));
  const sweepCov = useMutation((b: RcsModelIn) => rcsApi.sweep({ factor: 'token_coverage', values: [0.3, 0.5, 0.7, 0.9], base: b }));
  const busy = run.busy || sweepLoad.busy || sweepCov.busy;
  const go = async () => {
    const body = { ...form, stream_mix: normalise(form) };
    await Promise.all([run.run(body), sweepLoad.run(body), sweepCov.run(body)]);
  };
  useEffect(() => { void go(); /* initial run with defaults */ // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Analysis · modelled" title="RCS v2 Model Explorer" subtitle="Monte Carlo of the clearance chain for port, origin and untokened trucks. Reproduces the plan's Section 9 tables and lets you move every assumption." actions={<Badge tone="violet">MODELLED</Badge>} />
      <Notice tone="warn">All figures are Monte Carlo estimates under the stated assumptions. They are not measurements and must be replaced with baseline data (weighbridge logs, gate timestamps, classification counts) before any saving is claimed.</Notice>
      <div className="grid gap-4 xl:grid-cols-[22rem_1fr]">
        <Card title="Assumptions" subtitle="POST /rcs/model" actions={<button className="btn-primary text-xs" disabled={busy} onClick={() => void go()}>{busy ? 'Running…' : 'Run model'}</button>}>
          <ModelForm form={form} setForm={setForm} />
        </Card>
        <div className="space-y-4">
          <ErrorBanner error={run.error ?? sweepLoad.error ?? sweepCov.error} />
          {run.result ? <Results r={run.result} /> : <Card><Skeleton lines={6} /></Card>}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Port trucks by average loading" subtitle="Stop shares at the road station (% of all trucks), sweep over average load 75–90 % of the limit">
          {sweepLoad.result ? <LoadingChart s={sweepLoad.result} /> : <Skeleton lines={6} />}
        </Card>
        <Card title="Mixed traffic by token coverage" subtitle="First station: share sent to the lane and to a static scale vs the road-only baseline, sweep over coverage 30–90 %">
          {sweepCov.result ? <CoverageChart s={sweepCov.result} /> : <Skeleton lines={6} />}
        </Card>
      </div>
    </div>
  );
}

function normalise(f: RcsModelIn): RcsModelIn['stream_mix'] {
  const untok = Math.max(0, 1 - f.token_coverage);
  const tok = f.stream_mix.port + f.stream_mix.origin;
  const port = tok > 0 ? (f.stream_mix.port / tok) * f.token_coverage : f.token_coverage;
  return { port: round3(port), origin: round3(f.token_coverage - port), untokened: round3(untok) };
}
const round3 = (x: number) => Math.round(x * 1000) / 1000;

function ModelForm({ form, setForm }: { form: RcsModelIn; setForm: (f: RcsModelIn) => void }) {
  const slider = (k: keyof RcsModelIn, label: string, min: number, max: number, step: number, fmt: (v: number) => string) => (
    <Field key={k} label={`${label}: ${fmt(form[k] as number)}`}>{(id) => <input id={id} type="range" min={min} max={max} step={step} className="w-full accent-brand-600" value={form[k] as number} onChange={(e) => setForm({ ...form, [k]: Number(e.target.value) })} />}</Field>
  );
  const num = (k: keyof RcsModelIn, label: string, step = 1) => (
    <Field key={k} label={label}>{(id) => <input id={id} type="number" step={step} className="input py-1" value={form[k] as number} onChange={(e) => setForm({ ...form, [k]: Number(e.target.value) })} />}</Field>
  );
  const pct = (v: number) => `${v} %`;
  const frac = (v: number) => `${(v * 100).toFixed(1)} %`;
  const portShare = form.stream_mix.port + form.stream_mix.origin > 0 ? form.stream_mix.port / (form.stream_mix.port + form.stream_mix.origin) : 1;
  return (
    <div className="space-y-3">
      <div className="section-title">Load population</div>
      {slider('avg_loading_pct', 'Average load (% of limit)', 60, 95, 1, pct)}
      {slider('load_spread_pct', 'Load spread (% of limit)', 4, 25, 1, pct)}
      {slider('overload_prob', 'Overloaded share', 0, 0.1, 0.005, frac)}
      <div className="section-title">Streams and tokens</div>
      {slider('token_coverage', 'Trucks with a port or origin token', 0, 1, 0.05, frac)}
      <Field label={`Of tokened trucks, from the port: ${(portShare * 100).toFixed(0)} %`}>{(id) => <input id={id} type="range" min={0} max={1} step={0.05} className="w-full accent-brand-600" value={portShare} onChange={(e) => { const p = Number(e.target.value); setForm({ ...form, stream_mix: { port: p, origin: 1 - p, untokened: 0 } }); }} />}</Field>
      {slider('audit_rate', 'Random audit rate', 0, 0.1, 0.005, frac)}
      <div className="section-title">Measurement errors</div>
      <div className="grid grid-cols-2 gap-2">{num('port_error_pct', 'Port scale %', 0.1)}{num('origin_error_pct', 'Origin scale %', 0.1)}{num('road_error_pct', 'Road WIM %', 0.1)}{num('lane_error_pct', 'Lane scale %', 0.1)}{num('lane_margin_pct', 'Lane margin %', 0.5)}{num('allowance_pct', 'Allowance % (< 5)', 0.5)}</div>
      <div className="flex flex-wrap gap-3 text-sm">
        <label className="inline-flex items-center gap-2"><input type="checkbox" className="h-4 w-4 rounded text-brand-600" checked={form.port_legal_grade} onChange={(e) => setForm({ ...form, port_legal_grade: e.target.checked })} />Port scale legal-grade</label>
        <label className="inline-flex items-center gap-2"><input type="checkbox" className="h-4 w-4 rounded text-brand-600" checked={form.lane_legal_grade} onChange={(e) => setForm({ ...form, lane_legal_grade: e.target.checked })} />Lane scale legal-grade</label>
      </div>
      <div className="section-title">Traffic and time</div>
      <div className="grid grid-cols-2 gap-2">{num('trucks_per_day', 'Trucks / day', 100)}{num('peak_per_hour', 'Peak trucks / h', 10)}{num('stop_minutes', 'Static stop (min)', 0.5)}{num('lane_minutes', 'Lane pass (min)', 0.25)}{num('n', 'Trucks simulated', 10_000)}{num('seed', 'Seed', 1)}</div>
    </div>
  );
}

function Results({ r }: { r: RcsModelOut }) {
  const s = r.shares;
  const cut = s.road_only_static - s.first_station_static;
  const gate = { cut: cut >= 10, fc: r.false_clear_rate <= 0.01, port: s.v2_port_reweigh <= 15 && r.lane_ok };
  const pass = gate.cut && gate.fc && gate.port;
  const p = (x: number) => `${fmtNum(x, 1)} %`;
  return (
    <>
      <Card title="Result" subtitle={`${r.inputs.n.toLocaleString()} trucks · seed ${r.inputs.seed} · ${r.label}`} actions={<Badge tone="violet">{r.label}</Badge>}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          <Stat label="Road-only: static stops" value={p(s.road_only_static)} hint="baseline, absolute rule" />
          <Stat label="Road-only + allowance" value={p(s.road_only_with_allowance)} hint="with discretion allowance" />
          <Stat label="v2: road static (port trucks)" value={p(s.v2_road_static)} tone="teal" delta={`−${fmtNum(s.road_only_static - s.v2_road_static, 1)} pts`} deltaTone="up" />
          <Stat label="v2: port re-weigh" value={p(s.v2_port_reweigh)} tone="amber" hint="moved into the port" />
          <Stat label="First station → lane" value={p(s.first_station_lane)} hint="mixed traffic, rolling" />
          <Stat label="First station → static" value={p(s.first_station_static)} tone={cut >= 10 ? 'green' : 'default'} delta={`−${fmtNum(cut, 1)} pts vs baseline`} deltaTone={cut >= 10 ? 'up' : 'flat'} />
          <Stat label="Later stations → lane" value={p(s.later_station_lane)} hint="audits and mismatches" />
          <Stat label="Later stations → static" value={p(s.later_station_static)} tone="green" hint="repeat stops" />
          <Stat label="Truck-hours saved / day" value={fmtNum(r.truck_hours_saved_per_day, 0)} tone="teal" hint="port trucks, v1 → v2" />
          <Stat label="Truck-hours saved (first station)" value={fmtNum(r.truck_hours_saved_first_station, 0)} tone="teal" hint="mixed traffic" />
          <Stat label="False clears" value={`${fmtNum(r.false_clear_rate * 100, 2)} %`} tone={r.false_clear_rate <= 0.01 ? 'green' : 'red'} hint="target ≤ 1 %" />
          <Stat label="Lane peak vs capacity" value={`${fmtNum(r.lane_peak_per_hour, 0)} / ${fmtNum(r.lane_capacity_per_hour, 0)} /h`} tone={r.lane_ok ? 'green' : 'red'} hint={r.lane_ok ? 'one lane per station is enough' : 'lane saturates at peak'} />
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="card-muted p-3 text-sm">
            <div className="font-medium">Reading it honestly</div>
            <p className="mt-1 text-xs text-ink-600 dark:text-slate-300">v2 does not delete the near-limit checks. It moves them from the public road to the port, where trucks are already in a controlled area. Total re-weighs: {fmtNum(r.total_reweighs_v1, 1)} % (v1) vs {fmtNum(r.total_reweighs_v2, 1)} % (v2). The saving comes from relieving road queues and from fixing overloads where it is cheap. Trucks loaded within the measurement margin of the limit still need a legal-grade reading or the discretion allowance.</p>
          </div>
          <div className="card-muted p-3 text-sm">
            <div className="flex items-center justify-between"><span className="font-medium">Go / no-go gate</span><Badge tone={pass ? 'green' : 'amber'}>{pass ? 'PROCEED' : 'NOT MET'}</Badge></div>
            <ul className="mt-1 space-y-1 text-xs">
              <GateRow ok={gate.cut} text={`Road stop share cut by ≥ 10 points (${fmtNum(cut, 1)} pts)`} />
              <GateRow ok={gate.fc} text={`False-clear rate ≤ 1 % (${fmtNum(r.false_clear_rate * 100, 2)} %)`} />
              <GateRow ok={gate.port} text={`Port re-weigh volume practical (${p(s.v2_port_reweigh)}) and lane within capacity`} />
            </ul>
            <p className="mt-1 text-[11px] text-ink-500">Gate thresholds from the simulation plan; the port re-weigh threshold (≤ 15 % here) is a placeholder until KPA states what its re-weigh lane can absorb.</p>
          </div>
        </div>
        <details className="mt-3 text-xs text-ink-600 dark:text-slate-300"><summary className="cursor-pointer">Assumptions used by the model</summary><ul className="mt-1 list-inside list-disc">{r.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></details>
      </Card>
    </>
  );
}

function GateRow({ ok, text }: { ok: boolean; text: string }) {
  return <li className={`flex items-start gap-1.5 ${ok ? 'text-green-700 dark:text-green-300' : 'text-amber-700 dark:text-amber-300'}`}><span aria-hidden="true">{ok ? '✓' : '✗'}</span><span>{text}</span></li>;
}

function LoadingChart({ s }: { s: RcsSweepOut }) {
  const dark = useDarkMode();
  const t = chartTheme(dark);
  const rows = s.rows.map((r) => ({ label: `${r.value} %`, ...r }));
  return (
    <div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={rows} margin={{ top: 8, right: 8, left: -12, bottom: 0 }} barGap={2}>
          <CartesianGrid stroke={t.grid} vertical={false} /><XAxis dataKey="label" tick={{ fontSize: 11, fill: t.text }} stroke={t.axis} /><YAxis tick={{ fontSize: 11, fill: t.text }} stroke={t.axis} unit="%" />
          <Tooltip contentStyle={t.tooltip} formatter={(v: number) => `${fmtNum(v, 1)} %`} /><Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="road_only_static" name="road-only screening" fill={C.base} radius={[4, 4, 0, 0]} />
          <Bar dataKey="road_only_with_allowance" name="road-only + 5 % allowance" fill={C.allow} radius={[4, 4, 0, 0]} />
          <Bar dataKey="v2_road_static" name="RCS v2 road stops" fill={C.road} radius={[4, 4, 0, 0]} />
          <Bar dataKey="v2_port_reweigh" name="RCS v2 port re-weigh" fill={C.port} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <Table head={['Average load', 'Road-only', 'With allowance', 'v2 road stops', 'v2 port re-weigh', 'Truck-hours saved / day']} dense>
        {s.rows.map((r) => <tr key={r.value} className="tr"><td className="td">{r.value} %</td><td className="td tabular-nums">{fmtNum(r.road_only_static, 1)} %</td><td className="td tabular-nums">{fmtNum(r.road_only_with_allowance, 1)} %</td><td className="td tabular-nums">{fmtNum(r.v2_road_static, 1)} %</td><td className="td tabular-nums">{fmtNum(r.v2_port_reweigh, 1)} %</td><td className="td tabular-nums">about {fmtNum(r.truck_hours_saved_per_day, 0)}</td></tr>)}
      </Table>
    </div>
  );
}

function CoverageChart({ s }: { s: RcsSweepOut }) {
  const dark = useDarkMode();
  const t = chartTheme(dark);
  const rows = s.rows.map((r) => ({ label: `${Math.round(r.value * 100)} %`, ...r }));
  return (
    <div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={rows} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid stroke={t.grid} vertical={false} /><XAxis dataKey="label" tick={{ fontSize: 11, fill: t.text }} stroke={t.axis} /><YAxis tick={{ fontSize: 11, fill: t.text }} stroke={t.axis} unit="%" />
          <Tooltip contentStyle={t.tooltip} formatter={(v: number) => `${fmtNum(v, 1)} %`} /><Legend wrapperStyle={{ fontSize: 11 }} />
          <Line dataKey="road_only_static" name="road-only baseline (static)" stroke={C.base} strokeWidth={2} strokeDasharray="5 3" dot={{ r: 3 }} />
          <Line dataKey="first_station_lane" name="sent to the lane" stroke={C.lane} strokeWidth={2} dot={{ r: 4 }} />
          <Line dataKey="first_station_static" name="sent to a static scale" stroke={C.stat} strokeWidth={2} dot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
      <Table head={['Tokened trucks', 'Sent to lane', 'Sent to static', 'Road-only baseline', 'Truck-hours saved / day']} dense>
        {s.rows.map((r) => <tr key={r.value} className="tr"><td className="td">{Math.round(r.value * 100)} %</td><td className="td tabular-nums">{fmtNum(r.first_station_lane, 1)} %</td><td className="td tabular-nums">{fmtNum(r.first_station_static, 1)} %</td><td className="td tabular-nums">{fmtNum(r.road_only_static, 1)} %</td><td className="td tabular-nums">about {fmtNum(r.truck_hours_saved_first_station, 0)}</td></tr>)}
      </Table>
    </div>
  );
}
