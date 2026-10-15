import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Radio, Send, Zap, RotateCcw } from 'lucide-react'
import { api, type IngestResult, type PersonRow } from '../api'
import { Badge, Panel, Spinner } from '../ui'

const PRESETS = [
  { author: 'lena.novak', channel: 'eng-announcements', text: 'Update: search-api is now owned by the Data team. Aiko and Ben will run it from Monday.' },
  { author: 'olu.adeyemi', channel: 'sre', text: 'Decision: lift the Friday deploy freeze again now that canary analysis covers the payment flow.' },
  { author: 'marco.rossi', channel: 'platform', text: 'Mei Lin completed her first auth-gateway token rotation today, pairing with Jonas on SAML next.' },
]

type Log = { at: string; text: string; author: string; res: IngestResult }

export default function LiveView({ onIngested, goAsk }: { onIngested: () => void; goAsk: () => void }) {
  const [people, setPeople] = useState<PersonRow[]>([])
  const [author, setAuthor] = useState(PRESETS[0].author)
  const [channel, setChannel] = useState(PRESETS[0].channel)
  const [text, setText] = useState(PRESETS[0].text)
  const [busy, setBusy] = useState(false)
  const [log, setLog] = useState<Log[]>([])
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api.people().then((r) => setPeople(r.people.filter((p) => p.active)))
  }, [])

  async function send() {
    setBusy(true)
    setErr(null)
    try {
      const res = await api.ingest(channel, author, text)
      setLog((l) => [{ at: new Date().toLocaleTimeString(), text, author, res }, ...l])
      onIngested()
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function reset() {
    setBusy(true)
    await api.reset()
    setLog([])
    onIngested()
    setBusy(false)
  }

  return (
    <div>
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-5">
        <Panel title={<span className="flex items-center gap-2"><Radio size={15} className="text-lime" /> Post a new message</span>}
          right={<button onClick={reset} disabled={busy} className="flex items-center gap-1 text-xs text-muted hover:text-rose"><RotateCcw size={12} /> reset demo data</button>}>
          <p className="mb-4 text-sm text-muted">
            New messages go through the same pipeline as the seed data: entity linking, ownership and decision extraction,
            temporal reconciliation against what the graph already believes, stale-doc detection and re-ranking of expertise.
          </p>
          <div className="mb-3 flex flex-wrap gap-2">
            {PRESETS.map((p, i) => (
              <button key={i} onClick={() => { setAuthor(p.author); setChannel(p.channel); setText(p.text) }} className="rounded-full border border-line px-3 py-1 text-xs text-muted hover:border-lime/40 hover:text-lime">
                Example {i + 1}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs text-muted">Author
              <select value={author} onChange={(e) => setAuthor(e.target.value)} className="mt-1 w-full rounded-lg border border-line bg-panel-2 px-2 py-1.5 text-sm text-soft">
                {people.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
            <label className="text-xs text-muted">Channel
              <input value={channel} onChange={(e) => setChannel(e.target.value)} className="mt-1 w-full rounded-lg border border-line bg-panel-2 px-2 py-1.5 font-mono text-sm text-soft" />
            </label>
          </div>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} className="mt-3 w-full rounded-xl border border-line bg-panel-2 p-3 text-sm text-soft outline-none focus:border-lime/40" />
          {err && <div className="mt-2 text-xs text-rose">{err}</div>}
          <button onClick={send} disabled={busy || !text.trim()} className="mt-3 flex items-center gap-2 rounded-xl bg-lime px-4 py-2 text-sm font-semibold text-ink disabled:opacity-40">
            {busy ? <Spinner /> : <Send size={15} />} Ingest into the graph
          </button>
        </Panel>

        <Panel title={<span className="flex items-center gap-2"><Zap size={15} className="text-amber" /> What the graph learned</span>}>
          {log.length === 0 && <div className="text-sm text-muted">Post a message to see the graph update.</div>}
          <div className="space-y-3">
            {log.map((l, i) => (
              <motion.div key={l.at + i} initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} className="rounded-xl border border-line bg-panel-2/50 p-3">
                <div className="text-xs text-muted">{l.at} · {l.author}</div>
                <div className="mt-1 text-sm text-soft">“{l.text}”</div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {l.res.mentions.map((m) => <Badge key={m.id} tone="cyan">{m.label}: {m.name}</Badge>)}
                </div>
                <div className="mt-2 space-y-1 text-[13px]">
                  {l.res.changes.length === 0 && <div className="text-muted">Linked to entities; no ownership or decision change.</div>}
                  {l.res.changes.map((c, k) => (
                    <div key={k} className="flex gap-2">
                      <span className={c.type.includes('superseded') || c.type.includes('amended') ? 'text-amber' : 'text-lime'}>●</span>
                      <span className="text-soft">{describe(c)}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>
          {log.length > 0 && (
            <button onClick={goAsk} className="mt-4 text-sm text-lime hover:underline">Ask about it →</button>
          )}
        </Panel>
      </div>
    </div>
  )
}

function describe(c: { type: string; [k: string]: string }) {
  switch (c.type) {
    case 'claim_created': return `New ownership fact: ${c.subject} → ${c.owner}`
    case 'claim_superseded': return `Replaced: ${c.subject} was owned by ${c.from}, now ${c.to}`
    case 'claim_confirmed': return `Confirmed existing fact: ${c.subject} → ${c.owner}`
    case 'decision_created': return `New decision recorded: “${c.title}”`
    case 'decision_superseded': return `Decision replaced: “${c.title}”`
    case 'decision_amended': return `Decision amended: “${c.title}”`
    default: return JSON.stringify(c)
  }
}
