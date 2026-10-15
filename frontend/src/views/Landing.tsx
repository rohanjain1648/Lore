import { useState, useEffect, useRef } from 'react'
import {
  Sparkles, ShieldAlert, Users, Network, ArrowRight,
  ChevronRight, CheckCircle2, AlertTriangle, Clock, Terminal,
  Layers, Activity, Check, HelpCircle, Bot,
  ArrowUpRight, Copy, CheckCheck
} from 'lucide-react'

interface LandingProps {
  onEnterApp: (viewId?: string) => void
  currentTenant?: string | null
  stats?: {
    nodes: Record<string, number>
    relationships: Record<string, number>
  }
}

// -------------------------------------------------------------
// Interactive Node / Canvas Simulation for Hero
// -------------------------------------------------------------
function HeroGraphCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animId: number
    let width = (canvas.width = canvas.parentElement?.clientWidth || 600)
    let height = (canvas.height = canvas.parentElement?.clientHeight || 480)

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return
      width = canvas.width = canvas.parentElement.clientWidth
      height = canvas.height = canvas.parentElement.clientHeight
    }
    window.addEventListener('resize', handleResize)

    // Knowledge nodes with real project concepts
    const nodes = [
      { id: 'p1', label: 'Marco Ross', type: 'Person', color: '#2563eb', x: width * 0.28, y: height * 0.35, vx: 0.2, vy: 0.15, r: 14, tag: 'Platform Lead' },
      { id: 'p2', label: 'Priya Sharma', type: 'Person', color: '#2563eb', x: width * 0.72, y: height * 0.25, vx: -0.18, vy: 0.12, r: 12, tag: 'Core Eng' },
      { id: 't1', label: 'Platform Team', type: 'Team', color: '#7c3aed', x: width * 0.22, y: height * 0.65, vx: 0.12, vy: -0.15, r: 15, tag: 'Active Owner' },
      { id: 's1', label: 'payments-service', type: 'System', color: '#0891b2', x: width * 0.48, y: height * 0.48, vx: -0.1, vy: 0.08, r: 16, tag: 'Critical System' },
      { id: 'd1', label: 'Friday Deploy Freeze', type: 'Decision', color: '#db2777', x: width * 0.75, y: height * 0.62, vx: 0.15, vy: -0.1, r: 15, tag: 'In Force (Aug)' },
      { id: 'd0', label: 'Canary Deploy RFC', type: 'Decision', color: '#94a3b8', x: width * 0.85, y: height * 0.42, vx: -0.12, vy: 0.18, r: 11, tag: 'Superseded (May)' },
      { id: 'c1', label: 'Claim #409: Ownership', type: 'Claim', color: '#10b981', x: width * 0.38, y: height * 0.22, vx: 0.08, vy: 0.2, r: 12, tag: 'valid_from: Jun' },
      { id: 'src1', label: '[S4] INC-7 Postmortem', type: 'Source', color: '#f59e0b', x: width * 0.58, y: height * 0.78, vx: -0.14, vy: -0.12, r: 11, tag: 'Root Cause' },
      { id: 'src2', label: '[S2] Slack #announcements', type: 'Source', color: '#f59e0b', x: width * 0.15, y: height * 0.22, vx: 0.1, vy: 0.15, r: 10, tag: 'Ownership Reorg' },
    ]

    const edges = [
      { source: 't1', target: 's1', label: 'OWNS', color: 'rgba(37,99,235,0.7)', width: 2.2, dash: [] },
      { source: 'p1', target: 't1', label: 'MEMBER_OF', color: 'rgba(124,58,237,0.5)', width: 1.5, dash: [] },
      { source: 'c1', target: 's1', label: 'ABOUT', color: 'rgba(16,185,129,0.6)', width: 1.5, dash: [] },
      { source: 'c1', target: 'src2', label: 'SUPPORTED_BY', color: 'rgba(245,158,11,0.5)', width: 1.2, dash: [4, 4] },
      { source: 'd1', target: 'd0', label: 'SUPERSEDES', color: 'rgba(219,39,119,0.7)', width: 2, dash: [] },
      { source: 'd1', target: 'src1', label: 'BASED_ON', color: 'rgba(245,158,11,0.5)', width: 1.2, dash: [4, 4] },
      { source: 'p1', target: 's1', label: 'EXPERT_IN', color: 'rgba(8,145,178,0.5)', width: 1.5, dash: [] },
      { source: 'd1', target: 's1', label: 'AFFECTS', color: 'rgba(219,39,119,0.5)', width: 1.5, dash: [] },
      { source: 'p2', target: 'p1', label: 'COLLABORATES', color: 'rgba(100,116,139,0.3)', width: 1, dash: [2, 3] },
    ]

    let mouseX = -100
    let mouseY = -100
    let hoveredNode: typeof nodes[0] | null = null

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      mouseX = e.clientX - rect.left
      mouseY = e.clientY - rect.top
      hoveredNode = nodes.find(n => {
        const dx = n.x - mouseX
        const dy = n.y - mouseY
        return Math.sqrt(dx * dx + dy * dy) < n.r + 8
      }) || null
    }

    const handleMouseLeave = () => {
      mouseX = -100
      mouseY = -100
      hoveredNode = null
    }

    canvas.addEventListener('mousemove', handleMouseMove)
    canvas.addEventListener('mouseleave', handleMouseLeave)

    let frame = 0

    const render = () => {
      frame++
      ctx.clearRect(0, 0, width, height)

      // Background subtle grid lines
      ctx.strokeStyle = 'rgba(226, 232, 240, 0.4)'
      ctx.lineWidth = 1

      // Physics update: subtle floating & mouse repulsion
      nodes.forEach(n => {
        n.x += n.vx
        n.y += n.vy

        if (n.x < 30 || n.x > width - 30) n.vx *= -1
        if (n.y < 30 || n.y > height - 30) n.vy *= -1

        // Mouse gentle pull
        if (mouseX > 0) {
          const dx = mouseX - n.x
          const dy = mouseY - n.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < 120 && dist > 10) {
            n.x += (dx / dist) * 0.4
            n.y += (dy / dist) * 0.4
          }
        }
      })

      // Draw edges
      edges.forEach(e => {
        const src = nodes.find(n => n.id === e.source)
        const tgt = nodes.find(n => n.id === e.target)
        if (!src || !tgt) return

        const isHl = hoveredNode && (hoveredNode.id === src.id || hoveredNode.id === tgt.id)

        ctx.save()
        ctx.beginPath()
        ctx.setLineDash(e.dash)
        ctx.moveTo(src.x, src.y)
        ctx.lineTo(tgt.x, tgt.y)
        ctx.strokeStyle = isHl ? '#2563eb' : e.color
        ctx.lineWidth = isHl ? e.width + 1.5 : e.width
        ctx.stroke()

        // Edge particle pulse
        if (isHl || e.label === 'SUPERSEDES' || e.label === 'OWNS') {
          const t = ((frame * 0.015) % 1)
          const px = src.x + (tgt.x - src.x) * t
          const py = src.y + (tgt.y - src.y) * t
          ctx.beginPath()
          ctx.arc(px, py, 3, 0, Math.PI * 2)
          ctx.fillStyle = isHl ? '#3b82f6' : e.color
          ctx.fill()
        }

        // Edge label
        const mx = (src.x + tgt.x) / 2
        const my = (src.y + tgt.y) / 2
        ctx.font = '10px "JetBrains Mono", monospace'
        ctx.fillStyle = isHl ? '#0f172a' : '#94a3b8'
        ctx.textAlign = 'center'
        ctx.fillText(e.label, mx, my - 4)
        ctx.restore()
      })

      // Draw nodes
      nodes.forEach(n => {
        const isHovered = hoveredNode?.id === n.id

        // Glow ring
        if (isHovered) {
          ctx.beginPath()
          ctx.arc(n.x, n.y, n.r + 8, 0, Math.PI * 2)
          ctx.fillStyle = `${n.color}22`
          ctx.fill()
        }

        // Node circle
        ctx.beginPath()
        ctx.arc(n.x, n.y, isHovered ? n.r + 2 : n.r, 0, Math.PI * 2)
        ctx.fillStyle = n.color
        ctx.fill()
        ctx.lineWidth = 2
        ctx.strokeStyle = '#ffffff'
        ctx.stroke()

        // Node label
        ctx.font = isHovered ? '600 12px "Plus Jakarta Sans", sans-serif' : '500 11px "Plus Jakarta Sans", sans-serif'
        ctx.fillStyle = isHovered ? '#0f172a' : '#1e293b'
        ctx.textAlign = 'center'
        ctx.fillText(n.label, n.x, n.y + n.r + 14)

        // Subtag
        ctx.font = '9px "JetBrains Mono", monospace'
        ctx.fillStyle = '#64748b'
        ctx.fillText(n.tag, n.x, n.y + n.r + 26)
      })

      animId = requestAnimationFrame(render)
    }

    render()

    return () => {
      cancelAnimationFrame(animId)
      window.removeEventListener('resize', handleResize)
      canvas.removeEventListener('mousemove', handleMouseMove)
      canvas.removeEventListener('mouseleave', handleMouseLeave)
    }
  }, [])

  return (
    <div className="relative h-full w-full min-h-[420px] rounded-2xl border border-line bg-gradient-to-br from-blue-50/40 via-white to-slate-50/60 p-2 shadow-[0_8px_30px_rgb(0,0,0,0.04)] overflow-hidden">
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2 rounded-lg border border-line bg-white/90 px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm backdrop-blur">
        <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
        <span>Live FalkorDB Graph Simulation</span>
        <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">interactive</span>
      </div>
      <canvas ref={canvasRef} className="h-full w-full cursor-crosshair" />
      <div className="absolute bottom-3 right-4 z-10 text-[11px] text-slate-400">
        Hover nodes to trace temporal relations & citations
      </div>
    </div>
  )
}

