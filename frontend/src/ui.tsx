import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d'
import { FileText, MessageSquare, Ticket, MessageCircle, Users, ExternalLink, AlertTriangle } from 'lucide-react'
import type { Citation, GEdge, GNode } from './api'

export const LABEL_COLOR: Record<string, string> = {
  Person: '#2563eb',
  Team: '#7c3aed',
  System: '#0891b2',
  Project: '#ea580c',
  Decision: '#db2777',
  Topic: '#ca8a04',
  Document: '#475569',
  Chunk: '#94a3b8',
  Message: '#94a3b8',
  Ticket: '#94a3b8',
  Comment: '#94a3b8',
  Meeting: '#94a3b8',
  Action: '#0f172a',
}

export const KIND_ICON: Record<string, ReactNode> = {
  chunk: <FileText size={14} />,
  message: <MessageSquare size={14} />,
  ticket: <Ticket size={14} />,
  comment: <MessageCircle size={14} />,
  meeting: <Users size={14} />,
}

export const KIND_LABEL: Record<string, string> = {
  chunk: 'Doc', message: 'Chat', ticket: 'Ticket', comment: 'Comment', meeting: 'Meeting',
}

export function Panel({ title, right, children, className = '', flush = false }: { title?: ReactNode; right?: ReactNode; children: ReactNode; className?: string; flush?: boolean }) {
  return (
    <section className={`rounded-2xl border border-line bg-white ${className}`}>
      {title && (
        <header className="flex items-center justify-between gap-4 border-b border-line px-6 py-5">
          <h3 className="flex items-center gap-2 text-[17px] font-semibold text-heading">{title}</h3>
          {right && <div className="text-[15px] text-muted">{right}</div>}
        </header>
      )}
      <div className={flush ? '' : 'p-6'}>{children}</div>
    </section>
  )
}

/** The page frame from the dashboard design: breadcrumb, big title with icon, then the content. */
export function PageCard({ crumb, title, icon, right, children, fill = false }: {
  crumb: string; title: string; icon: ReactNode; right?: ReactNode; children: ReactNode; fill?: boolean
}) {
  return (
    <div className={`h-full overflow-y-auto p-7 ${fill ? 'flex flex-col' : ''}`}>
      <div className={`rounded-3xl border border-line bg-white px-7 pt-6 pb-7 shadow-[0_1px_2px_rgba(15,23,42,0.04)] ${fill ? 'flex min-h-0 flex-1 flex-col' : ''}`}>
        <nav className="text-[16px]">
          <span className="text-lime">Dashboard</span>
          <span className="mx-2 text-muted">/</span>
          <span className="text-soft">{crumb}</span>
        </nav>
        <div className="mt-3 mb-6 flex items-center justify-between gap-4">
          <h1 className="font-display flex items-center gap-3 text-[28px] font-bold tracking-tight text-heading">
            <span className="text-heading">{icon}</span>
            {title}
          </h1>
          {right}
        </div>
        <div className={fill ? 'min-h-0 flex-1' : ''}>{children}</div>
      </div>
    </div>
  )
}

export function Badge({ children, tone = 'muted' }: { children: ReactNode; tone?: 'lime' | 'rose' | 'amber' | 'cyan' | 'muted' | 'violet' }) {
  const tones = {
    lime: 'bg-lime/10 text-lime border-lime/30',
    rose: 'bg-rose/10 text-rose border-rose/30',
    amber: 'bg-amber/10 text-amber border-amber/30',
    cyan: 'bg-cyan/10 text-cyan border-cyan/30',
    violet: 'bg-violet/10 text-violet border-violet/30',
    muted: 'bg-slate-100 text-muted border-line-2',
  }
  return <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>{children}</span>
}

