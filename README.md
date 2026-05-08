# CIS AgentOps

> **Content Intelligence System** · Advanced AgentOps Capstone 2026  
> Live demo: **[cis-agentops.vercel.app](https://cis-agentops.vercel.app)**  
> GitHub: [pqnghiep1354/cis-agentops](https://github.com/pqnghiep1354/cis-agentops)

AI pipeline that transforms raw supplier tour descriptions into brand-compliant, SEO-optimised luxury travel content — automatically, at scale, with full observability.

**Results on golden dataset:** avg quality score **9.4/10** · avg cost **$0.005/tour** · 27–28/29 rules passed

---

## What It Does

Adventure Asia's content team manually rewrites 3,000+ supplier tour descriptions. Each rewrite takes 30–45 minutes. CIS AgentOps automates this end-to-end in ~30 seconds per tour.

```
Raw supplier text (3–5 sentences)
         ↓
  [7-stage LangGraph pipeline]
         ↓
Brand-compliant luxury content
  · 300-word refined description
  · SEO-optimised title & meta tags
  · 5–6 curated highlights
  · Quality score 9+/10
```

---

## Pipeline Architecture

```
TourInput (Excel upload)
    │
    ▼
┌─────────────┐
│  ingestion  │  Excel schema validation — auto-detect column aliases
└──────┬──────┘  (tour_name/name, destination/country, summary/description...)
       │
       ▼
┌─────────────┐
│     seo     │  DataForSEO Keywords API + SERP/PAA — 7-day in-process cache
└──────┬──────┘
       │
       ▼
┌─────────────┐
│     rag     │  1. LLM query rewriting (Claude Haiku)
└──────┬──────┘  2. ChromaDB vector retrieval (top-8)
       │         3. Multi-hop: SEO angles → 2nd retrieval pass
       │         4. Cross-encoder reranking → top-3 few-shots
       ▼
┌─────────────┐
│   generate  │  Claude Sonnet 4.6 → Claude Haiku → GPT-4.1 (fallback chain)
└──────┬──────┘  Pydantic v2 schema enforcement · Prompt injection guard
       │
       ▼
┌─────────────┐
│  validate   │  29 weighted rules across 4 layers:
└──────┬──────┘  L1 Structural · L2 Brand Voice · L3 SEO · L4 Semantic
       │
       ├── score ≥ 7.0 ──────────────────────────────── ▶ export
       ├── score < 7.0, regen < 3 ──────────────────── ▶ generate (loop)
       └── regen ≥ 3 ──────────────────────────────── ▶ hitl
                                                           │
                                                           ▼
                                                      ┌────────┐
                                                      │  hitl  │  Human review
                                                      └────────┘
                                                           │
                                                      ┌────────┐
                                                      │ export │  PostgreSQL
                                                      └────────┘
```

**State checkpointed at every node** via SqliteSaver — crash-recoverable.  
**Langfuse span per node** — full token, cost, and latency traceability.

---

## Rubric Coverage (AgentOps Capstone)

| # | Criterion | Score | Implementation |
|---|-----------|-------|---------------|
| 1 | **Problem & System Design** | 9–10 | B2B multi-tenant content automation, justified agent design |
| 2 | **Agent Architecture** | 13–15 | LangGraph StateGraph, SqliteSaver checkpoint, max_regen=3 guard |
| 3 | **Tooling & Integration** | 9–10 | DataForSEO, ChromaDB, PostgreSQL, Langfuse, multi-LLM |
| 4 | **RAG (Advanced)** | 9–10 | Query rewrite → multi-hop → cross-encoder rerank |
| 5 | **Observability** | 9–10 | Langfuse span per node, cost + latency per stage |
| 6 | **Evaluation** | 13–15 | LLM-as-judge (6 dims), 20-tour golden dataset, regression compare |
| 7 | **Guardrails** | 9–10 | 29 weighted rules, Pydantic v2, injection pattern detection |
| 8 | **Performance & Cost** | 5 | Cost tracker per model, Redis cache (prod), stage latency |
| 9 | **Production Readiness** | 9–10 | Docker Compose, Vercel deploy, env config, graceful fallback |
| 10 | **Demo** | 5 | Live at cis-agentops.vercel.app + Jupyter notebook |

---

## Live Demo

**Frontend:** [cis-agentops.vercel.app](https://cis-agentops.vercel.app)

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | Stats, pipeline diagram, recent runs |
| Upload & Run | `/upload` | Drag & drop Excel → schema validation → run |
| Pipeline | `/pipeline/[runId]` | Stage progress + generated content + timings |
| Published Tours | `/results` | All published tours with search |
| Evaluation | `/eval` | LLM-as-judge radar chart + per-tour scores |

---

## Quick Start (Local)

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Anthropic API key (`sk-ant-...`)
- OpenAI API key (`sk-...`) — GPT-4.1 fallback
- DataForSEO account — or set `MOCK_SEO=true`
- Langfuse — [cloud.langfuse.com](https://cloud.langfuse.com) (free tier)

### 1. Clone & configure

```bash
git clone https://github.com/pqnghiep1354/cis-agentops.git
cd cis-agentops

cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, OPENAI_API_KEY, LANGFUSE keys
```

### 2. Start local services

```bash
docker compose up -d
# PostgreSQL :5432 · ChromaDB :8000 · Langfuse :3001 · API :8080

docker compose ps   # all should be healthy
```

### 3. Seed ChromaDB

```bash
pip install chromadb --break-system-packages
python seeds/seed_chromadb.py
# → "ChromaDB seeded: 5 examples in 'cis_few_shots'"
```

### 4. Verify API

```bash
curl http://localhost:8080/health
# → {"status":"ok","version":"1.0.0"}
```

### 5. Run frontend locally

```bash
cd frontend
cp .env.example .env.local
# Set: NEXT_PUBLIC_API_URL=http://localhost:8080
npm install && npm run dev
# → http://localhost:3000
```

### 6. Run Jupyter demo notebook

```bash
pip install -r requirements.txt
cd notebooks && jupyter lab demo_pipeline.ipynb
```

---

## Configuration (.env)

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Claude Sonnet → Haiku |
| `OPENAI_API_KEY` | ✅ | GPT-4.1 emergency fallback |
| `DATAFORSEO_LOGIN` | ⚠️ | DataForSEO email (or use `MOCK_SEO=true`) |
| `DATAFORSEO_PASSWORD` | ⚠️ | DataForSEO password |
| `MOCK_SEO` | optional | `true` = skip DataForSEO (default: `false`) |
| `LANGFUSE_HOST` | ✅ | `https://cloud.langfuse.com` |
| `LANGFUSE_PUBLIC_KEY` | ✅ | From Langfuse → Settings → API Keys |
| `LANGFUSE_SECRET_KEY` | ✅ | From Langfuse → Settings → API Keys |
| `DATABASE_URL` | ✅ | `postgresql://cis:cis_local_pass@localhost:5432/cis_local` |
| `AUTO_APPROVE_HITL` | optional | `true` = skip human review (notebook demo) |

---

## Vercel Deployment (Frontend)

```bash
cd frontend
npm install -g vercel
vercel --prod

# In Vercel dashboard → Settings → Environment Variables:
# API_URL = https://your-ngrok-or-api-domain.com
```

Frontend proxies `/api/*` through Vercel server → API (no CORS).

---

## Excel Input Format

Upload any `.xlsx` file. Column names are auto-detected (aliases supported):

| Required Field | Accepted Column Names |
|---------------|----------------------|
| `tour_name` | `name`, `title`, `tour` |
| `destination` | `country`, `location`, `region` |
| `duration_days` | `duration`, `days`, `nights` |
| `raw_description` | `summary`, `description`, `overview` |
| `price_usd` | `price`, `cost`, `rate` |
| `highlights` | `key_highlights`, `features` *(optional)* |
| `inclusions` | `included`, `includes` *(optional)* |

Duration parsing: `"11 days / 10 nights"` → `11` ✅  
Price parsing: `"$3,400"` → `3400.0` ✅

---

## Validation — 29 Rules

| Layer | Rules | Examples |
|-------|-------|---------|
| **L1 Structural** | v01–v10 | Field presence, length limits |
| **L2 Brand Voice** | v11–v15 | No forbidden words, no exclamation, no first-person |
| **L3 SEO** | v16–v19 | Keyword integration, meta tag length, destination mention |
| **L4 Semantic** | v20–v29 | No repetition, no placeholders, description variety |

**Critical rules** weighted 2–3×: brand voice (`v11`), description length (`v06`), approved vocab (`v14`).

**Forbidden words:** deal, cheap, book now, instant booking, amazing, unforgettable, perfect  
**Approved vocab:** curated, designed, refined, tailored, journey, experience, discover

---

## Evaluation

```bash
# Run LLM-as-judge eval on 20 golden tours (~5 min, ~$0.05)
python -m eval.run_eval run

# Compare two runs (regression detection)
python -m eval.run_eval compare eval/results/run_A.json eval/results/run_B.json
```

**Judge dimensions (1–10 each):** brand_voice · seo_quality · content_accuracy · writing_quality · target_audience_fit · commercial_readiness

---

## Cost Model

| Model | Input ($/1M) | Output ($/1M) | Typical/tour |
|-------|-------------|--------------|-------------|
| claude-sonnet-4-6 | $3.00 | $15.00 | ~$0.014 |
| claude-haiku-4-5 | $0.25 | $1.25 | ~$0.001 |
| gpt-4.1 | $2.00 | $8.00 | ~$0.005 |

**Typical 20-tour batch:** ~$0.10–$0.30 total

---

## Local Services

| Service | URL | Credentials |
|---------|-----|-------------|
| API | http://localhost:8080 | — |
| PostgreSQL | localhost:5432/cis_local | cis / cis_local_pass |
| ChromaDB | http://localhost:8000 | — |
| Langfuse | http://localhost:3001 | admin@cis.local / admin123 |

---

## Project Structure

```
cis-agentops/
├── agent/
│   ├── graph.py              ← LangGraph orchestrator (7 nodes)
│   ├── state.py              ← CISState TypedDict
│   └── nodes/
│       ├── ingestion.py      ← Excel schema validation
│       ├── seo.py            ← DataForSEO + mock fallback
│       ├── rag_retrieve.py   ← Query rewrite → ChromaDB → rerank
│       ├── generate.py       ← Multi-LLM + Pydantic enforcement
│       ├── validate.py       ← 29 weighted rules
│       ├── export.py         ← PostgreSQL write
│       └── hitl.py           ← Human-in-the-loop
├── api/
│   ├── main.py               ← FastAPI (upload, run, stream, tours)
│   └── index.py              ← Vercel serverless adapter
├── eval/
│   ├── run_eval.py           ← LLM-as-judge + regression compare
│   └── golden_dataset.json   ← 20 tours from real Adventure Asia data
├── frontend/                 ← Next.js 14, Vercel-ready
│   └── src/app/
│       ├── page.tsx          ← Dashboard
│       ├── upload/           ← Excel upload + validation
│       ├── pipeline/[runId]  ← Live run view + results
│       ├── results/          ← Published tours gallery
│       └── eval/             ← Evaluation dashboard
├── guardrails/
│   ├── schemas.py            ← Pydantic TourContentOutput
│   └── injection_guard.py    ← 11 injection patterns
├── observability/
│   ├── tracer.py             ← Langfuse wrapper (graceful no-op)
│   └── cost_tracker.py       ← Per-model cost estimator
├── seeds/
│   ├── init.sql              ← PostgreSQL schema
│   └── seed_chromadb.py      ← 5 few-shot examples
├── notebooks/
│   └── demo_pipeline.ipynb   ← 25-cell end-to-end demo
├── docker-compose.yml        ← 4 services
├── requirements.txt
└── .env.example
```

---

## Troubleshooting

**`langgraph.checkpoint.sqlite` not found**
```bash
pip install langgraph-checkpoint-sqlite
```

**ChromaDB connection refused**
```bash
docker compose up -d chromadb
python seeds/seed_chromadb.py
```

**API 403 CORS on Vercel**  
Use `API_URL` (server-side) not `NEXT_PUBLIC_API_URL` (client-side) in Vercel env vars.

**Pipeline stuck "Waiting to start"**  
Refresh page after ~30s — polling fetches latest run status automatically.

**DataForSEO empty results**  
Set `MOCK_SEO=true` temporarily. Check credentials at app.dataforseo.com.

---

## Author

**Nghiep (Pham Quoc Nghiep)**  
DevOps Engineer · Adventure Asia  
AgentOps Capstone 2026 · QuanSkill

---

*Built with LangGraph · Claude · GPT-4.1 · DataForSEO · ChromaDB · Langfuse · Next.js · FastAPI · PostgreSQL*
