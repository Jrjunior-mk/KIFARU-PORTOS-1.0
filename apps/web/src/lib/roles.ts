import type { Role } from '../api/types';
import type { IconName } from '../components/icons';

export type RouteGroup = 'Operations' | 'Registry' | 'Analysis' | 'Admin';
export interface RouteDef { path: string; label: string; roles: Role[]; description: string; icon: IconName; group: RouteGroup }

/** Route -> role map (platform_admin can open everything; see README). */
export const ROUTES: RouteDef[] = [
  { path: '/control', label: 'Control Centre', roles: ['port_controller', 'auditor', 'regulator_readonly'], description: 'Network view of stations, queues, clearance feed, incidents', icon: 'dashboard', group: 'Operations' },
  { path: '/operator', label: 'Weighbridge', roles: ['weighbridge_operator'], description: 'Lane console: readings, decisions, verification lane, release orders', icon: 'scale', group: 'Operations' },
  { path: '/transporter', label: 'Transporter', roles: ['transporter_admin', 'dispatcher'], description: 'Fleet, shipments, slot booking, backhaul, permits', icon: 'truck', group: 'Operations' },
  { path: '/driver', label: 'Driver', roles: ['driver'], description: 'Large-tile in-cab screen', icon: 'steering', group: 'Operations' },
  { path: '/owner', label: 'Cargo owner', roles: ['cargo_owner'], description: 'Shipment passport, alerts, backhaul offers', icon: 'box', group: 'Operations' },
  { path: '/warehouse', label: 'Warehouse', roles: ['warehouse_manager'], description: 'Incoming shipments and readiness', icon: 'warehouse', group: 'Operations' },
  { path: '/port', label: 'Port operations', roles: ['port_controller', 'weighbridge_operator', 'transporter_admin', 'dispatcher', 'cargo_owner', 'auditor'], description: 'Eleven-stage truck and cargo workflow from pre-arrival to delivery, port KPIs and benchmarks', icon: 'anchor', group: 'Operations' },
  { path: '/registry', label: 'Clearance Registry', roles: ['port_controller', 'weighbridge_operator', 'auditor', 'regulator_readonly'], description: 'Load Compliance Tokens, release orders, permits, trust tiers and policy', icon: 'registry', group: 'Registry' },
  { path: '/model', label: 'RCS v2 Model', roles: ['port_controller', 'auditor', 'regulator_readonly'], description: 'Monte Carlo explorer for the port-anchored clearance chain (modelled)', icon: 'flask', group: 'Analysis' },
  { path: '/data', label: 'Data register', roles: ['port_controller', 'weighbridge_operator', 'transporter_admin', 'dispatcher', 'driver', 'cargo_owner', 'warehouse_manager', 'auditor', 'regulator_readonly'], description: 'Every parameter with its provenance: actual, published, estimated or simulated', icon: 'database', group: 'Analysis' },
  { path: '/twin', label: 'Digital twin', roles: ['port_controller', 'weighbridge_operator', 'auditor', 'regulator_readonly', 'transporter_admin', 'dispatcher'], description: '3D port scene driven by live events', icon: 'cube', group: 'Analysis' },
  { path: '/admin', label: 'Admin', roles: [], description: 'Users, stations, integrations, ledger, agents', icon: 'settings', group: 'Admin' },
];

export const GROUP_ORDER: RouteGroup[] = ['Operations', 'Registry', 'Analysis', 'Admin'];

export function routesFor(roles: Role[]): RouteDef[] {
  if (roles.includes('platform_admin')) return ROUTES;
  return ROUTES.filter((r) => r.roles.some((x) => roles.includes(x)));
}

export function routeByPath(path: string): RouteDef | undefined {
  return ROUTES.find((r) => path === r.path || path.startsWith(`${r.path}/`));
}

/** Landing route after login. */
export function homeFor(roles: Role[]): string {
  if (roles.includes('platform_admin')) return '/admin';
  const order: Role[] = ['port_controller', 'weighbridge_operator', 'transporter_admin', 'dispatcher', 'driver', 'cargo_owner', 'warehouse_manager', 'auditor', 'regulator_readonly'];
  for (const r of order) if (roles.includes(r)) return routesFor([r])[0]?.path ?? '/';
  return '/';
}