/** Renders text, turning [S3] markers into clickable citation chips and "- " lines into bullets. */
export function CiteText({ text, onCite, active }: { text: string; onCite?: (sid: string) => void; active?: string | null }) {
  const lines = text.split('\n').filter((l, i, a) => l.trim() || (i > 0 && a[i - 1].trim()))
  return (
    <div className="space-y-1.5 leading-relaxed">
      {lines.map((line, i) => {
        const bullet = /^\s*[-•*]\s+/.test(line)
        const content = line.replace(/^\s*[-•*]\s+/, '')
        const parts = content.split(/(\[S\d+\])/g)
        const heading = /^[A-Z][^.]{0,40}:$/.test(content.trim())
        return (
          <div key={i} className={`${bullet ? 'pl-4 relative' : ''} ${heading ? 'pt-2 text-xs uppercase tracking-wider text-muted font-semibold' : ''}`}>
            {bullet && <span className="absolute left-0 top-0 text-lime">•</span>}
            {parts.map((p, j) => {
              const m = p.match(/^\[(S\d+)\]$/)
              if (m)
                return (
                  <button
                    key={j}
                    onClick={() => onCite?.(m[1])}
                    className={`mx-0.5 inline-flex items-center rounded-md px-1.5 py-[1px] align-[1px] font-mono text-[10.5px] font-medium transition
                      ${active === m[1] ? 'bg-lime text-ink' : 'bg-lime/12 text-lime hover:bg-lime/25 border border-lime/25'}`}
                  >
                    {m[1]}
                  </button>
                )
              return <span key={j}>{renderBold(p)}</span>
            })}
          </div>
        )
      })}
    </div>
  )
}

function renderBold(s: string) {
  const parts = s.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((p, i) => (p.startsWith('**') ? <strong key={i} className="text-heading">{p.slice(2, -2)}</strong> : p))
}

export function SourceCard({ c, active, onClick, stale }: { c: Citation; active?: boolean; onClick?: () => void; stale?: boolean }) {
  return (
    <div
      id={`src-${c.sid}`}
      onClick={onClick}
      className={`group cursor-pointer rounded-xl border p-3 transition ${active ? 'border-lime/60 bg-lime/5 glow' : 'border-line bg-panel-2/60 hover:border-line-2'}`}
    >
      <div className="flex items-center gap-2 text-xs text-muted">
        <span className="font-mono rounded bg-lime/12 px-1.5 text-lime">{c.sid}</span>
        <span className="flex items-center gap-1">{KIND_ICON[c.kind]} {KIND_LABEL[c.kind] ?? c.kind}</span>
        <span>·</span>
        <span>{c.author_name ?? c.author}</span>
        <span>·</span>
        <span className="font-mono">{c.ts?.slice(0, 10)}</span>
        {stale && <Badge tone="amber"><AlertTriangle size={11} /> out of date</Badge>}
        <a href={c.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} className="ml-auto opacity-0 group-hover:opacity-100 text-cyan">
          <ExternalLink size={13} />
        </a>
      </div>
      <div className="mt-1.5 text-sm font-medium text-soft">{c.title}</div>
      <div className="mt-1 text-[13px] leading-snug text-muted whitespace-pre-line">{c.snippet}</div>
    </div>
  )
}

