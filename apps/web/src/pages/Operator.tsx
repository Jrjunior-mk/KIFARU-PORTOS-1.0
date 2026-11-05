import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { fleet as fleetApi, rcs as rcsApi, stations as stationsApi, weighing as weighingApi } from '../api/endpoints';
import type { CalibrationIn, CalibrationMethod, LaneOut, ReleaseOrderIn, SensorOut, SimulateIn, StationOut, WeighingOut } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { LaneTypeBadge, RouteBadge, StationKindBadge, StreamBadge, TokenRefLink } from '../components/rcs';
import { Badge, Card, Confirm, DecisionBadge, Empty, ErrorBanner, Field, KV, Notice, PageHeader, SourceBadge, Spinner, Stat, StatusDot, Table, Tabs, Toggle } from '../components/ui';
import { AxleTable, DecisionPanel, IdentityPanel, SensorHealthGrid, TicketCard, WeighingHistoryTable } from '../components/weighing';
import { useLiveEvents } from '../hooks/useLiveEvents';
import { useMutation, useQuery } from '../hooks/useQuery';
import { fmtAgo, fmtDateTime, fmtKg, kmh, titleCase } from '../lib/format';
import { fmtUsd, laneTypeLabel, nodeKindForLane, nodeKindLabel, sourceLabel } from '../lib/rcs';

const LOAD_SENSORS = new Set(['piezo_quartz', 'piezo_polymer', 'bending_plate', 'strain_gauge']);
const DEFAULT_SIM: Omit<SimulateIn, 'lane_id'> = { count: 1, overload_prob: 0.15, sensor_fault_prob: 0.03, anpr_misread_prob: 0.05, rfid_missing_prob: 0.1, clone_prob: 0.01, unregistered_prob: 0.05, pavement_temp_c: 32, vehicle_id: null, force_gvm_kg: null, seed: null, oversize_prob: 0.02, lifted_axle_prob: 0.02 };
const DIMENSION_NODES = new Set(['verification_lane', 'port_gateout']);

