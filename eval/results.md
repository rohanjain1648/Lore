# Evaluation: Lore vs. vector-only RAG

Agent mode: **offline**. 22 golden questions over the Northwind Labs dataset (`eval/golden.json`). Reproduce with `uv run python -m lore.evaluate`.

| Metric | Lore (graph) | Vector-only RAG |
|---|---|---|
| Answer contains the expected facts | 22/22 (100%) | 14/22 (64%) |
| Expected source cited / retrieved | 16/16 (100%) | 12/16 (75%) |
| Gives the *current* fact first (facts that changed) | 7/7 (100%) | 3/7 (43%) |

## Expected facts by question type

| Bucket | Lore | Vector-only RAG |
|---|---|---|
| decisions | 7/7 (100%) | 7/7 (100%) |
| expertise | 4/4 (100%) | 2/4 (50%) |
| freshness | 2/2 (100%) | 0/2 (0%) |
| lookup | 2/2 (100%) | 1/2 (50%) |
| ownership | 4/4 (100%) | 2/4 (50%) |
| time-travel | 3/3 (100%) | 2/3 (67%) |

The baseline is scored on its whole top-8 retrieved context (an upper bound for an LLM answering from it), and it has no notion of time, so it is not given the as-of date.

## Per question

| id | question | as of | tools | Lore fact / evidence / current | RAG fact / evidence / current |
|---|---|---|---|---|---|
| own-1 | Who owns payments-service? |  | who_owns | ✅ ✅ ✅ | ✅ ✅ ❌ |
| own-2 | Who owns search-api? |  | who_owns | ✅ ✅ ✅ | ✅ ✅ ✅ |
| own-3 | Who owns data-pipeline? |  | who_owns | ✅ ✅ - | ❌ ❌ - |
| own-4 | Who owns auth-gateway? |  | who_owns | ✅ ✅ - | ❌ ❌ - |
| dec-1 | Why did we choose FalkorDB for the recommendations engine? |  | trace_decision | ✅ ✅ - | ✅ ✅ - |
| dec-2 | Who approved using FalkorDB as the graph store for recs-engine? |  | trace_decision | ✅ ✅ - | ✅ ✅ - |
| dec-3 | Can we deploy on Fridays? |  | trace_decision | ✅ ✅ ✅ | ✅ ✅ ✅ |
| dec-4 | Why was the Friday deploy freeze brought back? |  | trace_decision | ✅ ✅ - | ✅ ✅ - |
| dec-5 | What is our policy on gRPC for mobile-facing APIs? |  | trace_decision | ✅ ✅ ✅ | ✅ ✅ ❌ |
| dec-6 | Which ticket implemented the decision to revert mobile APIs to REST? |  | trace_decision | ✅ ✅ - | ✅ ✅ - |
| dec-7 | Who proposed lifting the Friday deploy freeze? |  | trace_decision | ✅ ✅ - | ✅ ✅ - |
| exp-1 | Who knows about Kafka? |  | find_experts | ✅ - - | ✅ - - |
| exp-2 | Who should I ask about auth-gateway? |  | find_experts | ✅ - - | ❌ - - |
| exp-3 | What is the bus factor risk for auth-gateway? |  | bus_factor | ✅ - - | ❌ - - |
| exp-4 | Tell me about Project Shield |  | profile | ✅ - - | ✅ - - |
| fresh-1 | Which docs are out of date? |  | freshness | ✅ - - | ❌ - - |
| fresh-2 | What changed since June? |  | whats_changed | ✅ - - | ❌ - - |
| time-1 | Who owns payments-service? | 2026-05-01 | who_owns | ✅ ✅ ✅ | ✅ ✅ ✅ |
| time-2 | Can we deploy on Fridays? | 2026-06-01 | trace_decision | ✅ ✅ ✅ | ✅ ✅ ❌ |
| time-3 | Who owns search-api? | 2026-03-01 | who_owns | ✅ ✅ ✅ | ❌ ❌ ❌ |
| srch-1 | How do retries avoid duplicate charges? |  | search | ✅ ✅ - | ❌ ❌ - |
| srch-2 | How many Kafka brokers does the data pipeline have? |  | search | ✅ ✅ - | ✅ ✅ - |
