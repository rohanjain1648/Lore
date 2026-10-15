import { useEffect, useState } from 'react'
import { GitBranch, ArrowRight } from 'lucide-react'
import { api, type DecisionRow, type ToolResponse, type TraceResult } from '../api'
import { Badge, CiteText, GraphCanvas, Legend, Panel, SourceCard, Spinner } from '../ui'

export default function DecisionsView({ asOf, version }: { asOf: string | null; version: number }) {
  const [rows, setRows] = useState<DecisionRow[]>([])
  const [sel, setSel] = useState<DecisionRow | null>(null)
  const [trace, setTrace] = useState<ToolResponse<TraceResult> | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeSid, setActiveSid] = useState<string | null>(null)

  useEffect(() => {
    api.decisions(asOf).then((r) => {
      setRows(r.result.decisions)
      setSel((s) => r.result.decisions.find((d) => d.id === s?.id) ?? r.result.decisions[r.result.decisions.length - 1] ?? null)
    })
  }, [asOf, version])

  useEffect(() => {
    if (!sel) return
    setLoading(true)
    api.decision(sel.title, asOf).then(setTrace).finally(() => setLoading(false))
  }, [sel, asOf])

  return (
    <div className="grid h-full grid-cols-[380px_minmax(0,1fr)] gap-0 overflow-hidden rounded-2xl border border-line">
      <div className="overflow-y-auto border-r border-line p-5">
        <div className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-soft">
          <GitBranch size={16} className="text-pink" /> Decision log
        </div>
        <div className="relative space-y-3 pl-5 before:absolute before:left-[7px] before:top-2 before:bottom-2 before:w-px before:bg-line-2">
          {rows.map((d) => (
            <button key={d.id} onClick={() => setSel(d)} className={`relative block w-full rounded-xl border p-3 text-left transition ${sel?.id === d.id ? 'border-pink/50 bg-pink/[0.06]' : 'border-line bg-panel-2/40 hover:border-line-2'}`}>
              <span className={`absolute -left-[18px] top-4 h-2.5 w-2.5 rotate-45 ${d.status === 'active' ? 'bg-pink' : 'bg-line-2'}`} />
              <div className="flex items-center gap-2 font-mono text-[11px] text-muted">
                {d.at.slice(0, 10)}
                <Badge tone={d.status === 'active' ? 'lime' : 'muted'}>{d.status === 'active' ? 'in force' : 'replaced'}</Badge>
              </div>
              <div className={`mt-1 text-sm ${d.status === 'active' ? 'text-heading' : 'text-muted line-through decoration-muted/50'}`}>{d.title}</div>
              <div className="mt-1 text-[11px] text-muted">{d.src_title}</div>
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 overflow-y-auto p-6">
        {loading && <Spinner />}
        {trace && !loading && (
          <div className="space-y-5">
            <Panel title="Lineage" right={<span className="text-xs text-muted">{trace.result.lineage.length} decision(s) in this chain</span>}>
              <div className="flex flex-wrap items-stretch gap-2">
                {trace.result.lineage.map((l, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className={`w-64 rounded-xl border p-3 ${l.status === 'in force' ? 'border-lime/40 bg-lime/[0.05]' : 'border-line bg-panel-2/40'}`}>
                      <div className="flex items-center justify-between font-mono text-[11px] text-muted">
                        {l.decided}
                        <Badge tone={l.status === 'in force' ? 'lime' : 'muted'}>{l.status === 'in force' ? 'in force' : l.status.startsWith('amended') ? 'amended' : 'replaced'}</Badge>
                      </div>
                      <div className="mt-1.5 text-sm text-heading">{l.title}</div>
                      <div className="mt-2 space-y-0.5 text-[11.5px] text-muted">
                        <div>where: <span className="text-soft">{l.made_in}</span> <CiteInline t={l.cite} on={setActiveSid} /></div>
                        {l.proposed_by && <div>proposed: <span className="text-soft">{l.proposed_by}</span></div>}
                        {l.approved_by && <div>approved: <span className="text-soft">{l.approved_by}</span></div>}
                        {l.evidence_cite && <div>evidence: <CiteInline t={l.evidence_cite} on={setActiveSid} /></div>}
                        {l.implemented_by.length > 0 && <div>implemented: <span className="font-mono text-soft">{l.implemented_by.join(', ')}</span></div>}
                      </div>
                    </div>
                    {i < trace.result.lineage.length - 1 && <ArrowRight size={18} className="text-pink" />}
                  </div>
                ))}
              </div>
              <div className="mt-4 text-sm text-soft"><CiteText text={trace.result.summary.split('\n')[0]} onCite={setActiveSid} active={activeSid} /></div>
            </Panel>
            <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-5">
              <Panel title="Trace graph">
                <GraphCanvas nodes={trace.subgraph.nodes} edges={trace.subgraph.edges} height={420} highlight={activeSid ? new Set([activeSid]) : undefined} onNodeClick={(n) => n.sid && setActiveSid(n.sid as string)} />
                <div className="mt-2"><Legend labels={['Decision', 'Person']} /></div>
              </Panel>
              <Panel title="Sources">
                <div className="max-h-[460px] space-y-2 overflow-y-auto pr-1">
                  {trace.citations.map((c) => <SourceCard key={c.sid} c={c} active={activeSid === c.sid} onClick={() => setActiveSid(c.sid)} />)}
                </div>
              </Panel>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function CiteInline({ t, on }: { t: string; on: (s: string) => void }) {
  return <span className="inline-block"><CiteText text={t} onCite={on} /></span>
}
