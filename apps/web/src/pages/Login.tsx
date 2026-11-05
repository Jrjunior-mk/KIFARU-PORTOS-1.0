import { type FormEvent, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Icon, type IconName } from '../components/icons';
import { ErrorBanner, Field, Notice } from '../components/ui';
import { homeFor } from '../lib/roles';

const TILES: { icon: IconName; title: string; body: string }[] = [
  { icon: 'port', title: 'Weigh once at the first trusted point', body: 'Port exit for port cargo; the loading site or first road station for mines, quarries and factories. The overload is fixed where it is cheapest to fix.' },
  { icon: 'token', title: 'Honour the Load Compliance Token downstream', body: 'A signed token travels with the truck. Later stations only check that identity and weight are unchanged, so compliant trucks keep moving.' },
  { icon: 'lane', title: 'Rolling Verification Lane at ~10 km/h', body: 'Doubtful trucks roll through per-wheel scales and a LiDAR dimension portal without stopping: about 370 trucks an hour, roughly 25 static lanes.' },
];

export default function Login() {
  const { session, login, verifyMfa, roles } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const from = (loc.state as { from?: string } | null)?.from;
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(false);
  const [code, setCode] = useState('');
  const [step, setStep] = useState<'credentials' | 'mfa'>(session?.mfa_required ? 'mfa' : 'credentials');
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  if (session && !session.mfa_required) return <Navigate to={from && from !== '/login' ? from : homeFor(roles)} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      if (step === 'credentials') {
        const t = await login(email.trim(), password, undefined, remember);
        if (t.mfa_required) setStep('mfa');
        else nav(from && from !== '/login' ? from : homeFor(t.roles), { replace: true });
      } else {
        const t = await verifyMfa(code.trim());
        nav(from && from !== '/login' ? from : homeFor(t.roles), { replace: true });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, (err as Error).message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.15fr_1fr]">
      <section className="relative hidden overflow-hidden bg-ink-950 px-10 py-12 text-white lg:flex lg:flex-col lg:justify-between" aria-label="About the platform">
        <div className="pointer-events-none absolute -left-24 -top-24 h-96 w-96 rounded-full bg-brand-500/20 blur-3xl" aria-hidden="true" />
        <div className="pointer-events-none absolute -bottom-32 right-0 h-96 w-96 rounded-full bg-brand-700/20 blur-3xl" aria-hidden="true" />
        <div className="relative">
          <div className="flex items-center gap-3">
            <img src="/favicon.svg" alt="" width="40" height="40" className="rounded-xl" />
            <div><div className="text-lg font-bold tracking-tight">KIFARU <span className="text-brand-400">PORTOS</span></div><div className="text-xs uppercase tracking-wider text-ink-300">Rolling Clearance System v2</div></div>
          </div>
          <h1 className="mt-12 max-w-xl text-4xl font-bold leading-tight tracking-tight">Port-anchored clearance for the Northern Corridor.</h1>
          <p className="mt-4 max-w-xl text-ink-300">Every heavy truck is weighed at its first trusted point. Every later station honours that result, so compliant trucks stop once instead of at every weighbridge.</p>
          <ul className="mt-10 grid gap-4">
            {TILES.map((t) => (
              <li key={t.title} className="flex gap-4 rounded-2xl border border-white/10 bg-white/5 p-4 backdrop-blur">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-500/20 text-brand-300"><Icon name={t.icon} size={20} /></span>
                <div><div className="font-semibold">{t.title}</div><div className="mt-1 text-sm text-ink-300">{t.body}</div></div>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative mt-10 text-xs text-ink-400">
          The static scale remains the legal reference. Screening readings decide who needs a static weighing and never replace it as proof of overload (Reg 4(6)). A digital green status rests on Reg 10(2) of the EAC Vehicle Load Control (Enforcement Measures) Regulations, 2018.
          {' '}<a className="underline underline-offset-2 hover:text-white" href="/about">How RCS v2 works</a>
        </p>
      </section>

      <section className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-sm">
          <div className="mb-6 flex items-center gap-3 lg:hidden">
            <img src="/favicon.svg" alt="" width="36" height="36" className="rounded-xl" />
            <div><div className="text-lg font-bold leading-tight">KIFARU <span className="text-brand-600 dark:text-brand-400">PORTOS</span></div><div className="text-xs text-ink-500">Rolling Clearance System v2</div></div>
          </div>
          <div className="card p-6">
            <h2 className="text-lg font-semibold">Sign in</h2>
            <p className="mt-0.5 text-sm text-ink-500 dark:text-ink-300">Role dashboards for port control, weighbridges, transporters, drivers, cargo owners and warehouses.</p>
            <form onSubmit={submit} className="mt-5 space-y-3" aria-describedby={error ? 'login-error' : undefined}>
              {step === 'credentials' ? (
                <>
                  <Field label="Email" required>{(id) => <input id={id} className="input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
                  <Field label="Password" required>{(id) => <input id={id} className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />}</Field>
                  <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-500" checked={remember} onChange={(e) => setRemember(e.target.checked)} />Remember this device (installed app)</label>
                </>
              ) : (
                <>
                  <Notice>Your role requires multi-factor authentication. Enter the 6-digit code from your authenticator app.</Notice>
                  <Field label="MFA code" required>{(id) => <input id={id} className="input text-center text-lg tracking-widest" inputMode="numeric" pattern="[0-9]{6,8}" autoComplete="one-time-code" required value={code} onChange={(e) => setCode(e.target.value)} autoFocus />}</Field>
                </>
              )}
              {error && <div id="login-error"><ErrorBanner error={error.status === 401 && step === 'credentials' ? 'Invalid email or password' : error} /></div>}
              <button className="btn-primary w-full" disabled={busy} type="submit">{busy ? 'Please wait…' : step === 'credentials' ? 'Sign in' : 'Verify code'}</button>
              {step === 'mfa' && <button type="button" className="btn-ghost w-full text-xs" onClick={() => { setStep('credentials'); setCode(''); }}>Back</button>}
            </form>
          </div>
          <p className="mt-4 text-center text-xs text-ink-500 dark:text-ink-300">
            Have a weighing ticket or token QR? <a className="underline underline-offset-2" href="/verify">Verify it</a> without signing in · <a className="underline underline-offset-2" href="/about">About RCS v2</a>
          </p>
        </div>
      </section>
    </main>
  );
}
