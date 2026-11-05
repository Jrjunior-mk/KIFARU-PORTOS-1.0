/** Public explainer for RCS v2 (no sign-in). Content follows docs/01-requirements (port-anchored clearance plan). */
import { Icon } from '../components/icons';
import { Badge } from '../components/ui';

const STREAMS = [
  { stream: 'A. Port trucks', examples: 'Containers from Mombasa', first: 'Port gate-out weigh node', risk: 'Cargo changes after the port (low)' },
  { stream: 'B. Industrial origin trucks', examples: 'Mine, quarry, cement, sugar, fuel depot, farm and factory loads', first: 'An approved scale at the loading site, linked to the registry', risk: 'Under-reported weights at private scales; bulk loads that shift or settle' },
  { stream: 'C. Untokened trucks', examples: 'Spot loads, traders, small fleets, first-time users', first: 'The first RCS road station or Rolling Verification Lane', risk: 'No earlier weight to compare, so more uncertainty' },
];

const CHECKPOINTS = [
  { el: 'A. Port gate-out weigh node', where: 'KPA exit lane, beside the i-Gate', job: 'Low-speed weighing of every loaded truck. Reads plate, RFID tag, container number and e-seal. Compares measured with expected weight. Issues the token.' },
  { el: 'B. Origin weigh nodes', where: 'Mines, quarries, factories, depots', job: 'Approved scale at the loading site linked to the registry, with plate, tag and a signed digital ticket. Issues an origin token.' },
  { el: 'C. Road screening nodes', where: 'Dongo Kundu, Mariakani, Mtwapa and other stations', job: 'Existing high-speed WIM feed plus plate, tag and LiDAR readers. Checks tokens and issues road tokens.' },
  { el: 'D. Rolling Verification Lane', where: 'Beside each road station', job: 'Low-speed scales, dimension portal and cameras. Captures every static-bridge parameter without stopping.' },
  { el: 'E. Static scales', where: 'Existing weighbridges and a port re-weigh lane', job: 'Legal proof for red cases and audits. Results feed calibration.' },
  { el: 'Clearance registry', where: 'Cloud, with edge caches at each site', job: 'One record per truck-journey: tokens, weights, dimensions, certificates, permits, release orders, demerit points, release status.' },
];

const RULES = [
  { where: 'Port', result: 'GREEN', cond: 'Identity and releases valid, gross and axle-group loads below the limit after the margin, measured and expected weight within tolerance. Token issued.' },
  { where: 'Port', result: 'AMBER', cond: 'Near the limit or weight variance too large. Re-weigh in the port, correct if needed.' },
  { where: 'Port', result: 'RED', cond: 'Over the limit beyond the margin. Held for corrective action.' },
  { where: 'Origin', result: 'GREEN', cond: 'Approved scale reading below the limit after the margin, identity match, signed ticket. Origin token issued at an initial trust tier.' },
  { where: 'Road mainline', result: 'GREEN', cond: 'Valid token and identity match, weight within tolerance of the token weight (about 8 % for port or origin tokens, 11 % for road tokens), dimensions inside limits, axle count matches registration. Or no token but weight below the limit by the full margin.' },
  { where: 'Road mainline', result: 'Divert to lane', cond: 'No token and weight inside the margin band, inconsistent weight, dimension or axle-count mismatch, unreadable identity, or random audit.' },
  { where: 'Verification lane', result: 'GREEN', cond: 'Full parameter set within limits after the margin. Token issued, valid downstream.' },
  { where: 'Verification lane', result: 'RED', cond: 'Over the limit beyond the margin, dimension or permit breach, or inconclusive. Static scale and officer.' },
];

function Flow() {
  const nodes = [
    { x: 20, label: 'Port exit', sub: 'gate-out weigh node', c: '#0d9488' },
    { x: 210, label: 'Road node', sub: 'high-speed WIM + token check', c: '#475569' },
    { x: 400, label: 'Verification lane', sub: '~10 km/h, full parameters', c: '#2563eb' },
    { x: 590, label: 'Static scale', sub: 'legal proof, officer', c: '#dc2626' },
  ];
  return (
    <svg viewBox="0 0 760 170" role="img" aria-label="Flow: port exit, road node, verification lane, static scale" className="h-auto w-full text-ink-800 dark:text-slate-100">
      <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5 0 10z" fill="currentColor" /></marker></defs>
      {nodes.map((n) => (
        <g key={n.label}>
          <rect x={n.x} y="40" width="150" height="62" rx="12" fill={n.c} opacity="0.12" stroke={n.c} strokeWidth="1.5" />
          <text x={n.x + 75} y="66" textAnchor="middle" fontSize="13" fontWeight="600" fill="currentColor">{n.label}</text>
          <text x={n.x + 75} y="86" textAnchor="middle" fontSize="10.5" fill="currentColor" opacity="0.75">{n.sub}</text>
        </g>
      ))}
      <g stroke="currentColor" strokeWidth="1.5" fill="none" markerEnd="url(#arr)">
        <path d="M170 71 H208" /><path d="M360 71 H398" /><path d="M550 71 H588" />
      </g>
      <g fontSize="10.5" fill="currentColor" opacity="0.8">
        <text x="189" y="62" textAnchor="middle">token</text>
        <text x="379" y="62" textAnchor="middle">AMBER</text>
        <text x="569" y="62" textAnchor="middle">RED</text>
      </g>
      <path d="M285 102 C 285 150, 110 150, 95 102" stroke="#16a34a" strokeWidth="1.5" fill="none" strokeDasharray="4 3" markerEnd="url(#arr)" />
      <text x="190" y="152" textAnchor="middle" fontSize="10.5" fill="#16a34a">GREEN: continue, token honoured at later stations</text>
      <path d="M475 102 C 475 135, 300 140, 290 108" stroke="#16a34a" strokeWidth="1.5" fill="none" strokeDasharray="4 3" markerEnd="url(#arr)" />
      <text x="430" y="132" textAnchor="middle" fontSize="10.5" fill="#16a34a">lane pass issues a token</text>
    </svg>
  );
}