export default function Operator() {
  const { me } = useAuth();
  const stationsQ = useQuery(() => stationsApi.list(), [], { pollMs: 60_000 });
  const vehiclesQ = useQuery(() => fleetApi.vehicles(), []);
  const [stationId, setStationId] = useState<string>('');
  const [laneId, setLaneId] = useState<string>('');
  const station = useMemo(() => stationsQ.data?.find((s) => s.id === stationId), [stationsQ.data, stationId]);
  const lanes = useMemo(() => (station?.lanes ?? []).slice().sort((a, b) => a.lane_no - b.lane_no), [station]);
  const lane = lanes.find((l) => l.id === laneId);
  useEffect(() => { if (!stationId && stationsQ.data?.length) setStationId(stationsQ.data[0].id); }, [stationsQ.data, stationId]);
  useEffect(() => { if (lanes.length && !lanes.some((l) => l.id === laneId)) setLaneId(lanes.find((l) => l.type !== 'static')?.id ?? lanes[0].id); }, [lanes, laneId]);

  const eventsQ = useQuery(() => weighingApi.events({ station_id: stationId, limit: 100 }), [stationId], { enabled: !!stationId, pollMs: 30_000 });
  const [params] = useSearchParams();
  const [selectedId, setSelectedId] = useState<string | null>(params.get('event'));
  const live = useLiveEvents(['clearance.decided', 'sensor.health', 'truck.released', 'truck.diverted'], stationId || null, 100, (ev) => {
    if (ev.type === 'clearance.decided') { void eventsQ.refetch(); setSelectedId((ev.payload as { weighing_event_id?: string }).weighing_event_id ?? null); }
    if (ev.type === 'sensor.health') void stationsQ.refetch();
  });
  const laneEvents = useMemo(() => (eventsQ.data ?? []).filter((e) => !laneId || e.lane_id === laneId), [eventsQ.data, laneId]);
  const selected = useMemo(() => laneEvents.find((e) => e.id === selectedId) ?? laneEvents[0] ?? null, [laneEvents, selectedId]);

  const [tab, setTab] = useState<'reading' | 'decision' | 'identity' | 'token' | 'dimensions' | 'verify' | 'release' | 'ticket'>('reading');
  const selNode = selected ? (selected.node_kind ?? nodeKindForLane(lanes.find((l) => l.id === selected.lane_id)?.type)) : null;
  const showDims = !!selNode && DIMENSION_NODES.has(selNode);
  const isRed = selected?.decision?.decision === 'RED';
  useEffect(() => { if ((tab === 'dimensions' && !showDims) || (tab === 'release' && !isRed)) setTab('reading'); }, [tab, showDims, isRed]);

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Operations" title="Weighbridge Operator Console" subtitle={<>{me?.full_name} · live {live.status} · {live.hasLive ? 'live measurements present' : 'simulated passes only'}</>} actions={
        <>
          <Field label="Station">{(id) => <select id={id} className="input w-auto py-1" value={stationId} onChange={(e) => setStationId(e.target.value)}>{(stationsQ.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.code} — {s.name}</option>)}</select>}</Field>
          <Field label="Lane">{(id) => <select id={id} className="input w-auto py-1" value={laneId} onChange={(e) => setLaneId(e.target.value)}>{lanes.map((l) => <option key={l.id} value={l.id}>Lane {l.lane_no} · {laneTypeLabel(l.type)} · {l.direction}</option>)}</select>}</Field>
        </>} />
      <ErrorBanner error={stationsQ.error ?? eventsQ.error} />
      {station && lane && (
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <StationKindBadge kind={station.kind} />
          <LaneTypeBadge type={lane.type} legalGrade={lane.legal_grade} />
          <span className="flex items-center gap-1"><StatusDot status={station.status} /> station {station.status}</span>
          <span className="flex items-center gap-1"><StatusDot status={lane.status} /> lane {lane.status}</span>
          <CalibrationBadge validTo={lane.calibration_valid_to} label="lane calibration" />
          <span className="text-ink-500">device {lane.device_id ?? '—'} · {lane.sensors.length} sensors · {nodeKindLabel(nodeKindForLane(lane.type))}</span>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-1">
          {lane && lane.type !== 'static' ? <SimulatePanel lane={lane} station={station!} vehicles={vehiclesQ.data ?? []} onDone={(evs) => { void eventsQ.refetch(); if (evs[0]) setSelectedId(evs[0].id); }} /> : <Card title="Simulate pass"><Empty>Select a WIM lane to simulate passes. Static lanes receive verifications only.</Empty></Card>}
          {lane && <SensorPanel lane={lane} onChanged={() => void stationsQ.refetch()} />}
        </div>

        <div className="space-y-4 xl:col-span-2">
          <Card title={selected ? <span className="flex flex-wrap items-center gap-2">Latest pass <SourceBadge source={selected.source} /> <StreamBadge stream={selected.stream} /> <span className="text-xs font-normal text-ink-500">{fmtDateTime(selected.occurred_at)} · {fmtAgo(selected.occurred_at)} · {nodeKindLabel(selNode)}</span></span> : 'Latest pass'}
            actions={selected && <DecisionBadge decision={selected.decision?.decision} />}>
            {!selected ? <Empty>No weighing events on this lane yet. Use “Simulate pass” or wait for a live pass.</Empty> : (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <Stat label="GVM" value={fmtKg(selected.gvm_kg)} hint={`± ${fmtKg(selected.gvm_uncertainty_kg)} (k=2)`} />
                  <Stat label="Axles / class" value={`${selected.axle_count} · ${selected.class_code ?? '—'}`} hint={selected.detected_axle_config ?? 'config n/a'} />
                  <Stat label="Speed" value={kmh(selected.speed_mps)} hint={selected.pavement_temp_c !== null ? `pavement ${selected.pavement_temp_c.toFixed(1)} °C` : undefined} />
                  <Stat label="Plate" value={selected.plate ?? 'unknown'} hint={selected.identity ? `${selected.identity.method} · ${(selected.identity.confidence * 100).toFixed(0)} %` : 'no identity'} />
                </div>
                <div className="card-muted flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
                  <span className="section-title">Route</span>
                  <RouteBadge route={selected.decision?.route} decision={selected.decision?.decision} nodeKind={selNode} withInstruction />
                  {(selected.token_ref || selected.decision?.token_checked_ref) && <span className="text-xs text-ink-500">token <TokenRefLink tokenRef={selected.decision?.token_checked_ref ?? selected.token_ref} /></span>}
                  {selected.decision?.token_issued_ref && <Badge tone="teal">token issued</Badge>}
                </div>
                {selected.quality_flags.length > 0 && <div className="flex flex-wrap gap-1 text-xs">quality flags: {selected.quality_flags.map((f) => <Badge key={f} tone="amber">{f}</Badge>)}</div>}
                <Tabs value={tab} onChange={setTab} tabs={[{ id: 'reading', label: 'Axle readings' }, { id: 'decision', label: 'Decision' }, { id: 'identity', label: 'Identity' }, { id: 'token', label: 'Token' }, ...(showDims ? [{ id: 'dimensions' as const, label: 'Dimensions' }] : []), { id: 'verify', label: 'Static verify / override' }, ...(isRed ? [{ id: 'release' as const, label: 'Release order' }] : []), { id: 'ticket', label: 'Ticket' }]} />
                {tab === 'reading' && <div className="space-y-3"><AxleTable ev={selected} /><h4 className="label">Sensor health at the time of the pass</h4><SensorHealthGrid health={selected.sensor_health} /></div>}
                {tab === 'decision' && <DecisionPanel d={selected.decision} />}
                {tab === 'identity' && <IdentityPanel ev={selected} />}
                {tab === 'token' && <TokenTab ev={selected} />}
                {tab === 'dimensions' && <DimensionsTab ev={selected} />}
                {tab === 'verify' && <VerifyPanel ev={selected} onChanged={() => void eventsQ.refetch()} />}
                {tab === 'release' && <ReleaseOrderPanel ev={selected} onChanged={() => void eventsQ.refetch()} />}
                {tab === 'ticket' && (selected.decision?.ticket_id ? <TicketCard ticketId={selected.decision.ticket_id} /> : <Empty>No ticket issued for this pass</Empty>)}
              </div>
            )}
          </Card>

          <Card title="Lane history" subtitle="GET /weighing/events — latest 100 for this station, filtered by lane">
            <WeighingHistoryTable events={laneEvents} onSelect={(e) => setSelectedId(e.id)} selectedId={selected?.id} />
          </Card>

          <Card title="Verification history" subtitle="Passes with a static-scale record (legal reference) or an operator override">
            <VerificationHistory events={eventsQ.data ?? []} />
          </Card>
        </div>
      </div>
    </div>
  );
}

