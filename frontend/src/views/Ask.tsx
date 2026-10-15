import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowUp, AlertTriangle, Wrench, Sparkles, Bot } from 'lucide-react'
import { api } from '../api'
import type { Turn } from '../App'
import { Badge, CiteText, GraphCanvas, Legend, SourceCard, Spinner } from '../ui'

const SUGGESTIONS = [
  'Who owns payments-service?',
  'Why did we choose FalkorDB for the recommendations engine?',
  'Can we deploy on Fridays?',
  'Who should I ask about auth-gateway?',
  'Who knows about Kafka?',
  'What changed since June?',
  'Which docs are out of date?',
  'Give me an onboarding brief for Project Atlas',
]

export default function AskView({ asOf, turns, setTurns, pendingQ, clearPending }: {
  asOf: string | null; turns: Turn[]; setTurns: (f: (t: Turn[]) => Turn[]) => void; pendingQ?: string | null; clearPending?: () => void
}) {
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState<number | null>(null)
  const [activeSid, setActiveSid] = useState<string | null>(null)
  const [tab, setTab] = useState<'graph' | 'sources' | 'steps'>('graph')
  const bottom = useRef<HTMLDivElement>(null)
  const busy = turns.some((t) => t.pending)

  const current = selected !== null ? turns[selected] : [...turns].reverse().find((t) => t.res)
  const res = current?.res

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns.length, busy])

  // a question typed into the header search box
  useEffect(() => {
    if (pendingQ) {
      clearPending?.()
      send(pendingQ)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingQ])

  async function send(question: string) {
    if (!question.trim() || busy) return
    setQ('')
    setSelected(null)
    setActiveSid(null)
    const history = turns.flatMap((t) => (t.res ? [{ role: 'user', content: t.q }, { role: 'assistant', content: t.res.answer }] : []))
    setTurns((t) => [...t, { q: question, pending: true }])
    try {
      const r = await api.ask(question, asOf, history)
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { q: question, res: r } : x)))
    } catch (e) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { q: question, error: String(e) } : x)))
    }
  }

  const cite = (sid: string) => {
    setActiveSid(sid)
    setTab('sources')
    setTimeout(() => document.getElementById(`src-${sid}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50)
  }

  const usedSids = useMemo(() => new Set(res?.citations.filter((c) => c.used).map((c) => c.sid) ?? []), [res])
  const highlight = useMemo(() => (activeSid ? new Set([activeSid]) : usedSids), [activeSid, usedSids])
  const staleTitles = useMemo(() => new Set((res?.warnings ?? []).map((w) => w.match(/^'(.+?)' is cited/)?.[1]).filter(Boolean) as string[]), [res])

  return (
    <div className="grid h-full min-h-[560px] grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] gap-0 overflow-hidden rounded-2xl border border-line">
      {/* Conversation */}
      <div className="flex min-h-0 flex-col border-r border-line">
        <div className="min-h-0 flex-1 overflow-y-auto px-8 py-6">
          {turns.length === 0 && (
            <div className="mx-auto mt-10 max-w-xl text-center">
              <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-lime/30 bg-lime/10 glow">
                <Sparkles className="text-lime" />
              </div>
              <h1 className="text-3xl font-extrabold tracking-tight text-heading">Ask how the company works</h1>
              <p className="mt-3 text-muted">
                Lore connects docs, tickets, chat and meeting notes into one FalkorDB graph. Every answer cites its sources,
                knows what changed and when, and you can rewind time with the slider above.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => send(s)} className="rounded-full border border-line bg-panel-2/70 px-3.5 py-1.5 text-sm text-soft transition hover:border-lime/40 hover:text-lime">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="space-y-6">
            {turns.map((t, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-br-md bg-lime/90 px-4 py-2.5 text-sm font-medium text-ink">{t.q}</div>
                </div>
                <div
                  onClick={() => t.res && setSelected(i)}
                  className={`glass cursor-pointer rounded-2xl rounded-bl-md p-4 text-[14.5px] text-soft transition ${current === t ? 'border-lime/30' : 'opacity-80 hover:opacity-100'}`}
                >
                  {t.pending && <div className="flex items-center gap-2 text-muted"><Spinner /> Walking the graph…</div>}
                  {t.error && <div className="text-rose">{t.error}</div>}
                  {t.res && (
                    <>
                      <div className="mb-2 flex flex-wrap items-center gap-1.5">
                        <Badge tone={t.res.mode === 'llm' ? 'lime' : 'cyan'}><Bot size={11} /> {t.res.mode === 'llm' ? (t.res.provider === 'openai' ? 'OpenAI (fallback)' : 'Groq') : 'offline agent'}</Badge>
                        {t.res.as_of && <Badge tone="amber">as of {t.res.as_of.slice(0, 10)}</Badge>}
                        {t.res.steps.map((s, k) => <Badge key={k}><Wrench size={10} /> {s.tool}</Badge>)}
                      </div>
                      <CiteText text={t.res.answer} onCite={cite} active={current === t ? activeSid : null} />
                      {t.res.warnings.length > 0 && (
                        <div className="mt-3 space-y-1 rounded-xl border border-amber/25 bg-amber/[0.06] p-2.5 text-xs text-amber">
                          {t.res.warnings.map((w, k) => <div key={k} className="flex gap-1.5"><AlertTriangle size={13} className="mt-0.5 shrink-0" />{w}</div>)}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
          <div ref={bottom} />
        </div>
        <form onSubmit={(e) => { e.preventDefault(); send(q) }} className="border-t border-line p-4">
          <div className="flex items-center gap-2 rounded-2xl border border-line-2 bg-panel-2 px-4 py-2 focus-within:border-lime/50 focus-within:glow">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={asOf ? `Ask about the company as of ${asOf.slice(0, 10)}…` : 'Who owns…? Why did we…? Who knows about…?'}
              className="flex-1 bg-transparent py-1.5 text-sm text-heading outline-none placeholder:text-muted"
            />
            <button disabled={busy || !q.trim()} className="flex h-8 w-8 items-center justify-center rounded-xl bg-lime text-ink transition disabled:opacity-30">
              {busy ? <Spinner /> : <ArrowUp size={17} />}
            </button>
          </div>
        </form>
      </div>

      {/* Evidence */}
      <div className="flex min-h-0 flex-col">
        <div className="flex items-center gap-1 border-b border-line px-5 pt-3">
          {(['graph', 'sources', 'steps'] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`relative px-3 pb-2.5 text-sm capitalize ${tab === t ? 'text-heading' : 'text-muted hover:text-soft'}`}>
              {t === 'graph' ? 'Reasoning graph' : t === 'sources' ? `Sources${res ? ` (${res.citations.filter((c) => c.used).length})` : ''}` : 'Tool calls'}
              {tab === t && <motion.span layoutId="tab" className="absolute inset-x-2 -bottom-px h-0.5 rounded bg-lime" />}
            </button>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {!res && <div className="p-10 text-center text-sm text-muted">The graph path, sources and tool calls behind each answer show up here.</div>}
          {res && tab === 'graph' && (
            <div className="flex h-full flex-col">
              <div className="min-h-0 flex-1">
                <GraphCanvas nodes={res.subgraph.nodes} edges={res.subgraph.edges} highlight={highlight} dim={!!activeSid} onNodeClick={(n) => n.sid && cite(n.sid as string)} />
              </div>
              <div className="border-t border-line px-5 py-3"><Legend labels={['Person', 'Team', 'System', 'Project', 'Decision', 'Topic', 'Document']} /></div>
            </div>
          )}
          {res && tab === 'sources' && (
            <div className="space-y-2.5 p-5">
              {res.citations.filter((c) => c.used).map((c) => (
                <SourceCard key={c.sid} c={c} active={activeSid === c.sid} onClick={() => setActiveSid(c.sid)} stale={[...staleTitles].some((t) => c.title.startsWith(t))} />
              ))}
              {res.citations.some((c) => !c.used) && (
                <>
                  <div className="pt-3 text-xs uppercase tracking-wider text-muted">Also retrieved</div>
                  {res.citations.filter((c) => !c.used).map((c) => <SourceCard key={c.sid} c={c} active={activeSid === c.sid} onClick={() => setActiveSid(c.sid)} />)}
                </>
              )}
            </div>
          )}
          {res && tab === 'steps' && (
            <div className="space-y-3 p-5">
              {res.steps.map((s, i) => (
                <div key={i} className="rounded-xl border border-line bg-panel-2/60 p-3">
                  <div className="flex items-center gap-2 font-mono text-sm text-lime"><Wrench size={13} /> {s.tool}</div>
                  <pre className="mt-1.5 overflow-x-auto font-mono text-[11.5px] text-muted">{JSON.stringify(s.input)}</pre>
                  <div className="mt-2 border-t border-line pt-2 text-[12.5px] text-soft"><CiteText text={s.summary} onCite={cite} /></div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
