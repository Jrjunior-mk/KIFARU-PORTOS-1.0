/** Clearance Registry: Load Compliance Tokens, release orders, special-load permits, trust tiers and policy (GET /rcs/*). */
import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { fleet as fleetApi, rcs as rcsApi, stations as stationsApi } from '../api/endpoints';
import type { PermitIn, PermitOut, RcsPolicyOut, RcsStatsOut, ReleaseOrderOut, TokenOut, VehicleOut } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { ROUTE_COLORS, ShareBar, StationKindBadge, STREAM_COLORS, TierBadge, TokenStatusBadge } from '../components/rcs';
import { Badge, Card, Confirm, Drawer, Empty, ErrorBanner, Field, KV, Notice, PageHeader, Skeleton, SourceBadge, Spinner, Stat, Table, Tabs } from '../components/ui';
import { useMutation, useQuery } from '../hooks/useQuery';
import { fmtAgo, fmtDateTime, fmtKg, fmtPct, isoToLocalInput, localToIso, titleCase } from '../lib/format';
import { fmtUsd, ROUTE_LABEL, ROUTES_ALL, sourceLabel, streamLabel } from '../lib/rcs';

type Tab = 'tokens' | 'orders' | 'permits' | 'policy';

export default function Registry() {
  const { hasRole } = useAuth();
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState<Tab>((params.get('tab') as Tab) || 'tokens');
  const statsQ = useQuery(() => rcsApi.stats(), [], { pollMs: 30_000 });
  const stationsQ = useQuery(() => stationsApi.list(), []);
  const canOps = hasRole('port_controller', 'weighbridge_operator', 'platform_admin');
  const canPermit = hasRole('transporter_admin', 'platform_admin');
  useEffect(() => { if (params.get('token')) setTab('tokens'); }, [params]);

  return (
    <div className="space-y-4">
      <PageHeader eyebrow="RCS v2" title="Clearance Registry" subtitle="One record per truck-journey: Load Compliance Tokens, release orders, permits, trust tiers and policy. Later stations honour a valid token instead of repeating the work." actions={<a className="btn-secondary text-xs" href="/about">How it works</a>} />
      <ErrorBanner error={statsQ.error} />
      {statsQ.data ? <StatsHeader s={statsQ.data} /> : <Card><Skeleton lines={4} /></Card>}
      <Tabs value={tab} onChange={(t) => { setTab(t); setParams((p) => { p.set('tab', t); p.delete('token'); return p; }); }} tabs={[{ id: 'tokens', label: 'Tokens' }, { id: 'orders', label: 'Release orders' }, { id: 'permits', label: 'Permits' }, { id: 'policy', label: 'Trust tiers & policy' }]} />
      {tab === 'tokens' && <Tokens canOps={canOps} stations={stationsQ.data ?? []} initialRef={params.get('token')} />}
      {tab === 'orders' && <Orders canOps={canOps} />}
      {tab === 'permits' && <Permits canCreate={canPermit} />}
      {tab === 'policy' && <Policy />}
    </div>
  );
}