// -------------------------------------------------------------
// Interactive Problem vs Solution Scenarios
// -------------------------------------------------------------
const SCENARIOS = [
  {
    id: 'ownership',
    title: '1. Ownership Reorg & Stale Wikis',
    question: 'Who owns payments-service today?',
    vectorRag: {
      answer: 'Payments service is owned by Priya Sharma and the Core Checkout Team.',
      source: 'Doc: /wiki/team-directory.md (Last modified: January 2026)',
      flaw: 'Retrieved stale doc due to high keyword match. Ignores June reorg where Marco\'s Platform team took over. Still routes critical pages to Priya!',
      verdict: 'CONFIDENT HALLUCINATION',
    },
    loreGraph: {
      answer: 'Marco Ross and the Platform Team own payments-service (effective 2026-06-15) [S1]. Replaced Priya Sharma after Core Checkout split [S2].',
      sources: [
        { sid: 'S1', text: 'Chat: #announcements — "Platform team takes over payments-service from Priya starting June 15"', date: '2026-06-15' },
        { sid: 'S2', text: 'Doc: /wiki/team-directory.md flagged STALE (contradicted by S1 since June 15)', date: '2026-01-10' },
      ],
      advantage: 'Bi-temporal Claim traversal: old Claim closed (valid_to: Jun 15), SUPERSEDES edge created. Stale doc automatically flagged!',
      verdict: 'VERIFIED CURRENT TRUTH',
    },
  },
  {
    id: 'decisions',
    title: '2. Policy Supersession Chain',
    question: 'Can we deploy to production on Friday afternoon?',
    vectorRag: {
      answer: 'Yes! Teams may deploy on Fridays if they utilize canary rollouts and have SRE sign-off.',
      source: 'Doc: /rfc/RFC-42-canary-deployments.md (Decided May 2026)',
      flaw: 'Matches cosine similarity for "deploy on Friday". Misses that INC-7 outage in August reinstated the strict Friday deploy freeze!',
      verdict: 'DANGEROUS OUTDATED POLICY',
    },
    loreGraph: {
      answer: 'No. The decision in force is "Reinstate Friday deploy freeze after INC-7 outage" (2026-08-31) [S1], which superseded the May canary policy [S2]. Implemented by SRE-71 [S3].',
      sources: [
        { sid: 'S1', text: 'Meeting: Postmortem INC-7 Checkout Outage (Decided 2026-08-31 by Alex Chen)', date: '2026-08-31' },
        { sid: 'S2', text: 'Decision: RFC-42 Canary Deployments (Superseded by S1)', date: '2026-05-12' },
        { sid: 'S3', text: 'Ticket: SRE-71 Lock CI/CD pipeline on Fridays after 14:00 UTC', date: '2026-09-02' },
      ],
      advantage: 'Decision nodes with SUPERSEDES chain: traverses backwards from INC-7 to RFC-42, reporting exact lineage and current status.',
      verdict: 'FULL DECISION LINEAGE',
    },
  },
  {
    id: 'busfactor',
    title: '3. Departure & Bus Factor Risk',
    question: 'Who actually understands auth-gateway internals?',
    vectorRag: {
      answer: 'Alex Chen is the primary author and subject matter expert for auth-gateway.',
      source: 'Docs: Auth-Gateway Architecture & 18 closed PRs',
      flaw: 'Alex left the company in July! Vector RAG has no concept of employment lifecycle or expertise decay.',
      verdict: 'DEAD-END ASSIGNMENT',
    },
    loreGraph: {
      answer: 'High knowledge risk (Bus Factor = 1)! Top historical expert Alex Chen left the company on 2026-07-31 [S1]. Only active contributor is junior engineer Kevin Wu with 1 touched ticket [S2].',
      sources: [
        { sid: 'S1', text: 'Person: Alex Chen (status: left_at: 2026-07-31, former score: 0.94)', date: '2026-07-31' },
        { sid: 'S2', text: 'Ticket: AUTH-49 minor dependency bump touched by Kevin Wu (score: 0.18)', date: '2026-09-10' },
      ],
      advantage: 'FalkorDB time-decayed EXPERT_IN algorithm (e^-age/120d) combined with Person.active flag detects critical knowledge silos.',
      verdict: 'PROACTIVE BUS FACTOR WARNING',
    },
  },
]

// -------------------------------------------------------------
// Interactive 6-Stage Pipeline
// -------------------------------------------------------------
const PIPELINE_STEPS = [
  {
    step: '01',
    title: 'Multi-Modal Ingestion',
    category: 'Ingest & Connectors',
    desc: 'Connectors for wiki docs, Jira/tracker tickets & comments, Slack threads, meeting notes, and real public GitHub repos (issues, PRs, comments, CODEOWNERS).',
    cypher: `// Normalizes everything into typed :Source nodes
UNWIND $rows AS r
MERGE (s:Source:Message {id: r.id})
SET s.text = r.text, s.ts = r.ts, s.t = r.t,
    s.url = r.url, s.title = r.title, s.author_id = r.author`,
    detail: 'Every piece of evidence is simultaneously typed (e.g. :Message, :Ticket, :Meeting, :Chunk) AND labelled :Source with unified timestamping.',
  },
  {
    step: '02',
    title: 'Structural Knowledge Graph',
    category: 'FalkorDB Graph Model',
    desc: 'Deterministic and LLM extractors map entities into rich FalkorDB graphs with typed relationships: AUTHORED, TOUCHES, MENTIONS, MEMBER_OF, OWNS.',
    cypher: `// Relational graph building in FalkorDB
OPTIONAL MATCH (a:Person {id: r.author})
FOREACH (_ IN CASE WHEN a IS NULL THEN [] ELSE [1] END |
  MERGE (a)-[:AUTHORED]->(s)
)
MERGE (s)-[:TOUCHES]->(sys:System {id: r.system_id})`,
    detail: 'Explicit ownership statements, @mentions, and ticket assignments form the structural backbone before any semantic search occurs.',
  },
  {
    step: '03',
    title: 'Local Vector & Full-Text Search',
    category: 'Hybrid Dual-Index',
    desc: 'BGE-small 384-dimensional embeddings generated locally with native FalkorDB cosine vector indexing and fulltext indexing over all :Source nodes.',
    cypher: `// FalkorDB Native Indexes
CREATE VECTOR INDEX FOR (s:Source) ON (s.embedding)
  OPTIONS {dimension: 384, similarityFunction: 'cosine'}
CREATE FULLTEXT INDEX FOR (s:Source) ON (s.text)
CREATE VECTOR INDEX FOR (d:Decision) ON (d.embedding)`,
    detail: 'Hybrid search combines vector semantic similarity with BM25 full-text keyword matching using reciprocal rank fusion.',
  },
  {
    step: '04',
    title: 'Bi-Temporal Claim Reconciliation',
    category: 'Time-Aware Graph Logic',
    desc: 'Claims carry valid_from, valid_to, and recorded_at. When a new statement arrives, Lore reconciles it against the current claim.',
    cypher: `// Closing old claim & linking SUPERSEDES edge
MATCH (new:Claim {id: $new}), (old:Claim {id: $old})
SET old.status = 'superseded',
    old.valid_to = $ts, old.valid_to_t = $t
CREATE (new)-[:SUPERSEDES]->(old)
WITH old MATCH ()-[o:OWNS {claim_id: $old}]->()
SET o.until = $ts, o.until_t = $t`,
    detail: 'Same value corroborates the claim; new value archives the old fact and creates a navigable SUPERSEDES edge for time travel.',
  },
  {
    step: '05',
    title: 'Evidence Linking & Stale Docs',
    category: 'Provenance & Freshness',
    desc: 'Decisions are linked to pre-decision BASED_ON evidence and post-decision IMPLEMENTED_BY tickets. Docs supporting superseded claims are flagged.',
    cypher: `// Identifying stale docs with invalidated claims
MATCH (doc:Document)-[:HAS_CHUNK]->(ch:Chunk)<-[:SUPPORTED_BY]-(old:Claim {status:'superseded'})
MATCH (cur:Claim {status:'current'})
WHERE cur.subject_key = old.subject_key
  AND NOT (cur)-[:SUPPORTED_BY]->(:Chunk)<-[:HAS_CHUNK]-(doc)
  AND cur.valid_from_t > doc.updated_t
RETURN doc.id, old.value_name AS was, cur.value_name AS now`,
    detail: 'Flags the exact out-of-date sentence, the date it became invalid, and the new source that contradicted it.',
  },
  {
    step: '06',
    title: 'Graph Analytics & Citation Verifier',
    category: 'Agent Execution & MCP',
    desc: 'FalkorDB PageRank & Betweenness Centrality determine real experts. Agent chains tools, and Citation Verifier strips any hallucinated citations.',
    cypher: `// FalkorDB Algorithmic Derivations
CALL algo.pageRank('Person', 'COLLABORATES_WITH')
  YIELD node, score SET node.influence = score
CALL algo.betweenness({
  nodeLabels: ['Person'], relationshipTypes: ['COLLABORATES_WITH']
}) YIELD node, score SET node.broker = score`,
    detail: 'Answers pass through verify_citations: any [S#] marker not present in retrieved context is purged before the user or IDE sees it.',
  },
]

