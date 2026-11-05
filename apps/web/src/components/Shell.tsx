import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { notifications as notifApi } from '../api/endpoints';
import type { LiveEvent, NotificationOut } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { useLiveEvents } from '../hooks/useLiveEvents';
import { useQuery } from '../hooks/useQuery';
import { fmtAgo } from '../lib/format';
import { GROUP_ORDER, routeByPath, routesFor, type RouteDef } from '../lib/roles';
import { Icon } from './icons';
import { Badge, Empty, Spinner } from './ui';

const SIDEBAR_KEY = 'kifaru.sidebar.collapsed';

export default function Shell() {
  const { me, session, roles, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [drawer, setDrawer] = useState(false);
  const [collapsed, setCollapsed] = useState<boolean>(() => { try { return localStorage.getItem(SIDEBAR_KEY) === '1'; } catch { return false; } });
  const routes = routesFor(roles);
  const current = routeByPath(loc.pathname);
  const live = useLiveEvents([], null, 1);

  useEffect(() => { setDrawer(false); }, [loc.pathname]);
  useEffect(() => { try { localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0'); } catch { /* ignore */ } }, [collapsed]);

  const groups = GROUP_ORDER.map((g) => ({ g, items: routes.filter((r) => r.group === g) })).filter((x) => x.items.length);

  const NavItems = ({ compact }: { compact: boolean }) => (
    <nav aria-label="Primary" className="flex flex-col gap-4">
      {groups.map(({ g, items }) => (
        <div key={g}>
          {!compact && <div className="mb-1 px-2.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400">{g}</div>}
          <ul className="space-y-0.5">
            {items.map((r: RouteDef) => (
              <li key={r.path}>
                <NavLink to={r.path} title={compact ? r.label : r.description} className={({ isActive }) => `nav-item ${isActive ? 'nav-item-active' : ''} ${compact ? 'justify-center px-2' : ''}`}>
                  <Icon name={r.icon} size={18} className="shrink-0" />
                  {!compact && <span className="truncate">{r.label}</span>}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      {/* Sidebar (desktop) */}
      <aside className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-ink-800 bg-ink-950 text-white transition-[width] duration-200 md:flex ${collapsed ? 'w-[68px]' : 'w-60'}`}>
        <div className={`flex items-center gap-2 px-3 py-3.5 ${collapsed ? 'justify-center' : ''}`}>
          <img src="/favicon.svg" alt="" width="30" height="30" className="rounded-lg" />
          {!collapsed && <div className="leading-tight"><div className="text-sm font-bold tracking-tight">KIFARU <span className="text-brand-400">PORTOS</span></div><div className="text-[10px] uppercase tracking-wider text-ink-400">Port-anchored clearance</div></div>}
        </div>
        <div className="flex-1 overflow-y-auto px-2.5 py-2"><NavItems compact={collapsed} /></div>
        <div className="border-t border-ink-800 p-2">
          <button className="nav-item w-full justify-center" onClick={() => setCollapsed((c) => !c)} aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'} aria-expanded={!collapsed}>
            <Icon name="chevron" size={16} className={`transition ${collapsed ? '' : 'rotate-180'}`} />{!collapsed && <span className="text-xs">Collapse</span>}
          </button>
        </div>
      </aside>

      {/* Mobile drawer */}
      {drawer && (
        <div className="fixed inset-0 z-50 flex md:hidden" onMouseDown={(e) => { if (e.target === e.currentTarget) setDrawer(false); }}>
          <div className="absolute inset-0 bg-ink-950/60" />
          <aside className="relative flex h-full w-72 max-w-[85vw] flex-col bg-ink-950 text-white shadow-pop" role="dialog" aria-modal="true" aria-label="Navigation">
            <div className="flex items-center justify-between px-3 py-3">
              <div className="flex items-center gap-2"><img src="/favicon.svg" alt="" width="28" height="28" className="rounded-lg" /><span className="text-sm font-bold">KIFARU <span className="text-brand-400">PORTOS</span></span></div>
              <button className="nav-item p-1.5" aria-label="Close navigation" onClick={() => setDrawer(false)}><Icon name="close" size={18} /></button>
            </div>
            <div className="flex-1 overflow-y-auto px-2.5 py-2"><NavItems compact={false} /></div>
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 border-b border-ink-100 bg-white/85 backdrop-blur dark:border-ink-800 dark:bg-ink-950/85">
          <div className="flex items-center gap-3 px-4 py-2">
            <button className="btn-ghost p-2 md:hidden" aria-label="Open navigation" aria-expanded={drawer} onClick={() => setDrawer(true)}><Icon name="menu" size={20} /></button>
            <nav aria-label="Breadcrumb" className="min-w-0 flex-1 truncate text-sm">
              <ol className="flex items-center gap-1.5 text-ink-500 dark:text-ink-300">
                <li><NavLink to="/" className="hover:text-ink-900 dark:hover:text-white">Home</NavLink></li>
                {current && <><li aria-hidden="true">/</li><li className="truncate font-medium text-ink-900 dark:text-white">{current.label}</li></>}
              </ol>
            </nav>
            <LivePill status={live.status} hasLive={live.hasLive} />
            <Bell />
            <UserMenu name={me?.full_name ?? session?.full_name ?? ''} org={me?.org_name ?? roles.join(', ')} onLogout={async () => { await logout(); nav('/login'); }} />
          </div>
        </header>
        <main className="mx-auto w-full max-w-screen-2xl flex-1 px-4 py-5 sm:px-6">
          <Outlet />
        </main>
        <footer className="border-t border-ink-100 px-4 py-3 text-center text-[11px] text-ink-500 dark:border-ink-800 dark:text-ink-300">
          Times shown in Africa/Nairobi. Records tagged SIMULATED are synthetic and never presented as live measurements. The static scale remains the legal reference; a screening reading never replaces it as proof of overload.
          {' '}<a className="underline underline-offset-2" href="/about">How RCS v2 works</a>
        </footer>
      </div>
    </div>
  );
}

function LivePill({ status, hasLive }: { status: string; hasLive: boolean }) {
  const ok = status === 'open' || status === 'polling';
  return (
    <span className="hidden items-center gap-1.5 rounded-full border border-ink-200 px-2 py-0.5 text-[11px] font-medium text-ink-600 sm:inline-flex dark:border-ink-700 dark:text-ink-300" title={`Live feed: ${status}${hasLive ? ' · live measurements seen' : ' · simulated data only'}`}>
      <span className={`inline-block h-2 w-2 rounded-full ${ok ? 'bg-brand-500' : status === 'connecting' ? 'bg-amber-500' : 'bg-rose-500'}`} aria-hidden="true" />
      {status === 'open' ? 'live' : status}{hasLive ? '' : ' · sim'}
    </span>
  );
}

function UserMenu({ name, org, onLogout }: { name: string; org: string; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);
  const initials = name.split(' ').filter(Boolean).slice(0, 2).map((s) => s[0]?.toUpperCase()).join('') || '?';
  return (
    <div className="relative" ref={ref}>
      <button className="flex items-center gap-2 rounded-full border border-ink-200 py-0.5 pl-0.5 pr-2 text-left hover:bg-surface-100 dark:border-ink-700 dark:hover:bg-ink-800" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-600 text-[11px] font-bold text-white" aria-hidden="true">{initials}</span>
        <span className="hidden text-xs leading-tight sm:block"><span className="block font-medium">{name}</span><span className="block text-ink-500 dark:text-ink-300">{org}</span></span>
      </button>
      {open && (
        <div role="menu" className="card absolute right-0 mt-1 w-56 overflow-hidden p-1">
          <div className="px-3 py-2 text-xs text-ink-500 dark:text-ink-300"><div className="font-medium text-ink-900 dark:text-white">{name}</div>{org}</div>
          <a role="menuitem" className="nav-item text-ink-700 hover:bg-surface-100 hover:text-ink-900 dark:text-slate-200" href="/about">About RCS v2</a>
          <a role="menuitem" className="nav-item text-ink-700 hover:bg-surface-100 hover:text-ink-900 dark:text-slate-200" href="/verify">Verify a ticket or token</a>
          <button role="menuitem" className="nav-item w-full text-rose-700 hover:bg-rose-50 dark:text-rose-300 dark:hover:bg-rose-950/40" onClick={onLogout}><Icon name="logout" size={16} />Sign out</button>
        </div>
      )}
    </div>
  );
}

function Bell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const q = useQuery(() => notifApi.inbox(false), [], { pollMs: 60_000 });
  // Live push: refresh inbox when a notification event arrives for this user/org.
  useLiveEvents(['notification'], null, 50, (ev: LiveEvent) => { if (ev.type === 'notification') void q.refetch(); });
  const unread = (q.data ?? []).filter((n) => !n.read_at).length;

  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);

  const markRead = async (n: NotificationOut) => {
    if (n.read_at) return;
    await notifApi.markRead(n.id);
    q.setData((prev) => (prev ?? []).map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)));
  };

  return (
    <div className="relative" ref={ref}>
      <button className="btn-ghost relative p-2" aria-label={`Notifications, ${unread} unread`} aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <Icon name="bell" size={20} />
        {unread > 0 && <span className="absolute -right-0.5 -top-0.5 min-w-[18px] rounded-full bg-brand-600 px-1 text-center text-[10px] font-bold text-white">{unread}</span>}
      </button>
      {open && (
        <div role="dialog" aria-label="Notifications" className="card absolute right-0 mt-1 w-80 max-w-[90vw] overflow-hidden">
          <div className="flex items-center justify-between border-b border-ink-100 px-3 py-2 text-sm font-semibold dark:border-ink-800">Inbox <Badge tone={unread ? 'teal' : 'slate'}>{unread} unread</Badge></div>
          <ul className="max-h-80 divide-y divide-ink-100 overflow-y-auto dark:divide-ink-800">
            {q.loading && <li className="p-3"><Spinner /></li>}
            {!q.loading && (q.data ?? []).length === 0 && <li className="p-3"><Empty>No notifications</Empty></li>}
            {(q.data ?? []).map((n) => (
              <li key={n.id}>
                <button className={`w-full px-3 py-2 text-left hover:bg-surface-50 dark:hover:bg-ink-800 ${n.read_at ? 'opacity-60' : ''}`} onClick={() => void markRead(n)}>
                  <div className="flex items-center justify-between gap-2 text-sm font-medium"><span>{n.title}</span><Badge tone="slate">{n.channel}</Badge></div>
                  <div className="text-xs text-ink-600 dark:text-slate-300">{n.body}</div>
                  <div className="text-[11px] text-ink-400">{fmtAgo(n.created_at)}{n.read_at ? ' · read' : ' · tap to mark read'}</div>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
