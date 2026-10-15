import { useEffect, useState } from 'react'
import { ListChecks, Ticket, FileWarning, Mail } from 'lucide-react'
import { api, type ActionRow } from '../api'
import { Badge, Panel } from '../ui'

const ICON = { ticket: <Ticket size={15} />, doc_update: <FileWarning size={15} />, message: <Mail size={15} /> } as Record<string, React.ReactNode>

export default function ActionsView({ version }: { version: number }) {
  const [rows, setRows] = useState<ActionRow[]>([])
  useEffect(() => {
    api.actions().then((r) => setRows(r.actions))
  }, [version])
  return (
    <div>
      <Panel title={<span className="flex items-center gap-2"><ListChecks size={15} className="text-lime" /> Work Lore has done</span>}>
        <p className="mb-4 text-sm text-muted">
          Tickets, doc-update requests and drafted messages created by the agent (ask it to "open a ticket…" or "draft a message to…")
          or from the Freshness page. Each one is linked into the graph to the system, person or document it is about.
        </p>
        {rows.length === 0 && <div className="text-sm text-muted">Nothing yet.</div>}
        <div className="space-y-2">
          {rows.map((a) => (
            <div key={a.id} className="flex items-start gap-3 rounded-xl border border-line bg-panel-2/50 p-3">
              <div className="mt-0.5 text-lime">{ICON[a.kind]}</div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-heading">{a.title}</span>
                  <Badge tone="cyan">{a.kind.replace('_', ' ')}</Badge>
                  <Badge>{a.status}</Badge>
                </div>
                <div className="mt-1 whitespace-pre-line text-[13px] text-muted">{a.body}</div>
                <div className="mt-1 text-[11px] text-muted">about: {a.about.join(', ') || '—'} · {a.created_at}</div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}
