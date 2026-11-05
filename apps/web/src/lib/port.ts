/** SmartPort port-process helpers: stage labels, owning agencies, field rendering heuristics, duration formatting. */
import { PORT_STAGES, type DataClassification, type PortStage, type PortStageDef } from '../api/types';

export const STAGE_LABEL: Record<PortStage, string> = {
  pre_registered: 'Pre-arrival registration',
  customs_cleared: 'Customs clearance',
  arrived: 'Arrival and identification',
  gate_in: 'Gate-in and security',
  yard_allocated: 'Yard allocation',
  loaded: 'Cargo verification and loading',
  weighed: 'Automated weighing',
  final_cleared: 'Final clearance',
  gate_out: 'Gate-out',
  in_transit: 'Inland transport',
  delivered: 'Delivery and trip closure',
};
export const STAGE_SHORT: Record<PortStage, string> = {
  pre_registered: 'Pre-registered', customs_cleared: 'Customs cleared', arrived: 'Arrived', gate_in: 'Gate-in', yard_allocated: 'Yard', loaded: 'Loaded',
  weighed: 'Weighed', final_cleared: 'Final clearance', gate_out: 'Gate-out', in_transit: 'In transit', delivered: 'Delivered',
};
export const STAGE_AGENCY: Record<PortStage, string> = {
  pre_registered: 'Transporter / clearing agent', customs_cleared: 'KRA, KenTrade, KEBS', arrived: 'KPA', gate_in: 'KPA', yard_allocated: 'KPA',
  loaded: 'KPA', weighed: 'KPA + KeNHA', final_cleared: 'KPA', gate_out: 'KPA', in_transit: 'Transporters, telematics, KeNHA', delivered: 'Cargo owner / warehouse',
};

/** Fallback stage definitions used until GET /port/stages answers (same order and owning agency as the contract). */
export const FALLBACK_STAGES: PortStageDef[] = PORT_STAGES.map((s, i) => ({ stage: s, order: i + 1, label: STAGE_LABEL[s], required_fields: [], agency: STAGE_AGENCY[s] }));

export function stageLabel(s: string | null | undefined): string { return s && s in STAGE_LABEL ? STAGE_LABEL[s as PortStage] : (s ?? '—').replace(/_/g, ' '); }
export function stageShort(s: string | null | undefined): string { return s && s in STAGE_SHORT ? STAGE_SHORT[s as PortStage] : (s ?? '—').replace(/_/g, ' '); }
export function nextStage(s: string | null | undefined): PortStage | null {
  const i = PORT_STAGES.indexOf(s as PortStage);
  return i >= 0 && i < PORT_STAGES.length - 1 ? PORT_STAGES[i + 1] : null;
}

export const CLASS_TONE: Record<DataClassification, 'teal' | 'blue' | 'amber' | 'slate'> = { actual: 'teal', published: 'blue', estimated: 'amber', simulated: 'slate' };
export function classTone(c: string | null | undefined): 'teal' | 'blue' | 'amber' | 'slate' { return c && c in CLASS_TONE ? CLASS_TONE[c as DataClassification] : 'slate'; }

/** Allowed values for enumerated stage fields (contract §1). */
export const FIELD_OPTIONS: Record<string, string[]> = {
  trade_direction: ['import', 'export', 'transit'],
  duty_status: ['paid', 'unpaid', 'pending'],
  customs_status: ['cleared', 'pending', 'held'],
  inspection_status: ['required', 'completed', 'not_required'],
  permit_status: ['approved', 'rejected', 'pending'],
  vehicle_inspection: ['passed', 'failed'],
  cargo_verification: ['matched', 'mismatched'],
  cargo_condition: ['good', 'damaged'],
  cargo_release_status: ['approved', 'pending'],
  payment_status: ['paid', 'unpaid'],
  cargo_type: ['general', 'container', 'bulk', 'liquid', 'reefer', 'hazardous'],
  truck_type: ['container', 'flatbed', 'tanker', 'tipper', 'box', 'reefer'],
  delay_reason: ['none', 'traffic', 'breakdown', 'road_closure', 'weighbridge', 'police_check', 'other'],
};
const BOOL_FIELDS = new Set(['appointment_valid', 'access_authorised', 'driver_verified', 'calibration_valid', 'exit_cargo_verified', 'exit_authorised']);

export type FieldKind = 'datetime' | 'number' | 'select' | 'boolean' | 'text';
export function fieldKind(name: string): FieldKind {
  if (name in FIELD_OPTIONS) return 'select';
  if (BOOL_FIELDS.has(name)) return 'boolean';
  if (name.endsWith('_at')) return 'datetime';
  if (/(_s|_kg|_km|_lat|_lon|_position|_length)$/.test(name) || name === 'queue_position' || name === 'queue_length') return 'number';
  return 'text';
}
export function fieldLabel(name: string): string {
  const base = name.replace(/_at$/, ' time').replace(/_s$/, ' (seconds)').replace(/_kg$/, ' (kg)').replace(/_km$/, ' (km)').replace(/_/g, ' ');
  return base.charAt(0).toUpperCase() + base.slice(1);
}

export function fmtSeconds(s: number | null | undefined, digits = 0): string {
  if (s === null || s === undefined) return '—';
  if (s < 90) return `${s.toFixed(0)} s`;
  if (s < 5400) return `${(s / 60).toFixed(digits)} min`;
  return `${(s / 3600).toFixed(1)} h`;
}
export function fmtBench(v: number | string, unit: string): string {
  return typeof v === 'number' ? `${v.toLocaleString('en-KE', { maximumFractionDigits: 2 })} ${unit}` : `${v} ${unit}`;
}
