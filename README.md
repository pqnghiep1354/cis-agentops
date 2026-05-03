# CIS AgentOps

**Adventure Asia — Content Intelligence System**  
*Advanced AgentOps Capstone Project*

Automated AI pipeline that transforms raw supplier tour descriptions into
brand-compliant, SEO-optimised luxury travel content. Built with LangGraph,
Claude Sonnet, DataForSEO, ChromaDB RAG, and Langfuse observability.

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Anthropic API key
- OpenAI API key (GPT-4.1 fallback)
- DataForSEO account (for real SEO data)
- Langfuse account — cloud: https://cloud.langfuse.com (free tier works)

### 2. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/cis-agentops.git
cd cis-agentops

cp .env.example .env
# Edit .env — fill in all API keys (see Configuration section below)
```

### 3. Start local services

```bash
docker compose up -d
# Starts: PostgreSQL (5432), ChromaDB (8000), Langfuse (3000)

# Wait ~20 seconds for Langfuse to initialise
docker compose ps   # all should be healthy
```

### 4. Install Python dependencies

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Seed ChromaDB with few-shot examples

```bash
python seeds/seed_chromadb.py
# Expected output: "ChromaDB seeded: 5 examples in 'cis_few_shots'"
```

### 6. Run the pipeline

```bash
# Single tour smoke test
python -m agent.graph

# Interactive notebook
cd notebooks
jupyter lab demo_pipeline.ipynb

# Full evaluation (20 golden tours, ~5 min, costs ~$0.05)
python -m eval.run_eval run

# Compare two eval runs (regression detection)
python -m eval.run_eval compare eval/results/run_A.json eval/results/run_B.json
```

---

## Configuration (.env)

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Primary LLM — Claude Sonnet → Haiku |
| `OPENAI_API_KEY` | ✅ | Emergency fallback — GPT-4.1 |
| `DATAFORSEO_LOGIN` | ✅ (or MOCK) | DataForSEO account email |
| `DATAFORSEO_PASSWORD` | ✅ (or MOCK) | DataForSEO password |
| `MOCK_SEO` | optional | `true` = skip DataForSEO API calls (default: `false`) |
| `LANGFUSE_HOST` | ✅ | `https://cloud.langfuse.com` or self-hosted URL |
| `LANGFUSE_PUBLIC_KEY` | ✅ | From Langfuse → Settings → API Keys |
| `LANGFUSE_SECRET_KEY` | ✅ | From Langfuse → Settings → API Keys |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `CHROMA_HOST` | optional | Default: `localhost` |
| `CHROMA_PORT` | optional | Default: `8000` |
| `AUTO_APPROVE_HITL` | optional | `true` = auto-approve HITL (notebook demo only) |

**Note:** If `MOCK_SEO=false` and DataForSEO credentials are wrong, the pipeline
falls back to mock data automatically and logs a warning. No crash.

---

## Architecture

### Pipeline Flow

```
TourInput (supplier data)
    │
    ▼
┌─────────────────┐
│   seo_node      │  DataForSEO Keywords API + SERP/PAA
│                 │  In-process cache (7-day TTL)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   rag_node      │  1. LLM query rewriting (Claude Haiku)
│                 │  2. ChromaDB vector retrieval (top-8)
│                 │  3. Multi-hop: SEO angles → 2nd retrieval pass
│                 │  4. Cross-encoder reranking → top-3 few-shots
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  generate_node  │  Claude Sonnet → Claude Haiku → GPT-4.1
│                 │  Pydantic v2 schema enforcement
│                 │  Prompt injection guard (pre-check)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  validate_node  │  29 weighted rules across 4 layers:
│                 │  L1 Structural · L2 Brand Voice
│                 │  L3 SEO · L4 Semantic Quality
└────────┬────────┘
         │
         ├── quality_score ≥ 7.0  ──────────────────────────┐
         │                                                   ▼
         ├── quality_score < 7.0, regen < 3  ─── back to generate_node
         │
         └── quality_score < 7.0, regen ≥ 3
                 │
                 ▼
         ┌──────────────┐
         │   hitl_node  │  Human-in-the-loop review
         └──────┬───────┘  (CLI locally / SQS in production)
                │
                ├── approved ─────────────────────────────────┐
                │                                             ▼
                └── rejected ──▶ [END]              ┌──────────────────┐
                                                    │  export_node     │
                                                    │  PostgreSQL write │
                                                    └──────────────────┘
                                                              │
                                                            [END] ✅
```

### State Checkpointing

