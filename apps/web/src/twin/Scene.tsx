/**
 * Stylised 3D scene: Port of Mombasa container terminal + gate, the trunk road, two weighing stations (RCS v2 layout:
 * high-speed WIM screening node on the mainline, rolling verification lane, static scale, inspection/holding area) and a
 * warehouse.
 *
 * Trucks enter one at a time from the port end, in the order their clearance decisions arrived, keep a safe headway behind
 * the truck ahead, drive the whole approach, and split at the station according to their route:
 *   GREEN  continue            -> straight through on the mainline at full speed
 *   AMBER  verification_lane   -> diverges into the rolling verification lane, rolls through slowly, rejoins
 *   AMBER  static_scale        -> diverges to the static scale, stops, rejoins
 *   RED    static_scale / hold -> static scale, then inspection / holding bay, then leaves
 */
import { Html, OrbitControls } from '@react-three/drei';
import { Canvas, useFrame } from '@react-three/fiber';
import { useEffect, useRef, useState } from 'react';
import type { Group, Mesh } from 'three';
import type { Decision } from '../api/types';

export type TwinRoute = 'continue' | 'verification_lane' | 'static_scale' | 'port_reweigh' | 'hold';
export interface TwinStation { id: string; code: string; name: string; status: string; queue_len: number; x: number; laneIds: string[]; hasLane: boolean }
export interface TwinTruck { id: string; laneId: string | null; stationIdx: number; decision: Decision | null; route: TwinRoute; plate: string | null; spawnedAt: number; source: string | null }
export interface TwinIncident { id: string; stationIdx: number | null; severity: string; title: string }

const DECISION_HEX: Record<Decision, string> = { GREEN: '#16a34a', AMBER: '#d97706', RED: '#dc2626' };
export const STATION_X = [-8, 18];
const ROAD_Z = 0; // mainline (high-speed WIM screening node)
const LANE_Z = 3.4; // rolling verification lane (~10 km/h, no stop)
const STATIC_Z = 6.8; // static scale (legal reference)
const PARK = { x: 6, z: 12 };
const ROAD_START = -46;
const ROAD_END = 46;
const BASE_SPEED = 7; // scene units per second at 1x
const HEADWAY = 9; // minimum gap between trucks on the same lane
const TRUCK_LEN = 4;

type Pos = { x: number; z: number; done: boolean };
type Positions = Map<string, Pos>;

function Box({ position, size, color, opacity = 1 }: { position: [number, number, number]; size: [number, number, number]; color: string; opacity?: number }) {
  return (
    <mesh position={position} castShadow receiveShadow>
      <boxGeometry args={size} />
      <meshStandardMaterial color={color} transparent={opacity < 1} opacity={opacity} />
    </mesh>
  );
}

function Label({ position, children, small }: { position: [number, number, number]; children: React.ReactNode; small?: boolean }) {
  return (
    <Html position={position} center distanceFactor={small ? 40 : 60} zIndexRange={[10, 0]} style={{ pointerEvents: 'none' }}>
      <div className={`whitespace-nowrap rounded bg-slate-900/80 px-1.5 py-0.5 text-white ${small ? 'text-[10px]' : 'text-xs font-semibold'}`}>{children}</div>
    </Html>
  );
}

function Terminal() {
  const stacks: JSX.Element[] = [];
  const colors = ['#1e40af', '#0f766e', '#7c2d12', '#374151', '#4c1d95'];
  for (let r = 0; r < 4; r++) for (let c = 0; c < 7; c++) {
    const h = 1 + ((r * 7 + c) % 3);
    stacks.push(<Box key={`${r}-${c}`} position={[-42 + c * 2.6, h / 2, -10 - r * 3.2]} size={[2.4, h, 1.2]} color={colors[(r + c) % colors.length]} />);
  }
  return (
    <group>
      <Box position={[-33, -0.02, -14]} size={[22, 0.04, 14]} color="#475569" />
      {stacks}
      {[-40, -32, -24].map((x) => (
        <group key={x} position={[x, 0, -22]}>
          <Box position={[-1.5, 3.5, 0]} size={[0.3, 7, 0.3]} color="#dc8a3a" /><Box position={[1.5, 3.5, 0]} size={[0.3, 7, 0.3]} color="#dc8a3a" /><Box position={[0, 7, 1]} size={[0.3, 0.3, 8]} color="#dc8a3a" />
        </group>
      ))}
      <Box position={[-33, -0.1, -27]} size={[26, 0.02, 6]} color="#1e3a8a" />
      <Label position={[-33, 6, -14]}>Port of Mombasa — container terminal</Label>
    </group>
  );
}

