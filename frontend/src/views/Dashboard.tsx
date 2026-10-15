import { useEffect, useState } from 'react'
import { Activity, GitBranch, FileWarning, Users, Server, UserX } from 'lucide-react'
import { api, type DecisionRow, type Meta, type PersonRow, type StaleDoc, type SystemRow } from '../api'
import { Badge, Panel } from '../ui'

const RISK = { high: 'rose', medium: 'amber', low: 'lime' } as const

export default function DashboardView({ asOf, version, go }: { asOf: string | null; version: number; go: (v: string) => void }) {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [systems, setSystems] = useState<SystemRow[]>([])
  const [people, setPeople] = useState<PersonRow[]>([])
  const [decisions, setDecisions] = useState<DecisionRow[]>([])
  const [stale, setStale] = useState<StaleDoc[]>([])

  useEffect(() => {
    api.meta().then(setMeta)
    api.people().then((r) => setPeople(r.people))
    api.freshness().then((r) => setStale(r.result.stale_documents))
  }, [version])
  useEffect(() => {
    api.systems(asOf).then((r) => setSystems(r.systems))
    api.decisions(asOf).then((r) => setDecisions(r.result.decisions))
  }, [asOf, version])

  const active = people.filter((p) => p.active).length
  const inForce = decisions.filter((d) => d.status === 'active').length
  const highRisk = systems.filter((s) => s.risk === 'high').length

  const tiles = [
    { label: 'People', value: `${active}`, sub: `${people.length - active} left the company`, icon: Users, to: 'people' },
    { label: 'Systems', value: `${systems.length}`, sub: `${highRisk} at high knowledge risk`, icon: Server, to: 'people', warn: highRisk > 0 },
    { label: 'Decisions in force', value: `${inForce}`, sub: `${decisions.length - inForce} replaced over time`, icon: GitBranch, to: 'decisions' },
    { label: 'Out-of-date docs', value: `${stale.length}`, sub: 'contradicted by newer evidence', icon: FileWarning, to: 'freshness', warn: stale.length > 0 },
  ]

  return (
    <div className="space-y-7">
      <div className="grid grid-cols-4 gap-5">
        {tiles.map((t) => (
          <button key={t.label} onClick={() => go(t.to)} className="rounded-2xl border border-line bg-white p-5 text-left transition hover:border-line-2 hover:shadow-sm">
            <div className="flex items-center justify-between text-[15px] text-muted">
              {t.label}
              <t.icon size={19} className={t.warn ? 'text-rose' : 'text-lime'} />
            </div>
            <div className="mt-2 text-[34px] font-semibold leading-none text-heading">{t.value}</div>
            <div className={`mt-2 text-[13.5px] ${t.warn ? 'text-rose' : 'text-muted'}`}>{t.sub}</div>
          </button>
        ))}
      </div>

      <Panel
        flush
        title={<><Activity size={18} className="text-lime" /> Knowledge health, by system</>}
        right={`Ownership ${asOf ? 'as of ' + asOf.slice(0, 10) : 'today'} · computed from docs, tickets, chat and meetings`}
      >
        <table className="data-table">
          <thead>
            <tr>
              <th>System</th><th>Owner</th><th>Projects</th><th className="num">Active experts</th><th>Top expert</th><th>Bus factor</th>
            </tr>
          </thead>
          <tbody>
            {systems.map((s) => (
              <tr key={s.id} className="clickable" onClick={() => go('people')}>
                <td className="font-medium">{s.id}</td>
                <td>{s.owner ?? <span className="text-muted">not recorded</span>}</td>
                <td className="text-muted">{s.projects.join(', ') || '—'}</td>
                <td className="num">{s.active_experts.length}</td>
                <td>
                  {s.top_expert ?? '—'}
                  {s.top_expert && !s.top_expert_active && <span className="ml-2"><Badge tone="rose"><UserX size={11} /> left</Badge></span>}
                </td>
                <td><Badge tone={RISK[s.risk]}>{s.risk}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <div className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] gap-7">
        <Panel flush title={<><GitBranch size={18} className="text-pink" /> Decision log</>} right={`${inForce} in force`}>
          <table className="data-table">
            <thead><tr><th>Day</th><th>Decision</th><th>Status</th></tr></thead>
            <tbody>
              {[...decisions].reverse().map((d) => (
                <tr key={d.id} className="clickable" onClick={() => go('decisions')}>
                  <td className="whitespace-nowrap">{fmt(d.at)}</td>
                  <td className={d.status === 'active' ? '' : 'text-muted line-through decoration-slate-300'}>{d.title}</td>
                  <td><Badge tone={d.status === 'active' ? 'lime' : 'muted'}>{d.status === 'active' ? 'in force' : 'replaced'}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel flush title={<><FileWarning size={18} className="text-amber" /> Needs updating</>} right={`${stale.length} docs`}>
          <table className="data-table">
            <thead><tr><th>Document</th><th className="num">Last updated</th></tr></thead>
            <tbody>
              {stale.map((d) => (
                <tr key={d.id} className="clickable" onClick={() => go('freshness')}>
                  <td>
                    <div className="font-medium">{d.title}</div>
                    <div className="mt-0.5 text-[13px] text-muted">{d.reasons[0]}</div>
                  </td>
                  <td className="num whitespace-nowrap">{fmt(d.updated)}</td>
                </tr>
              ))}
              {stale.length === 0 && <tr><td colSpan={2} className="text-muted">Every document matches the latest evidence.</td></tr>}
            </tbody>
          </table>
        </Panel>
      </div>
      {meta && <div className="text-right text-[13px] text-muted">{meta.company} · data from {fmt(meta.first)} to {fmt(meta.last)}</div>}
    </div>
  )
}

const fmt = (iso: string) => new Date(iso.slice(0, 10)).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).replace(' ', '. ').replace('May.', 'May')