function CalibrationBadge({ validTo, label }: { validTo: string | null; label: string }) {
  if (!validTo) return <Badge tone="red" title="No calibration record">{label}: missing</Badge>;
  const days = (new Date(validTo).getTime() - Date.now()) / 86_400_000;
  if (days < 0) return <Badge tone="red">{label}: expired {fmtAgo(validTo)}</Badge>;
  if (days < 30) return <Badge tone="amber">{label}: expires in {Math.ceil(days)} d</Badge>;
  return <Badge tone="green">{label}: valid {Math.ceil(days)} d</Badge>;
}

function SimulatePanel({ lane, station, vehicles, onDone }: { lane: LaneOut; station: StationOut; vehicles: import('../api/types').VehicleOut[]; onDone: (evs: WeighingOut[]) => void }) {
  const [opts, setOpts] = useState(DEFAULT_SIM);
  const sim = useMutation((body: SimulateIn) => weighingApi.simulate(body));
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const r = await sim.run({ ...opts, lane_id: lane.id, vehicle_id: opts.vehicle_id || null, force_gvm_kg: opts.force_gvm_kg || null, seed: opts.seed ?? null });
    if (r) onDone(r);
  };
  const fe = sim.error?.fieldErrors ?? {};
  const prob = (key: keyof typeof DEFAULT_SIM, label: string) => (
    <Field key={key} label={`${label} (${Math.round((opts[key] as number) * 100)} %)`} error={fe[key]}>
      {(id) => <input id={id} type="range" min={0} max={1} step={0.01} className="w-full accent-brand-600" value={opts[key] as number} onChange={(e) => setOpts({ ...opts, [key]: Number(e.target.value) })} />}
    </Field>
  );
  return (
    <Card title="Simulate pass" subtitle={`POST /weighing/simulate · ${station.code} lane ${lane.lane_no} · output is tagged SIMULATED`}>
      <form onSubmit={submit} className="space-y-3">
        <Notice tone="warn">Simulator output is synthetic and is labelled SIMULATED on every record and ticket.</Notice>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Passes" error={fe.count}>{(id) => <input id={id} type="number" min={1} max={50} className="input" value={opts.count} onChange={(e) => setOpts({ ...opts, count: Number(e.target.value) })} />}</Field>
          <Field label="Pavement °C" error={fe.pavement_temp_c}>{(id) => <input id={id} type="number" min={-10} max={80} step={0.5} className="input" value={opts.pavement_temp_c} onChange={(e) => setOpts({ ...opts, pavement_temp_c: Number(e.target.value) })} />}</Field>
        </div>
        {prob('overload_prob', 'Overload')}
        {prob('sensor_fault_prob', 'Sensor fault')}
        {prob('anpr_misread_prob', 'ANPR misread')}
        {prob('rfid_missing_prob', 'RFID missing')}
        {prob('clone_prob', 'Cloned tag')}
        {prob('unregistered_prob', 'Unregistered vehicle')}
        {prob('oversize_prob', 'Oversize (dimension portal)')}
        {prob('lifted_axle_prob', 'Lifted axle')}
        <Field label="Specific vehicle" hint="Optional — otherwise a random active vehicle is chosen">{(id) => <select id={id} className="input" value={opts.vehicle_id ?? ''} onChange={(e) => setOpts({ ...opts, vehicle_id: e.target.value || null })}><option value="">random</option>{vehicles.map((v) => <option key={v.id} value={v.id}>{v.plate} · {v.axle_config} · {v.body_type}</option>)}</select>}</Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Force GVM (kg)" error={fe.force_gvm_kg}>{(id) => <input id={id} type="number" min={1000} max={90000} className="input" placeholder="auto" value={opts.force_gvm_kg ?? ''} onChange={(e) => setOpts({ ...opts, force_gvm_kg: e.target.value ? Number(e.target.value) : null })} />}</Field>
          <Field label="Seed" error={fe.seed}>{(id) => <input id={id} type="number" className="input" placeholder="random" value={opts.seed ?? ''} onChange={(e) => setOpts({ ...opts, seed: e.target.value ? Number(e.target.value) : null })} />}</Field>
        </div>
        <button className="btn-primary w-full" disabled={sim.busy} type="submit">{sim.busy ? 'Running simulator…' : `Simulate ${opts.count} pass${opts.count > 1 ? 'es' : ''}`}</button>
        <ErrorBanner error={sim.error} />
        {sim.result && <p className="text-xs text-slate-500">Last run: {sim.result.length} pass(es) → {sim.result.map((r) => r.decision?.decision ?? '?').join(', ')}</p>}
      </form>
    </Card>
  );
}