// -------------------------------------------------------------
// Interactive Time-Travel Simulator Data
// -------------------------------------------------------------
const TIME_STOPS = [
  {
    date: '2026-01-15',
    label: 'January 2026',
    paymentsOwner: 'Priya Sharma (Core Checkout)',
    fridayDeploy: 'Restricted (Pre-RFC)',
    staleDocCount: 0,
    activeClaim: 'Claim #101: Priya OWNS payments-service',
    notes: 'Initial company baseline. All wiki docs fresh.',
    cypher: `MATCH (o)-[r:OWNS]->(s:System {id:'payments-service'})
WHERE r.since_t <= 1768435200 AND coalesce(r.until_t, 9999999999) > 1768435200
RETURN o.name // => Priya Sharma`,
  },
  {
    date: '2026-05-12',
    label: 'May 2026',
    paymentsOwner: 'Priya Sharma (Core Checkout)',
    fridayDeploy: 'Allowed with Canaries (RFC-42)',
    staleDocCount: 0,
    activeClaim: 'Claim #101: Priya OWNS payments-service',
    notes: 'RFC-42 approved: Canary deploys permitted on Fridays with SRE buddy.',
    cypher: `MATCH (d:Decision {id:'rfc-42'})
WHERE d.decided_t <= 1778544000
RETURN d.title, d.status // => 'RFC-42 Canary Deployments', active`,
  },
  {
    date: '2026-06-20',
    label: 'June 2026',
    paymentsOwner: 'Marco Ross (Platform Team)',
    fridayDeploy: 'Allowed with Canaries (RFC-42)',
    staleDocCount: 1,
    activeClaim: 'Claim #409: Platform Team OWNS payments-service',
    notes: 'Reorg announcement! Claim #409 supersedes Claim #101. Wiki team-directory is now STALE!',
    cypher: `MATCH (new:Claim {id:'claim-409'})-[:SUPERSEDES]->(old:Claim {id:'claim-101'})
RETURN new.valid_from, old.valid_to // => 2026-06-15, 2026-06-15`,
  },
  {
    date: '2026-08-31',
    label: 'August 2026',
    paymentsOwner: 'Marco Ross (Platform Team)',
    fridayDeploy: 'Freeze Reinstated (INC-7 Outage)',
    staleDocCount: 2,
    activeClaim: 'Claim #409: Platform Team OWNS payments-service',
    notes: 'Major checkout incident INC-7. Friday deploy freeze reinstated. RFC-42 superseded.',
    cypher: `MATCH (d:Decision {id:'dec-inc7'})-[:SUPERSEDES]->(rfc:Decision {id:'rfc-42'})
RETURN d.title, rfc.status // => 'Reinstate freeze', superseded`,
  },
  {
    date: '2026-10-13',
    label: 'Today (Present)',
    paymentsOwner: 'Marco Ross (Platform Team)',
    fridayDeploy: 'Freeze Reinstated (INC-7 Outage)',
    staleDocCount: 3,
    activeClaim: 'Claim #409: Platform Team OWNS payments-service',
    notes: 'Alex Chen departed; auth-gateway flagged for critical bus-factor risk.',
    cypher: `MATCH (p:Person {id:'alex-chen'}) WHERE p.active = false
OPTIONAL MATCH (p)-[e:EXPERT_IN]->(s:System)
RETURN s.id, e.score // => 'auth-gateway', Bus factor: 1`,
  },
]

// -------------------------------------------------------------
// Interactive Query Simulator
// -------------------------------------------------------------
const PRESET_QUERIES = [
  {
    q: 'Who owns payments-service today, and who used to own it?',
    tool: 'who_owns(system="payments-service")',
    cypherTrace: 'MATCH (c:Claim {subject:"payments-service"})-[:SUPERSEDES*0..2]->(hist) RETURN c, hist',
    citations: ['[S1] Chat #announcements (2026-06-15)', '[S2] Doc /wiki/team-directory.md (2026-01-10) [STALE]'],
    answer: `The payments-service is currently owned by the **Platform Team** led by **Marco Ross** (effective 2026-06-15) [S1].

It was previously owned by **Priya Sharma** and the Core Checkout team from January 2026 until June 2026 [S2]. Note that the wiki page \`/wiki/team-directory.md\` still lists Priya and has been flagged out of date.`,
    graphNodes: ['Platform Team (Team)', 'payments-service (System)', 'Marco Ross (Person)', 'Priya Sharma (Person)', 'Claim #409 (Claim)', 'Claim #101 (Claim)'],
  },
  {
    q: 'Can we deploy to production on Friday afternoon?',
    tool: 'trace_decision(query="deploy on friday")',
    cypherTrace: 'MATCH (d:Decision {id:"dec-inc7"})-[:SUPERSEDES]->(earlier) RETURN d, earlier',
    citations: ['[S4] INC-7 Postmortem (2026-08-31)', '[S5] RFC-42 Canaries (2026-05-12)', '[S8] Ticket SRE-71 (2026-09-02)'],
    answer: `**No, you cannot deploy on Friday afternoon.**

The decision in force is **"Reinstate Friday deploy freeze after INC-7 outage"** (decided 2026-08-31) [S4]. This decision superseded the May 2026 canary rollout policy [S5]. The freeze is enforced via CI/CD branch protection in ticket **SRE-71** [S8].`,
    graphNodes: ['Friday Freeze (Decision)', 'RFC-42 (Decision)', 'INC-7 Postmortem (Meeting)', 'SRE-71 (Ticket)'],
  },
  {
    q: 'Who knows auth-gateway, and what is our bus factor risk?',
    tool: 'bus_factor(system="auth-gateway")',
    cypherTrace: 'MATCH (p:Person)-[e:EXPERT_IN]->(s:System {id:"auth-gateway"}) RETURN p.name, p.active, e.score',
    citations: ['[S3] Person Directory (alex-chen: left 2026-07-31)', '[S7] Ticket AUTH-49'],
    answer: `⚠️ **CRITICAL BUS FACTOR RISK (Score: 1)** for \`auth-gateway\`.

The primary author and top domain expert **Alex Chen** (former score 0.94) left the company on 2026-07-31 [S3].
The only active engineer with any commits is **Kevin Wu** (score 0.18, 1 touched ticket) [S7].
*Recommendation: Initiate urgent knowledge transfer and architecture review.*`,
    graphNodes: ['auth-gateway (System)', 'Alex Chen (Person: Inactive)', 'Kevin Wu (Person)', 'AUTH-49 (Ticket)'],
  },
  {
    q: 'What decisions were superseded after the INC-7 incident?',
    tool: 'whats_changed(from="2026-08-01", to="2026-09-01")',
    cypherTrace: 'MATCH (d:Decision)-[:SUPERSEDES]->(old) WHERE d.decided_t >= $t0 RETURN d, old',
    citations: ['[S1] INC-7 Incident Postmortem', '[S2] RFC-42 Policy'],
    answer: `Following incident **INC-7** on August 31, 2026:
1. **Friday Deploy Policy**: RFC-42 (Canary deploys) was fully superseded by "Reinstate Friday deploy freeze" [S1][S2].
2. **Database Connection Pool**: PostgreSQL idle timeout was reduced from 60s to 15s in response to connection exhaustion.`,
    graphNodes: ['INC-7 (Meeting)', 'RFC-42 (Decision)', 'Freeze (Decision)', 'PostgreSQL (System)'],
  },
]

// -------------------------------------------------------------
// Interactive Entity Schema Data Model
// -------------------------------------------------------------
const GRAPH_SCHEMA = [
  {
    label: 'Person',
    color: '#2563eb',
    badge: 'Entity',
    desc: 'Company employees and contributors with PageRank influence and Betweenness broker scores.',
    properties: ['id', 'name', 'role', 'active', 'left_at', 'influence (PageRank)', 'broker (Betweenness)', 'community'],
    edges: ['MEMBER_OF (Team)', 'AUTHORED (Source)', 'EXPERT_IN (System)', 'COLLABORATES_WITH (Person)'],
  },
  {
    label: 'Claim',
    color: '#10b981',
    badge: 'Temporal Fact',
    desc: 'Bi-temporal fact nodes capturing ownership and assertions with valid-time and transaction-time.',
    properties: ['id', 'subject', 'predicate', 'value', 'valid_from', 'valid_to', 'recorded_at', 'status'],
    edges: ['ABOUT (System)', 'SUPPORTED_BY (Source)', 'SUPERSEDES (Claim)'],
  },
  {
    label: 'Decision',
    color: '#db2777',
    badge: 'Lineage Node',
    desc: 'Architectural and operational decisions linked to proposal meetings, evidence, and tickets.',
    properties: ['id', 'title', 'decided_at', 'status (active/amended/superseded)', 'affects', 'embedding'],
    edges: ['DECIDED_IN (Source)', 'PROPOSED_BY (Person)', 'BASED_ON (Source)', 'IMPLEMENTED_BY (Ticket)', 'SUPERSEDES (Decision)'],
  },
  {
    label: 'System',
    color: '#0891b2',
    badge: 'Asset',
    desc: 'Microservices, platforms, and codebases with bus-factor monitoring and expertise metrics.',
    properties: ['id', 'name', 'aliases', 'keywords'],
    edges: ['OWNS (from Team {since, until})', 'TOUCHES (from Ticket)', 'AFFECTS (from Decision)'],
  },
  {
    label: 'Document',
    color: '#475569',
    badge: 'Content',
    desc: 'Wiki pages and architectural docs tracked for obsolescence and contradicted claims.',
    properties: ['id', 'title', 'url', 'updated_at', 'stale (boolean)', 'stale_reasons'],
    edges: ['HAS_CHUNK (Chunk)'],
  },
  {
    label: ':Source',
    color: '#f59e0b',
    badge: 'Evidence',
    desc: 'Unified evidence node (Chunk, Message, Ticket, Comment, Meeting) indexed with 384-dim vector embeddings.',
    properties: ['id', 'kind', 'text', 'ts', 't', 'url', 'author_id', 'embedding (vector index)'],
    edges: ['AUTHORED (by Person)', 'MENTIONS (Entity)', 'SUPPORTED_BY (for Claim)'],
  },
]