Every node checkpoint is written to `.checkpoints.db` (SQLite, local).
If a run crashes mid-pipeline, resume from the last checkpoint:

```python
from agent.graph import build_graph
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

conn = sqlite3.connect(".checkpoints.db", check_same_thread=False)
graph = build_graph(checkpointer=SqliteSaver(conn))
# Invoke with same thread_id to resume
graph.invoke(None, config={"configurable": {"thread_id": "previous-thread-id"}})
```

### Multi-LLM Fallback Chain

```
Claude Sonnet 4.6 (primary)
    ↓ ThrottlingException / overloaded
Claude Haiku 4.5 (fast fallback)
    ↓ Bedrock unavailable
GPT-4.1 (emergency fallback)
    ↓ All fail
Pipeline routes to HITL
```

---

## Rubric Mapping

### Criterion 1 — Problem & System Design

Adventure Asia's content team manually rewrites 3,000+ supplier tour descriptions.
Each rewrite takes 30–45 minutes. The goal: <2 minutes end-to-end, brand-compliant,
SEO-ready output at $0.003–$0.02 per tour.

**Design decisions justified:**
- LangGraph over Step Functions locally: state checkpointing, branching, loop control
- ChromaDB over pgvector: dedicated vector ops, client-side reranking
- DataForSEO over Google Ads API: pre-aggregated keyword data, no OAuth complexity
- Langfuse over custom logging: LLM-native spans, token tracking, cost attribution

### Criterion 2 — Agent Architecture

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Orchestrator | LangGraph StateGraph | Native checkpointing, conditional edges, loop control |
| State store | TypedDict + SqliteSaver | Typed schema, crash-recoverable, portable |
| Max regen | 3 attempts | Prevents infinite loops; routes to HITL after |
| Entry point | `seo` node | SEO context needed before generation |

`agent/graph.py` — full orchestrator with conditional routing  
`agent/state.py` — CISState TypedDict with 6 typed sub-schemas

### Criterion 3 — Tooling & Integration

| Tool | Integration | File |
|------|-------------|------|
| DataForSEO | Keywords API v3 + SERP v3 | `agent/nodes/seo.py` |
| ChromaDB | HTTP client + cosine similarity | `agent/nodes/rag_retrieve.py` |
| PostgreSQL | psycopg2 direct | `agent/nodes/export.py` |
| Langfuse | Trace + span per node | `observability/tracer.py` |
| Claude (Anthropic) | Messages API | `agent/nodes/generate.py` |
| GPT-4.1 (OpenAI) | Chat completions | `agent/nodes/generate.py` |

### Criterion 4 — Retrieval / RAG (Advanced)

Three-stage advanced RAG in `agent/nodes/rag_retrieve.py`:

1. **Query rewriting** — Claude Haiku rewrites raw supplier description into a retrieval-optimised query incorporating SEO keywords
2. **Multi-hop retrieval** — Second ChromaDB pass uses competitor angles from SEO context to surface differentiated examples
3. **Cross-encoder reranking** — `cross-encoder/ms-marco-MiniLM-L-6-v2` rescores and reranks the merged candidate pool; falls back to distance-based sort if model unavailable

### Criterion 5 — Observability

Every node creates a Langfuse span with:
- Input: tour name, parameters
- Output: key metrics (score, token count, latency, model used)
- Cost: calculated from `observability/cost_tracker.py`

View traces: your Langfuse URL → Traces → filter by `name:cis-pipeline`

Stage timings stored in `CISState.stage_timings` (dict of node → ms).
Total cost accumulated in `CISState.total_cost_usd`.

### Criterion 6 — Evaluation & Testing

**LLM-as-judge** (`eval/run_eval.py`):
- Judge model: Claude Haiku (cheap, fast)
- 6 scoring dimensions: brand_voice, seo_quality, content_accuracy, writing_quality, target_audience_fit, commercial_readiness
- Scores 1–10 per dimension + overall
- Returns JSON with reasoning

**Golden dataset** (`eval/golden_dataset.json`):
- 20 real Adventure Asia tours parsed from `CIS_Golden_Tours_20_v1.xlsx`
- Each tour has expected quality range and annotation notes
- Covers 8 countries, 5 trip types

**Regression detection**:
```bash
python -m eval.run_eval run          # saves eval/results/run_{timestamp}.json
python -m eval.run_eval compare \
  eval/results/run_A.json \
  eval/results/run_B.json            # delta per metric + dimension
```

### Criterion 7 — Reliability & Guardrails

**Input guard** (`guardrails/injection_guard.py`):
- 9 regex patterns for prompt injection detection
- Blocks: ignore instructions, jailbreak, DAN, token injection, system reveal
- Applied before every LLM call; routes to HITL if triggered