function SensorPanel({ lane, onChanged }: { lane: LaneOut; onChanged: () => void }) {
  const [sensorId, setSensorId] = useState<string>('');
  const sensor = lane.sensors.find((s) => s.id === sensorId) ?? null;
  const health = useMutation((args: { id: string; status: 'ok' | 'degraded' | 'fault'; reason: string | null }) => stationsApi.sensorHealth(args.id, { status: args.status, reason: args.reason }));
  const [reason, setReason] = useState('');
  return (
    <Card title="Lane sensors" subtitle="Health per sensor · POST /stations/sensors/{id}/health · calibration per load sensor">
      <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">
        {lane.sensors.slice().sort((a, b) => (a.channel ?? 0) - (b.channel ?? 0)).map((s) => (
          <li key={s.id}>
            <button className={`flex w-full items-center justify-between rounded border px-2 py-1 text-left text-xs ${sensorId === s.id ? 'border-brand-500 ring-1 ring-brand-500' : 'border-slate-200 dark:border-slate-800'}`} onClick={() => setSensorId(s.id)} aria-pressed={sensorId === s.id}>
              <span className="min-w-0"><span className="block truncate font-medium">{titleCase(s.kind)} <span className="text-slate-400">ch{s.channel}</span></span><span className="block text-slate-500">{s.install_position_m !== null ? `${s.install_position_m} m` : ''} {s.serial ?? ''}</span></span>
              <span className="flex flex-col items-end gap-0.5"><Badge tone={s.status === 'ok' ? 'green' : s.status === 'degraded' ? 'amber' : 'red'}>{s.status}</Badge>{LOAD_SENSORS.has(s.kind) && <CalDot s={s} />}</span>
            </button>
          </li>
        ))}
      </ul>
      {sensor && (
        <div className="mt-3 space-y-3 rounded border border-slate-200 p-3 dark:border-slate-800">
          <div className="text-sm font-medium">{titleCase(sensor.kind)} · channel {sensor.channel} {sensor.health_reason && <span className="text-xs text-slate-500">— {sensor.health_reason}</span>}</div>
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Reason">{(id) => <input id={id} className="input w-48" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="optional" />}</Field>
            {(['ok', 'degraded', 'fault'] as const).map((st) => (
              <button key={st} className="btn-secondary text-xs" disabled={health.busy} onClick={async () => { if (await health.run({ id: sensor.id, status: st, reason: reason || null })) { setReason(''); onChanged(); } }}>Set {st}</button>
            ))}
          </div>
          <ErrorBanner error={health.error} />
          {LOAD_SENSORS.has(sensor.kind) ? <CalibrationSection sensor={sensor} onChanged={onChanged} /> : <p className="text-xs text-slate-500">Calibration records apply to load sensors (piezo, bending plate, strain gauge).</p>}
        </div>
      )}
    </Card>
  );
}

function CalDot({ s }: { s: SensorOut }) {
  if (!s.calibration_valid_to) return <span className="text-[10px] text-rose-600">no cal</span>;
  const ok = new Date(s.calibration_valid_to).getTime() > Date.now();
  return <span className={`text-[10px] ${ok ? 'text-brand-700 dark:text-brand-300' : 'text-rose-600'}`}>{ok ? 'cal ok' : 'cal expired'}</span>;
}

