export type Citation = {
  sid: string
  id: string
  kind: string
  title: string
  url: string
  ts: string
  author?: string
  author_name?: string
  snippet: string
  used?: boolean
}

export type GNode = { id: string; label: string; name: string; [k: string]: unknown }
export type GEdge = { source: string; target: string; type: string; [k: string]: unknown }
export type Subgraph = { nodes: GNode[]; edges: GEdge[] }

export type Step = { tool: string; input: Record<string, unknown>; summary: string }

export type AskResponse = {
  question: string
  as_of: string | null
  answer: string
  mode: 'llm' | 'offline'
  provider?: 'groq' | 'openai' | null
  citations: Citation[]
  steps: Step[]
  warnings: string[]
  subgraph: Subgraph
}

export type ToolResponse<T> = { result: T; citations: Citation[]; subgraph: Subgraph }

export type Meta = {
  company: string
  now: string
  first: string
  last: string
  llm: boolean
  primary?: string | null
  fallback?: string | null
  model?: string | null
  stats: { nodes: Record<string, number>; relationships: Record<string, number> }
}

const BASE = import.meta.env.VITE_API_BASE ?? ''

let TENANT: string | null = null
export const setTenant = (t: string | null) => {
  TENANT = t
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  if (TENANT) {
    path += (path.includes('?') ? '&' : '?') + `tenant=${encodeURIComponent(TENANT)}`
    if (init?.body) init = { ...init, body: JSON.stringify({ ...JSON.parse(init.body as string), tenant: TENANT }) }
  }
  const r = await fetch(BASE + path, { headers: { 'content-type': 'application/json' }, ...init })
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`)
  return r.json() as Promise<T>
}

const qs = (o: Record<string, string | null | undefined>) => {
  const p = new URLSearchParams()
  Object.entries(o).forEach(([k, v]) => v && p.set(k, v))
  const s = p.toString()
  return s ? `?${s}` : ''
}

export const api = {
  meta: () => req<Meta>('/api/meta'),
  tenants: () => req<{ tenants: string[]; default: string }>('/api/tenants'),
  ask: (question: string, as_of: string | null, history: { role: string; content: string }[]) =>
    req<AskResponse>('/api/ask', { method: 'POST', body: JSON.stringify({ question, as_of, history }) }),
  systems: (as_of: string | null) => req<{ systems: SystemRow[] }>(`/api/systems${qs({ as_of })}`),
  people: () => req<{ people: PersonRow[] }>('/api/people'),
  experts: (subject: string) => req<ToolResponse<ExpertsResult>>(`/api/experts${qs({ subject })}`),
  decisions: (as_of: string | null) => req<ToolResponse<{ decisions: DecisionRow[] }>>(`/api/decisions${qs({ as_of })}`),
  decision: (query: string, as_of: string | null) => req<ToolResponse<TraceResult>>(`/api/decision${qs({ query, as_of })}`),
  freshness: () => req<ToolResponse<{ stale_documents: StaleDoc[]; summary: string }>>('/api/freshness'),
  changes: (since: string, as_of: string | null) => req<ToolResponse<{ summary: string }>>(`/api/changes${qs({ since, as_of })}`),
  ownership: (entity: string, as_of: string | null) => req<ToolResponse<{ summary: string }>>(`/api/ownership${qs({ entity, as_of })}`),
  profile: (name: string, as_of: string | null) => req<ToolResponse<{ summary: string }>>(`/api/profile${qs({ name, as_of })}`),
  overview: (as_of: string | null) => req<{ nodes: GNode[]; edges: GEdge[] }>(`/api/graph/overview${qs({ as_of })}`),
  ingest: (channel: string, author: string, text: string) =>
    req<IngestResult>('/api/ingest/message', { method: 'POST', body: JSON.stringify({ channel, author, text }) }),
  actions: () => req<{ actions: ActionRow[] }>('/api/actions'),
  createAction: (kind: string, title: string, body: string, target?: string) =>
    req<{ summary: string }>('/api/actions', { method: 'POST', body: JSON.stringify({ kind, title, body, target }) }),
  reset: () => req<unknown>('/api/reset', { method: 'POST' }),
}

export type SystemRow = {
  id: string; kind: string; owner: string | null; projects: string[]; risk: 'high' | 'medium' | 'low'
  active_experts: string[]; top_expert: string | null; top_expert_active: boolean
}
export type PersonRow = {
  id: string; name: string; role: string; active: boolean; left_at: string | null; team: string
  influence: number; broker: number; community: number | null; knows: string[]
}
export type Expert = {
  name: string; team: string; role: string; active: boolean; left_at: string | null; score: number
  contributions: number; last_active: string | null; cite: string
}
export type ExpertsResult = { subject: string; experts: Expert[]; summary: string }
export type DecisionRow = {
  id: string; title: string; at: string; affects: string[]; topics: string[]; src: string; src_title: string
  supersedes: string[]; superseded_by: string[]; status: 'active' | 'superseded'; cite: string
}
export type Lineage = {
  title: string; decided: string; status: string; made_in: string; cite: string; proposed_by: string | null
  approved_by: string | null; evidence_cite: string; implemented_by: string[]; implemented_cite: string
}
export type TraceResult = { lineage: Lineage[]; summary: string; error?: string }
export type StaleDoc = { id: string; title: string; url: string; updated: string; reasons: string[]; author: string; cite: string }
export type IngestResult = {
  item: string
  mentions: { label: string; id: string; name: string }[]
  changes: { type: string; [k: string]: string }[]
}
export type ActionRow = { id: string; kind: string; title: string; body: string; status: string; created_at: string; about: string[] }