function Gate() {
  return (
    <group position={[-30, 0, ROAD_Z]}>
      <Box position={[0, 1.5, -2.5]} size={[0.6, 3, 0.6]} color="#64748b" /><Box position={[0, 1.5, 2.5]} size={[0.6, 3, 0.6]} color="#64748b" /><Box position={[0, 3.2, 0]} size={[0.6, 0.5, 6]} color="#64748b" />
      <Box position={[0, 0.02, 0]} size={[2.4, 0.05, 3.6]} color="#0ea5a0" opacity={0.9} />
      <Label position={[0, 4.2, 0]} small>Gate 18 — gate-out weigh node</Label>
    </group>
  );
}

function Station({ s, idx }: { s: TwinStation; idx: number }) {
  const x = STATION_X[idx];
  const col = s.status === 'operational' ? '#0d9488' : s.status === 'degraded' ? '#d97706' : '#dc2626';
  return (
    <group position={[x, 0, 0]}>
      {/* high-speed WIM sensor rows in the mainline */}
      <Box position={[-1.2, 0.02, ROAD_Z]} size={[0.6, 0.05, 3.6]} color="#0ea5a0" opacity={0.9} />
      <Box position={[1.2, 0.02, ROAD_Z]} size={[0.6, 0.05, 3.6]} color="#0ea5a0" opacity={0.9} />
      {/* screening gantry: cameras, RFID, LiDAR */}
      <Box position={[0, 2.6, -2.6]} size={[0.3, 5.2, 0.3]} color={col} /><Box position={[0, 2.6, 2.4]} size={[0.3, 5.2, 0.3]} color={col} /><Box position={[0, 5.2, -0.1]} size={[0.3, 0.3, 5.3]} color={col} />
      {/* rolling verification lane: per-wheel scales + dimension portal */}
      <Box position={[0, 0.03, LANE_Z]} size={[8, 0.06, 2.2]} color={s.hasLane ? '#115e59' : '#3f3f46'} />
      <Box position={[-3, 0.05, LANE_Z]} size={[0.5, 0.06, 2.0]} color="#5eead4" /><Box position={[3, 0.05, LANE_Z]} size={[0.5, 0.06, 2.0]} color="#5eead4" />
      <Box position={[-4.5, 2.2, LANE_Z - 1.5]} size={[0.25, 4.4, 0.25]} color="#5eead4" /><Box position={[-4.5, 2.2, LANE_Z + 1.5]} size={[0.25, 4.4, 0.25]} color="#5eead4" /><Box position={[-4.5, 4.4, LANE_Z]} size={[0.25, 0.25, 3.2]} color="#5eead4" />
      <Label position={[0, 1.4, LANE_Z + 1.9]} small>{s.hasLane ? 'rolling verification lane · ~10 km/h' : 'verification lane (not built)'}</Label>
      {/* static scale + cabin */}
      <Box position={[0, 0.03, STATIC_Z]} size={[5, 0.06, 2]} color="#94a3b8" />
      <Box position={[0, 1, STATIC_Z + 2.2]} size={[2, 2, 1.2]} color="#e2e8f0" />
      <Label position={[0, 1.4, STATIC_Z - 1.6]} small>static scale · legal reference</Label>
      <Label position={[0, 6.4, -0.5]}>{s.code} · {s.status} · queue {s.queue_len}</Label>
    </group>
  );
}