function CalibrationSection({ sensor, onChanged }: { sensor: SensorOut; onChanged: () => void }) {
  const list = useQuery(() => stationsApi.calibrations(sensor.id), [sensor.id]);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState<CalibrationIn>({ method: 'reference_vehicle', reference_mass_kg: 40000, gain: 1, offset: 0, temp_coeff_per_c: 0, reference_temp_c: 25, uncertainty_pct: 5, valid_days: 180, notes: '' });
  const add = useMutation((b: CalibrationIn) => stationsApi.addCalibration(sensor.id, b));
  const fe = add.error?.fieldErrors ?? {};
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (await add.run({ ...form, notes: form.notes || null, reference_mass_kg: form.reference_mass_kg || null })) { setShow(false); void list.refetch(); onChanged(); }
  };
  const num = (k: keyof CalibrationIn, label: string, step = 'any') => (
    <Field key={k} label={label} error={fe[k]}>{(id) => <input id={id} type="number" step={step} className="input" value={(form[k] as number) ?? ''} onChange={(e) => setForm({ ...form, [k]: e.target.value === '' ? null : Number(e.target.value) })} />}</Field>
  );
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between"><h4 className="label mb-0">Calibration · {list.data?.length ?? 0} record(s)</h4><button className="btn-secondary px-2 py-1 text-xs" onClick={() => setShow((s) => !s)}>{show ? 'Cancel' : 'Add calibration'}</button></div>
      {show && (
        <form onSubmit={submit} className="grid grid-cols-2 gap-2 rounded border border-slate-200 p-2 dark:border-slate-800">
          <Field label="Method" error={fe.method}>{(id) => <select id={id} className="input" value={form.method} onChange={(e) => setForm({ ...form, method: e.target.value as CalibrationMethod })}>{['reference_vehicle', 'static_scale_comparison', 'shunt', 'bench'].map((m) => <option key={m} value={m}>{titleCase(m)}</option>)}</select>}</Field>
          {num('reference_mass_kg', 'Reference mass (kg)', '1')}
          {num('gain', 'Gain')}{num('offset', 'Offset')}{num('temp_coeff_per_c', 'Temp coeff /°C')}{num('reference_temp_c', 'Ref temp °C')}{num('uncertainty_pct', 'Uncertainty %')}{num('valid_days', 'Valid days', '1')}
          <div className="col-span-2"><Field label="Notes">{(id) => <input id={id} className="input" value={form.notes ?? ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} />}</Field></div>
          <div className="col-span-2 flex items-center gap-2"><button className="btn-primary" disabled={add.busy} type="submit">Save calibration</button><ErrorBanner error={add.error} /></div>
        </form>
      )}
      {list.loading ? <Spinner /> : list.data && list.data.length > 0 ? (
        <Table head={['Valid from', 'Valid to', 'Method', 'Gain / offset', 'U %']} dense>
          {list.data.map((c) => <tr key={c.id} className="tr"><td className="td">{fmtDateTime(c.valid_from)}</td><td className="td">{fmtDateTime(c.valid_to)}</td><td className="td">{titleCase(c.method)}</td><td className="td tabular-nums">{c.gain} / {c.offset}</td><td className="td">{c.uncertainty_pct}</td></tr>)}
        </Table>
      ) : <Empty>No calibration records for this sensor</Empty>}
    </div>
  );
}