**Output schema** (`guardrails/schemas.py`):
- Pydantic v2 `TourContentOutput` with field validators
- Enforced: title 5–60 chars, description 50+ words, 3+ highlights, meta ≤60/155 chars

**29 validation rules** (`agent/nodes/validate.py`):
- L1 (10 rules): Structural completeness
- L2 (5 rules): Brand voice — forbidden words, exclamation ban, first-person ban
- L3 (4 rules): SEO compliance — keyword integration, meta tags, destination mention
- L4 (10 rules): Semantic quality — variety, specificity, no placeholders

Weighted scoring: critical rules (brand voice) weighted 2–3x; score out of 10.

### Criterion 8 — Performance & Cost

Cost model in `observability/cost_tracker.py`:

| Model | Input ($/1M) | Output ($/1M) |
|-------|-------------|--------------|
| claude-sonnet-4-6 | $3.00 | $15.00 |
| claude-haiku-4-5 | $0.25 | $1.25 |
| gpt-4.1 | $2.00 | $8.00 |

Typical per-tour cost: $0.003–$0.02 depending on model tier used.  
SEO in-process cache (7-day TTL) eliminates repeat DataForSEO API charges.

### Criterion 9 — Production Readiness

```
docker-compose.yml      — PostgreSQL + ChromaDB + Langfuse (3 services)
seeds/init.sql          — DB schema (auto-applied on first container start)
seeds/seed_chromadb.py  — Vector store seeding (run once)
.env.example            — Full config template
.gitignore              — .env, checkpoints, eval results excluded
requirements.txt        — Pinned deps with langgraph-checkpoint-sqlite
```

All nodes degrade gracefully:
- ChromaDB offline → generation proceeds without few-shots
- DataForSEO fails → mock SEO data used, warning logged
- Langfuse offline → no-op tracer, pipeline continues
- LLM tier fails → next tier attempted automatically

### Criterion 10 — Demo & Explanation

`notebooks/demo_pipeline.ipynb` — 25 cells covering:
1. Service health checks
2. Architecture diagram (ASCII)
3. Single tour end-to-end run
4. Generated content display
5. RAG detail (rewrite → multi-hop → rerank)
6. Observability (stage timings chart + cost)
7. Guardrails demo (injection test cases)
8. 29-rule validation breakdown by layer
9. Automated evaluation (LLM-as-judge)
10. Before/after comparison (raw vs generated)
11. Regression comparison (two eval runs)
12. Summary and next steps

---

## Project Structure

```
cis-agentops/
├── agent/
│   ├── graph.py              ← LangGraph pipeline orchestrator
│   ├── state.py              ← CISState TypedDict (checkpointed)
│   └── nodes/
│       ├── seo.py            ← DataForSEO Keywords + SERP/PAA
│       ├── rag_retrieve.py   ← Query rewrite → ChromaDB → rerank
│       ├── generate.py       ← Multi-LLM generation + Pydantic validation
│       ├── validate.py       ← 29 weighted brand/quality rules
│       ├── export.py         ← PostgreSQL write
│       └── hitl.py           ← Human-in-the-loop (CLI / SQS in prod)
├── eval/
│   ├── run_eval.py           ← LLM-as-judge + regression compare
│   ├── golden_dataset.json   ← 20 tours from real Adventure Asia data
│   └── results/              ← Eval run JSONs (gitignored)
├── guardrails/
│   ├── schemas.py            ← Pydantic TourContentOutput
│   └── injection_guard.py    ← Prompt injection pattern detection
├── observability/
│   ├── tracer.py             ← Langfuse wrapper (graceful no-op fallback)
│   └── cost_tracker.py       ← Token cost estimator per model
├── seeds/
│   ├── init.sql              ← PostgreSQL schema (auto-applied by Docker)
│   └── seed_chromadb.py      ← ChromaDB seeder with 5 few-shot examples
├── notebooks/
│   └── demo_pipeline.ipynb   ← 25-cell end-to-end demo
├── docker-compose.yml        ← PostgreSQL + ChromaDB + Langfuse
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Local Services

| Service | Port | Credentials |
|---------|------|-------------|
| PostgreSQL | 5432 | cis / cis_local_pass / cis_local |
| ChromaDB API | 8000 | — |
| Langfuse UI | 3000 | admin@cis.local / admin123 |

Connect to PostgreSQL locally:
```bash
psql postgresql://cis:cis_local_pass@localhost:5432/cis_local
\dt                    # list tables
SELECT * FROM published_tours LIMIT 5;
```

---

## Troubleshooting

**Import error: `langgraph.checkpoint.sqlite`**
```bash
pip install langgraph-checkpoint-sqlite
```

**ChromaDB connection refused**
```bash
docker compose up -d chromadb
python seeds/seed_chromadb.py   # re-seed after restart
```

**Langfuse not receiving traces**
- Check `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` in `.env`
- For cloud: `LANGFUSE_HOST=https://cloud.langfuse.com`
- Pipeline continues even if Langfuse is unreachable (graceful no-op)

