import { useEffect, useState } from 'react'
import { Search, UserX, AlertTriangle } from 'lucide-react'
import { api, type ExpertsResult, type PersonRow, type SystemRow, type ToolResponse } from '../api'
import { Badge, CiteText, GraphCanvas, Panel, SourceCard, Spinner } from '../ui'

const TOPICS = ['Kafka', 'SSO and tokens', 'Idempotency', 'Graph databases', 'Deploy policy', 'PCI compliance', 'Observability']

export default function PeopleView({ asOf, version }: { asOf: string | null; version: number }) {
  const [systems, setSystems] = useState<SystemRow[]>([])
  const [people, setPeople] = useState<PersonRow[]>([])
  const [subject, setSubject] = useState('auth-gateway')
  const [input, setInput] = useState('')
  const [exp, setExp] = useState<ToolResponse<ExpertsResult> | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.systems(asOf).then((r) => setSystems(r.systems))
  }, [asOf, version])
  useEffect(() => {
    api.people().then((r) => setPeople(r.people))
  }, [version])
  useEffect(() => {
    setLoading(true)
    api.experts(subject).then(setExp).finally(() => setLoading(false))
  }, [subject, version])

  const maxInf = Math.max(...people.map((p) => p.influence || 0), 0.0001)
  const riskTone = { high: 'rose', medium: 'amber', low: 'lime' } as const

  return (
    <div>
      <div className="grid grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] gap-5">
        <Panel title={`Systems · owner ${asOf ? 'as of ' + asOf.slice(0, 10) : 'now'} · knowledge risk`}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-muted">
                <th className="pb-2 font-medium">System</th><th className="pb-2 font-medium">Owner</th>
                <th className="pb-2 font-medium">Bus factor</th><th className="pb-2 font-medium">Active experts</th>
              </tr>
            </thead>
            <tbody>
              {systems.map((s) => (
                <tr key={s.id} onClick={() => setSubject(s.id)} className={`cursor-pointer border-t border-line transition hover:bg-slate-50 ${subject === s.id ? 'bg-lime/[0.04]' : ''}`}>
                  <td className="py-2.5 font-mono text-[13px] text-cyan">{s.id}</td>
                  <td className="py-2.5 text-soft">{s.owner ?? <span className="text-muted">—</span>}</td>
                  <td className="py-2.5">
                    <Badge tone={riskTone[s.risk]}>{s.risk}</Badge>
                    {!s.top_expert_active && s.top_expert && <span className="ml-1.5"><Badge tone="rose"><UserX size={10} /> {s.top_expert} left</Badge></span>}
                  </td>
                  <td className="py-2.5 text-[12.5px] text-muted">{s.active_experts.slice(0, 3).join(', ') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel
          title={<>Who knows <span className="text-lime normal-case">{exp?.result.subject ?? subject}</span></>}
          right={loading ? <Spinner /> : null}
        >
          <form onSubmit={(e) => { e.preventDefault(); if (input.trim()) setSubject(input.trim()) }} className="mb-3 flex items-center gap-2 rounded-xl border border-line bg-panel-2 px-3 py-1.5 focus-within:border-lime/40">
            <Search size={15} className="text-muted" />
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="system, topic or anything (e.g. 'token rotation')" className="flex-1 bg-transparent py-1 text-sm outline-none placeholder:text-muted" />
          </form>
          <div className="mb-4 flex flex-wrap gap-1.5">
            {TOPICS.map((t) => (
              <button key={t} onClick={() => setSubject(t)} className="rounded-full border border-line px-2.5 py-0.5 text-xs text-muted hover:border-lime/40 hover:text-lime">{t}</button>
            ))}
          </div>
          {exp && (
            <div className="space-y-2">
              {exp.result.experts.map((p, i) => (
                <div key={p.name} className={`flex items-center gap-3 rounded-xl border p-3 ${p.active ? 'border-line bg-panel-2/50' : 'border-rose/30 bg-rose/[0.05]'}`}>
                  <div className="w-5 text-center font-mono text-xs text-muted">{i + 1}</div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-heading">{p.name}</span>
                      {!p.active && <Badge tone="rose"><UserX size={10} /> left {p.left_at}</Badge>}
                    </div>
                    <div className="text-xs text-muted">{p.role} · {p.team} · {p.contributions} contributions · last {p.last_active}</div>
                  </div>
                  <div className="w-28">
                    <div className="h-1.5 overflow-hidden rounded bg-line">
                      <div className="h-full rounded bg-lime" style={{ width: `${Math.min(100, (p.score / (exp.result.experts[0]?.score || 1)) * 100)}%` }} />
                    </div>
                    <div className="mt-1 text-right font-mono text-[11px] text-muted">{p.score}</div>
                  </div>
                </div>
              ))}
              {exp.result.experts[0] && !exp.result.experts[0].active && (
                <div className="flex gap-2 rounded-xl border border-amber/30 bg-amber/[0.06] p-3 text-xs text-amber">
                  <AlertTriangle size={14} className="shrink-0" /> The top expert has left. Knowledge on this is concentrated in people who are no longer here.
                </div>
              )}
            </div>
          )}
        </Panel>
      </div>

      {exp && (
        <div className="mt-5 grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-5">
          <Panel title="Expertise graph">
            <GraphCanvas nodes={exp.subgraph.nodes} edges={exp.subgraph.edges} height={340} />
          </Panel>
          <Panel title="Evidence behind the ranking">
            <div className="mb-3 text-sm text-soft"><CiteText text={exp.result.summary} /></div>
            <div className="max-h-[260px] space-y-2 overflow-y-auto pr-1">
              {exp.citations.slice(0, 8).map((c) => <SourceCard key={c.sid} c={c} />)}
            </div>
          </Panel>
        </div>
      )}

      <Panel title="People · influence (PageRank) · knowledge brokers (betweenness) · working groups (label propagation)" className="mt-5">
        <div className="grid grid-cols-3 gap-3">
          {people.map((p) => (
            <div key={p.id} className={`rounded-xl border p-3 ${p.active ? 'border-line bg-panel-2/40' : 'border-rose/25 bg-rose/[0.04]'}`}>
              <div className="flex items-center justify-between">
                <span className="font-semibold text-heading">{p.name}</span>
                <span className="flex gap-1">
                  {p.community !== null && <Badge tone="violet">group {p.community}</Badge>}
                  {!p.active && <Badge tone="rose">left</Badge>}
                </span>
              </div>
              <div className="text-xs text-muted">{p.role} · {p.team}</div>
              <div className="mt-2 flex items-center gap-2 text-[11px] text-muted">
                <span className="w-16">influence</span>
                <div className="h-1 flex-1 rounded bg-line"><div className="h-full rounded bg-lime" style={{ width: `${(p.influence / maxInf) * 100}%` }} /></div>
              </div>
              <div className="mt-1 text-[11px] text-muted">broker score <span className="font-mono text-soft">{Math.round(p.broker || 0)}</span></div>
              <div className="mt-1.5 truncate text-[11px] text-cyan">{p.knows.join(' · ')}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}
