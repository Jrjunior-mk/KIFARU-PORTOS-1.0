/**
 * Port operations (SmartPort layer): KPI tiles with published benchmarks, the eleven-stage visit board, visit drawer with
 * stage timeline and "advance stage" form, and a new-visit form. Contract: docs/02-architecture/smartport-port-process-contract.md.
 */
import { type FormEvent, useEffect, useState } from 'react';
import { fleet as fleetApi, port as portApi, shipments as shipmentsApi } from '../api/endpoints';
import type { PortBenchmark, PortKpisOut, PortStageDef, PortVisitIn, PortVisitOut, VehicleOut } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { Icon } from '../components/icons';
import { Badge, Card, Confirm, Drawer, Empty, ErrorBanner, Field, KV, Notice, PageHeader, Skeleton, SourceBadge, Stat } from '../components/ui';
import { useMutation, useQuery } from '../hooks/useQuery';
import { fmtAgo, fmtDateTime, fmtNum, titleCase } from '../lib/format';
import { FALLBACK_STAGES, FIELD_OPTIONS, fieldKind, fieldLabel, fmtBench, fmtSeconds, nextStage, stageLabel, stageShort } from '../lib/port';

const ACT_ROLES = ['port_controller', 'platform_admin', 'weighbridge_operator'] as const;
const TRANSPORT_ROLES = ['transporter_admin', 'dispatcher', 'cargo_owner', 'platform_admin'] as const;

export default function Port() {
  const { hasRole } = useAuth();
  const canOperate = hasRole(...ACT_ROLES);
  const canRegister = hasRole(...TRANSPORT_ROLES) || canOperate;
  const stagesQ = useQuery(() => portApi.stages(), []);
  const kpisQ = useQuery(() => portApi.kpis(24), [], { pollMs: 60_000 });
  const boardQ = useQuery(() => portApi.board(), [], { pollMs: 30_000 });
  const stages = stagesQ.data?.length ? stagesQ.data : FALLBACK_STAGES;
  const [selected, setSelected] = useState<PortVisitOut | null>(null);
  const [showNew, setShowNew] = useState(false);
  const refresh = () => { void boardQ.refetch(); void kpisQ.refetch(); };

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Operations" title="Port operations" subtitle="Truck and cargo movement from pre-arrival registration to delivery: eleven stages, one record per port visit, with the data each agency needs at each stage."
        actions={canRegister && <button className="btn-primary text-xs" onClick={() => setShowNew(true)}>New port visit</button>} />
      <ErrorBanner error={kpisQ.error ?? boardQ.error} />
      <Card title="Port KPIs" subtitle={`GET /port/kpis · last 24 h · ${kpisQ.data?.label ?? 'measured from platform records'} · published benchmarks shown beside each tile`}>
        {kpisQ.data ? <KpiTiles k={kpisQ.data} /> : !kpisQ.error && <Skeleton lines={3} />}
      </Card>
      <Card title="Visit board" subtitle="GET /port/board · one column per stage · tap a card for its timeline and to advance it" actions={<Badge tone="slate">{boardQ.data?.stages.reduce((a, c) => a + c.count, 0) ?? 0} visits</Badge>}>
        {boardQ.data ? <Board stages={stages} columns={boardQ.data.stages} onSelect={setSelected} /> : !boardQ.error && <Skeleton lines={6} />}
      </Card>
      <Drawer open={!!selected} title={selected ? <span className="flex items-center gap-2">{selected.reference} <SourceBadge source={selected.source} /></span> : ''} onClose={() => setSelected(null)} width="max-w-2xl">
        {selected && <VisitDetail v={selected} stages={stages} canOperate={canOperate} canTransport={canRegister} onChanged={(v) => { setSelected(v); refresh(); }} />}
      </Drawer>
      <Drawer open={showNew} title="New port visit — pre-arrival registration" onClose={() => setShowNew(false)}>
        <NewVisitForm onDone={(v) => { setShowNew(false); refresh(); setSelected(v); }} />
      </Drawer>
    </div>
  );
}

function Bench({ b }: { b: PortBenchmark | undefined }) {
  if (!b) return null;
  return (
    <span className="mt-0.5 inline-flex items-center gap-1 text-[11px] text-ink-500 dark:text-ink-300">
      {b.label}: {fmtBench(b.value, b.unit)}
      {b.source_url && <a href={b.source_url} target="_blank" rel="noreferrer" aria-label={`Source for ${b.label}`} className="text-brand-600 hover:underline dark:text-brand-400"><Icon name="link" size={12} /></a>}
      <Badge tone={b.classification === 'published' ? 'blue' : b.classification === 'actual' ? 'teal' : 'amber'}>{b.classification}</Badge>
    </span>
  );
}