function StatsHeader({ s }: { s: RcsStatsOut }) {
  return (
    <Card title="Network snapshot" subtitle="GET /rcs/stats · all stations" actions={<Badge tone="slate">{s.total} passes</Badge>}>
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr_auto]">
        <div><div className="section-title mb-1.5">Stream mix</div><ShareBar ariaLabel="Share of passes by truck stream" colors={STREAM_COLORS} parts={(['port', 'origin', 'untokened'] as const).map((k) => ({ key: k, value: s.by_stream[k] ?? 0, label: streamLabel(k) }))} /></div>
        <div><div className="section-title mb-1.5">Route mix</div><ShareBar ariaLabel="Share of passes by route" colors={ROUTE_COLORS} parts={ROUTES_ALL.map((k) => ({ key: k, value: s.by_route[k] ?? 0, label: ROUTE_LABEL[k] }))} /></div>
        <div className="grid grid-cols-3 gap-2 lg:w-[22rem]">
          <Stat label="Token coverage" value={fmtPct(s.token_coverage)} tone="teal" hint="passes with a token" />
          <Stat label="Active tokens" value={s.tokens_active} hint={`${s.honoured_total} honoured`} />
          <Stat label="Open orders" value={s.release_orders_open} tone={s.release_orders_open ? 'red' : 'default'} hint="release orders" />
        </div>
      </div>
      {s.per_station.length > 0 && (
        <div className="mt-4">
          <Table head={['Station', 'Kind', 'Passes', 'Continue', 'Lane', 'Static', 'Port re-weigh', 'Lane share', 'Static share']} dense>
            {s.per_station.map((p) => (
              <tr key={p.station_id} className="tr">
                <td className="td font-medium">{p.code}</td><td className="td"><StationKindBadge kind={p.kind} /></td><td className="td tabular-nums">{p.total}</td>
                <td className="td tabular-nums">{p.routes.continue ?? 0}</td><td className="td tabular-nums">{p.routes.verification_lane ?? 0}</td><td className="td tabular-nums">{p.routes.static_scale ?? 0}</td><td className="td tabular-nums">{p.routes.port_reweigh ?? 0}</td>
                <td className="td tabular-nums">{fmtPct(p.lane_share, 1)}</td><td className="td tabular-nums">{fmtPct(p.static_share, 1)}</td>
              </tr>
            ))}
          </Table>
        </div>
      )}
    </Card>
  );
}

function Tokens({ canOps, stations, initialRef }: { canOps: boolean; stations: import('../api/types').StationOut[]; initialRef: string | null }) {
  const [status, setStatus] = useState('');
  const [source, setSource] = useState('');
  const [stationId, setStationId] = useState('');
  const [search, setSearch] = useState(initialRef ?? '');
  const q = useQuery(() => rcsApi.tokens({ status: status || undefined, source: source || undefined, station_id: stationId || undefined, limit: 200 }), [status, source, stationId], { pollMs: 30_000 });
  const [sel, setSel] = useState<TokenOut | null>(null);
  const list = useMemo(() => {
    const s = search.trim().toLowerCase();
    return (q.data ?? []).filter((t) => !s || t.token_ref.toLowerCase().includes(s) || (t.plate ?? '').toLowerCase().includes(s) || (t.container_number ?? '').toLowerCase().includes(s));
  }, [q.data, search]);
  useEffect(() => { if (initialRef && q.data) { const t = q.data.find((x) => x.token_ref === initialRef); if (t) setSel(t); } }, [initialRef, q.data]);

  return (
    <Card title="Load Compliance Tokens" subtitle="GET /rcs/tokens · signed at the first verified weighing point; honoured downstream while valid and consistent" actions={
      <div className="flex flex-wrap gap-2">
        <input className="input w-44 py-1 text-xs" aria-label="Search plate, reference or container" placeholder="plate, ref, container" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="input w-auto py-1 text-xs" aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">any status</option>{['active', 'expired', 'suspended', 'revoked'].map((s) => <option key={s} value={s}>{s}</option>)}</select>
        <select className="input w-auto py-1 text-xs" aria-label="Source" value={source} onChange={(e) => setSource(e.target.value)}><option value="">any source</option>{['port', 'origin', 'road', 'lane'].map((s) => <option key={s} value={s}>{sourceLabel(s)}</option>)}</select>
        <select className="input w-auto py-1 text-xs" aria-label="Issuing station" value={stationId} onChange={(e) => setStationId(e.target.value)}><option value="">any station</option>{stations.map((s) => <option key={s.id} value={s.id}>{s.code}</option>)}</select>
      </div>}>
      <ErrorBanner error={q.error} />
      {q.loading ? <Skeleton lines={5} /> : list.length === 0 ? <Empty>No tokens match. Tokens are issued on GREEN at port gate-out, origin and road nodes and the verification lane.</Empty> : (
        <Table head={['Reference', 'Plate', 'Source', 'Tier', 'GVM', 'Issued', 'Expires', 'Honoured', 'Status', 'Sig', 'Src']} dense>
          {list.slice(0, 200).map((t) => (
            <tr key={t.id} className="tr cursor-pointer" onClick={() => setSel(t)} tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') setSel(t); }}>
              <td className="td mono">{t.token_ref}</td><td className="td font-medium">{t.plate ?? '—'}</td><td className="td">{sourceLabel(t.source)} <span className="text-ink-400">{t.issuing_station_code}</span></td>
              <td className="td"><TierBadge tier={t.trust_tier} /></td><td className="td tabular-nums">{fmtKg(t.gvm_kg)}</td><td className="td whitespace-nowrap">{fmtAgo(t.issued_at)}</td><td className="td whitespace-nowrap">{fmtDateTime(t.expires_at)}</td>
              <td className="td tabular-nums">{t.honoured_count}</td><td className="td"><TokenStatusBadge status={t.status} /></td><td className="td"><Badge tone={t.signature_valid ? 'green' : 'red'}>{t.signature_valid ? 'ok' : 'bad'}</Badge></td><td className="td"><SourceBadge source={t.source_label} /></td>
            </tr>
          ))}
        </Table>
      )}
      <Drawer open={!!sel} title={sel ? <span className="flex items-center gap-2">Token <span className="mono">{sel.token_ref}</span><TokenStatusBadge status={sel.status} /></span> : ''} onClose={() => setSel(null)}>
        {sel && <TokenDetail t={sel} canOps={canOps} onChanged={(t) => { setSel(t); void q.refetch(); }} />}
      </Drawer>
    </Card>
  );
}