function VerifyPanel({ ev, onChanged }: { ev: WeighingOut; onChanged: () => void }) {
  const { me } = useAuth();
  const [staticKg, setStaticKg] = useState<number>(ev.decision?.static_verified_gvm_kg ?? ev.gvm_kg);
  const [notes, setNotes] = useState('');
  const [reason, setReason] = useState('');
  const [confirm, setConfirm] = useState(false);
  useEffect(() => { setStaticKg(ev.decision?.static_verified_gvm_kg ?? ev.gvm_kg); }, [ev.id, ev.gvm_kg, ev.decision?.static_verified_gvm_kg]);
  const verify = useMutation(() => weighingApi.staticVerify(ev.id, { static_gvm_kg: staticKg, notes: notes || null }));
  const override = useMutation(() => weighingApi.overrideRelease(ev.id, { reason }));
  const d = ev.decision;
  if (!d) return <Empty>No decision to verify</Empty>;
  const err = ev.gvm_kg - staticKg;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <form className="space-y-2" onSubmit={async (e) => { e.preventDefault(); if (await verify.run()) onChanged(); }}>
        <h4 className="font-medium">Static-scale verification</h4>
        <p className="text-xs text-slate-500">Records the legal static weight for this {d.decision} pass and issues a <b>static_certified</b> ticket (replaces the pre-screen ticket). WIM error is logged for accuracy benchmarking.</p>
        <Field label="Static GVM (kg)" required error={verify.error?.fieldErrors.static_gvm_kg}>{(id) => <input id={id} type="number" min={500} max={90000} className="input" value={staticKg} onChange={(e) => setStaticKg(Number(e.target.value))} required />}</Field>
        <p className="text-xs text-slate-500">WIM {fmtKg(ev.gvm_kg)} vs static {fmtKg(staticKg)} → error {err > 0 ? '+' : ''}{fmtKg(err)} ({staticKg ? ((err / staticKg) * 100).toFixed(2) : '—'} %)</p>
        <Field label="Notes">{(id) => <input id={id} className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
        <button className="btn-primary" disabled={verify.busy} type="submit">Record static verification</button>
        <ErrorBanner error={verify.error} />
        {d.static_verified_gvm_kg !== null && <Notice tone="ok">Static verified: {fmtKg(d.static_verified_gvm_kg)} · ticket {d.ticket_type}</Notice>}
      </form>
      <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); setConfirm(true); }}>
        <h4 className="font-medium">Operator override (release)</h4>
        <p className="text-xs text-slate-500">Requires MFA-verified session and an existing static verification. The original decision is never deleted; the override is written to the signed ledger and audit log.</p>
        {me && me.mfa_enabled && !me.mfa_verified && <Notice tone="warn">Your session is not MFA-verified. Sign out and sign in with your authenticator code to override.</Notice>}
        {!me?.mfa_enabled && <Notice>MFA is not enrolled on this account; the server will enforce MFA once it is enabled.</Notice>}
        <Field label="Reason (min 10 chars)" required error={override.error?.fieldErrors.reason}>{(id) => <textarea id={id} className="input" rows={3} minLength={10} maxLength={300} required value={reason} onChange={(e) => setReason(e.target.value)} />}</Field>
        <button className="btn-danger" disabled={override.busy || d.static_verified_gvm_kg === null} type="submit" title={d.static_verified_gvm_kg === null ? 'Static verification required first' : undefined}>Override and release</button>
        <ErrorBanner error={override.error} />
        {d.override_reason && <Notice tone="warn">Overridden: {d.override_reason}</Notice>}
        <Confirm open={confirm} title="Confirm override" danger confirmLabel="Override" body={<span>Release {ev.plate ?? 'this vehicle'} despite a {d.decision} decision? Reason: “{reason}”.</span>} onCancel={() => setConfirm(false)} onConfirm={async () => { setConfirm(false); if (await override.run()) onChanged(); }} />
      </form>
    </div>
  );
}

function TokenTab({ ev }: { ev: WeighingOut }) {
  const d = ev.decision;
  const checked = d?.token_checked_ref ?? ev.token_ref ?? null;
  const issued = d?.token_issued_ref ?? null;
  const tm = d?.margins.token;
  const tokenRules = (d?.rules_fired ?? []).filter((r) => r.rule.startsWith('TOKEN'));
  if (!checked && !issued && !tm) return <Empty>No Load Compliance Token was checked or issued on this pass. Untokened trucks are cleared on the absolute rule and receive a road token on GREEN.</Empty>;
  const items: [string, ReactNode][] = [
    ['Token checked', checked ? <TokenRefLink tokenRef={checked} /> : 'none (untokened truck)'],
    ['Token issued', issued ? <span className="flex items-center gap-2"><TokenRefLink tokenRef={issued} /><Badge tone="teal">valid downstream</Badge></span> : 'none'],
  ];
  if (tm) {
    items.push(['Source / tier', `${sourceLabel(tm.source)} · tier ${tm.trust_tier ?? '—'}`]);
    items.push(['Token GVM vs measured', <span className="tabular-nums">{fmtKg(tm.token_gvm_kg)} vs {fmtKg(tm.measured_kg ?? ev.gvm_kg)} → {tm.diff_kg !== undefined && tm.diff_kg > 0 ? '+' : ''}{fmtKg(tm.diff_kg)} (tolerance ± {fmtKg(tm.tolerance_kg)}{tm.tolerance_pct !== undefined ? `, ${(tm.tolerance_pct * 100).toFixed(0)} %` : ''})</span>]);
    items.push(['Consistency', <Badge tone={tm.consistent ? 'green' : 'amber'}>{tm.consistent ? 'consistent — weight unchanged since issue' : 'inconsistent — diverted to the lane'}</Badge>]);
  }
  return (
    <div className="space-y-3">
      <KV items={items} />
      {tokenRules.length > 0 && <ul className="space-y-1 text-sm">{tokenRules.map((r) => <li key={r.rule} className="flex gap-2"><Badge tone={r.severity === 'RED' ? 'red' : r.severity === 'AMBER' ? 'amber' : 'slate'}>{r.severity}</Badge><span><span className="mono">{r.rule}</span> — {r.detail}</span></li>)}</ul>}
      <p className="text-xs text-ink-500">With a valid, consistent token the near-limit AMBER rules are downgraded: the road reading only has to confirm the weight is unchanged since the first trusted weighing (Reg 10(2)).</p>
    </div>
  );
}