function KpiTiles({ k }: { k: PortKpisOut }) {
  const bench = (keys: string[]) => k.benchmarks.find((b) => keys.some((x) => b.key.includes(x)));
  const tiles: { label: string; value: string; hint: React.ReactNode; tone?: 'teal' | 'green' | 'amber' | 'red' }[] = [
    { label: 'Queue wait', value: fmtSeconds(k.avg_queue_wait_s), hint: <Bench b={bench(['gate_scanning', 'queue'])} /> },
    { label: 'Gate-in processing', value: fmtSeconds(k.avg_gate_in_processing_s), hint: <Bench b={bench(['gate_in', 'gate_scanning'])} /> },
    { label: 'Yard wait', value: fmtSeconds(k.avg_yard_wait_s), hint: <Bench b={bench(['yard'])} /> },
    { label: 'Loading', value: fmtSeconds(k.avg_loading_duration_s), hint: <Bench b={bench(['loading'])} /> },
    { label: 'Weighing service', value: fmtSeconds(k.avg_weighing_service_s), hint: <Bench b={bench(['weigh', 'static_service'])} /> },
    { label: 'Final clearance', value: fmtSeconds(k.avg_clearance_duration_s), hint: <Bench b={bench(['clearance', 'kentrade', 'permit'])} /> },
    { label: 'Port dwell time', value: fmtSeconds(k.avg_dwell_time_s), hint: <span className="flex flex-col"><span className="text-[11px] text-ink-500">P90 {fmtSeconds(k.p90_dwell_time_s)}</span><Bench b={bench(['truck_turnaround', 'dwell'])} /></span>, tone: 'teal' },
    { label: 'Transit time', value: fmtSeconds(k.avg_transit_time_s), hint: <Bench b={bench(['transit'])} /> },
    { label: 'Throughput', value: k.throughput_per_hour === null ? '—' : `${fmtNum(k.throughput_per_hour, 1)} / h`, hint: <span className="flex flex-col"><span className="text-[11px] text-ink-500">{k.gate_outs_total} gate-outs · {k.exceptions_total} exceptions</span><Bench b={bench(['trucks_per_day'])} /></span>, tone: 'green' },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
      {tiles.map((t) => <Stat key={t.label} label={t.label} value={t.value} hint={t.hint} tone={t.tone} />)}
      <Stat label="Visits (24 h)" value={k.visits_total} hint={<span className="text-[11px] text-ink-500">{Object.entries(k.visits_by_stage).filter(([, n]) => n > 0).map(([s, n]) => `${stageShort(s)} ${n}`).join(' · ') || 'none yet'}</span>} />
    </div>
  );
}