function TokenDetail({ t, canOps, onChanged }: { t: TokenOut; canOps: boolean; onChanged: (t: TokenOut) => void }) {
  const [reason, setReason] = useState('');
  const [confirm, setConfirm] = useState<'suspend' | 'revoke' | null>(null);
  const act = useMutation((a: { kind: 'suspend' | 'revoke' }) => (a.kind === 'suspend' ? rcsApi.suspendToken(t.id, reason) : rcsApi.revokeToken(t.id, reason)));
  const dims = t.dimensions;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2"><TierBadge tier={t.trust_tier} /><Badge tone="teal">{sourceLabel(t.source)}</Badge><Badge tone={t.signature_valid ? 'green' : 'red'}>{t.signature_valid ? 'signature valid' : 'SIGNATURE INVALID'}</Badge><SourceBadge source={t.source_label} /></div>
      <KV items={[
        ['Plate / trailer', `${t.plate ?? '—'} / ${t.trailer_plate ?? '—'}`],
        ['RFID tag', <span className="mono">{t.rfid_epc ?? '—'}</span>],
        ['Container / seal', `${t.container_number ?? '—'} / ${t.seal_id ?? '—'}`],
        ['Shipment', t.shipment_id ? <span className="mono">{t.shipment_id}</span> : '—'],
        ['GVM at issue', <span>{fmtKg(t.gvm_kg)}{t.expected_gvm_kg !== null && <span className="text-ink-500"> · expected {fmtKg(t.expected_gvm_kg)} · variance {t.variance_kg !== null && t.variance_kg > 0 ? '+' : ''}{fmtKg(t.variance_kg)}</span>}</span>],
        ['Axle groups', <span className="tabular-nums">{t.axle_group_loads_kg.map((x) => fmtKg(x)).join(' · ') || '—'} {t.axle_config ? `(${t.axle_config})` : ''}</span>],
        ['Dimensions', dims ? `${dims.length_m ?? '—'} m × ${dims.width_m ?? '—'} m × ${dims.height_m ?? '—'} m (L×W×H)` : 'not captured'],
        ['Permit', t.permit_ref ?? 'none'],
        ['Release status', Object.keys(t.release_status).length ? <span className="flex flex-wrap gap-1">{Object.entries(t.release_status).map(([k, v]) => <Badge key={k} tone={v === 'released' || v === 'ok' ? 'green' : 'slate'}>{k}: {v}</Badge>)}</span> : '—'],
        ['Route / destination', `${t.route ?? '—'} / ${t.destination ?? '—'}`],
        ['Issued', `${fmtDateTime(t.issued_at)} at ${t.issuing_station_code}`],
        ['Expires', fmtDateTime(t.expires_at)],
        ['Honoured', `${t.honoured_count}× · last ${t.last_honoured_at ? fmtAgo(t.last_honoured_at) : 'never'}`],
        ['Issuing event', <a className="mono underline" href={`/operator?event=${t.issuing_event_id}`}>{t.issuing_event_id}</a>],
        ['Signer', <span className="mono">{t.signer_key_id}</span>],
        ['Signature', <span className="mono break-all">{t.signature}</span>],
        ['Public verify', <a className="underline" href={`/verify/token/${encodeURIComponent(t.token_ref)}`} target="_blank" rel="noreferrer">/verify/token/{t.token_ref}</a>],
      ]} />
      {t.suspended_reason && <Notice tone="warn">Suspended / revoked: {t.suspended_reason}</Notice>}
      {canOps && t.status === 'active' && (
        <div className="card-muted space-y-2 p-3">
          <div className="text-sm font-medium">Suspend or revoke</div>
          <p className="text-xs text-ink-500">Suspend when an origin scale drifts or an audit fails (the truck is verified in the lane). Revoke for fraud (plate swap, cargo added after weighing). Both are written to the signed ledger.</p>
          <Field label="Reason (min 10 chars)" required>{(id) => <input id={id} className="input" minLength={10} value={reason} onChange={(e) => setReason(e.target.value)} />}</Field>
          <div className="flex gap-2"><button className="btn-secondary text-xs" disabled={act.busy || reason.length < 10} onClick={() => setConfirm('suspend')}>Suspend</button><button className="btn-danger text-xs" disabled={act.busy || reason.length < 10} onClick={() => setConfirm('revoke')}>Revoke</button></div>
          <ErrorBanner error={act.error} />
          <Confirm open={!!confirm} title={`${titleCase(confirm ?? '')} token ${t.token_ref}?`} danger body={<span>Reason: “{reason}”. Later stations will stop honouring this token.</span>} confirmLabel={titleCase(confirm ?? 'Confirm')} onCancel={() => setConfirm(null)} onConfirm={async () => { const k = confirm!; setConfirm(null); const r = await act.run({ kind: k }); if (r) { setReason(''); onChanged(r); } }} />
        </div>
      )}
    </div>
  );
}