function QueueGhosts({ s, idx }: { s: TwinStation; idx: number }) {
  const n = Math.min(s.queue_len, 16);
  const x0 = STATION_X[idx] - 4;
  return (
    <group>
      {Array.from({ length: n }, (_, i) => <Box key={i} position={[x0 - i * 1.4, 0.4, STATIC_Z]} size={[1.1, 0.8, 0.7]} color="#94a3b8" opacity={0.4} />)}
      {s.queue_len > 0 && <Label position={[x0 - Math.min(n, 6) * 0.7, 2, STATIC_Z + 1.2]} small>observed static queue {s.queue_len}</Label>}
    </group>
  );
}

function Parking() {
  return (
    <group position={[PARK.x, 0, PARK.z]}>
      <Box position={[0, -0.01, 0]} size={[16, 0.04, 6]} color="#52525b" />
      <Label position={[0, 1.5, 0]} small>inspection / holding · officer release order</Label>
    </group>
  );
}

function Warehouse() {
  return (
    <group position={[34, 0, 12]}>
      <Box position={[0, 2, 0]} size={[12, 4, 7]} color="#cbd5e1" /><Box position={[0, 4.3, 0]} size={[12.4, 0.5, 7.4]} color="#64748b" />
      {[-3, 0, 3].map((z) => <Box key={z} position={[-6.1, 1, z]} size={[0.2, 2, 1.6]} color="#334155" />)}
      <Label position={[0, 5.5, 0]}>Warehouse / ICD</Label>
    </group>
  );
}

function Road() {
  return (
    <group>
      <Box position={[0, -0.03, ROAD_Z]} size={[ROAD_END - ROAD_START + 4, 0.02, 4.2]} color="#334155" />
      {/* diverge / merge connectors for the lane and the scale at each station */}
      {STATION_X.map((x) => (
        <group key={x}>
          <Box position={[x, -0.03, (ROAD_Z + STATIC_Z) / 2]} size={[26, 0.02, STATIC_Z - ROAD_Z + 2]} color="#27272a" />
          <Box position={[x, -0.025, LANE_Z]} size={[26, 0.02, 2.4]} color="#3f3f46" />
          <Box position={[x, -0.025, STATIC_Z]} size={[20, 0.02, 2.2]} color="#3f3f46" />
        </group>
      ))}
      {Array.from({ length: 23 }, (_, i) => <Box key={i} position={[ROAD_START + 2 + i * 4, 0, ROAD_Z]} size={[2, 0.03, 0.12]} color="#e2e8f0" />)}
      <Label position={[ROAD_START + 2, 1.5, -3]} small>from port →</Label>
      <Label position={[ROAD_END - 2, 1.5, -3]} small>→ Northern Corridor</Label>
    </group>
  );
}

function routeFor(t: TwinTruck, hasLane: boolean): TwinRoute {
  if (t.decision === 'GREEN') return 'continue';
  if (t.decision === 'RED') return 'hold';
  if (t.route === 'verification_lane' && !hasLane) return 'static_scale';
  if (t.route === 'continue' || t.route === 'port_reweigh') return 'static_scale';
  return t.route;
}

/** Target lane (z) for a truck at longitudinal position x, given its route and the station it is approaching. */
function targetZ(route: TwinRoute, x: number, sx: number): number {
  const inDiverge = x > sx - 11 && x < sx + 11;
  if (!inDiverge) return ROAD_Z;
  if (route === 'verification_lane') return LANE_Z;
  if (route === 'static_scale' || route === 'hold') return STATIC_Z;
  return ROAD_Z;
}

/** Speed factor for a truck at x: slow roll through the verification lane, stop on the static scale. */
function speedFor(route: TwinRoute, x: number, sx: number): number {
  if (route === 'verification_lane' && x > sx - 5 && x < sx + 5) return 0.35;
  if ((route === 'static_scale' || route === 'hold') && x > sx - 3 && x < sx + 3) return 0.5;
  return 1;
}