function DimensionsTab({ ev }: { ev: WeighingOut }) {
  const dm = ev.decision?.margins.dimensions;
  const limits = { l: dm?.max_length_m ?? 22, w: dm?.max_width_m ?? 2.65, h: dm?.max_height_m ?? 4.3 };
  const rows: { k: string; v: number | null | undefined; lim: number }[] = [
    { k: 'Length', v: ev.length_m ?? dm?.length_m, lim: limits.l }, { k: 'Width', v: ev.width_m ?? dm?.width_m, lim: limits.w }, { k: 'Height', v: ev.height_m ?? dm?.height_m, lim: limits.h },
  ];
  const lifted = ev.lifted_axle ?? dm?.lifted_axle ?? false;
  if (rows.every((r) => r.v === null || r.v === undefined)) return <Empty>No dimension scan on this pass (the LiDAR portal is fitted on verification and port gate-out lanes).</Empty>;
  return (
    <div className="space-y-3">
      <Table head={['Parameter', 'Measured', 'Limit', 'Status']} dense>
        {rows.map((r) => { const over = r.v !== null && r.v !== undefined && r.v > r.lim; return <tr key={r.k} className="tr"><td className="td">{r.k}</td><td className="td tabular-nums font-medium">{r.v !== null && r.v !== undefined ? `${r.v.toFixed(2)} m` : '—'}</td><td className="td tabular-nums">{r.lim.toFixed(2)} m</td><td className="td"><Badge tone={over ? (dm?.permit_ref ? 'blue' : 'red') : 'green'}>{over ? (dm?.permit_ref ? `permitted (${dm.permit_ref})` : 'over') : 'ok'}</Badge></td></tr>; })}
        <tr className="tr"><td className="td">Lifted axle</td><td className="td" colSpan={2}>{lifted ? 'detected by side LiDAR / camera classification' : 'none detected'}</td><td className="td"><Badge tone={lifted ? 'amber' : 'green'}>{lifted ? 'mismatch' : 'ok'}</Badge></td></tr>
      </Table>
      <p className="text-xs text-ink-500">Dimension and lifted-axle checks are what high-speed WIM cannot provide; a dimension breach without a valid special-load permit is RED.</p>
    </div>
  );
}