export default function About() {
  return (
    <main className="min-h-screen bg-surface-50 dark:bg-ink-950">
      <header className="border-b border-ink-100 bg-white/80 backdrop-blur dark:border-ink-800 dark:bg-ink-950/80">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <a href="/" className="flex items-center gap-2 font-bold"><img src="/favicon.svg" alt="" width="28" height="28" className="rounded-lg" />KIFARU <span className="text-brand-600 dark:text-brand-400">PORTOS</span></a>
          <nav className="flex items-center gap-2 text-sm"><a className="btn-ghost text-xs" href="/verify">Verify</a><a className="btn-primary text-xs" href="/login">Sign in</a></nav>
        </div>
      </header>
      <article className="mx-auto max-w-5xl space-y-10 px-4 py-10 sm:px-6">
        <section>
          <div className="section-title">Rolling Clearance System v2</div>
          <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">How port-anchored clearance works</h1>
          <p className="mt-3 max-w-3xl text-ink-600 dark:text-slate-300">Weighing every heavy truck at its first trusted point, and letting later stations honour that result, is what removes repeat stops. For port cargo that point is the port exit. For mines, quarries, factories and other loaders it is the loading site or the first road station.</p>
          <div className="card mt-6 p-4 sm:p-6"><Flow /></div>
        </section>

        <section>
          <h2 className="text-xl font-semibold">Three truck streams, one rule</h2>
          <p className="mt-1 text-sm text-ink-600 dark:text-slate-300">A signed Load Compliance Token is issued at a truck's first verified weighing point, and every later station honours it until it expires or a consistency check fails.</p>
          <div className="card mt-4 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead><tr><th className="th">Stream</th><th className="th">Examples</th><th className="th">First trusted weight</th><th className="th">Main risk</th></tr></thead>
              <tbody>{STREAMS.map((s) => <tr key={s.stream} className="tr"><td className="td font-medium">{s.stream}</td><td className="td">{s.examples}</td><td className="td">{s.first}</td><td className="td">{s.risk}</td></tr>)}</tbody>
            </table>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold">Five checkpoints and one registry</h2>
          <div className="card mt-4 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead><tr><th className="th">Element</th><th className="th">Where</th><th className="th">Job</th></tr></thead>
              <tbody>{CHECKPOINTS.map((c) => <tr key={c.el} className="tr"><td className="td font-medium">{c.el}</td><td className="td">{c.where}</td><td className="td">{c.job}</td></tr>)}</tbody>
            </table>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-semibold">Decision rules</h2>
          <div className="card mt-4 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead><tr><th className="th">Where</th><th className="th">Result</th><th className="th">Conditions</th></tr></thead>
              <tbody>{RULES.map((r, i) => <tr key={i} className="tr"><td className="td">{r.where}</td><td className="td"><Badge tone={r.result === 'GREEN' ? 'green' : r.result === 'RED' ? 'red' : 'amber'}>{r.result}</Badge></td><td className="td">{r.cond}</td></tr>)}</tbody>
            </table>
          </div>
          <p className="mt-3 text-sm text-ink-600 dark:text-slate-300">For loads in the margin band, the road reading no longer has to be accurate against the limit. It only has to confirm that the weight is unchanged since the port, which is a much easier test. Random audits send about 3 % of mainline greens through the lane at first, falling toward 1–2 % as trust builds.</p>
        </section>

        <section className="grid gap-4 sm:grid-cols-3">
          {[
            { icon: 'shield' as const, t: 'The legal opening', b: 'Reg 10(2) excuses vehicles previously confirmed compliant by screening devices from producing a paper certificate. Reg 3(4) still reserves tickets and release orders for overloaded vehicles to authorised officers.' },
            { icon: 'lane' as const, t: 'Own lanes', b: 'A Rolling Verification Lane beside each station lets doubtful trucks roll through at about 10 km/h: one lane handles about 370 trucks an hour, roughly 25 times a static lane.' },
            { icon: 'ruler' as const, t: 'Weight is not enough', b: 'High-speed WIM does not measure dimensions, lifted axles, per-wheel balance, permits or certificates. RCS adds a LiDAR portal, cameras, per-wheel scales and registry checks.' },
          ].map((c) => (
            <div key={c.t} className="card p-4"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300"><Icon name={c.icon} /></span><div className="mt-3 font-semibold">{c.t}</div><p className="mt-1 text-sm text-ink-600 dark:text-slate-300">{c.b}</p></div>
          ))}
        </section>

        <footer className="border-t border-ink-100 pt-6 text-xs text-ink-500 dark:border-ink-800 dark:text-ink-300">
          Modelled figures on this platform are Monte Carlo estimates under stated assumptions and must be replaced with measured data. The static scale remains the legal reference. Source: EAC Vehicle Load Control (Enforcement Measures) Regulations, 2018.
        </footer>
      </article>
    </main>
  );
}