function Truck({ t, station, positions, speed, leaderId, onDone }: { t: TwinTruck; station: TwinStation | undefined; positions: Positions; speed: number; leaderId: string | null; onDone: (id: string) => void }) {
  const g = useRef<Group>(null);
  const sx = STATION_X[t.stationIdx] ?? STATION_X[0];
  const route = routeFor(t, station?.hasLane ?? true);
  const st = useRef({ x: ROAD_START, z: ROAD_Z, phase: 'approach' as 'approach' | 'weighing' | 'to_park' | 'holding' | 'leaving' | 'done', timer: 0, weighed: false });
  useEffect(() => {
    positions.set(t.id, { x: ROAD_START, z: ROAD_Z, done: false });
    return () => { positions.delete(t.id); };
  }, [t.id, positions]);

  useFrame((_, dtRaw) => {
    const s = st.current; const grp = g.current;
    if (!grp || s.phase === 'done') return;
    const dt = Math.min(dtRaw, 0.1) * speed;
    const v = BASE_SPEED;

    if (s.phase === 'weighing') {
      s.timer -= dt;
      if (s.timer <= 0) { s.weighed = true; s.phase = route === 'hold' ? 'to_park' : 'approach'; }
    } else if (s.phase === 'to_park') {
      const dx = PARK.x - s.x, dz = PARK.z - s.z; const d = Math.hypot(dx, dz);
      if (d < 0.4) { s.phase = 'holding'; s.timer = 6; } else { s.x += (dx / d) * v * 0.8 * dt; s.z += (dz / d) * v * 0.8 * dt; }
    } else if (s.phase === 'holding') {
      s.timer -= dt;
      if (s.timer <= 0) s.phase = 'leaving';
    } else if (s.phase === 'leaving') {
      // released by the officer: back onto the mainline beyond the station and on towards the corridor
      const tx = sx + 16;
      if (s.x < tx - 0.3 || Math.abs(s.z - ROAD_Z) > 0.3) {
        const dx = tx - s.x, dz = ROAD_Z - s.z; const d = Math.hypot(dx, dz);
        s.x += (dx / d) * v * 0.8 * dt; s.z += (dz / d) * v * 0.8 * dt;
      } else {
        s.x += v * dt;
      }
    } else {
      // approach / through: follow the route geometry, keep headway behind the leader when sharing a lane
      const tz = targetZ(route, s.x, sx);
      let factor = speedFor(route, s.x, sx);
      const lead = leaderId ? positions.get(leaderId) : undefined;
      if (lead && !lead.done && Math.abs(lead.z - s.z) < 1.2) {
        const gap = lead.x - s.x;
        if (gap > 0 && gap < HEADWAY) factor = Math.min(factor, Math.max(0, (gap - TRUCK_LEN) / (HEADWAY - TRUCK_LEN)));
      }
      s.x += v * factor * dt;
      s.z += (tz - s.z) * Math.min(1, dt * 2.5);
      // stop on the static scale once (legal weighing), then continue or go to the holding bay
      if ((route === 'static_scale' || route === 'hold') && !s.weighed && Math.abs(s.x - sx) < 0.25) {
        s.phase = 'weighing'; s.timer = route === 'hold' ? 2.5 : 3;
      }
    }

    if (s.x > ROAD_END) { s.phase = 'done'; const p = positions.get(t.id); if (p) p.done = true; onDone(t.id); return; }
    const p = positions.get(t.id); if (p) { p.x = s.x; p.z = s.z; }
    grp.position.set(s.x, 0, s.z);
  });

  const color = t.decision ? DECISION_HEX[t.decision] : '#94a3b8';
  const tag = route === 'continue' ? 'continue' : route === 'verification_lane' ? 'verification lane' : route === 'hold' ? 'static → holding' : 'static scale';
  return (
    <group ref={g} position={[ROAD_START, 0, ROAD_Z]}>
      <Box position={[0.9, 0.9, 0]} size={[1.2, 1.4, 1.1]} color={color} />
      <Box position={[-1.1, 1, 0]} size={[2.6, 1.6, 1.2]} color="#1e293b" />
      <Box position={[-1.1, 1.9, 0]} size={[2.6, 0.2, 1.2]} color={color} />
      {[-2, -1.2, 1].map((x) => <mesh key={x} position={[x, 0.3, 0]}><cylinderGeometry args={[0.3, 0.3, 1.3, 10]} /><meshStandardMaterial color="#0f172a" /></mesh>)}
      <Label position={[0, 2.8, 0]} small>{t.plate ?? '…'} · {t.decision ?? 'pending'} · {tag}</Label>
    </group>
  );
}