// -------------------------------------------------------------
// Interactive Screenshot Showcase
// -------------------------------------------------------------
const SCREENSHOT_TABS = [
  {
    id: 'ask',
    title: 'Ask Lore',
    tag: 'Verified Citations',
    src: '/screenshots/ask.png',
    desc: 'Interactive tool-use agent answering questions with verified [S#] citations, provenance inspection, and real-time subgraph visualization.',
    highlights: ['Grounded in FalkorDB subgraph', 'Hallucinated citations automatically stripped', 'Offline deterministic fallback mode'],
  },
  {
    id: 'decisions',
    title: 'Decisions Lineage',
    tag: 'Temporal Tree',
    src: '/screenshots/decisions.png',
    desc: 'Visual trace of all enterprise decisions showing who proposed it, what incident caused it, and the full SUPERSEDES evolution.',
    highlights: ['Historical supersedes chains', 'Based-on incident evidence links', 'Direct links to implementing Jira/GitHub tickets'],
  },
  {
    id: 'people',
    title: 'Who Knows & Bus Factor',
    tag: 'Graph Analytics',
    src: '/screenshots/people.png',
    desc: 'Computed expertise matrix with time-decay scoring, PageRank influence, and proactive bus-factor alerts when key engineers leave.',
    highlights: ['FalkorDB PageRank & Betweenness scores', 'Time-decayed expertise (e^-age/120d)', 'Departed expert risk detection'],
  },
  {
    id: 'freshness',
    title: 'Freshness & Stale Docs',
    tag: 'Contradiction Engine',
    src: '/screenshots/freshness.png',
    desc: 'Automated identification of out-of-date documentation caused by superseded ownership claims and updated policies.',
    highlights: ['Identifies the exact invalid sentence', 'Lists the newer conflicting source', 'Automated ticket creation to fix doc'],
  },
  {
    id: 'graph',
    title: 'Force Graph Explorer',
    tag: 'Interactive Cypher',
    src: '/screenshots/graph.png',
    desc: 'Full force-directed graph view of the company with multi-tenant graph switching and interactive time-slider inspection.',
    highlights: ['Multi-tenant (lore_northwind, lore_falkordb)', 'Filter by date as-of slider', 'Live node neighborhood inspector'],
  },
]