**DataForSEO returns empty results**
- Verify credentials: `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD`
- Check account credit balance at app.dataforseo.com
- Set `MOCK_SEO=true` temporarily to bypass

**Quality score always 0**
- `generated_content` is `None` → LLM call failed
- Check `ANTHROPIC_API_KEY` is valid
- Run with `MOCK_SEO=true` first to isolate LLM issues

---

## Extending the System

**Add a new validation rule:**
```python
# In agent/nodes/validate.py
RULES["v30_my_rule"] = lambda c, t, s: "desired phrase" in c.get("description", "")
RULE_WEIGHTS["v30_my_rule"] = 2.0  # optional weight boost
```

**Add a new few-shot example to ChromaDB:**
```python
# In seeds/seed_chromadb.py → FEW_SHOT_EXAMPLES list
# Then re-run: python seeds/seed_chromadb.py
```

**Swap checkpointer for PostgreSQL (production):**
```python
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string(os.getenv("DATABASE_URL"))
graph = build_graph(checkpointer=checkpointer)
```

---

## Cost Estimate (per 100 tours)

| Scenario | Model | Est. Cost |
|----------|-------|-----------|
| All Sonnet (best quality) | claude-sonnet-4-6 | ~$1.50 |
| All Haiku (fast/cheap) | claude-haiku-4-5 | ~$0.12 |
| Mixed (typical) | Sonnet + 1 regen Haiku | ~$0.80 |
| DataForSEO (100 keywords) | — | ~$0.10 |
| **Typical 100 tours total** | | **~$0.90** |

---

## Frontend (Next.js) — Vercel Deployment

### Local dev

```bash
cd frontend
cp .env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8080
npm install
npm run dev    # → http://localhost:3000
```

### Deploy to Vercel

```bash
cd frontend
npm install -g vercel
vercel            # follow prompts

# Set env var in Vercel dashboard:
# NEXT_PUBLIC_API_URL = https://your-api-domain.com
```

### Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard — stats, recent runs, pipeline diagram |
| `/upload` | Drag & drop Excel → schema validation → run |
| `/pipeline` | All pipeline runs list |
| `/pipeline/[runId]` | Live SSE stream — stage progress + results |
| `/results` | Published tours gallery with search |
| `/eval` | LLM-as-judge radar chart + per-tour scores |

---

## Ingestion Node

New `agent/nodes/ingestion.py` — validates every tour before entering the pipeline:

**Column detection** — accepts common aliases:
- `tour_name` | `name` | `title`
- `destination` | `country` | `location`
- `duration` | `duration_days` | `days`
- `summary` | `description` | `raw_description`
- `price_usd` | `price` | `cost`

**Validation rules:**
- Required fields present and non-empty
- Description ≥ 20 words
- Duration parseable (handles `"11 days / 10 nights"`, `"7"`, `"3-day"`)
- Price parseable (`"$3,400"`, `3400`, `3400.00`)
- Price and duration in valid ranges
- Pipeline routes to HITL immediately if ingestion fails

**Excel file validation** (via `/api/upload`):
- Auto-detects sheet name (`tour`, `data`, `golden`, or first sheet)
- Returns per-row errors with row numbers
- Returns `tours_preview` (first 3 valid tours) for UI preview
- `valid=true` only if all required columns present AND zero row errors

---

## Full Local Stack

```bash
docker compose up -d              # PostgreSQL + ChromaDB + Langfuse + API

# Seed
python seeds/seed_chromadb.py

# Frontend
cd frontend && npm install && npm run dev

# Services:
# API        → http://localhost:8080
# Frontend   → http://localhost:3000
# Langfuse   → http://localhost:3000 (langfuse container on same port — change if conflict)
# ChromaDB   → http://localhost:8000
# PostgreSQL → localhost:5432
```

> **Note:** If Langfuse and the Next.js frontend both want port 3000, change Langfuse to `"3001:3000"` in `docker-compose.yml` and update `LANGFUSE_HOST=http://localhost:3001` in `.env`.