/** Releases queued trucks one at a time: the next truck enters only when the previous one has cleared the headway. */
function Spawner({ queue, lastSpawnedId, positions, onSpawn }: { queue: TwinTruck[]; lastSpawnedId: string | null; positions: Positions; onSpawn: () => void }) {
  const cooldown = useRef(0);
  useFrame((_, dt) => {
    cooldown.current -= dt;
    if (!queue.length || cooldown.current > 0) return;
    if (lastSpawnedId) {
      const p = positions.get(lastSpawnedId);
      if (p === undefined) return; // previous truck not mounted yet
      if (!p.done && p.x - ROAD_START < HEADWAY) return;
    }
    cooldown.current = 0.3;
    onSpawn();
  });
  return null;
}

function IncidentMarker({ idx, severity, title }: { idx: number; severity: string; title: string }) {
  const m = useRef<Mesh>(null);
  useFrame(({ clock }) => { if (m.current) { m.current.position.y = 8 + Math.sin(clock.elapsedTime * 3) * 0.4; m.current.rotation.y += 0.02; } });
  return (
    <group position={[STATION_X[idx], 0, -5]}>
      <mesh ref={m} position={[0, 8, 0]}><coneGeometry args={[0.8, 1.6, 4]} /><meshStandardMaterial color={severity === 'critical' || severity === 'high' ? '#dc2626' : '#d97706'} emissive="#7f1d1d" /></mesh>
      <Label position={[0, 10, 0]} small>⚠ {title}</Label>
    </group>
  );
}

export default function Scene({ stations, queue, incidents, speed = 1, onSpawned, onActiveChange }: {
  stations: TwinStation[]; queue: TwinTruck[]; incidents: TwinIncident[]; speed?: number; onSpawned: (id: string) => void; onActiveChange?: (n: number) => void;
}) {
  const [active, setActive] = useState<TwinTruck[]>([]);
  const positions = useRef<Positions>(new Map()).current;
  const lastSpawned = useRef<string | null>(null);
  useEffect(() => { onActiveChange?.(active.length); }, [active.length, onActiveChange]);

  const spawn = () => {
    const next = queue[0];
    if (!next) return;
    lastSpawned.current = next.id;
    setActive((a) => (a.some((t) => t.id === next.id) ? a : [...a, next]));
    onSpawned(next.id);
  };
  const done = (id: string) => setActive((a) => a.filter((t) => t.id !== id));

  return (
    <Canvas shadows camera={{ position: [0, 28, 46], fov: 45 }} dpr={[1, 1.5]} gl={{ antialias: true, powerPreference: 'low-power' }}>
      <color attach="background" args={['#0b1220']} />
      <fog attach="fog" args={['#0b1220', 70, 150]} />
      <ambientLight intensity={0.55} />
      <directionalLight position={[20, 30, 10]} intensity={1.2} castShadow shadow-mapSize={[1024, 1024]} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.05, 0]} receiveShadow><planeGeometry args={[160, 100]} /><meshStandardMaterial color="#1f2937" /></mesh>
      <Terminal /><Gate /><Road /><Parking /><Warehouse />
      {stations.slice(0, 2).map((s, i) => <group key={s.id}><Station s={s} idx={i} /><QueueGhosts s={s} idx={i} /></group>)}
      {active.map((t, i) => <Truck key={t.id} t={t} station={stations[t.stationIdx]} positions={positions} speed={speed} leaderId={i > 0 ? active[i - 1].id : null} onDone={done} />)}
      <Spawner queue={queue} lastSpawnedId={lastSpawned.current} positions={positions} onSpawn={spawn} />
      {incidents.filter((i) => i.stationIdx !== null).map((i) => <IncidentMarker key={i.id} idx={i.stationIdx!} severity={i.severity} title={i.title} />)}
      <OrbitControls maxPolarAngle={Math.PI / 2.1} minDistance={15} maxDistance={110} target={[0, 0, 3]} />
    </Canvas>
  );
}