export function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [size, setSize] = useState({ width: 400, height: 300 })
  useEffect(() => {
    if (!ref.current) return
    const ro = new ResizeObserver(([e]) => setSize({ width: e.contentRect.width, height: e.contentRect.height }))
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  return [ref, size] as const
}

type FGNode = GNode & { x?: number; y?: number }

/** Force-directed graph of a subgraph. Highlighted ids glow; sources show their citation label. */
export function GraphCanvas({
  nodes, edges, highlight, onNodeClick, height, dim,
}: {
  nodes: GNode[]; edges: GEdge[]; highlight?: Set<string>; onNodeClick?: (n: GNode) => void; height?: number; dim?: boolean
}) {
  const [ref, size] = useSize<HTMLDivElement>()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fg = useRef<ForceGraphMethods<any, any> | undefined>(undefined)
  const data = useMemo(() => {
    const ids = new Set(nodes.map((n) => n.id))
    return {
      nodes: nodes.map((n) => ({ ...n })),
      links: edges.filter((e) => ids.has(e.source) && ids.has(e.target)).map((e) => ({ ...e })),
    }
  }, [nodes, edges])
  useEffect(() => {
    const g = fg.current
    if (!g) return
    g.d3Force('charge')?.strength(-260)
    g.d3Force('link')?.distance(70)
    g.d3ReheatSimulation()
  }, [data])
  return (
    <div ref={ref} className="h-full w-full" style={height ? { height } : undefined}>
      <ForceGraph2D
        ref={fg}
        graphData={data}
        onEngineStop={() => fg.current?.zoomToFit(400, 40)}
        width={size.width}
        height={height ?? size.height}
        backgroundColor="rgba(0,0,0,0)"
        cooldownTicks={120}
        d3VelocityDecay={0.3}
        linkColor={(l: { type?: string; current?: boolean }) =>
          l.type === 'SUPERSEDES' ? 'rgba(219,39,119,0.75)' : l.type === 'OWNS' && l.current ? 'rgba(37,99,235,0.85)' : 'rgba(100,116,139,0.28)'}
        linkWidth={(l: { type?: string; current?: boolean }) => (l.type === 'OWNS' && l.current ? 2.2 : l.type === 'SUPERSEDES' ? 1.8 : 1)}
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        linkLineDash={(l: { type?: string; until?: string | null }) => (l.type === 'OWNS' && l.until ? [3, 3] : null)}
        onNodeClick={(n: FGNode) => onNodeClick?.(n)}
        nodeLabel={(n: FGNode) => `${n.label}: ${n.name}`}
        nodeCanvasObject={(n: FGNode, ctx: CanvasRenderingContext2D, scale: number) => {
          const isSource = ['Chunk', 'Message', 'Ticket', 'Comment', 'Meeting'].includes(n.label)
          const hl = highlight?.has(n.id) || (n.sid && highlight?.has(n.sid as string))
          const r = n.label === 'Person' || n.label === 'System' ? 6 : n.label === 'Decision' ? 6.5 : isSource ? 4 : 5.5
          const color = n.active === false ? '#dc2626' : n.stale ? '#d97706' : LABEL_COLOR[n.label] ?? '#999'
          const x = n.x ?? 0
          const y = n.y ?? 0
          ctx.globalAlpha = dim && !hl && highlight && highlight.size ? 0.35 : 1
          if (hl) {
            ctx.beginPath()
            ctx.arc(x, y, r + 5, 0, 2 * Math.PI)
            ctx.fillStyle = 'rgba(37,99,235,0.18)'
            ctx.fill()
          }
          ctx.beginPath()
          if (n.label === 'Decision') {
            ctx.moveTo(x, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x, y + r); ctx.lineTo(x - r, y); ctx.closePath()
          } else if (isSource) {
            ctx.rect(x - r, y - r, r * 2, r * 2)
          } else {
            ctx.arc(x, y, r, 0, 2 * Math.PI)
          }
          ctx.fillStyle = color
          ctx.fill()
          const fs = Math.max(10 / scale, 2.5)
          ctx.font = `${isSource ? 400 : 600} ${fs}px Outfit`
          ctx.textAlign = 'center'
          ctx.textBaseline = 'top'
          ctx.fillStyle = isSource ? 'rgba(71,85,105,0.85)' : '#0f172a'
          const label = isSource && n.sid ? `${n.sid} ${truncate(n.name, 22)}` : truncate(n.name, 30)
          if (scale > 0.9 || !isSource || hl) ctx.fillText(label, x, y + r + 2)
          ctx.globalAlpha = 1
        }}
        nodePointerAreaPaint={(n: FGNode, color: string, ctx: CanvasRenderingContext2D) => {
          ctx.fillStyle = color
          ctx.beginPath()
          ctx.arc(n.x ?? 0, n.y ?? 0, 8, 0, 2 * Math.PI)
          ctx.fill()
        }}
      />
    </div>
  )
}

const truncate = (s: string, n: number) => (s && s.length > n ? s.slice(0, n - 1) + '…' : s)

export function Legend({ labels }: { labels: string[] }) {
  return (
    <div className="flex flex-wrap gap-3 text-[11px] text-muted">
      {labels.map((l) => (
        <span key={l} className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: LABEL_COLOR[l] }} /> {l}
        </span>
      ))}
      <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-rose" /> left company</span>
      <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-amber" /> out of date</span>
    </div>
  )
}

export function Spinner() {
  return <div className="h-4 w-4 animate-spin rounded-full border-2 border-lime/30 border-t-lime" />
}
