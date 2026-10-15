import { useEffect, useMemo, useRef, useState } from 'react'
import {
  LayoutDashboard, MessageSquareText, Users, GitBranch, ShieldAlert, Network, Radio, ListChecks, Clock, RotateCcw,
  Search, Bell, Building2, ChevronDown, Sparkles, CircleUserRound,
} from 'lucide-react'
import { api, setTenant, type AskResponse, type Meta } from './api'
import { PageCard } from './ui'
import DashboardView from './views/Dashboard'
import AskView from './views/Ask'
import PeopleView from './views/People'
import DecisionsView from './views/Decisions'
import FreshnessView from './views/Freshness'
import ExploreView from './views/Explore'
import LiveView from './views/Live'
import ActionsView from './views/Actions'
import LandingView from './views/Landing'

export type Turn = { q: string; res?: AskResponse; error?: string; pending?: boolean }

const SECTIONS = [
  { title: null, items: [{ id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard }] },
  {
    title: 'Company brain',
    items: [
      { id: 'ask', label: 'Ask Lore', icon: MessageSquareText },
      { id: 'people', label: 'Who knows', icon: Users },
      { id: 'decisions', label: 'Decisions', icon: GitBranch },
      { id: 'freshness', label: 'Freshness', icon: ShieldAlert },
    ],
  },
  {
    title: 'Operations',
    items: [
      { id: 'explore', label: 'Graph explorer', icon: Network },
      { id: 'live', label: 'Live ingest', icon: Radio },
      { id: 'actions', label: 'Actions', icon: ListChecks },
    ],
  },
] as const
type ViewId = (typeof SECTIONS)[number]['items'][number]['id']

const PAGE: Record<ViewId, { title: string; crumb: string; icon: typeof LayoutDashboard; fill?: boolean }> = {
  dashboard: { title: 'Overview', crumb: 'Overview', icon: LayoutDashboard },
  ask: { title: 'Ask Lore', crumb: 'Ask', icon: MessageSquareText, fill: true },
  people: { title: 'Who knows what', crumb: 'Who knows', icon: Users },
  decisions: { title: 'Decisions', crumb: 'Decisions', icon: GitBranch, fill: true },
  freshness: { title: 'Freshness', crumb: 'Freshness', icon: ShieldAlert },
  explore: { title: 'Graph explorer', crumb: 'Graph explorer', icon: Network, fill: true },
  live: { title: 'Live ingest', crumb: 'Live ingest', icon: Radio },
  actions: { title: 'Actions', crumb: 'Actions', icon: ListChecks },
}

const DAY = 86400000

