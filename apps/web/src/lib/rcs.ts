/** RCS v2 labels, instructions and tone helpers shared by pages (contract: docs/02-architecture/rcs-v2-api-contract.md). */
import type { Decision, LaneType, NodeKind, Route, StationKind, Stream, TokenSource } from '../api/types';

export const ROUTE_INSTRUCTION: Record<Route, string> = {
  continue: 'Continue — no stop required',
  verification_lane: 'Divert to the rolling verification lane (about 10 km/h, no stop)',
  static_scale: 'Proceed to the static scale for legal weighing',
  port_reweigh: 'Return to the port re-weigh lane',
  hold: 'Hold for corrective action',
};
export const ROUTE_LABEL: Record<Route, string> = {
  continue: 'Continue', verification_lane: 'Verification lane', static_scale: 'Static scale', port_reweigh: 'Port re-weigh', hold: 'Hold',
};
export const ROUTE_SPEECH: Record<Route, string> = {
  continue: 'Green. Continue. No stop required.',
  verification_lane: 'Amber. Divert to the rolling verification lane. Keep rolling at ten kilometres per hour.',
  static_scale: 'Proceed to the static scale for legal weighing.',
  port_reweigh: 'Return to the port re-weigh lane.',
  hold: 'Red. Hold for corrective action and wait for an officer.',
};
export const ROUTES_ALL: Route[] = ['continue', 'verification_lane', 'static_scale', 'port_reweigh', 'hold'];

export function routeOf(route: string | null | undefined, decision: Decision | null | undefined, nodeKind?: string | null): Route | null {
  if (route && (ROUTES_ALL as string[]).includes(route)) return route as Route;
  if (!decision) return null;
  if (decision === 'GREEN') return 'continue';
  if (decision === 'AMBER') return nodeKind === 'port_gateout' ? 'port_reweigh' : nodeKind === 'verification_lane' ? 'static_scale' : 'verification_lane';
  return nodeKind === 'port_gateout' ? 'hold' : 'static_scale';
}

export const ROUTE_TONE: Record<Route, 'green' | 'amber' | 'red' | 'blue' | 'slate'> = {
  continue: 'green', verification_lane: 'amber', static_scale: 'red', port_reweigh: 'amber', hold: 'red',
};

export const LANE_TYPE_LABEL: Record<LaneType, string> = {
  wim_highspeed: 'WIM high-speed', wim_lowspeed: 'WIM low-speed', static: 'Static scale',
  port_gateout: 'Port gate-out', origin_scale: 'Origin scale', rolling_verification: 'Rolling verification',
};
export const STATION_KIND_LABEL: Record<StationKind, string> = { road_station: 'Road station', port_gate: 'Port gate', origin_site: 'Origin site' };
export const NODE_KIND_LABEL: Record<NodeKind, string> = { port_gateout: 'Port gate-out node', origin: 'Origin weigh node', road_mainline: 'Road screening node', verification_lane: 'Rolling verification lane', static: 'Static scale' };
export const STREAM_LABEL: Record<Stream, string> = { port: 'Port truck', origin: 'Industrial origin', untokened: 'Untokened' };
export const SOURCE_LABEL: Record<TokenSource, string> = { port: 'Port gate-out', origin: 'Approved origin scale', road: 'Road node', lane: 'Verification lane' };

export function laneTypeLabel(t: string | null | undefined): string { return t && t in LANE_TYPE_LABEL ? LANE_TYPE_LABEL[t as LaneType] : (t ?? '—'); }
export function stationKindLabel(k: string | null | undefined): string { return k && k in STATION_KIND_LABEL ? STATION_KIND_LABEL[k as StationKind] : 'Road station'; }
export function nodeKindLabel(k: string | null | undefined): string { return k && k in NODE_KIND_LABEL ? NODE_KIND_LABEL[k as NodeKind] : (k ?? 'Road screening node'); }
export function streamLabel(s: string | null | undefined): string { return s && s in STREAM_LABEL ? STREAM_LABEL[s as Stream] : 'Untokened'; }
export function sourceLabel(s: string | null | undefined): string { return s && s in SOURCE_LABEL ? SOURCE_LABEL[s as TokenSource] : (s ?? '—'); }

/** Node kind derived from lane type when the record does not carry one. */
export function nodeKindForLane(laneType: string | null | undefined): NodeKind {
  switch (laneType) {
    case 'port_gateout': return 'port_gateout';
    case 'origin_scale': return 'origin';
    case 'rolling_verification': return 'verification_lane';
    case 'static': return 'static';
    default: return 'road_mainline';
  }
}

export function fmtUsd(x: number | null | undefined): string {
  if (x === null || x === undefined) return '—';
  return `USD ${Math.round(x).toLocaleString('en-KE')}`;
}