function Orders({ canOps }: { canOps: boolean }) {
  const [status, setStatus] = useState('');
  const q = useQuery(() => rcsApi.releaseOrders({ status: status || undefined }), [status], { pollMs: 30_000 });
  const [sel, setSel] = useState<ReleaseOrderOut | null>(null);
  const set = useMutation((a: { id: string; s: 'paid' | 'closed' }) => rcsApi.releaseOrderStatus(a.id, a.s));
  const list = q.data ?? [];
  return (
    <Card title="Release orders (Reg 14)" subtitle="GET /rcs/release-orders · officer e-signed; a second overload in the same journey triples the fee" actions={<select className="input w-auto py-1 text-xs" aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">any status</option>{['issued', 'paid', 'closed'].map((s) => <option key={s}>{s}</option>)}</select>}>
      <ErrorBanner error={q.error ?? set.error} />
      {q.loading ? <Skeleton lines={4} /> : list.length === 0 ? <Empty>No release orders. They are issued from the Weighbridge console for RED passes after a static weighing.</Empty> : (
        <Table head={['Order', 'Plate', 'Station', 'Overload', 'Fee', '×', 'Total', 'Flags', 'Officer', 'Issued', 'Status', '']} dense>
          {list.map((o) => (
            <tr key={o.id} className="tr">
              <td className="td mono"><button className="underline" onClick={() => setSel(o)}>{o.order_ref}</button></td><td className="td font-medium">{o.plate ?? '—'}</td><td className="td">{o.station_code}</td>
              <td className="td tabular-nums">{fmtKg(o.overload_kg)}</td><td className="td tabular-nums">{fmtUsd(o.fee_usd)}</td><td className="td tabular-nums">{o.fee_multiplier}{o.repeat_offence && <Badge tone="red">repeat</Badge>}</td><td className="td tabular-nums font-medium">{fmtUsd(o.total_usd)}</td>
              <td className="td"><span className="flex flex-wrap gap-1">{o.transit && <Badge tone="blue">transit</Badge>}{o.customs_notified && <Badge tone="violet">customs</Badge>}{o.hazardous && <Badge tone="red">hazmat</Badge>}{o.perishable && <Badge tone="amber">perishable</Badge>}</span></td>
              <td className="td text-xs">{o.officer_name ?? o.officer_user_id}</td><td className="td whitespace-nowrap text-xs">{fmtDateTime(o.issued_at)}</td>
              <td className="td"><Badge tone={o.status === 'issued' ? 'red' : o.status === 'paid' ? 'amber' : 'green'}>{o.status}</Badge></td>
              <td className="td">{canOps && o.status !== 'closed' && <button className="btn-secondary px-1.5 py-0.5 text-[11px]" disabled={set.busy} onClick={async () => { if (await set.run({ id: o.id, s: o.status === 'issued' ? 'paid' : 'closed' })) void q.refetch(); }}>{o.status === 'issued' ? 'mark paid' : 'close'}</button>}</td>
            </tr>
          ))}
        </Table>
      )}
      <Drawer open={!!sel} title={sel ? `Release order ${sel.order_ref}` : ''} onClose={() => setSel(null)}>
        {sel && (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2"><Badge tone={sel.status === 'issued' ? 'red' : sel.status === 'paid' ? 'amber' : 'green'}>{sel.status}</Badge>{sel.repeat_offence && <Badge tone="red">repeat offence ×{sel.fee_multiplier}</Badge>}<SourceBadge source={sel.source_label} /></div>
            <KV items={[
              ['Plate', sel.plate ?? '—'], ['Station', sel.station_code],
              ['Measured GVM', fmtKg(sel.measured_gvm_kg)], ['Allowed GVM', `${fmtKg(sel.allowed_gvm_kg)} + allowance ${fmtKg(sel.allowance_kg)}`], ['Adjusted load', fmtKg(sel.adjusted_gvm_kg)], ['Overload', <span className="font-semibold text-decision-red">{fmtKg(sel.overload_kg)}</span>],
              ['Fee', `${fmtUsd(sel.fee_usd)} × ${sel.fee_multiplier}`], ['Detention', `${sel.detention_days} day(s) · ${fmtUsd(sel.detention_usd)}`], ['Total', <span className="text-base font-semibold">{fmtUsd(sel.total_usd)}</span>],
              ['Transit / customs', `${sel.transit ? 'transit cargo' : 'domestic'} · ${sel.customs_notified ? 'customs notified' : 'no customs notice'}`], ['Handling flags', [sel.hazardous && 'hazardous', sel.perishable && 'perishable'].filter(Boolean).join(', ') || 'none'],
              ['Officer', `${sel.officer_name ?? sel.officer_user_id}`], ['Officer signature', <span className="mono break-all">{sel.officer_signature}</span>],
              ['Issued / valid until', `${fmtDateTime(sel.issued_at)} → ${fmtDateTime(sel.valid_until)}`], ['Journey ref', sel.journey_ref ?? '—'], ['Weighing event', <a className="mono underline" href={`/operator?event=${sel.weighing_event_id}`}>{sel.weighing_event_id}</a>], ['Notes', sel.notes ?? '—'],
            ]} />
          </div>
        )}
      </Drawer>
    </Card>
  );
}

function Permits({ canCreate }: { canCreate: boolean }) {
  const q = useQuery(() => rcsApi.permits(), []);
  const vehiclesQ = useQuery(() => fleetApi.vehicles(), [], { enabled: canCreate });
  return (
    <div className={`grid gap-4 ${canCreate ? 'lg:grid-cols-3' : ''}`}>
      <Card title="Special-load permits" subtitle="GET /rcs/permits · dimension and mass permits checked by the LiDAR portal against the plate" className={canCreate ? 'lg:col-span-2' : ''}>
        <ErrorBanner error={q.error} />
        {q.loading ? <Skeleton /> : (q.data ?? []).length === 0 ? <Empty>No permits registered</Empty> : <PermitTable rows={q.data ?? []} />}
      </Card>
      {canCreate && <PermitForm vehicles={vehiclesQ.data ?? []} onCreated={() => void q.refetch()} />}
    </div>
  );
}

export function PermitTable({ rows }: { rows: PermitOut[] }) {
  return (
    <Table head={['Reference', 'Plate', 'Max L × W × H', 'Max GVM', 'Route', 'Valid', 'Status']} dense>
      {rows.map((p) => (
        <tr key={p.id} className="tr">
          <td className="td mono">{p.reference}</td><td className="td font-medium">{p.plate}</td><td className="td tabular-nums">{p.max_length_m} × {p.max_width_m} × {p.max_height_m} m</td><td className="td tabular-nums">{p.max_gvm_kg ? fmtKg(p.max_gvm_kg) : '—'}</td>
          <td className="td">{p.route ?? '—'}</td><td className="td whitespace-nowrap text-xs">{fmtDateTime(p.valid_from)} → {fmtDateTime(p.valid_to)}</td><td className="td"><Badge tone={p.status === 'valid' ? 'green' : p.status === 'future' ? 'blue' : 'slate'}>{p.status}</Badge></td>
        </tr>
      ))}
    </Table>
  );
}

export function PermitForm({ vehicles, onCreated }: { vehicles: VehicleOut[]; onCreated: () => void }) {
  const now = new Date();
  const [form, setForm] = useState<PermitIn>({ vehicle_id: '', reference: '', max_length_m: 25, max_width_m: 3.2, max_height_m: 4.6, max_gvm_kg: null, valid_from: now.toISOString(), valid_to: new Date(now.getTime() + 30 * 86_400_000).toISOString(), route: 'A109 Mombasa – Nairobi' });
  useEffect(() => { if (!form.vehicle_id && vehicles[0]) setForm((f) => ({ ...f, vehicle_id: vehicles[0].id })); }, [vehicles, form.vehicle_id]);
  const create = useMutation((b: PermitIn) => rcsApi.createPermit(b));
  const fe = create.error?.fieldErrors ?? {};
  const submit = async (e: FormEvent) => { e.preventDefault(); if (await create.run({ ...form, route: form.route || null, max_gvm_kg: form.max_gvm_kg || null })) { setForm({ ...form, reference: '' }); onCreated(); } };
  const num = (k: 'max_length_m' | 'max_width_m' | 'max_height_m', label: string) => <Field key={k} label={label} error={fe[k]}>{(id) => <input id={id} type="number" step="0.01" min={0} className="input" value={form[k]} onChange={(e) => setForm({ ...form, [k]: Number(e.target.value) })} required />}</Field>;
  return (
    <Card title="Register permit" subtitle="POST /rcs/permits">
      <form onSubmit={submit} className="grid grid-cols-2 gap-2">
        <div className="col-span-2"><Field label="Vehicle" required error={fe.vehicle_id}>{(id) => <select id={id} className="input" value={form.vehicle_id} onChange={(e) => setForm({ ...form, vehicle_id: e.target.value })} required>{vehicles.map((v) => <option key={v.id} value={v.id}>{v.plate} · {v.axle_config}</option>)}</select>}</Field></div>
        <div className="col-span-2"><Field label="Permit reference" required error={fe.reference}>{(id) => <input id={id} className="input" required value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} placeholder="KeNHA/SLP/2026/0001" />}</Field></div>
        {num('max_length_m', 'Max length (m)')}{num('max_width_m', 'Max width (m)')}{num('max_height_m', 'Max height (m)')}
        <Field label="Max GVM (kg)" error={fe.max_gvm_kg}>{(id) => <input id={id} type="number" className="input" value={form.max_gvm_kg ?? ''} onChange={(e) => setForm({ ...form, max_gvm_kg: e.target.value ? Number(e.target.value) : null })} placeholder="optional" />}</Field>
        <Field label="Valid from" error={fe.valid_from}>{(id) => <input id={id} type="datetime-local" className="input" value={isoToLocalInput(form.valid_from)} onChange={(e) => setForm({ ...form, valid_from: localToIso(e.target.value) })} />}</Field>
        <Field label="Valid to" error={fe.valid_to}>{(id) => <input id={id} type="datetime-local" className="input" value={isoToLocalInput(form.valid_to)} onChange={(e) => setForm({ ...form, valid_to: localToIso(e.target.value) })} />}</Field>
        <div className="col-span-2"><Field label="Route" error={fe.route}>{(id) => <input id={id} className="input" value={form.route ?? ''} onChange={(e) => setForm({ ...form, route: e.target.value })} />}</Field></div>
        <div className="col-span-2"><button className="btn-primary w-full" type="submit" disabled={create.busy || !form.vehicle_id}>Register permit</button><ErrorBanner error={create.error} className="mt-2" />{create.result && <Notice tone="ok" className="mt-2">Permit {create.result.reference} registered for {create.result.plate}</Notice>}</div>
      </form>
    </Card>
  );
}