export default function App() {
  const [mode, setMode] = useState<'landing' | 'app'>(() => {
    if (typeof window !== 'undefined') {
      if (window.location.search.includes('app=true') || window.location.hash === '#app') return 'app'
      if (window.location.search.includes('landing=true') || window.location.hash === '#landing') return 'landing'
    }
    return 'landing'
  })
  const [meta, setMeta] = useState<Meta | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [view, setView] = useState<ViewId>('dashboard')
  const [asOf, setAsOf] = useState<string | null>(null) // YYYY-MM-DD or null = now
  const [turns, setTurns] = useState<Turn[]>([])
  const [version, setVersion] = useState(0) // bump after live ingest so views refetch
  const [tenants, setTenants] = useState<string[]>([])
  const [tenant, setTenantState] = useState<string | null>(null)
  const [staleCount, setStaleCount] = useState(0)
  const [pendingQ, setPendingQ] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [tenantOpen, setTenantOpen] = useState(false)
  const searchRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.tenants().then((r) => {
      setTenants(r.tenants)
      setTenantState((t) => t ?? r.default)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    api.meta().then(setMeta).catch((e) => setErr(String(e)))
    api.freshness().then((r) => setStaleCount(r.result.stale_documents.length)).catch(() => {})
  }, [version])

  // "/" focuses the search box, as in the design
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (e.key === '/' && t.tagName !== 'INPUT' && t.tagName !== 'TEXTAREA') {
        e.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  function switchTenant(t: string) {
    setTenant(t)
    setTenantState(t)
    setTenantOpen(false)
    setTurns(() => [])
    setAsOf(null)
    setVersion((v) => v + 1)
  }

  function askFromSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!search.trim()) return
    setPendingQ(search.trim())
    setSearch('')
    setView('ask')
  }

  const asOfIso = asOf ? `${asOf}T23:59:59` : null
  const page = PAGE[view]
  const Icon = page.icon

  if (mode === 'landing') {
    return (
      <LandingView
        onEnterApp={(targetView) => {
          if (targetView && targetView in PAGE) {
            setView(targetView as ViewId)
          }
          setMode('app')
        }}
        currentTenant={tenant}
        stats={meta?.stats}
      />
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Top header */}
      <header className="flex h-[78px] shrink-0 items-center gap-5 border-b border-line bg-white px-8">
        <div className="flex items-center gap-4">
          <div className="flex h-[52px] w-[52px] items-center justify-center rounded-xl border border-line bg-white">
            <img src="/favicon.svg" className="h-7 w-7" />
          </div>
          <span className="font-display text-[22px] font-bold tracking-tight text-heading">Lore AI</span>
        </div>

        {/* View mode switcher */}
        <div className="flex items-center gap-1 rounded-xl border border-line bg-slate-100/80 p-1">
          <button
            onClick={() => setMode('landing')}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-blue-600 transition"
            title="View Project Landing Page, Architecture & Evaluation"
          >
            <Sparkles size={14} className="text-blue-600" />
            <span>Story & Architecture</span>
          </button>
          <div className="flex items-center gap-1.5 rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-blue-600 shadow-xs">
            <LayoutDashboard size={14} />
            <span>Workspace</span>
          </div>
        </div>

        <div className="relative">
          <button
            onClick={() => setTenantOpen((o) => !o)}
            className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-[15px] font-medium text-lime"
            title="Each company is its own FalkorDB graph"
          >
            <Building2 size={17} /> {meta?.company ?? 'Loading…'}
            {tenants.length > 1 && <ChevronDown size={15} />}
          </button>
          {tenantOpen && tenants.length > 1 && (
            <div className="absolute left-0 top-12 z-30 w-64 rounded-xl border border-line bg-white p-1.5 shadow-lg">
              {tenants.map((t) => (
                <button key={t} onClick={() => switchTenant(t)} className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50 ${t === tenant ? 'text-lime' : 'text-soft'}`}>
                  <span>{t}</span><span className="font-mono text-xs text-muted">lore_{t}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <form onSubmit={askFromSearch} className="mx-auto flex w-full max-w-[450px] items-center gap-3 rounded-xl border border-line-2 bg-white px-4 py-3 focus-within:border-lime focus-within:glow">
          <Search size={19} className="text-muted" />
          <input
            ref={searchRef}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Ask anything… (Press / to focus)"
            className="flex-1 bg-transparent text-[16px] text-heading outline-none placeholder:text-muted"
          />
        </form>
        <button onClick={() => setView('freshness')} className="relative flex h-[52px] w-[52px] items-center justify-center rounded-xl border border-line bg-white text-soft hover:bg-slate-50" title="Out-of-date documents">
          <Bell size={20} />
          {staleCount > 0 && (
            <span className="absolute -right-2 -top-2 flex h-7 min-w-7 items-center justify-center rounded-full bg-rose px-1.5 text-[13px] font-semibold text-white">{staleCount}</span>
          )}
        </button>
        <div className="flex h-[52px] items-center gap-2.5 rounded-xl border border-line bg-white px-4 text-[16px] font-medium text-heading">
          <CircleUserRound size={22} />
          {meta?.llm ? (meta.primary === 'groq' ? 'Groq agent' : 'OpenAI agent') : 'Offline agent'}
          <Sparkles size={14} className={meta?.llm ? 'text-lime' : 'text-muted'} />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* Sidebar */}
        <aside className="flex w-[300px] shrink-0 flex-col overflow-y-auto border-r border-line bg-white pt-6">
          <div className="mx-6 mb-5">
            <button
              onClick={() => setMode('landing')}
              className="flex w-full items-center justify-between rounded-xl border border-blue-200 bg-blue-50/70 px-4 py-2.5 text-xs font-bold text-blue-700 hover:bg-blue-100/80 transition shadow-xs"
            >
              <div className="flex items-center gap-2">
                <Sparkles size={15} />
                <span>Project Landing Page</span>
              </div>
              <ChevronDown size={14} className="-rotate-90 text-blue-500" />
            </button>
          </div>
          {SECTIONS.map((s, i) => (
            <div key={i} className={i ? 'mt-7' : ''}>
              {s.title && <div className="mb-3 px-8 text-[13px] font-semibold uppercase tracking-[0.1em] text-heading">{s.title}</div>}
              {s.items.map((n) => {
                const active = view === n.id
                return (
                  <button
                    key={n.id}
                    onClick={() => setView(n.id)}
                    className={`relative flex w-full items-center gap-4 px-8 py-[11px] text-[17px] transition ${active ? 'font-medium text-heading' : 'text-soft hover:bg-slate-50'}`}
                  >
                    {active && <span className="absolute left-0 top-0 h-full w-[3px] bg-lime" />}
                    <n.icon size={21} strokeWidth={1.7} />
                    {n.label}
                  </button>
                )
              })}
            </div>
          ))}
          {meta && (
            <div className="mx-6 mt-auto mb-6 rounded-xl border border-line bg-panel-2 p-4 text-[13px] text-muted">
              <div className="mb-2 font-semibold text-heading">Graph · lore_{tenant}</div>
              <div className="grid grid-cols-2 gap-y-1 font-mono text-[12px]">
                <span>nodes</span><span className="text-right text-heading">{Object.values(meta.stats.nodes).reduce((a, b) => a + b, 0)}</span>
                <span>edges</span><span className="text-right text-heading">{Object.values(meta.stats.relationships).reduce((a, b) => a + b, 0)}</span>
                <span>sources</span><span className="text-right text-heading">{meta.stats.nodes.Source ?? 0}</span>
              </div>
            </div>
          )}
        </aside>

        {/* Main */}
        <main className="flex min-w-0 flex-1 flex-col bg-page">
          {meta && <TimeTravel meta={meta} asOf={asOf} setAsOf={setAsOf} />}
          {err && <div className="mx-7 mt-5 rounded-xl border border-rose/40 bg-rose/10 p-4 text-sm text-rose">API not reachable: {err}</div>}
          <div className="min-h-0 flex-1">
            <PageCard crumb={page.crumb} title={page.title} icon={<Icon size={28} strokeWidth={1.8} />} fill={page.fill}>
              {view === 'dashboard' && <DashboardView asOf={asOfIso} version={version} go={(v) => setView(v as ViewId)} />}
              {view === 'ask' && <AskView asOf={asOfIso} turns={turns} setTurns={setTurns} pendingQ={pendingQ} clearPending={() => setPendingQ(null)} />}
              {view === 'people' && <PeopleView asOf={asOfIso} version={version} />}
              {view === 'decisions' && <DecisionsView asOf={asOfIso} version={version} />}
              {view === 'freshness' && <FreshnessView asOf={asOfIso} version={version} />}
              {view === 'explore' && <ExploreView asOf={asOfIso} version={version} />}
              {view === 'live' && <LiveView onIngested={() => setVersion((v) => v + 1)} goAsk={() => setView('ask')} />}
              {view === 'actions' && <ActionsView version={version} />}
            </PageCard>
          </div>
        </main>
      </div>
    </div>
  )
}

function TimeTravel({ meta, asOf, setAsOf }: { meta: Meta; asOf: string | null; setAsOf: (d: string | null) => void }) {
  const start = useMemo(() => new Date(meta.first.slice(0, 10)).getTime(), [meta.first])
  const end = useMemo(() => Math.max(new Date(meta.now.slice(0, 10)).getTime(), new Date(meta.last.slice(0, 10)).getTime()), [meta])
  const days = Math.round((end - start) / DAY)
  const value = asOf ? Math.round((new Date(asOf).getTime() - start) / DAY) : days
  const [draft, setDraft] = useState(value)
  useEffect(() => {
    setDraft(value)
  }, [value])
  const draftDate = new Date(start + draft * DAY).toISOString().slice(0, 10)
  const months: Date[] = []
  for (let d = new Date(start); d.getTime() <= end; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) months.push(d)
  const commit = () => setAsOf(draft >= days ? null : draftDate)
  return (
    <div className="mx-7 mt-6 flex items-center gap-6 rounded-2xl border border-line bg-white px-6 py-3.5">
      <div className="flex shrink-0 items-center gap-2 text-[15px]">
        <Clock size={18} className={asOf ? 'text-amber' : 'text-lime'} />
        <span className="text-muted">Viewing as of</span>
        <span className={`rounded-md px-2 py-0.5 font-semibold ${asOf ? 'bg-amber-50 text-amber' : 'bg-blue-50 text-lime'}`}>{asOf ? draftDate : 'today'}</span>
      </div>
      <div className="flex-1">
        <input type="range" className="timeline w-full" min={0} max={days} value={draft}
          onChange={(e) => setDraft(Number(e.target.value))} onMouseUp={commit} onKeyUp={commit} onTouchEnd={commit} />
        <div className="flex justify-between text-[12px] text-muted">
          {months.map((m, i) => <span key={i}>{m.toLocaleString('en', { month: 'short' })}</span>)}
        </div>
      </div>
      <button onClick={() => setAsOf(null)} disabled={!asOf}
        className="flex items-center gap-1.5 rounded-lg border border-line px-3 py-1.5 text-sm text-soft transition enabled:hover:bg-slate-50 disabled:opacity-40">
        <RotateCcw size={14} /> Today
      </button>
    </div>
  )
}
