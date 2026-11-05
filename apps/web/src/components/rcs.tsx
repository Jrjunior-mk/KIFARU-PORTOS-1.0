/** RCS v2 presentational components: route / stream / lane-type / station-kind / token badges and the stream-mix bar. */
import type { ReactNode } from 'react';
import type { Decision, TokenOut } from '../api/types';
import { Badge } from './ui';
import { Icon, type IconName } from './icons';
import { fmtAgo, fmtDateTime, fmtKg } from '../lib/format';
import { laneTypeLabel, ROUTE_INSTRUCTION, ROUTE_LABEL, ROUTE_TONE, routeOf, sourceLabel, stationKindLabel, streamLabel } from '../lib/rcs';

export function RouteBadge({ route, decision, nodeKind, withInstruction }: { route?: string | null; decision?: Decision | null; nodeKind?: string | null; withInstruction?: boolean }) {
  const r = routeOf(route, decision, nodeKind);
  if (!r) return <Badge tone="slate">no route</Badge>;
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <Badge tone={ROUTE_TONE[r]}>{ROUTE_LABEL[r]}</Badge>
      {withInstruction && <span className="text-sm text-ink-700 dark:text-slate-200">{ROUTE_INSTRUCTION[r]}</span>}
    </span>
  );
}

const LANE_ICON: Record<string, IconName> = { wim_highspeed: 'road', wim_lowspeed: 'road', static: 'static', port_gateout: 'port', origin_scale: 'quarry', rolling_verification: 'lane' };
const LANE_TONE: Record<string, 'slate' | 'teal' | 'blue' | 'violet' | 'amber' | 'green' | 'red'> = { wim_highspeed: 'slate', wim_lowspeed: 'slate', static: 'red', port_gateout: 'teal', origin_scale: 'violet', rolling_verification: 'blue' };

export function LaneTypeBadge({ type: t, legalGrade }: { type: string | null | undefined; legalGrade?: boolean }) {
  const key = t ?? 'wim_highspeed';
  return (
    <span className="inline-flex items-center gap-1">
      <Badge tone={LANE_TONE[key] ?? 'slate'}><span className="inline-flex items-center gap-1"><Icon name={LANE_ICON[key] ?? 'road'} size={12} />{laneTypeLabel(t)}</span></Badge>
      {legalGrade !== undefined && <Badge tone={legalGrade ? 'green' : 'slate'} title={legalGrade ? 'Weights-and-measures approved (Reg 5)' : 'Screening only: static scale remains the legal reference'}>{legalGrade ? 'legal grade' : 'screening'}</Badge>}
    </span>
  );
}

const KIND_ICON: Record<string, IconName> = { road_station: 'road', port_gate: 'port', origin_site: 'quarry' };
export function StationKindBadge({ kind }: { kind: string | null | undefined }) {
  const k = kind ?? 'road_station';
  const tone = k === 'port_gate' ? 'teal' : k === 'origin_site' ? 'violet' : 'slate';
  return <Badge tone={tone}><span className="inline-flex items-center gap-1"><Icon name={KIND_ICON[k] ?? 'road'} size={12} />{stationKindLabel(kind)}</span></Badge>;
}

export function StreamBadge({ stream }: { stream: string | null | undefined }) {
  const tone = stream === 'port' ? 'teal' : stream === 'origin' ? 'violet' : 'slate';
  return <Badge tone={tone}>{streamLabel(stream)}</Badge>;
}

export function TokenStatusBadge({ status }: { status: string | null | undefined }) {
  const tone = status === 'active' ? 'green' : status === 'expired' ? 'slate' : status === 'suspended' ? 'amber' : status === 'revoked' ? 'red' : 'slate';
  return <Badge tone={tone}>{status ?? 'unknown'}</Badge>;
}

export function TierBadge({ tier }: { tier: number | null | undefined }) {
  if (tier === null || tier === undefined) return <Badge tone="slate">tier —</Badge>;
  const tone = tier === 1 ? 'teal' : tier === 2 ? 'violet' : tier === 3 ? 'blue' : 'amber';
  return <Badge tone={tone} title={`Trust tier ${tier}`}>tier {tier}</Badge>;
}

export function TokenRefLink({ tokenRef, children }: { tokenRef: string | null | undefined; children?: ReactNode }) {
  if (!tokenRef) return <span className="text-ink-400">—</span>;
  return <a className="mono text-brand-700 underline-offset-2 hover:underline dark:text-brand-300" href={`/registry?token=${encodeURIComponent(tokenRef)}`}>{children ?? tokenRef}</a>;
}

/** One-line token summary used in operator / driver / transporter views. */
export function TokenSummary({ t }: { t: TokenOut }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <Icon name="token" size={16} className="text-brand-600" />
      <TokenRefLink tokenRef={t.token_ref} />
      <TokenStatusBadge status={t.status} />
      <TierBadge tier={t.trust_tier} />
      <span className="text-ink-600 dark:text-slate-300">{sourceLabel(t.source)} · {t.issuing_station_code} · {fmtKg(t.gvm_kg)} · issued {fmtAgo(t.issued_at)} · expires {fmtDateTime(t.expires_at)} · honoured {t.honoured_count}×</span>
    </div>
  );
}

/** Horizontal stacked share bar. `parts` are absolute counts; colours by key. */
export function ShareBar({ parts, colors, ariaLabel }: { parts: { key: string; value: number; label?: string }[]; colors: Record<string, string>; ariaLabel: string }) {
  const total = parts.reduce((a, p) => a + p.value, 0);
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-ink-100 dark:bg-ink-800" role="img" aria-label={ariaLabel}>
        {total > 0 && parts.filter((p) => p.value > 0).map((p) => <div key={p.key} style={{ width: `${(p.value / total) * 100}%`, background: colors[p.key] ?? '#94a3b8' }} title={`${p.label ?? p.key}: ${p.value}`} />)}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-ink-500 dark:text-ink-300">
        {parts.map((p) => (
          <span key={p.key} className="inline-flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-sm" style={{ background: colors[p.key] ?? '#94a3b8' }} />{p.label ?? p.key} <span className="font-semibold tabular-nums text-ink-800 dark:text-slate-100">{total ? `${((p.value / total) * 100).toFixed(0)} %` : '—'}</span></span>
        ))}
      </div>
    </div>
  );
}

export const STREAM_COLORS: Record<string, string> = { port: '#0d9488', origin: '#7c3aed', untokened: '#94a3b8' };
export const ROUTE_COLORS: Record<string, string> = { continue: '#16a34a', verification_lane: '#2563eb', static_scale: '#dc2626', port_reweigh: '#d97706', hold: '#7f1d1d' };
