import { useEffect, useState } from 'react'
import { FileWarning, Flag, Check, History } from 'lucide-react'
import { api, type StaleDoc, type ToolResponse } from '../api'
import { Badge, CiteText, Panel, SourceCard, Spinner } from '../ui'

export default function FreshnessView({ asOf, version }: { asOf: string | null; version: number }) {
  const [fresh, setFresh] = useState<ToolResponse<{ stale_documents: StaleDoc[]; summary: string }> | null>(null)
  const [since, setSince] = useState('2026-06-01')
  const [changes, setChanges] = useState<ToolResponse<{ summary: string }> | null>(null)
  const [flagged, setFlagged] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.freshness().then(setFresh)
  }, [version])
  useEffect(() => {
    setLoading(true)
    api.changes(since, asOf).then(setChanges).finally(() => setLoading(false))
  }, [since, asOf, version])

  async function flag(d: StaleDoc) {
    const r = await api.createAction('doc_update', d.title, d.reasons.join('\n'), d.title)
    setFlagged((f) => ({ ...f, [d.id]: r.summary }))
  }

  return (
    <div>
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-5">
        <Panel title={<span className="flex items-center gap-2"><FileWarning size={15} className="text-amber" /> Out-of-date documents</span>}
          right={fresh && <Badge tone="amber">{fresh.result.stale_documents.length} need updates</Badge>}>
          <p className="mb-4 text-sm text-muted">
            Lore compares what each doc says with newer evidence in chat, tickets and meetings. When a newer fact replaces one a doc
            relies on, the doc gets flagged here with the reason.
          </p>
          <div className="space-y-3">
            {fresh?.result.stale_documents.map((d) => (
              <div key={d.id} className="rounded-xl border border-amber/25 bg-amber/[0.04] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <a href={d.url} target="_blank" rel="noreferrer" className="font-semibold text-heading hover:text-cyan">{d.title}</a>
                    <div className="text-xs text-muted">last updated {d.updated.slice(0, 10)} by {d.author}</div>
                  </div>
                  {flagged[d.id] ? (
                    <Badge tone="lime"><Check size={11} /> flagged</Badge>
                  ) : (
                    <button onClick={() => flag(d)} className="flex shrink-0 items-center gap-1.5 rounded-lg border border-amber/40 px-2.5 py-1 text-xs text-amber hover:bg-amber/10">
                      <Flag size={12} /> Flag for update
                    </button>
                  )}
                </div>
                <ul className="mt-3 space-y-1.5 text-[13px] text-soft">
                  {d.reasons.map((r, i) => <li key={i} className="flex gap-2"><span className="text-amber">→</span>{r}</li>)}
                </ul>
                {flagged[d.id] && <div className="mt-2 text-xs text-lime">{flagged[d.id]}</div>}
              </div>
            ))}
          </div>
        </Panel>

        <Panel title={<span className="flex items-center gap-2"><History size={15} className="text-cyan" /> What changed</span>}
          right={<div className="flex items-center gap-2 text-xs text-muted">{loading && <Spinner />} since
            <input type="date" value={since} onChange={(e) => setSince(e.target.value)} className="rounded-md border border-line bg-panel-2 px-2 py-0.5 font-mono text-soft [color-scheme:light]" /></div>}>
          {changes && (
            <>
              <div className="text-sm text-soft"><CiteText text={changes.result.summary.split('\n').map((l) => '- ' + l).join('\n')} /></div>
              <div className="mt-4 space-y-2">
                {changes.citations.map((c) => <SourceCard key={c.sid} c={c} />)}
              </div>
            </>
          )}
        </Panel>
      </div>
    </div>
  )
}
