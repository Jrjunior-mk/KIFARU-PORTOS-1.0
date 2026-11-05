/** Data register: every parameter the platform and its simulations use, with provenance (actual / published / estimated / simulated). GET /data/register. */
import { useMemo, useState } from 'react';
import { data as dataApi } from '../api/endpoints';
import type { DataParameterOut } from '../api/types';
import { Icon } from '../components/icons';
import { Badge, Card, Empty, ErrorBanner, Field, PageHeader, Skeleton, Stat, Table } from '../components/ui';
import { useQuery } from '../hooks/useQuery';
import { classTone, fmtBench } from '../lib/port';

const CLASSES = [
  { id: 'actual', label: 'Actual', desc: 'Operational records from the platform or an agency system, tagged live.' },
  { id: 'published', label: 'Published', desc: 'Figures from official reports, annual bulletins and press statements, with the source linked.' },
  { id: 'estimated', label: 'Estimated', desc: 'Engineering assumptions used where actual records are not yet available; clearly labelled and validated where possible.' },
  { id: 'simulated', label: 'Simulated', desc: 'Outputs of the platform\'s models; never presented as measurements.' },
] as const;

export default function DataRegister() {
  const q = useQuery(() => dataApi.register(), []);
  const [cls, setCls] = useState('');
  const [agency, setAgency] = useState('');
  const [search, setSearch] = useState('');
  const rows: DataParameterOut[] = q.data ?? [];
  const agencies = useMemo(() => Array.from(new Set(rows.map((r) => r.agency))).sort(), [rows]);
  const filtered = rows.filter((r) => (!cls || r.classification === cls) && (!agency || r.agency === agency) && (!search || `${r.key} ${r.label} ${r.source_title ?? ''}`.toLowerCase().includes(search.toLowerCase())));
  const counts = CLASSES.map((c) => ({ ...c, n: rows.filter((r) => r.classification === c.id).length }));
  return (
    <div className="space-y-4">
      <PageHeader eyebrow="Analysis" title="Data register" subtitle="Where every number comes from. Where actual operational records are unavailable, clearly labelled estimates are used for preliminary modelling and validated where possible." />
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {counts.map((c) => (
          <button key={c.id} className={`text-left ${cls === c.id ? 'ring-2 ring-brand-500 rounded-xl' : ''}`} onClick={() => setCls(cls === c.id ? '' : c.id)} aria-pressed={cls === c.id}>
            <Stat label={c.label} value={c.n} hint={<span className="text-[11px]">{c.desc}</span>} tone={c.id === 'actual' ? 'teal' : c.id === 'estimated' ? 'amber' : 'default'} />
          </button>
        ))}
      </div>
      <Card title="Parameters and sources" subtitle="GET /data/register · click a classification tile to filter · sources open in a new tab" actions={<div className="flex flex-wrap gap-2">
        <Field label="Agency">{(id) => <select id={id} className="input w-auto py-1 text-xs" value={agency} onChange={(e) => setAgency(e.target.value)}><option value="">all</option>{agencies.map((a) => <option key={a} value={a}>{a}</option>)}</select>}</Field>
        <Field label="Search">{(id) => <input id={id} className="input w-44 py-1 text-xs" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="key, label, source" />}</Field>
      </div>}>
        <ErrorBanner error={q.error} />
        {q.loading ? <Skeleton lines={8} /> : filtered.length === 0 ? <Empty>No register entries match</Empty> : (
          <Table head={['Parameter', 'Value', 'Class', 'Agency / source', 'Period', 'Used by']} dense>
            {filtered.map((r) => (
              <tr key={r.key} className="tr">
                <td className="td"><div className="font-medium">{r.label}</div><div className="mono text-ink-500">{r.key}</div>{r.notes && <div className="text-[11px] text-ink-500">{r.notes}</div>}</td>
                <td className="td whitespace-nowrap font-semibold tabular-nums">{fmtBench(r.value, r.unit)}</td>
                <td className="td"><Badge tone={classTone(r.classification)}>{r.classification}</Badge></td>
                <td className="td"><div>{r.agency}</div>{r.source_url ? <a className="inline-flex items-center gap-1 text-brand-700 underline dark:text-brand-300" href={r.source_url} target="_blank" rel="noreferrer">{r.source_title ?? 'source'} <Icon name="link" size={12} /></a> : <span className="text-ink-500">{r.source_title ?? '—'}</span>}</td>
                <td className="td whitespace-nowrap">{r.period ?? '—'}</td>
                <td className="td"><div className="flex flex-wrap gap-1">{r.used_by.length ? r.used_by.map((u) => <span key={u} className="chip">{u}</span>) : <span className="text-ink-400">—</span>}</div></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