function Policy() {
  const q = useQuery<RcsPolicyOut>(() => rcsApi.policy(), []);
  if (q.error) return <ErrorBanner error={q.error} />;
  if (!q.data) return <Card><Spinner label="Loading policy" /></Card>;
  const p = q.data;
  const pct = (x: number) => `${(x * 100).toFixed(0)} %`;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Trust tiers and audit rates" subtitle="GET /rcs/policy · audit rates rise with demerit points and fall with a clean record">
        <Table head={['Tier', 'Token source', 'Audit rate', 'Description']} dense>
          {p.trust_tiers.map((t) => <tr key={t.tier} className="tr"><td className="td"><TierBadge tier={t.tier} /></td><td className="td font-medium">{t.label}</td><td className="td tabular-nums">{pct(t.audit_rate)}</td><td className="td text-xs">{t.description}</td></tr>)}
        </Table>
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {(['port', 'origin', 'lane', 'road'] as const).map((k) => <Stat key={k} label={`${sourceLabel(k)} token`} value={pct(p.token_tolerance[k])} hint={`valid ${p.token_validity_hours[k]} h`} />)}
        </div>
        <p className="mt-2 text-xs text-ink-500">Tolerance = how far a road reading may differ from the token weight before the truck is diverted to the lane. With a consistent token, the road reading only has to confirm the weight is unchanged.</p>
      </Card>
      <Card title="Limits, allowance and fees" subtitle={`limits ${p.limits_version} · engine ${p.engine_version}`}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Discretion allowance" value={`${p.discretion_allowance_pct} %`} hint="Second Schedule, < 5 %" tone={p.discretion_allowance_pct > 0 ? 'teal' : 'default'} />
          <Stat label="Max length" value={`${p.dimension_limits.max_length_m} m`} /><Stat label="Max width" value={`${p.dimension_limits.max_width_m} m`} /><Stat label="Max height" value={`${p.dimension_limits.max_height_m} m`} />
        </div>
        <div className="mt-3"><div className="section-title mb-1">Reported gross limits by axle count (to be verified)</div><div className="flex flex-wrap gap-1">{Object.entries(p.reported_gvm_by_axles).map(([k, v]) => <span key={k} className="chip">{k} axles · {fmtKg(v)}</span>)}</div></div>
        <div className="mt-3">
          <div className="section-title mb-1">Overload fee schedule ({p.fee_schedule.currency})</div>
          <Table head={['Overload (kg)', `Fee (${p.fee_schedule.currency})`]} dense>
            {p.fee_schedule.points.map(([kg, fee]) => <tr key={kg} className="tr"><td className="td tabular-nums">{fmtKg(kg)}</td><td className="td tabular-nums">{fmtUsd(fee)}</td></tr>)}
          </Table>
          <p className="mt-1 text-xs text-ink-500">Detention free for {p.fee_schedule.detention_free_days} days, then {fmtUsd(p.fee_schedule.detention_usd_per_day)} a day. Repeat overload in the same journey: ×{p.fee_schedule.repeat_offence_multiplier} (Reg 14). {p.fee_schedule.note}</p>
        </div>
      </Card>
      <Card title="Legal hooks (EAC Vehicle Load Control Regulations, 2018)" className="lg:col-span-2">
        <Table head={['Regulation', 'What it says', 'Design consequence']} dense>
          {p.legal_hooks.map((h) => <tr key={h.reg} className="tr"><td className="td whitespace-nowrap font-medium">{h.reg}</td><td className="td">{h.says}</td><td className="td">{h.consequence}</td></tr>)}
        </Table>
        {p.notes.length > 0 && <ul className="mt-3 list-inside list-disc text-xs text-ink-500">{p.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
      </Card>
    </div>
  );
}
