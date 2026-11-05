/** SmartPort port-process types (docs/02-architecture/smartport-port-process-contract.md §2). Re-exported from types.ts. */
import type { Source } from './types';

export const PORT_STAGES = [
  'pre_registered', 'customs_cleared', 'arrived', 'gate_in', 'yard_allocated', 'loaded', 'weighed', 'final_cleared', 'gate_out', 'in_transit', 'delivered',
] as const;
export type PortStage = (typeof PORT_STAGES)[number];
export interface PortStageDef { stage: PortStage | string; order: number; label: string; required_fields: string[]; agency: string }
export interface PortVisitTimelineEntry { stage: PortStage | string; at: string; data: Record<string, unknown> }
export interface PortVisitKpis {
  queue_wait_s: number | null; gate_in_processing_s: number | null; yard_wait_s: number | null; loading_duration_s: number | null;
  weighing_service_s: number | null; clearance_duration_s: number | null; dwell_time_s: number | null; transit_time_s: number | null;
}
export interface PortVisitOut {
  id: string; reference: string; shipment_id: string | null; shipment_reference: string | null; vehicle_id: string | null; plate: string | null;
  driver_id: string | null; transporter_org_id: string | null; appointment_id: string | null; stage: PortStage | string; stage_order: number;
  status: 'active' | 'closed' | 'cancelled' | string; source: Source;
  truck_type?: string | null; container_number?: string | null; cargo_type?: string | null; declared_mass_kg?: number | null; destination?: string | null;
  appointment_at?: string | null; expected_arrival_at?: string | null; pre_registered_at?: string | null;
  customs_declaration_ref?: string | null; bill_of_lading?: string | null; trade_direction?: string | null; duty_status?: string | null; customs_status?: string | null;
  inspection_status?: string | null; permit_status?: string | null; hold_reason?: string | null; customs_cleared_at?: string | null;
  arrived_at?: string | null; anpr_plate?: string | null; rfid_epc?: string | null; appointment_valid?: boolean | null; queue_position?: number | null; queue_length?: number | null; queue_wait_s?: number | null; arrival_lat?: number | null; arrival_lon?: number | null;
  gate_in_at?: string | null; gate_in_id?: string | null; access_authorised?: boolean | null; vehicle_inspection?: string | null; driver_verified?: boolean | null; gate_in_processing_s?: number | null; rejection_reason?: string | null;
  yard_allocated_at?: string | null; terminal_id?: string | null; yard_block?: string | null; container_position?: string | null; loading_instruction?: string | null; yard_wait_s?: number | null;
  loading_start_at?: string | null; loading_end_at?: string | null; equipment_id?: string | null; seal_number?: string | null; cargo_verification?: string | null; cargo_condition?: string | null; loading_exceptions?: string | null;
  weighing_event_id?: string | null; weighing_arrival_at?: string | null; weighing_start_at?: string | null; weighing_end_at?: string | null; tare_kg?: number | null; gross_kg?: number | null; net_kg?: number | null; weight_discrepancy_kg?: number | null; calibration_valid?: boolean | null; token_ref?: string | null;
  final_cleared_at?: string | null; cargo_release_status?: string | null; delivery_order_ref?: string | null; gate_pass_no?: string | null; payment_status?: string | null; clearance_exceptions?: string | null;
  gate_out_at?: string | null; gate_out_id?: string | null; exit_cargo_verified?: boolean | null; exit_authorised?: boolean | null; dwell_time_s?: number | null;
  departed_at?: string | null; route?: string | null; distance_km?: number | null; eta_at?: string | null; stoppage_s?: number | null; delay_reason?: string | null;
  arrived_destination_at?: string | null; delivered_at?: string | null; pod_ref?: string | null; transit_time_s?: number | null;
  timeline: PortVisitTimelineEntry[]; kpis: PortVisitKpis; outstanding: string[]; created_at: string; updated_at: string;
  [k: string]: unknown;
}
export interface PortVisitIn {
  shipment_id?: string | null; vehicle_id: string; driver_id?: string | null; appointment_id?: string | null;
  truck_type?: string | null; container_number?: string | null; cargo_type?: string | null; declared_mass_kg?: number | null; destination?: string | null;
  appointment_at?: string | null; expected_arrival_at?: string | null;
}
export interface StageAdvanceIn { stage: PortStage | string; data: Record<string, unknown>; at?: string }
export type DataClassification = 'actual' | 'published' | 'estimated' | 'simulated';
export interface PortBenchmark { key: string; label: string; value: number | string; unit: string; classification: DataClassification | string; source_url: string | null }
export interface PortKpisOut {
  period_hours: number; visits_total: number; visits_by_stage: Record<string, number>;
  avg_queue_wait_s: number | null; avg_gate_in_processing_s: number | null; avg_yard_wait_s: number | null; avg_loading_duration_s: number | null;
  avg_weighing_service_s: number | null; avg_clearance_duration_s: number | null; avg_dwell_time_s: number | null; p90_dwell_time_s: number | null;
  avg_transit_time_s: number | null; throughput_per_hour: number | null; gate_outs_total: number; exceptions_total: number;
  benchmarks: PortBenchmark[]; label: string;
}
export interface PortBoardColumn { stage: PortStage | string; label: string; count: number; visits: PortVisitOut[] }
export interface PortBoardOut { stages: PortBoardColumn[] }
export interface PortSimIn {
  trucks_per_day: number; hours: number; gates_in: number; gates_out: number; gate_service_existing_s: number; gate_service_smart_s: number;
  loading_equipment: number; loading_minutes_container: number; loading_minutes_bulk: number; loading_minutes_general: number;
  weighbridges: number; weigh_service_existing_s: number; weigh_service_smart_s: number;
  clearance_desks: number; clearance_minutes: number; hold_prob_existing: number; hold_prob_smart: number; hold_minutes: number;
  appointment_smoothing: boolean; peak_factor: number; inland_distance_km: number; inland_speed_kmh: number; stop_prob: number; stop_minutes: number; seed: number; reps: number;
}
export interface PortSimKpis {
  avg_wait_min: number; avg_queue_len: number; max_queue_len: number; avg_processing_min: number; weigh_service_min: number; throughput_per_hour: number;
  avg_dwell_h: number; p90_dwell_h: number; avg_transit_h: number; gate_in_utilisation: number; weigh_utilisation: number; [k: string]: number;
}
export interface PortSimOut { label: 'MODELLED' | string; scenarios: { existing: PortSimKpis; smartport: PortSimKpis }; deltas: Record<string, number>; assumptions: string[]; benchmarks: PortBenchmark[]; calibration_note?: string | null }
export interface DataParameterOut {
  key: string; label: string; value: number | string; unit: string; classification: DataClassification | string; agency: string;
  source_title: string | null; source_url: string | null; period: string | null; notes: string | null; used_by: string[];
}