function Board({ stages, columns, onSelect }: { stages: PortStageDef[]; columns: { stage: string; label: string; count: number; visits: PortVisitOut[] }[]; onSelect: (v: PortVisitOut) => void }) {
  const byStage = new Map(columns.map((c) => [c.stage, c]));
  return (
    <div className="-mx-4 overflow-x-auto px-4 pb-2">
      <ol className="flex min-w-max gap-3" aria-label="Port visit board">
        {stages.map((s) => {
          const col = byStage.get(s.stage);
          return (
            <li key={s.stage} className="w-56 shrink-0 rounded-xl border border-ink-100 bg-surface-50 p-2 dark:border-ink-800 dark:bg-ink-950/60">
              <div className="flex items-center justify-between gap-1 px-1">
                <div className="min-w-0"><div className="truncate text-xs font-semibold">{s.order}. {stageShort(s.stage)}</div><div className="truncate text-[10px] text-ink-500">{s.agency}</div></div>
                <Badge tone={col?.count ? 'teal' : 'slate'}>{col?.count ?? 0}</Badge>
              </div>
              <ul className="mt-2 space-y-1.5">
                {(col?.visits ?? []).map((v) => (
                  <li key={v.id}>
                    <button className="w-full rounded-lg border border-ink-100 bg-white p-2 text-left text-xs shadow-sm hover:border-brand-400 dark:border-ink-800 dark:bg-ink-900" onClick={() => onSelect(v)}>
                      <div className="flex items-center justify-between gap-1"><span className="font-semibold">{v.plate ?? 'no plate'}</span><SourceBadge source={v.source} /></div>
                      <div className="truncate text-ink-600 dark:text-slate-300">{v.reference}{v.cargo_type ? ` · ${titleCase(v.cargo_type)}` : ''}</div>
                      <div className="truncate text-[11px] text-ink-500">{v.destination ?? '—'} · {fmtAgo(lastStageAt(v))} in stage</div>
                    </button>
                  </li>
                ))}
                {(col?.count ?? 0) === 0 && <li className="px-1 py-3 text-center text-[11px] text-ink-400">empty</li>}
              </ul>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function lastStageAt(v: PortVisitOut): string { return v.timeline.length ? v.timeline[v.timeline.length - 1].at : v.updated_at; }

function VisitDetail({ v, stages, canOperate, canTransport, onChanged }: { v: PortVisitOut; stages: PortStageDef[]; canOperate: boolean; canTransport: boolean; onChanged: (v: PortVisitOut) => void }) {
  const next = nextStage(v.stage);
  const nextDef = stages.find((s) => s.stage === next);
  const nextOrder = nextDef?.order ?? 0;
  const mayAdvance = v.status === 'active' && next !== null && ((nextOrder >= 4 && nextOrder <= 9) ? canOperate : nextOrder >= 10 ? (canTransport || canOperate) : (canTransport || canOperate));
  const [confirmCancel, setConfirmCancel] = useState(false);
  const cancel = useMutation((reason: string) => portApi.cancel(v.id, reason));
  const k = v.kpis;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={v.status === 'active' ? 'teal' : v.status === 'closed' ? 'green' : 'red'}>{v.status}</Badge>
        <Badge tone="blue">{v.stage_order}. {stageLabel(v.stage)}</Badge>
        {v.token_ref && <a className="text-xs text-brand-700 underline dark:text-brand-300" href="/registry">token {v.token_ref}</a>}
      </div>
      <KV items={[
        ['Truck', v.plate ?? '—'], ['Shipment', v.shipment_reference ?? v.shipment_id ?? '—'], ['Cargo', v.cargo_type ? `${titleCase(v.cargo_type)}${v.container_number ? ` · ${v.container_number}` : ''}${v.declared_mass_kg ? ` · declared ${fmtNum(v.declared_mass_kg, 0)} kg` : ''}` : '—'],
        ['Destination', v.destination ?? '—'], ['Appointment', v.appointment_at ? fmtDateTime(v.appointment_at) : '—'], ['Registered', fmtDateTime(v.created_at)],
      ]} />
      <div>
        <h4 className="label">Visit KPIs</h4>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Queue wait" value={fmtSeconds(k.queue_wait_s)} /><Stat label="Gate-in" value={fmtSeconds(k.gate_in_processing_s)} /><Stat label="Yard wait" value={fmtSeconds(k.yard_wait_s)} /><Stat label="Loading" value={fmtSeconds(k.loading_duration_s)} />
          <Stat label="Weighing" value={fmtSeconds(k.weighing_service_s)} /><Stat label="Clearance" value={fmtSeconds(k.clearance_duration_s)} /><Stat label="Dwell" value={fmtSeconds(k.dwell_time_s)} tone="teal" /><Stat label="Transit" value={fmtSeconds(k.transit_time_s)} />
        </div>
      </div>
      <div>
        <h4 className="label">Stage timeline</h4>
        <ol className="space-y-1.5">
          {stages.map((s) => {
            const e = v.timeline.find((t) => t.stage === s.stage);
            const current = s.stage === v.stage;
            return (
              <li key={s.stage} className={`flex items-start gap-2 rounded-lg border px-2 py-1.5 text-xs ${e ? 'border-brand-200 bg-brand-50/60 dark:border-brand-900 dark:bg-brand-900/20' : current ? 'border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30' : 'border-ink-100 dark:border-ink-800'}`}>
                <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${e ? 'bg-brand-600 text-white' : 'bg-ink-200 text-ink-700 dark:bg-ink-700 dark:text-ink-100'}`}>{s.order}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center justify-between gap-1"><span className="font-medium">{stageLabel(s.stage)}</span><span className="text-ink-500">{e ? fmtDateTime(e.at) : s.agency}</span></div>
                  {e && Object.keys(e.data).length > 0 && <div className="mt-0.5 text-[11px] text-ink-600 dark:text-slate-300">{Object.entries(e.data).filter(([, val]) => val !== null && val !== '' && val !== undefined).map(([key, val]) => `${fieldLabel(key)}: ${String(val)}`).join(' · ')}</div>}
                </div>
              </li>
            );
          })}
        </ol>
      </div>
      {v.outstanding.length > 0 && <Notice tone="warn"><span className="font-medium">Outstanding for the next stage:</span> {v.outstanding.map(fieldLabel).join(' · ')}</Notice>}
      {next && nextDef && v.status === 'active' && (mayAdvance ? <AdvanceForm v={v} def={nextDef} onDone={onChanged} /> : <Notice>Advancing to “{stageLabel(next)}” is done by {nextDef.agency}; your role can view this visit.</Notice>)}
      {v.status === 'active' && (canOperate || canTransport) && (
        <div className="flex justify-end">
          <button className="btn-danger text-xs" disabled={cancel.busy} onClick={() => setConfirmCancel(true)}>Cancel visit</button>
          <Confirm open={confirmCancel} danger title="Cancel this port visit?" body="The record is kept with status cancelled; nothing is deleted." confirmLabel="Cancel visit" onCancel={() => setConfirmCancel(false)} onConfirm={async () => { setConfirmCancel(false); const r = await cancel.run('cancelled from the port operations board'); if (r) onChanged(r); }} />
        </div>
      )}
      <ErrorBanner error={cancel.error} />
    </div>
  );
}

function AdvanceForm({ v, def, onDone }: { v: PortVisitOut; def: PortStageDef; onDone: (v: PortVisitOut) => void }) {
  const [data, setData] = useState<Record<string, unknown>>({});
  useEffect(() => { setData({}); }, [def.stage, v.id]);
  const adv = useMutation((body: { stage: string; data: Record<string, unknown> }) => portApi.advance(v.id, body));
  const fe = adv.error?.fieldErrors ?? {};
  const fields = def.required_fields.length ? def.required_fields : v.outstanding;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const clean: Record<string, unknown> = {};
    for (const [k, val] of Object.entries(data)) if (val !== '' && val !== undefined) clean[k] = fieldKind(k) === 'datetime' && typeof val === 'string' ? new Date(val).toISOString() : val;
    const r = await adv.run({ stage: def.stage, data: clean });
    if (r) onDone(r);
  };
  return (
    <form onSubmit={submit} className="card-muted space-y-3 p-3">
      <div className="flex items-center justify-between"><h4 className="font-medium">Advance to {def.order}. {stageLabel(def.stage)}</h4><Badge tone="slate">{def.agency}</Badge></div>
      {fields.length === 0 ? <p className="text-xs text-ink-500">No additional data is required for this stage.</p> : (
        <div className="grid gap-2 sm:grid-cols-2">
          {fields.map((f) => <StageField key={f} name={f} value={data[f]} error={fe[f]} onChange={(val) => setData({ ...data, [f]: val })} />)}
        </div>
      )}
      <div className="flex items-center gap-2"><button className="btn-primary text-xs" type="submit" disabled={adv.busy}>{adv.busy ? 'Saving…' : `Record ${stageShort(def.stage).toLowerCase()}`}</button><ErrorBanner error={adv.error} /></div>
    </form>
  );
}

function StageField({ name, value, error, onChange }: { name: string; value: unknown; error?: string; onChange: (v: unknown) => void }) {
  const kind = fieldKind(name);
  const label = fieldLabel(name);
  if (kind === 'select') return <Field label={label} error={error}>{(id) => <select id={id} className="input py-1" value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)}><option value="">select…</option>{FIELD_OPTIONS[name].map((o) => <option key={o} value={o}>{titleCase(o)}</option>)}</select>}</Field>;
  if (kind === 'boolean') return <Field label={label} error={error}>{(id) => <select id={id} className="input py-1" value={value === undefined ? '' : String(value)} onChange={(e) => onChange(e.target.value === '' ? undefined : e.target.value === 'true')}><option value="">select…</option><option value="true">Yes</option><option value="false">No</option></select>}</Field>;
  if (kind === 'datetime') return <Field label={label} error={error}>{(id) => <input id={id} type="datetime-local" className="input py-1" value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} />}</Field>;
  if (kind === 'number') return <Field label={label} error={error}>{(id) => <input id={id} type="number" step="any" className="input py-1" value={value === undefined ? '' : String(value)} onChange={(e) => onChange(e.target.value === '' ? undefined : Number(e.target.value))} />}</Field>;
  return <Field label={label} error={error}>{(id) => <input id={id} className="input py-1" value={(value as string) ?? ''} onChange={(e) => onChange(e.target.value)} />}</Field>;
}

function NewVisitForm({ onDone }: { onDone: (v: PortVisitOut) => void }) {
  const vehiclesQ = useQuery(() => fleetApi.vehicles(), []);
  const shipmentsQ = useQuery(() => shipmentsApi.list(), []);
  const [form, setForm] = useState<PortVisitIn>({ vehicle_id: '', shipment_id: null, truck_type: 'container', cargo_type: 'container', container_number: '', declared_mass_kg: null, destination: 'Nairobi ICD', appointment_at: null, expected_arrival_at: null });
  const create = useMutation((b: PortVisitIn) => portApi.createVisit(b));
  const fe = create.error?.fieldErrors ?? {};
  const vehicles: VehicleOut[] = vehiclesQ.data ?? [];
  const pickShipment = (id: string) => {
    const s = (shipmentsQ.data ?? []).find((x) => x.id === id);
    setForm({ ...form, shipment_id: id || null, cargo_type: s?.cargo_type ?? form.cargo_type, container_number: s?.containers[0]?.number ?? form.container_number, declared_mass_kg: s?.declared_mass_kg ?? form.declared_mass_kg, destination: s?.destination ?? form.destination, vehicle_id: s?.vehicle_id ?? form.vehicle_id });
  };
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const r = await create.run({ ...form, container_number: form.container_number || null, declared_mass_kg: form.declared_mass_kg || null, appointment_at: form.appointment_at ? new Date(form.appointment_at).toISOString() : null, expected_arrival_at: form.expected_arrival_at ? new Date(form.expected_arrival_at).toISOString() : null });
    if (r) onDone(r);
  };
  return (
    <form onSubmit={submit} className="space-y-3">
      <Notice>Stage 1 of the SmartPort workflow: the transporter or clearing agent submits truck, driver, cargo and container details and books a collection appointment before the truck arrives.</Notice>
      <Field label="Shipment (digital cargo passport)" hint="Optional; pre-fills cargo, container and destination">{(id) => <select id={id} className="input" value={form.shipment_id ?? ''} onChange={(e) => pickShipment(e.target.value)}><option value="">none</option>{(shipmentsQ.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.reference} · {s.description.slice(0, 40)}</option>)}</select>}</Field>
      <Field label="Truck" required error={fe.vehicle_id}>{(id) => <select id={id} className="input" required value={form.vehicle_id} onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })}><option value="">select…</option>{vehicles.map((v) => <option key={v.id} value={v.id}>{v.plate} · {v.body_type} · {v.axle_config}</option>)}</select>}</Field>
      <div className="grid gap-2 sm:grid-cols-2">
        <Field label="Truck type" error={fe.truck_type}>{(id) => <select id={id} className="input" value={form.truck_type ?? ''} onChange={(e) => setForm({ ...form, truck_type: e.target.value })}>{FIELD_OPTIONS.truck_type.map((o) => <option key={o} value={o}>{titleCase(o)}</option>)}</select>}</Field>
        <Field label="Cargo type" error={fe.cargo_type}>{(id) => <select id={id} className="input" value={form.cargo_type ?? ''} onChange={(e) => setForm({ ...form, cargo_type: e.target.value })}>{FIELD_OPTIONS.cargo_type.map((o) => <option key={o} value={o}>{titleCase(o)}</option>)}</select>}</Field>
        <Field label="Container number" error={fe.container_number}>{(id) => <input id={id} className="input" value={form.container_number ?? ''} onChange={(e) => setForm({ ...form, container_number: e.target.value.toUpperCase() })} placeholder="MSKU1234567" />}</Field>
        <Field label="Declared cargo weight (kg)" error={fe.declared_mass_kg}>{(id) => <input id={id} type="number" min={0} className="input" value={form.declared_mass_kg ?? ''} onChange={(e) => setForm({ ...form, declared_mass_kg: e.target.value ? Number(e.target.value) : null })} />}</Field>
        <Field label="Destination" error={fe.destination}>{(id) => <input id={id} className="input" value={form.destination ?? ''} onChange={(e) => setForm({ ...form, destination: e.target.value })} />}</Field>
        <Field label="Appointment time" error={fe.appointment_at}>{(id) => <input id={id} type="datetime-local" className="input" value={form.appointment_at ?? ''} onChange={(e) => setForm({ ...form, appointment_at: e.target.value || null })} />}</Field>
        <Field label="Expected arrival" error={fe.expected_arrival_at}>{(id) => <input id={id} type="datetime-local" className="input" value={form.expected_arrival_at ?? ''} onChange={(e) => setForm({ ...form, expected_arrival_at: e.target.value || null })} />}</Field>
      </div>
      <div className="flex items-center gap-2"><button className="btn-primary" type="submit" disabled={create.busy || !form.vehicle_id}>{create.busy ? 'Registering…' : 'Register visit'}</button><ErrorBanner error={create.error} /></div>
      {vehicles.length === 0 && !vehiclesQ.loading && <Empty>No vehicles are visible to your account.</Empty>}
    </form>
  );
}