function ReleaseOrderPanel({ ev, onChanged }: { ev: WeighingOut; onChanged: () => void }) {
  const { me } = useAuth();
  const d = ev.decision!;
  const [form, setForm] = useState<ReleaseOrderIn>({ weighing_event_id: ev.id, static_gvm_kg: d.static_verified_gvm_kg ?? null, transit: false, hazardous: false, perishable: false, journey_ref: '', notes: '' });
  useEffect(() => { setForm((f) => ({ ...f, weighing_event_id: ev.id, static_gvm_kg: ev.decision?.static_verified_gvm_kg ?? null })); }, [ev.id, ev.decision?.static_verified_gvm_kg]);
  const existing = useQuery(() => rcsApi.releaseOrders({ vehicle_id: ev.vehicle_id ?? undefined }), [ev.vehicle_id], { enabled: !!ev.vehicle_id });
  const mine = (existing.data ?? []).filter((o) => o.weighing_event_id === ev.id);
  const issue = useMutation((b: ReleaseOrderIn) => rcsApi.issueReleaseOrder(b));
  const [confirm, setConfirm] = useState(false);
  const fe = issue.error?.fieldErrors ?? {};
  const order = issue.result ?? mine[0] ?? null;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); setConfirm(true); }}>
        <h4 className="font-medium">Issue release order (Reg 14)</h4>
        <p className="text-xs text-ink-500">An authorised officer e-signs the ticket and release order for this RED pass (Reg 3(4), Reg 11(3)). The registry computes the fee from the Third Schedule and the allowance policy; a second overload in the same journey triples the fee.</p>
        {d.fee_preview_usd !== null && d.fee_preview_usd !== undefined && <Notice tone="warn">Indicative fee preview: <b>{fmtUsd(d.fee_preview_usd)}</b> before detention and multipliers.</Notice>}
        {me && me.mfa_enabled && !me.mfa_verified && <Notice tone="warn">Your session is not MFA-verified. Sign in with your authenticator code to e-sign.</Notice>}
        <Field label="Static GVM (kg)" hint="Legal reference; leave empty to use the recorded static verification" error={fe.static_gvm_kg}>{(id) => <input id={id} type="number" min={500} max={90000} className="input" value={form.static_gvm_kg ?? ''} onChange={(e) => setForm({ ...form, static_gvm_kg: e.target.value ? Number(e.target.value) : null })} />}</Field>
        <div className="flex flex-wrap gap-3">
          <Toggle label="Transit cargo (e-seal, customs)" checked={form.transit} onChange={(v) => setForm({ ...form, transit: v })} />
          <Toggle label="Hazardous" checked={form.hazardous} onChange={(v) => setForm({ ...form, hazardous: v })} />
          <Toggle label="Perishable" checked={form.perishable} onChange={(v) => setForm({ ...form, perishable: v })} />
        </div>
        <Field label="Journey reference" error={fe.journey_ref}>{(id) => <input id={id} className="input" value={form.journey_ref ?? ''} onChange={(e) => setForm({ ...form, journey_ref: e.target.value })} placeholder="optional — trip plan / manifest ref" />}</Field>
        <Field label="Notes" error={fe.notes}>{(id) => <textarea id={id} className="input" rows={2} value={form.notes ?? ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} />}</Field>
        <button className="btn-danger" type="submit" disabled={issue.busy || !!order}>{order ? 'Release order issued' : 'E-sign and issue release order'}</button>
        <ErrorBanner error={issue.error} />
        <Confirm open={confirm} title="E-sign release order" danger confirmLabel="Issue" body={<span>Issue a Reg 14 release order for {ev.plate ?? 'this vehicle'} at {fmtKg(form.static_gvm_kg ?? d.static_verified_gvm_kg ?? ev.gvm_kg)}? The order is signed with your officer identity and written to the ledger.</span>} onCancel={() => setConfirm(false)} onConfirm={async () => { setConfirm(false); if (await issue.run({ ...form, journey_ref: form.journey_ref || null, notes: form.notes || null })) { void existing.refetch(); onChanged(); } }} />
      </form>
      <div className="space-y-2">
        <h4 className="font-medium">Issued order</h4>
        {existing.loading && <Spinner />}
        {!order && !existing.loading && <Empty>No release order for this pass yet</Empty>}
        {order && (
          <div className="card-muted p-3">
            <div className="flex flex-wrap items-center gap-2"><span className="mono font-semibold">{order.order_ref}</span><Badge tone={order.status === 'issued' ? 'red' : order.status === 'paid' ? 'amber' : 'green'}>{order.status}</Badge>{order.repeat_offence && <Badge tone="red">repeat offence ×{order.fee_multiplier}</Badge>}{order.customs_notified && <Badge tone="violet">customs notified</Badge>}</div>
            <KV items={[
              ['Overload', <span className="font-semibold text-decision-red">{fmtKg(order.overload_kg)}</span>], ['Allowed + allowance', `${fmtKg(order.allowed_gvm_kg)} + ${fmtKg(order.allowance_kg)}`],
              ['Fee', `${fmtUsd(order.fee_usd)} × ${order.fee_multiplier}`], ['Detention', `${order.detention_days} d · ${fmtUsd(order.detention_usd)}`], ['Total', <span className="text-base font-semibold">{fmtUsd(order.total_usd)}</span>],
              ['Officer', order.officer_name ?? order.officer_user_id], ['Valid until', fmtDateTime(order.valid_until)],
            ]} />
            <a className="mt-2 inline-block text-xs underline" href="/registry?tab=orders">Open in registry</a>
          </div>
        )}
      </div>
    </div>
  );
}

function VerificationHistory({ events }: { events: WeighingOut[] }) {
  const rows = events.filter((e) => e.decision && (e.decision.static_verified_gvm_kg !== null || e.decision.override_reason || e.decision.ticket_type === 'static_certified'));
  if (!rows.length) return <Empty>No static verifications or overrides yet for this station</Empty>;
  return (
    <Table head={['Time', 'Plate', 'WIM GVM', 'Static GVM', 'Error', 'Ticket', 'Override', 'Source']} dense>
      {rows.map((e) => {
        const d = e.decision!;
        const s = d.static_verified_gvm_kg;
        return (
          <tr key={e.id} className="tr">
            <td className="td whitespace-nowrap">{fmtDateTime(e.occurred_at)}</td><td className="td">{e.plate ?? '—'}</td><td className="td tabular-nums">{fmtKg(e.gvm_kg)}</td>
            <td className="td tabular-nums">{s !== null ? fmtKg(s) : '—'}</td><td className="td tabular-nums">{s ? `${(((e.gvm_kg - s) / s) * 100).toFixed(2)} %` : '—'}</td>
            <td className="td">{d.ticket_type ? <Badge tone={d.ticket_type === 'static_certified' ? 'green' : 'amber'}>{d.ticket_type}</Badge> : '—'}</td>
            <td className="td text-xs">{d.override_reason ?? '—'}</td><td className="td"><SourceBadge source={e.source} /></td>
          </tr>
        );
      })}
    </Table>
  );
}
