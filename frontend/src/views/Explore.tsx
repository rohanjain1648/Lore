import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { api, type GEdge, type GNode, type ToolResponse } from '../api'
import { CiteText, GraphCanvas, Legend, SourceCard, Spinner } from '../ui'

export default function ExploreView({ asOf, version }: { asOf: string | null; version: number }) {
  const [g, setG] = useState<{ nodes: GNode[]; edges: GEdge[] } | null>(null)
  const [sel, setSel] = useState<GNode | null>(null)
  const [prof, setProf] = useState<ToolResponse<{ summary: string }> | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.overview(asOf).then(setG)
  }, [asOf, version])

  useEffect(() => {
    if (!sel || sel.label === 'Decision' || sel.label === 'Topic') return
    setLoading(true)
    api.profile(sel.id, asOf).then(setProf).finally(() => setLoading(false))
  }, [sel, asOf])

  const edges = g?.edges.map((e) => (e.type === 'OWNS' ? { ...e, current: true } : e)) ?? []

  return (
    <div className="relative h-full min-h-[560px] overflow-hidden rounded-2xl border border-line bg-panel-2">
      {g && <GraphCanvas nodes={g.nodes} edges={edges} onNodeClick={setSel} highlight={sel ? new Set([sel.id]) : undefined} />}
      <div className="glass absolute left-5 top-5 max-w-md rounded-xl p-4">
        <div className="text-sm font-semibold text-heading">The company graph{asOf ? ` as of ${asOf.slice(0, 10)}` : ''}</div>
        <div className="mt-1 text-xs text-muted">
          Teams, people, systems, projects and decisions. Bright green links are current ownership (they move when you drag the
          time slider), pink links are decisions replacing earlier ones. Click any node.
        </div>
        <div className="mt-3"><Legend labels={['Person', 'Team', 'System', 'Project', 'Decision', 'Topic']} /></div>
      </div>
      {sel && (
        <div className="glass absolute right-5 top-5 bottom-5 w-[420px] overflow-y-auto rounded-2xl p-5">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-xs uppercase tracking-wider text-muted">{sel.label}</div>
              <div className="text-lg font-bold text-heading">{sel.name}</div>
            </div>
            <button onClick={() => { setSel(null); setProf(null) }} className="text-muted hover:text-heading"><X size={18} /></button>
          </div>
          {loading && <div className="mt-4"><Spinner /></div>}
          {prof && !loading && (
            <>
              <div className="mt-3 text-sm text-soft"><CiteText text={prof.result.summary} /></div>
              <div className="mt-4 space-y-2">{prof.citations.slice(0, 8).map((c) => <SourceCard key={c.sid} c={c} />)}</div>
            </>
          )}
          {(sel.label === 'Decision' || sel.label === 'Topic') && <div className="mt-3 text-sm text-muted">Open the Decisions or Who-knows views for details.</div>}
        </div>
      )}
    </div>
  )
}
