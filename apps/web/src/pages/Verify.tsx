import { type FormEvent, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { rcs as rcsApi, tickets as ticketsApi } from '../api/endpoints';
import type { TokenVerifyOut, VerifyOut } from '../api/types';
import { TierBadge, TokenStatusBadge } from '../components/rcs';
import { DecisionBadge, ErrorBanner, Field, KV, SourceBadge, Spinner } from '../components/ui';
import { useQuery } from '../hooks/useQuery';
import { fmtDateTime, fmtKg } from '../lib/format';
import { sourceLabel } from '../lib/rcs';

/** Public, unauthenticated verification: tickets (GET /tickets/verify/{qr}) and Load Compliance Tokens (GET /rcs/tokens/verify/{ref}). */
export default function Verify() {
  const { qrToken, tokenRef } = useParams<{ qrToken?: string; tokenRef?: string }>();
  const nav = useNavigate();
  const [manual, setManual] = useState('');
  const q = useQuery<VerifyOut>(() => ticketsApi.verify(qrToken!), [qrToken], { enabled: !!qrToken });
  const tq = useQuery<TokenVerifyOut>(() => rcsApi.tokenVerify(tokenRef!), [tokenRef], { enabled: !!tokenRef });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const t = manual.trim();
    // Accept a raw ticket token, a raw token reference (prefixed "token:") or a full verify URL pasted from a QR reader.
    const tok = t.match(/\/verify\/token\/([^/?#]+)/);
    if (tok) { nav(`/verify/token/${encodeURIComponent(tok[1])}`); return; }
    if (t.toLowerCase().startsWith('token:')) { nav(`/verify/token/${encodeURIComponent(t.slice(6).trim())}`); return; }
    const m = t.match(/\/verify\/([^/?#]+)/);
    nav(`/verify/${encodeURIComponent(m ? m[1] : t)}`);
  };

  const active = qrToken || tokenRef;
  return (
    <main className="mx-auto min-h-screen max-w-lg px-4 py-6">
      <header className="mb-5 flex items-center gap-3">
        <img src="/favicon.svg" alt="" width="32" height="32" className="rounded-lg" />
        <div><h1 className="text-lg font-semibold leading-tight">Ticket and token verification</h1><p className="text-xs text-ink-500">KIFARU PORTOS · public check · no sign-in required</p></div>
      </header>

      {!active && (
        <form onSubmit={submit} className="card space-y-3 p-4">
          <Field label="QR token, token reference or verify URL" required hint="Paste a weighing-ticket QR link, or a Load Compliance Token reference (prefix with token: or paste its /verify/token/ link)">{(id) => <input id={id} className="input" value={manual} onChange={(e) => setManual(e.target.value)} placeholder="Scan the QR code or paste its link" required />}</Field>
          <button className="btn-primary" type="submit">Verify</button>
        </form>
      )}

      {qrToken && q.loading && <Spinner label="Checking ticket" />}
      {qrToken && q.error && <ErrorBanner error={q.error} />}
      {qrToken && q.data && <TicketResult r={q.data} />}

      {tokenRef && tq.loading && <Spinner label="Checking token" />}
      {tokenRef && tq.error && <ErrorBanner error={tq.error} />}
      {tokenRef && tq.data && <TokenResult r={tq.data} tokenRef={tokenRef} />}

      {active && <a className="btn-ghost mt-4 text-sm" href="/verify">Check another</a>}
      <p className="mt-6 text-xs text-ink-500 dark:text-ink-300">A pre-screen ticket is produced by a weigh-in-motion pass and is informational only. Only a static-scale ticket is a legal weight certificate. A Load Compliance Token records that a truck was confirmed within limits at its first verified weighing point (Reg 10(2)); it is honoured by later stations while valid and consistent. Tickets and tokens are Ed25519-signed by the platform; the signature is validated server-side on every check.</p>
      <p className="mt-2 text-xs"><a className="underline underline-offset-2" href="/about">How RCS v2 works</a> · <a className="underline underline-offset-2" href="/login">Sign in</a></p>
    </main>
  );
}

function TicketResult({ r }: { r: VerifyOut }) {
  if (!r.valid) {
    return (
      <div role="alert" className="rounded-2xl border-2 border-rose-600 bg-rose-50 p-5 text-rose-900 dark:bg-rose-950/50 dark:text-rose-100">
        <div className="text-2xl font-bold">NOT VALID</div>
        <p className="mt-1 text-sm">{r.ticket_type ? 'The ticket exists but its signature does not verify — treat as tampered.' : 'No ticket matches this QR token.'}</p>
      </div>
    );
  }
  const legal = r.ticket_type === 'static_certified';
  return (
    <div className="space-y-4">
      <div className={`rounded-2xl border-2 p-5 ${legal ? 'border-green-600 bg-green-50 dark:bg-green-950/40' : 'border-amber-500 bg-amber-50 dark:bg-amber-950/40'}`}>
        <div className="text-xs font-semibold uppercase tracking-wide text-ink-600 dark:text-slate-300">Signature valid · legal status</div>
        <div className="mt-1 text-xl font-bold leading-tight">{legal ? 'LEGAL WEIGHT CERTIFICATE' : 'PRE-SCREEN ONLY'}</div>
        <p className="mt-1 text-sm">{r.legal_status}</p>
      </div>
      <div className="card p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <DecisionBadge decision={r.decision} size="lg" />
          <SourceBadge source={r.source} />
          {r.source !== 'live' && <span className="text-xs text-ink-500">This record was produced by the simulator, not by a real weighing.</span>}
        </div>
        <KV items={[
          ['Plate', <span className="text-base font-semibold">{r.plate ?? '—'}</span>],
          ['Gross vehicle mass', fmtKg(r.gvm_kg)],
          ['Station', r.station ?? '—'],
          ['Weighed at', fmtDateTime(r.occurred_at)],
          ['Ticket type', r.ticket_type ?? '—'],
          ['Evidence hash', <span className="mono break-all">{r.evidence_hash ?? '—'}</span>],
        ]} />
      </div>
    </div>
  );
}

function TokenResult({ r, tokenRef }: { r: TokenVerifyOut; tokenRef: string }) {
  if (!r.valid) {
    return (
      <div role="alert" className={`rounded-2xl border-2 p-5 ${r.status ? 'border-amber-500 bg-amber-50 text-amber-900 dark:bg-amber-950/40 dark:text-amber-100' : 'border-rose-600 bg-rose-50 text-rose-900 dark:bg-rose-950/50 dark:text-rose-100'}`}>
        <div className="text-2xl font-bold">{r.status ? `TOKEN ${String(r.status).toUpperCase()}` : 'NOT FOUND'}</div>
        <p className="mt-1 text-sm">{r.note ?? (r.status ? (r.signature_valid ? 'This token is not honoured: the truck must be weighed again at the next station.' : 'The token exists but its signature does not verify — treat as tampered.') : `No Load Compliance Token matches reference ${tokenRef}.`)}</p>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border-2 border-green-600 bg-green-50 p-5 dark:bg-green-950/40">
        <div className="text-xs font-semibold uppercase tracking-wide text-ink-600 dark:text-slate-300">Signature valid · Load Compliance Token</div>
        <div className="mt-1 text-xl font-bold leading-tight">HONOURED DOWNSTREAM</div>
        <p className="mt-1 text-sm">Confirmed within limits at its first verified weighing point. Later stations check identity and weight consistency only (Reg 10(2)).</p>
      </div>
      <div className="card p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2"><TokenStatusBadge status={r.status} /><TierBadge tier={r.trust_tier} /><SourceBadge source={r.source_label} />{r.source_label && r.source_label !== 'live' && <span className="text-xs text-ink-500">Simulator record, not a real weighing.</span>}</div>
        <KV items={[
          ['Reference', <span className="mono">{tokenRef}</span>],
          ['Plate', <span className="text-base font-semibold">{r.plate ?? '—'}</span>],
          ['Issued by', `${sourceLabel(r.source)} · ${r.issuing_station ?? '—'}`],
          ['Gross vehicle mass', fmtKg(r.gvm_kg)],
          ['Valid', `${fmtDateTime(r.issued_at)} → ${fmtDateTime(r.expires_at)}`],
          ['Honoured', `${r.honoured_count ?? 0} station(s)`],
          ['Signature', r.signature_valid ? 'valid' : 'INVALID'],
        ]} />
        {r.note && <p className="mt-2 text-xs text-ink-500">{r.note}</p>}
      </div>
    </div>
  );
}