export default function LandingView({ onEnterApp, currentTenant, stats }: LandingProps) {
  const [activeScenario, setActiveScenario] = useState(SCENARIOS[0].id)
  const [activeStep, setActiveStep] = useState(0)
  const [timeIndex, setTimeIndex] = useState(4) // Default to "Today"
  const [activeQueryIndex, setActiveQueryIndex] = useState(0)
  const [activeSchemaNode, setActiveSchemaNode] = useState(GRAPH_SCHEMA[0].label)
  const [activeScreenshotTab, setActiveScreenshotTab] = useState('ask')
  const [copiedQuery, setCopiedQuery] = useState(false)

  const currentTimeStop = TIME_STOPS[timeIndex]
  const currentQuery = PRESET_QUERIES[activeQueryIndex]
  const currentSchema = GRAPH_SCHEMA.find(s => s.label === activeSchemaNode) || GRAPH_SCHEMA[0]
  const currentScreenshot = SCREENSHOT_TABS.find(t => t.id === activeScreenshotTab) || SCREENSHOT_TABS[0]

  const totalNodes = stats ? Object.values(stats.nodes).reduce((a, b) => a + b, 0) : 312
  const totalEdges = stats ? Object.values(stats.relationships).reduce((a, b) => a + b, 0) : 748

  const handleCopyCypher = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedQuery(true)
    setTimeout(() => setCopiedQuery(false), 2000)
  }

  return (
    <div className="min-h-screen bg-[#fafbfc] text-[#0f172a] font-sans selection:bg-blue-500/20 selection:text-blue-900">
      {/* ------------------------------------------------------------- */}
      {/* Top Floating Navigation Bar */}
      {/* ------------------------------------------------------------- */}
      <nav className="sticky top-0 z-50 border-b border-line/80 bg-white/90 backdrop-blur-md px-6 py-3.5 transition-all">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white shadow-sm shadow-blue-500/30">
              <img src="/favicon.svg" alt="Lore Logo" className="h-6 w-6 brightness-200" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold tracking-tight text-heading">Lore AI</span>
                <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-700 border border-blue-200">
                  Company Brain
                </span>
              </div>
              <span className="text-[11px] text-muted font-medium">WeMakeDevs × FalkorDB Graph Hacks</span>
            </div>
          </div>

          <div className="hidden lg:flex items-center gap-7 text-[14px] font-medium text-slate-600">
            <a href="#problem" className="hover:text-blue-600 transition">Why Graph?</a>
            <a href="#architecture" className="hover:text-blue-600 transition">Architecture</a>
            <a href="#timetravel" className="hover:text-blue-600 transition">Time Travel</a>
            <a href="#datamodel" className="hover:text-blue-600 transition">Graph Model</a>
            <a href="#algorithms" className="hover:text-blue-600 transition">Algorithms</a>
            <a href="#benchmark" className="hover:text-blue-600 transition">Benchmark</a>
            <a href="#playground" className="hover:text-blue-600 transition">Query Sandbox</a>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => onEnterApp('dashboard')}
              className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-blue-500/25 hover:bg-blue-700 hover:shadow-lg transition active:scale-[0.98]"
            >
              <Sparkles size={16} />
              <span>Launch Workspace</span>
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </nav>

      {/* ------------------------------------------------------------- */}
      {/* Hero Section */}
      {/* ------------------------------------------------------------- */}
      <section className="relative overflow-hidden pt-14 pb-20 landing-grid border-b border-line">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            {/* Left Column: Headline & Value Prop */}
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50/80 px-3.5 py-1.5 text-xs font-semibold text-blue-800 shadow-sm">
                <span className="flex h-2 w-2 rounded-full bg-blue-600 animate-ping" />
                <span>Track 03: Company Brain · Powered by FalkorDB</span>
                <span className="text-blue-400">|</span>
                <span className="text-blue-700 font-mono">100% Citation Veracity</span>
              </div>

              <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-slate-900 leading-[1.12]">
                The company brain that <span className="text-gradient">cites its sources</span> — and knows what changed.
              </h1>

              <p className="text-lg sm:text-xl text-slate-600 leading-relaxed font-normal max-w-2xl">
                Lore unifies docs, tickets, chat, and GitHub repos into an active, bi-temporal
                <strong> FalkorDB</strong> knowledge graph. When a team reorg happens, a policy is superseded,
                or a key expert leaves, Lore tracks the lineage, flags stale docs, and proves every claim with verified citations.
              </p>

              <div className="flex flex-wrap items-center gap-4 pt-2">
                <button
                  onClick={() => onEnterApp('dashboard')}
                  className="flex items-center gap-2.5 rounded-xl bg-blue-600 px-6 py-3.5 text-base font-semibold text-white shadow-lg shadow-blue-500/25 hover:bg-blue-700 hover:shadow-xl transition active:scale-[0.98]"
                >
                  <Sparkles size={18} />
                  <span>Explore Live Workspace</span>
                  <ArrowRight size={17} />
                </button>

                <button
                  onClick={() => onEnterApp('ask')}
                  className="flex items-center gap-2 rounded-xl border border-line-2 bg-white px-5 py-3.5 text-base font-medium text-slate-700 hover:border-blue-400 hover:bg-blue-50/40 transition"
                >
                  <Bot size={18} className="text-blue-600" />
                  <span>Try "Ask Lore" Agent</span>
                </button>

                <a
                  href="#architecture"
                  className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-slate-500 hover:text-blue-600 transition"
                >
                  <span>View Architecture</span>
                  <ChevronRight size={16} />
                </a>
              </div>

              {/* Verified Metrics Strip */}
              <div className="pt-6 grid grid-cols-2 sm:grid-cols-4 gap-4 border-t border-slate-200/80">
                <div className="rounded-xl border border-line bg-white/70 p-3 shadow-xs">
                  <div className="text-2xl font-black text-blue-600 font-mono">100%</div>
                  <div className="text-xs font-medium text-slate-500">Fact Accuracy</div>
                  <div className="text-[10px] text-emerald-600 font-medium">vs 64% Vector RAG</div>
                </div>
                <div className="rounded-xl border border-line bg-white/70 p-3 shadow-xs">
                  <div className="text-2xl font-black text-indigo-600 font-mono">100%</div>
                  <div className="text-xs font-medium text-slate-500">Temporal Freshness</div>
                  <div className="text-[10px] text-emerald-600 font-medium">vs 43% Vector RAG</div>
                </div>
                <div className="rounded-xl border border-line bg-white/70 p-3 shadow-xs">
                  <div className="text-2xl font-black text-emerald-600 font-mono">0</div>
                  <div className="text-xs font-medium text-slate-500">Hallucinated Citations</div>
                  <div className="text-[10px] text-slate-400">Checked via Verifier</div>
                </div>
                <div className="rounded-xl border border-line bg-white/70 p-3 shadow-xs">
                  <div className="text-2xl font-black text-slate-800 font-mono">&lt;15ms</div>
                  <div className="text-xs font-medium text-slate-500">FalkorDB Cypher</div>
                  <div className="text-[10px] text-slate-400">Graph Multi-Hop</div>
                </div>
              </div>
            </div>

            {/* Right Column: Interactive Knowledge Graph Simulation */}
            <div className="lg:col-span-5">
              <HeroGraphCanvas />
              <div className="mt-3 flex items-center justify-between px-2 text-xs text-slate-500">
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-blue-600" /> Person</span>
                  <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-cyan-600" /> System</span>
                  <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-pink-600" /> Decision</span>
                  <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> Claim</span>
                </div>
                <button onClick={() => onEnterApp('explore')} className="text-blue-600 hover:underline font-medium flex items-center gap-1">
                  Full 2D Graph <ArrowUpRight size={12} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* The Core Problem: Why Your Wiki Is Lying To You */}
      {/* ------------------------------------------------------------- */}
      <section id="problem" className="py-20 bg-white border-b border-line">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
            <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-amber-700 border border-amber-200">
              The Real-World Dilemma
            </span>
            <h2 className="font-display text-3xl sm:text-4xl font-bold text-heading tracking-tight">
              Your wiki is lying to you. And so is your RAG bot.
            </h2>
            <p className="text-slate-600 text-base sm:text-lg">
              Standard vector retrieval embeds chunks of text and assumes higher cosine similarity equals truth.
              When organizations change, vector stores happily return outdated documents with confident hallucinations.
            </p>
          </div>

          {/* Interactive Scenario Selector */}
          <div className="flex flex-wrap justify-center gap-3 mb-10">
            {SCENARIOS.map(s => (
              <button
                key={s.id}
                onClick={() => setActiveScenario(s.id)}
                className={`rounded-xl px-5 py-3 text-sm font-semibold transition border ${
                  activeScenario === s.id
                    ? 'bg-blue-600 text-white border-blue-600 shadow-md shadow-blue-500/20'
                    : 'bg-slate-50 text-slate-700 border-line hover:bg-slate-100'
                }`}
              >
                {s.title}
              </button>
            ))}
          </div>

          {/* Side-by-Side Comparison Container */}
          {(() => {
            const sc = SCENARIOS.find(s => s.id === activeScenario) || SCENARIOS[0]
            return (
              <div className="rounded-2xl border border-line bg-panel-2 p-6 sm:p-8 shadow-sm">
                <div className="mb-6 flex items-center gap-3 bg-white p-4 rounded-xl border border-line">
                  <HelpCircle size={20} className="text-blue-600 shrink-0" />
                  <div className="text-sm sm:text-base font-semibold text-slate-900">
                    User Question: <span className="text-blue-700">"{sc.question}"</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  {/* Plain Vector RAG Box */}
                  <div className="rounded-2xl border border-rose-200 bg-rose-50/40 p-6 flex flex-col justify-between">
                    <div>
                      <div className="flex items-center justify-between pb-4 border-b border-rose-200/80 mb-4">
                        <div className="flex items-center gap-2">
                          <AlertTriangle size={18} className="text-rose-600" />
                          <span className="font-bold text-slate-900 text-sm uppercase tracking-wider">Vector-Only RAG</span>
                        </div>
                        <span className="rounded-full bg-rose-100 px-2.5 py-0.5 text-xs font-bold text-rose-700 border border-rose-200">
                          {sc.vectorRag.verdict}
                        </span>
                      </div>

                      <div className="space-y-4">
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Model Output</div>
                          <div className="mt-1 text-sm font-medium text-slate-800 bg-white p-3.5 rounded-xl border border-rose-100">
                            "{sc.vectorRag.answer}"
                          </div>
                        </div>

                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Retrieved Context</div>
                          <div className="mt-1 font-mono text-xs text-rose-900 bg-white/70 p-2.5 rounded-lg border border-rose-100">
                            {sc.vectorRag.source}
                          </div>
                        </div>

                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Why It Failed</div>
                          <p className="mt-1 text-xs text-rose-800 leading-relaxed">
                            {sc.vectorRag.flaw}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="mt-6 pt-4 border-t border-rose-200/60 text-xs font-semibold text-rose-700 flex items-center gap-1.5">
                      <span>Result: Misrouted incident escalation & broken policies</span>
                    </div>
                  </div>

                  {/* Lore FalkorDB Graph Box */}
                  <div className="rounded-2xl border border-emerald-300 bg-emerald-50/40 p-6 flex flex-col justify-between shadow-sm">
                    <div>
                      <div className="flex items-center justify-between pb-4 border-b border-emerald-200 mb-4">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 size={18} className="text-emerald-600" />
                          <span className="font-bold text-slate-900 text-sm uppercase tracking-wider">Lore (FalkorDB Graph)</span>
                        </div>
                        <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-800 border border-emerald-200">
                          {sc.loreGraph.verdict}
                        </span>
                      </div>

                      <div className="space-y-4">
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Verified Answer</div>
                          <div className="mt-1 text-sm font-medium text-slate-900 bg-white p-3.5 rounded-xl border border-emerald-100 shadow-xs">
                            {sc.loreGraph.answer}
                          </div>
                        </div>

                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Cited Sources (Zero Hallucination)</div>
                          <div className="mt-1 space-y-1.5">
                            {sc.loreGraph.sources.map(src => (
                              <div key={src.sid} className="flex items-start gap-2 bg-white/90 p-2 rounded-lg border border-emerald-100 text-xs">
                                <span className="font-mono font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">{src.sid}</span>
                                <span className="text-slate-700 flex-1">{src.text}</span>
                                <span className="text-slate-400 font-mono text-[10px] shrink-0">{src.date}</span>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">Graph Solution</div>
                          <p className="mt-1 text-xs text-emerald-900 font-medium leading-relaxed">
                            {sc.loreGraph.advantage}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="mt-6 pt-4 border-t border-emerald-200 text-xs font-semibold text-emerald-800 flex items-center justify-between">
                      <span>Confidence: Graph Traversal Verified</span>
                      <button onClick={() => onEnterApp('ask')} className="text-blue-600 hover:underline flex items-center gap-1 font-bold">
                        Ask in Live App <ArrowRight size={12} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )
          })()}
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* 6-Stage End-to-End Pipeline Architecture */}
      {/* ------------------------------------------------------------- */}
      <section id="architecture" className="py-20 bg-slate-50 border-b border-line">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
            <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-blue-700 border border-blue-200">
              System Architecture
            </span>
            <h2 className="font-display text-3xl sm:text-4xl font-bold text-heading tracking-tight">
              From raw documents to verified graph intelligence
            </h2>
            <p className="text-slate-600 text-base sm:text-lg">
              Click through each phase of Lore's ingestion and retrieval pipeline to inspect
              the exact FalkorDB Cypher queries and graph algorithms.
            </p>
          </div>

          {/* Interactive Pipeline Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
            {PIPELINE_STEPS.map((s, idx) => {
              const active = idx === activeStep
              return (
                <button
                  key={s.step}
                  onClick={() => setActiveStep(idx)}
                  className={`group relative text-left rounded-xl p-4 transition border ${
                    active
                      ? 'bg-white border-blue-600 shadow-md ring-2 ring-blue-500/20'
                      : 'bg-white/70 border-line hover:border-slate-300 hover:bg-white'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className={`font-mono text-xs font-bold ${active ? 'text-blue-600' : 'text-slate-400'}`}>
                      {s.step}
                    </span>
                    <span className="h-2 w-2 rounded-full bg-slate-200 group-hover:bg-blue-400" />
                  </div>
                  <div className={`text-xs font-bold line-clamp-1 ${active ? 'text-blue-900' : 'text-slate-800'}`}>
                    {s.title}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1 line-clamp-1 font-mono">
                    {s.category}
                  </div>
                </button>
              )
            })}
          </div>

          {/* Active Step Deep-Dive Drawer */}
          {(() => {
            const step = PIPELINE_STEPS[activeStep]
            return (
              <div className="rounded-2xl border border-line bg-white p-6 sm:p-8 shadow-sm">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
                  <div className="lg:col-span-5 space-y-4">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                        STAGE {step.step}
                      </span>
                      <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{step.category}</span>
                    </div>

                    <h3 className="text-2xl font-bold text-slate-900">{step.title}</h3>
                    <p className="text-slate-600 text-sm leading-relaxed">{step.desc}</p>

                    <div className="p-4 rounded-xl bg-blue-50/50 border border-blue-100 text-xs text-blue-900 leading-relaxed">
                      <strong>How it works: </strong>
                      {step.detail}
                    </div>

                    <div className="pt-2 flex items-center gap-3">
                      <button
                        onClick={() => onEnterApp('explore')}
                        className="text-xs font-semibold text-blue-600 hover:underline flex items-center gap-1"
                      >
                        Inspect in Graph Explorer <ArrowRight size={13} />
                      </button>
                    </div>
                  </div>

                  {/* Cypher Query Inspector */}
                  <div className="lg:col-span-7">
                    <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 shadow-inner text-slate-200">
                      <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3 text-xs">
                        <div className="flex items-center gap-2 text-slate-400 font-mono">
                          <Terminal size={14} className="text-blue-400" />
                          <span>FalkorDB Cypher Implementation</span>
                        </div>
                        <button
                          onClick={() => handleCopyCypher(step.cypher)}
                          className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-white transition"
                        >
                          {copiedQuery ? <CheckCheck size={13} className="text-emerald-400" /> : <Copy size={13} />}
                          <span>{copiedQuery ? 'Copied' : 'Copy'}</span>
                        </button>
                      </div>

                      <pre className="font-mono text-xs overflow-x-auto text-emerald-400 leading-relaxed py-1">
                        <code>{step.cypher}</code>
                      </pre>
                    </div>
                  </div>
                </div>
              </div>
            )
          })()}
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* Interactive Bi-Temporal Time Travel Simulator */}
      {/* ------------------------------------------------------------- */}
      <section id="timetravel" className="py-20 bg-white border-b border-line">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
            <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-indigo-700 border border-indigo-200">
              Bi-Temporal Knowledge
            </span>
            <h2 className="font-display text-3xl sm:text-4xl font-bold text-heading tracking-tight">
              Time Travel: What was true on any past date?
            </h2>
            <p className="text-slate-600 text-base sm:text-lg">
              All ownership edges carry <code className="text-blue-700 font-mono">since_t</code> and <code className="text-blue-700 font-mono">until_t</code> timestamps.
              Drag the timeline below to watch the company graph mutate in real time.
            </p>
          </div>

          <div className="rounded-2xl border border-line bg-panel-2 p-6 sm:p-8 shadow-sm">
            {/* Timeline Slider Control */}
            <div className="mb-8">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <Clock size={18} className="text-blue-600" />
                  <span>Viewing company graph as of:</span>
                  <span className="rounded-md bg-blue-100 px-2.5 py-0.5 font-mono text-blue-800 font-bold">
                    {currentTimeStop.date} ({currentTimeStop.label})
                  </span>
                </div>
                <span className="text-xs text-slate-500 font-mono">Drag slider to travel</span>
              </div>

              <input
                type="range"
                min={0}
                max={TIME_STOPS.length - 1}
                value={timeIndex}
                onChange={e => setTimeIndex(Number(e.target.value))}
                className="w-full accent-blue-600 cursor-pointer h-2 bg-slate-200 rounded-lg"
              />

              <div className="flex justify-between text-xs text-slate-500 font-mono mt-2">
                {TIME_STOPS.map((t, idx) => (
                  <button
                    key={t.date}
                    onClick={() => setTimeIndex(idx)}
                    className={`hover:text-blue-600 transition ${idx === timeIndex ? 'font-bold text-blue-600' : ''}`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Dynamic State Preview at Current Timestamp */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div className="rounded-xl border border-line bg-white p-5 shadow-xs">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                  Active Owner: payments-service
                </div>
                <div className="text-base font-bold text-slate-900">{currentTimeStop.paymentsOwner}</div>
                <div className="mt-2 text-xs font-mono text-emerald-700 bg-emerald-50 p-2 rounded border border-emerald-100">
                  {currentTimeStop.activeClaim}
                </div>
              </div>

              <div className="rounded-xl border border-line bg-white p-5 shadow-xs">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                  Friday Deploy Policy in Force
                </div>
                <div className="text-base font-bold text-slate-900">{currentTimeStop.fridayDeploy}</div>
                <div className="mt-2 text-xs text-slate-600 bg-slate-50 p-2 rounded border border-slate-100">
                  {currentTimeStop.notes}
                </div>
              </div>

              <div className="rounded-xl border border-line bg-white p-5 shadow-xs">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                  Contradicted Stale Documents
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-2xl font-black font-mono ${currentTimeStop.staleDocCount > 0 ? 'text-amber-600' : 'text-slate-400'}`}>
                    {currentTimeStop.staleDocCount}
                  </span>
                  <span className="text-xs text-slate-500">docs invalidated by newer evidence</span>
                </div>
                <button
                  onClick={() => onEnterApp('freshness')}
                  className="mt-3 text-xs text-blue-600 font-semibold hover:underline flex items-center gap-1"
                >
                  View Stale Doc List <ArrowRight size={12} />
                </button>
              </div>
            </div>

            {/* Cypher Query for this timestamp */}
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 text-xs font-mono text-emerald-400">
              <div className="text-slate-400 mb-2 flex items-center justify-between">
                <span>FalkorDB Temporal Range Query for as_of = '{currentTimeStop.date}'</span>
                <span className="text-[10px] text-slate-500">Evaluates [since_t, until_t) intervals</span>
              </div>
              <pre className="overflow-x-auto"><code>{currentTimeStop.cypher}</code></pre>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* Interactive Graph Data Model (Schema Explorer) */}
      {/* ------------------------------------------------------------- */}
      <section id="datamodel" className="py-20 bg-slate-50 border-b border-line">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
            <span className="rounded-full bg-cyan-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-cyan-800 border border-cyan-200">
              Data Model & Ontology
            </span>
            <h2 className="font-display text-3xl sm:text-4xl font-bold text-heading tracking-tight">
              Why facts and decisions are nodes, not strings
            </h2>
            <p className="text-slate-600 text-base sm:text-lg">
              In Lore, provenance (<code className="text-blue-700 font-mono">SUPPORTED_BY</code>, <code className="text-blue-700 font-mono">DECIDED_IN</code>)
              and temporal change (<code className="text-blue-700 font-mono">SUPERSEDES</code>) are traversable graph edges.
              Click a node type to inspect its properties and relationships.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left: Node Selector Tabs */}
            <div className="lg:col-span-4 space-y-2">
              {GRAPH_SCHEMA.map(s => {
                const active = s.label === activeSchemaNode
                return (
                  <button
                    key={s.label}
                    onClick={() => setActiveSchemaNode(s.label)}
                    className={`w-full text-left rounded-xl p-4 transition border flex items-center justify-between ${
                      active
                        ? 'bg-white border-blue-600 shadow-sm ring-1 ring-blue-500/20'
                        : 'bg-white/60 border-line hover:bg-white hover:border-slate-300'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className="h-3 w-3 rounded-full" style={{ backgroundColor: s.color }} />
                      <div>
                        <div className="text-sm font-bold text-slate-900">{s.label}</div>
                        <div className="text-xs text-slate-500">{s.badge}</div>
                      </div>
                    </div>
                    <ChevronRight size={16} className={active ? 'text-blue-600' : 'text-slate-400'} />
                  </button>
                )
              })}
            </div>

            {/* Right: Detailed Schema Card */}
            <div className="lg:col-span-8">
              <div className="rounded-2xl border border-line bg-white p-6 sm:p-8 shadow-sm">
                <div className="flex items-center justify-between pb-4 border-b border-line mb-6">
                  <div className="flex items-center gap-3">
                    <span className="h-4 w-4 rounded-full" style={{ backgroundColor: currentSchema.color }} />
                    <h3 className="text-2xl font-bold text-slate-900">{currentSchema.label}</h3>
                    <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                      {currentSchema.badge}
                    </span>
                  </div>
                  <button onClick={() => onEnterApp('explore')} className="text-xs font-semibold text-blue-600 hover:underline flex items-center gap-1">
                    Explore in Graph <ArrowRight size={12} />
                  </button>
                </div>

                <p className="text-slate-600 text-sm leading-relaxed mb-6">
                  {currentSchema.desc}
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Node Properties */}
                  <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-4">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
                      Key Properties
                    </div>
                    <div className="flex flex-wrap gap-1.5 font-mono text-xs">
                      {currentSchema.properties.map(p => (
                        <span key={p} className="bg-white px-2 py-1 rounded border border-line text-slate-800">
                          {p}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Connected Relationships */}
                  <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-4">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
                      Connected Relationships
                    </div>
                    <div className="space-y-1.5 font-mono text-xs">
                      {currentSchema.edges.map(e => (
                        <div key={e} className="flex items-center gap-2 text-slate-800 bg-white p-1.5 rounded border border-line">
                          <span className="text-blue-600">→</span>
                          <span>{e}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* FalkorDB Graph Algorithms Showcase */}
      {/* ------------------------------------------------------------- */}
      <section id="algorithms" className="py-20 bg-white border-b border-line">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
            <span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-violet-700 border border-violet-200">
              Graph Data Science
            </span>
            <h2 className="font-display text-3xl sm:text-4xl font-bold text-heading tracking-tight">
              "Who knows what" is computed, not declared
            </h2>
            <p className="text-slate-600 text-base sm:text-lg">
              Official org charts say who <em>should</em> know. FalkorDB algorithms reveal who <em>actually</em> knows
              by mining real tickets, discussions, and pull requests.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Algorithm 1: PageRank */}
            <div className="rounded-2xl border border-line bg-panel-2 p-6 flex flex-col justify-between hover:border-blue-400 transition">
              <div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 text-blue-600 mb-4">
                  <Activity size={20} />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">PageRank Influence</h3>
                <p className="text-xs text-slate-600 leading-relaxed mb-4">
                  Finds true technical influencers across the company based on who is consulted on architecture decisions and incidents.
                </p>
              </div>
              <div className="rounded-lg bg-slate-950 p-2.5 font-mono text-[11px] text-emerald-400">
                CALL algo.pageRank('Person', 'COLLABORATES_WITH')
              </div>
            </div>

            {/* Algorithm 2: Betweenness Centrality */}
            <div className="rounded-2xl border border-line bg-panel-2 p-6 flex flex-col justify-between hover:border-purple-400 transition">
              <div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-100 text-purple-600 mb-4">
                  <Network size={20} />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">Betweenness Brokers</h3>
                <p className="text-xs text-slate-600 leading-relaxed mb-4">
                  Detects key bridge individuals connecting siloed departments. If a broker leaves, cross-team alignment collapses.
                </p>
              </div>
              <div className="rounded-lg bg-slate-950 p-2.5 font-mono text-[11px] text-emerald-400">
                CALL algo.betweenness(&#123;nodeLabels:['Person']&#125;)
              </div>
            </div>

            {/* Algorithm 3: Label Propagation */}
            <div className="rounded-2xl border border-line bg-panel-2 p-6 flex flex-col justify-between hover:border-pink-400 transition">
              <div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-pink-100 text-pink-600 mb-4">
                  <Users size={20} />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">Label Propagation</h3>
                <p className="text-xs text-slate-600 leading-relaxed mb-4">
                  Uncovers organic working groups. For example, payments engineers clustered with SRE rather than their own team after incident INC-7!
                </p>
              </div>
              <div className="rounded-lg bg-slate-950 p-2.5 font-mono text-[11px] text-emerald-400">
                CALL algo.labelPropagation(...)
              </div>
            </div>

            {/* Algorithm 4: Time-Decayed Bus Factor */}
            <div className="rounded-2xl border border-line bg-panel-2 p-6 flex flex-col justify-between hover:border-amber-400 transition">
              <div>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 text-amber-600 mb-4">
                  <ShieldAlert size={20} />
                </div>
                <h3 className="text-lg font-bold text-slate-900 mb-2">Bus-Factor Scoring</h3>
                <p className="text-xs text-slate-600 leading-relaxed mb-4">
                  Exponential decay: &Sigma; weight &times; e<sup>-age/120d</sup>. Automatically alerts when the top expert on a critical service departs.
                </p>
              </div>
              <div className="rounded-lg bg-slate-950 p-2.5 font-mono text-[11px] text-emerald-400">
                score = &Sigma; w &times; exp(-age_days / 120)
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* Golden Benchmark Results (Measured, Not Claimed) */}
      {/* ------------------------------------------------------------- */}
      <section id="benchmark" className="py-20 bg-slate-50 border-b border-line">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-emerald-700 border border-emerald-200">
              Evaluation & Benchmarks
            </span>
            <h2 className="font-display text-3xl sm:text-4xl font-bold text-heading tracking-tight">
              Measured, not claimed: Lore vs Vector-Only RAG
            </h2>
            <p className="text-slate-600 text-base sm:text-lg">
              Evaluated across 22 golden enterprise questions covering ownership, decision chains,
              departures, and temporal changes. (Reproduce via <code className="text-blue-700 font-mono">uv run python -m lore.evaluate</code>).
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
            {/* Left: Benchmark Results Table */}
            <div className="lg:col-span-7">
              <div className="rounded-2xl border border-line bg-white p-6 shadow-sm overflow-hidden">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-line text-xs font-bold text-slate-400 uppercase tracking-wider">
                      <th className="pb-3">Evaluation Metric</th>
                      <th className="pb-3 text-right text-blue-600">Lore (FalkorDB Graph)</th>
                      <th className="pb-3 text-right text-slate-400">Vector-Only RAG</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line text-sm">
                    <tr>
                      <td className="py-4 font-semibold text-slate-900">
                        Answer contains the expected facts
                        <div className="text-xs text-slate-500 font-normal">Accurate identification across complex multi-hop entities</div>
                      </td>
                      <td className="py-4 text-right font-mono font-bold text-blue-600 text-base">22/22 (100%)</td>
                      <td className="py-4 text-right font-mono text-slate-500">14/22 (64%)</td>
                    </tr>
                    <tr>
                      <td className="py-4 font-semibold text-slate-900">
                        Expected source cited / retrieved
                        <div className="text-xs text-slate-500 font-normal">Accurate link to the originating ticket, chat, or RFC</div>
                      </td>
                      <td className="py-4 text-right font-mono font-bold text-blue-600 text-base">16/16 (100%)</td>
                      <td className="py-4 text-right font-mono text-slate-500">12/16 (75%)</td>
                    </tr>
                    <tr>
                      <td className="py-4 font-semibold text-slate-900">
                        Gives the <span className="text-emerald-600">current</span> fact first for temporal changes
                        <div className="text-xs text-slate-500 font-normal">Distinguishing updated claims from obsolete historic docs</div>
                      </td>
                      <td className="py-4 text-right font-mono font-bold text-emerald-600 text-base">7/7 (100%)</td>
                      <td className="py-4 text-right font-mono text-rose-500">3/7 (43%)</td>
                    </tr>
                  </tbody>
                </table>

                <div className="mt-4 pt-4 border-t border-line text-xs text-slate-500">
                  <em>Baseline Caveat:</em> Scored on top-8 retrieved context. Vector RAG matches single-hop lookups, but fails significantly on ownership changes, freshness, and departures.
                </div>
              </div>
            </div>

            {/* Right: Visual Bar Comparison */}
            <div className="lg:col-span-5 space-y-6">
              <div className="rounded-2xl border border-line bg-white p-6 shadow-sm">
                <div className="text-sm font-bold text-slate-900 mb-4">Temporal Freshness Rate</div>
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-xs font-semibold mb-1">
                      <span>Lore FalkorDB Graph</span>
                      <span className="text-blue-600 font-mono font-bold">100%</span>
                    </div>
                    <div className="h-3 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div className="h-full rounded-full bg-blue-600 w-full" />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs font-semibold mb-1">
                      <span>Vector-Only RAG</span>
                      <span className="text-slate-500 font-mono">43%</span>
                    </div>
                    <div className="h-3 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div className="h-full rounded-full bg-slate-400 w-[43%]" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-line bg-white p-6 shadow-sm">
                <div className="text-sm font-bold text-slate-900 mb-4">Fact Retrieval Completeness</div>
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-xs font-semibold mb-1">
                      <span>Lore FalkorDB Graph</span>
                      <span className="text-indigo-600 font-mono font-bold">100%</span>
                    </div>
                    <div className="h-3 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div className="h-full rounded-full bg-indigo-600 w-full" />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs font-semibold mb-1">
                      <span>Vector-Only RAG</span>
                      <span className="text-slate-500 font-mono">64%</span>
                    </div>
                    <div className="h-3 w-full rounded-full bg-slate-100 overflow-hidden">
                      <div className="h-full rounded-full bg-slate-400 w-[64%]" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* Interactive Query Playground / Sandbox */}
      {/* ------------------------------------------------------------- */}
      <section id="playground" className="py-20 bg-white border-b border-line">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
            <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold uppercase tracking-wider text-blue-700 border border-blue-200">
              Interactive Sandbox
            </span>
            <h2 className="font-display text-3xl sm:text-4xl font-bold text-heading tracking-tight">
              Test the company brain in action
            </h2>
            <p className="text-slate-600 text-base sm:text-lg">
              Select one of the benchmark queries below to see how Lore chains tools, traverses FalkorDB,
              and generates verified citation tags.
            </p>
          </div>

          {/* Preset Buttons */}
          <div className="flex flex-wrap justify-center gap-2 mb-8">
            {PRESET_QUERIES.map((q, idx) => (
              <button
                key={idx}
                onClick={() => setActiveQueryIndex(idx)}
                className={`rounded-xl px-4 py-2.5 text-xs font-semibold transition border ${
                  idx === activeQueryIndex
                    ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                    : 'bg-slate-50 text-slate-700 border-line hover:bg-slate-100'
                }`}
              >
                {q.q}
              </button>
            ))}
          </div>

          {/* Interactive Agent Output Simulation */}
          <div className="rounded-2xl border border-line bg-panel-2 p-6 sm:p-8 shadow-sm">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              {/* Left: Execution Trace */}
              <div className="lg:col-span-5 space-y-4">
                <div className="rounded-xl border border-line bg-white p-4">
                  <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                    Agent Tool Dispatch
                  </div>
                  <div className="font-mono text-xs text-blue-700 bg-blue-50 p-2.5 rounded-lg border border-blue-100">
                    {currentQuery.tool}
                  </div>
                </div>

                <div className="rounded-xl border border-line bg-white p-4">
                  <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                    FalkorDB Cypher Traversal
                  </div>
                  <div className="font-mono text-xs text-emerald-800 bg-emerald-50 p-2.5 rounded-lg border border-emerald-100 overflow-x-auto">
                    {currentQuery.cypherTrace}
                  </div>
                </div>

                <div className="rounded-xl border border-line bg-white p-4">
                  <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
                    Traversed Graph Subgraph
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {currentQuery.graphNodes.map(n => (
                      <span key={n} className="rounded-md bg-slate-100 px-2 py-1 text-[11px] font-mono text-slate-700 border border-line">
                        {n}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right: Rendered Verified Response */}
              <div className="lg:col-span-7">
                <div className="rounded-xl border border-blue-200 bg-white p-6 shadow-sm flex flex-col justify-between h-full">
                  <div>
                    <div className="flex items-center justify-between pb-3 border-b border-line mb-4">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 size={18} className="text-emerald-500" />
                        <span className="text-xs font-bold uppercase tracking-wider text-slate-800">
                          Citation Verifier: 100% Provenance Confirmed
                        </span>
                      </div>
                      <span className="rounded bg-blue-50 px-2 py-0.5 text-[11px] font-mono text-blue-700 border border-blue-200">
                        Zero Hallucinations
                      </span>
                    </div>

                    <div className="text-sm text-slate-800 leading-relaxed whitespace-pre-line mb-6 font-normal">
                      {currentQuery.answer}
                    </div>

                    <div className="space-y-2 border-t border-line pt-4">
                      <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                        Cited Evidence Registry:
                      </div>
                      {currentQuery.citations.map((c, i) => (
                        <div key={i} className="text-xs font-mono text-slate-600 bg-slate-50 p-2 rounded border border-line flex items-center gap-2">
                          <span className="h-1.5 w-1.5 rounded-full bg-blue-600" />
                          <span>{c}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-6 pt-4 border-t border-line flex items-center justify-between">
                    <span className="text-xs text-slate-400">Ready to test your own questions?</span>
                    <button
                      onClick={() => onEnterApp('ask')}
                      className="flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-sm hover:bg-blue-700 transition"
                    >
                      <Bot size={14} />
                      <span>Ask Lore Live</span>
                      <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* UI Screenshots & Feature Showcase */}
      {/* ------------------------------------------------------------- */}
      <section className="py-20 bg-slate-50 border-b border-line">
        <div className="mx-auto max-w-7xl px-6">
          <div className="text-center max-w-3xl mx-auto space-y-4 mb-14">
            <span className="rounded-full bg-slate-200 px-3 py-1 text-xs font-bold uppercase tracking-wider text-slate-700">
              Product Tour
            </span>
            <h2 className="font-display text-3xl sm:text-4xl font-bold text-heading tracking-tight">
              Designed for clarity, built for enterprise scale
            </h2>
            <p className="text-slate-600 text-base sm:text-lg">
              Explore the core views of Lore's user interface — from decision trees to real-time graph explorers.
            </p>
          </div>

          {/* Screenshot Navigation Tabs */}
          <div className="flex flex-wrap justify-center gap-2 mb-8">
            {SCREENSHOT_TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveScreenshotTab(tab.id)}
                className={`rounded-xl px-4 py-2.5 text-xs font-bold transition border ${
                  activeScreenshotTab === tab.id
                    ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                    : 'bg-white text-slate-700 border-line hover:bg-slate-100'
                }`}
              >
                {tab.title}
              </button>
            ))}
          </div>

          {/* Active Screenshot Display */}
          <div className="rounded-3xl border border-line bg-white p-4 sm:p-6 shadow-xl">
            <div className="flex flex-col lg:flex-row gap-6 items-center">
              <div className="lg:w-8/12 w-full rounded-2xl overflow-hidden border border-line shadow-sm bg-slate-100">
                <img
                  src={currentScreenshot.src}
                  alt={currentScreenshot.title}
                  className="w-full h-auto object-cover max-h-[520px]"
                />
              </div>

              <div className="lg:w-4/12 w-full space-y-4 p-2">
                <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-bold text-blue-700 border border-blue-200">
                  {currentScreenshot.tag}
                </span>
                <h3 className="text-2xl font-bold text-slate-900">{currentScreenshot.title}</h3>
                <p className="text-sm text-slate-600 leading-relaxed">
                  {currentScreenshot.desc}
                </p>

                <div className="space-y-2 pt-2">
                  {currentScreenshot.highlights.map((h, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs font-medium text-slate-700">
                      <Check size={14} className="text-emerald-500 shrink-0" />
                      <span>{h}</span>
                    </div>
                  ))}
                </div>

                <div className="pt-4">
                  <button
                    onClick={() => onEnterApp(currentScreenshot.id)}
                    className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-blue-700 transition"
                  >
                    <span>Open {currentScreenshot.title}</span>
                    <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* MCP Protocol Integration (Model Context Protocol) */}
      {/* ------------------------------------------------------------- */}
      <section className="py-20 bg-white border-b border-line">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            <div className="lg:col-span-6 space-y-6">
              <div className="inline-flex items-center gap-2 rounded-full border border-purple-200 bg-purple-50 px-3 py-1 text-xs font-semibold text-purple-800">
                <Layers size={14} />
                <span>Model Context Protocol (MCP)</span>
              </div>

              <h2 className="font-display text-3xl sm:text-4xl font-bold text-heading tracking-tight">
                Connect your IDE directly to company memory
              </h2>

              <p className="text-slate-600 text-base leading-relaxed">
                Lore exposes its entire graph toolset as an <strong>MCP Server</strong>.
                Whether you use <strong>Claude Desktop</strong>, <strong>Claude Code</strong>, or <strong>Cursor</strong>,
                your AI assistant can consult the company brain before generating code or modifying services.
              </p>

              <div className="space-y-3 pt-2">
                <div className="flex items-start gap-3">
                  <CheckCircle2 size={18} className="text-blue-600 shrink-0 mt-0.5" />
                  <div className="text-sm text-slate-700">
                    <strong>Autonomous PR verification: </strong> Coding assistant inspects who owns the touched files according to FalkorDB claims.
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle2 size={18} className="text-blue-600 shrink-0 mt-0.5" />
                  <div className="text-sm text-slate-700">
                    <strong>Smart reviewer routing: </strong> Queries <code>find_experts</code> with time decay instead of guessing from git blame.
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle2 size={18} className="text-blue-600 shrink-0 mt-0.5" />
                  <div className="text-sm text-slate-700">
                    <strong>Architecture policy check: </strong> Queries <code>trace_decision</code> to ensure code doesn't violate active supersession rules.
                  </div>
                </div>
              </div>
            </div>

            {/* MCP Config Snippet */}
            <div className="lg:col-span-6">
              <div className="rounded-2xl border border-slate-800 bg-slate-950 p-6 text-slate-300 shadow-xl">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4 text-xs">
                  <span className="font-mono text-purple-400">claude_desktop_config.json</span>
                  <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-400">MCP Client</span>
                </div>
                <pre className="font-mono text-xs text-slate-300 overflow-x-auto leading-relaxed">
{`{
  "mcpServers": {
    "lore": {
      "command": "uv",
      "args": ["run", "python", "-m", "lore.mcp"],
      "env": {
        "FALKORDB_HOST": "localhost",
        "FALKORDB_PORT": "6391",
        "LORE_TENANT": "northwind"
      }
    }
  }
}`}
                </pre>
                <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                  <span>Tools exposed: who_owns, trace_decision, find_experts, bus_factor, whats_changed</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* Call to Action & Launch */}
      {/* ------------------------------------------------------------- */}
      <section className="py-20 bg-gradient-to-b from-blue-50/60 to-white text-center">
        <div className="mx-auto max-w-4xl px-6 space-y-6">
          <span className="rounded-full bg-blue-100 px-3.5 py-1 text-xs font-bold uppercase tracking-wider text-blue-800 border border-blue-200">
            Graph Hacks: Track 03 Ready
          </span>

          <h2 className="font-display text-3xl sm:text-5xl font-bold text-heading tracking-tight">
            Stop guessing what your company decided.
          </h2>

          <p className="text-slate-600 text-lg max-w-2xl mx-auto">
            Experience the FalkorDB-powered company brain with real demo companies,
            interactive time travel, and verifiable provenance today.
          </p>

          <div className="flex flex-wrap justify-center items-center gap-4 pt-4">
            <button
              onClick={() => onEnterApp('dashboard')}
              className="flex items-center gap-2.5 rounded-xl bg-blue-600 px-8 py-4 text-base font-bold text-white shadow-xl shadow-blue-500/30 hover:bg-blue-700 hover:shadow-2xl transition active:scale-[0.98]"
            >
              <Sparkles size={18} />
              <span>Enter Workspace Dashboard</span>
              <ArrowRight size={17} />
            </button>

            <button
              onClick={() => onEnterApp('explore')}
              className="flex items-center gap-2 rounded-xl border border-line-2 bg-white px-6 py-4 text-base font-semibold text-slate-700 hover:border-blue-400 hover:bg-slate-50 transition"
            >
              <Network size={18} className="text-blue-600" />
              <span>Explore Graph Visualization</span>
            </button>
          </div>

          <div className="pt-8 text-xs text-slate-400 font-mono">
            Connected Graph: <span className="text-blue-600 font-bold">lore_{currentTenant || 'northwind'}</span> · {totalNodes} nodes · {totalEdges} relationships
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------- */}
      {/* Footer */}
      {/* ------------------------------------------------------------- */}
      <footer className="border-t border-line bg-white py-10 px-6 text-xs text-slate-500">
        <div className="mx-auto max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-white">
              <img src="/favicon.svg" alt="Lore Logo" className="h-4 w-4 brightness-200" />
            </div>
            <span className="font-bold text-slate-900 text-sm">Lore AI</span>
            <span>· Built for WeMakeDevs &times; FalkorDB Graph Hacks (Track 03)</span>
          </div>

          <div className="flex items-center gap-6">
            <button onClick={() => onEnterApp('dashboard')} className="hover:text-blue-600 transition">Workspace</button>
            <button onClick={() => onEnterApp('ask')} className="hover:text-blue-600 transition">Ask Lore</button>
            <button onClick={() => onEnterApp('decisions')} className="hover:text-blue-600 transition">Decisions</button>
            <button onClick={() => onEnterApp('explore')} className="hover:text-blue-600 transition">Graph Explorer</button>
          </div>
        </div>
      </footer>
    </div>
  )
}
