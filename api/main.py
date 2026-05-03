"""
CIS AgentOps — FastAPI Backend
Endpoints:
  POST /api/upload          — Upload Excel, validate schema
  POST /api/run             — Start pipeline for single tour
  POST /api/batch           — Start pipeline for all tours in upload
  GET  /api/run/{run_id}    — Get run status
  GET  /api/run/{run_id}/stream — SSE stream of real-time events
  GET  /api/tours           — List published tours
  GET  /api/eval/latest     — Latest eval results
  POST /api/eval            — Trigger eval run

Usage (local):
  uvicorn api.main:app --reload --port 8080

Usage (Docker):
  docker compose up api
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
import time
import uuid
import tempfile
import traceback
from datetime import datetime
from typing import Optional, AsyncGenerator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="CIS AgentOps API",
    description="Adventure Asia Content Intelligence System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory run store ────────────────────────────────────────────────────────

_runs: dict[str, dict] = {}      # run_id → run state
_run_events: dict[str, list] = {}  # run_id → list of SSE events


def _emit(run_id: str, event: str, data: dict):
    """Append an SSE event to the run's event queue."""
    if run_id not in _run_events:
        _run_events[run_id] = []
    _run_events[run_id].append({
        "event": event,
        "data": data,
        "ts": time.time(),
    })
    # Also update run state
    if run_id in _runs:
        _runs[run_id]["last_event"] = {"event": event, "data": data}


# ── Request/Response models ────────────────────────────────────────────────────

class TourRunRequest(BaseModel):
    tour_name: str
    destination: str
    duration_days: int
    raw_description: str
    highlights: list[str] = []
    inclusions: list[str] = []
    price_usd: float
    supplier_name: str = "Adventure Asia"


class BatchRunRequest(BaseModel):
    tour_ids: Optional[list[str]] = None  # None = run all from last upload
    upload_id: str


# ── Background pipeline runner ─────────────────────────────────────────────────

def _run_pipeline_sync(run_id: str, tour_input: dict):
    """Runs in a thread via asyncio.to_thread."""
    try:
        from agent.graph import run_pipeline
        from observability.tracer import get_tracer

        _runs[run_id]["status"] = "running"
        _emit(run_id, "started", {"tour": tour_input.get("tour_name"), "run_id": run_id})

        # Monkey-patch stage emit into tracer
        # We capture stage transitions by wrapping the graph
        class _PatchedGraph:
            def __init__(self, graph):
                self._g = graph

            def invoke(self, state, config):
                return self._g.invoke(state, config)

        # Run with event callbacks via LangGraph streaming
        from agent.graph import build_graph
        graph = build_graph()

        import sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver

        initial = {
            "tour_input": tour_input,
            "seo_context": None,
            "rag_context": None,
            "generated_content": None,
            "validation_result": None,
            "regeneration_count": 0,
            "hitl_approved": None,
            "export_id": None,
            "trace_id": run_id,
            "stage_timings": {},
            "total_cost_usd": 0.0,
            "messages": [],
        }

        config = {"configurable": {"thread_id": run_id}}

        # Stream events from LangGraph
        for chunk in graph.stream(initial, config=config, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                if node_name == "__end__":
                    continue
                _emit(run_id, "node_complete", {
                    "node": node_name,
                    "timings": node_output.get("stage_timings", {}),
                    "cost": node_output.get("total_cost_usd", 0),
                })

        # Get final state
        final = graph.get_state(config).values

        # Build summary
        gc = final.get("generated_content") or {}
        vr = final.get("validation_result") or {}
        result = {
            "run_id": run_id,
            "tour_name": tour_input.get("tour_name"),
            "destination": tour_input.get("destination"),
            "status": "complete",
            "quality_score": vr.get("quality_score", 0),
            "model_used": gc.get("model_used"),
            "cost_usd": final.get("total_cost_usd", 0),
            "export_id": final.get("export_id"),
            "stage_timings": final.get("stage_timings", {}),
            "generated": {
                "title": gc.get("title"),
                "tagline": gc.get("tagline"),
                "description": gc.get("description"),
                "highlights": gc.get("highlights", []),
                "seo_meta_title": gc.get("seo_meta_title"),
                "seo_meta_description": gc.get("seo_meta_description"),
            },
            "validation": {
                "passed": len(vr.get("passed_rules", [])),
                "failed": len(vr.get("failed_rules", [])),
                "failed_rules": vr.get("failed_rules", [])[:5],
                "quality_score": vr.get("quality_score", 0),
            },
            "raw_input": {
                "description": tour_input.get("raw_description", "")[:500],
            },
        }

        _runs[run_id].update({"status": "complete", "result": result})
        _emit(run_id, "complete", result)

    except Exception as e:
        tb = traceback.format_exc()
        _runs[run_id].update({"status": "error", "error": str(e)})
        _emit(run_id, "error", {"error": str(e), "traceback": tb[:500]})


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/upload")
async def upload_excel(file: UploadFile = File(...)):
    """
    Upload Excel file, validate schema, return parsed tours.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only .xlsx / .xls files are supported")

    contents = await file.read()
    upload_id = str(uuid.uuid4())[:8]

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    from agent.nodes.ingestion import validate_excel
    result = validate_excel(tmp_path)

    os.unlink(tmp_path)

    # Store for batch runs
    _runs[f"upload_{upload_id}"] = {
        "upload_id": upload_id,
        "filename": file.filename,
        "tours": result.get("tours", []),
        "created_at": datetime.utcnow().isoformat(),
    }

    return {
        "upload_id": upload_id,
        "filename": file.filename,
        "valid": result["valid"],
        "summary": result["summary"],
        "col_map": result.get("col_map", {}),
        "missing_required": result.get("missing_required", []),
        "tour_count": len(result.get("tours", [])),
        "row_errors": result.get("row_errors", [])[:20],
        "tours_preview": result.get("tours", [])[:3],  # first 3 for preview
    }


@app.post("/api/run")
async def run_single(req: TourRunRequest, background_tasks: BackgroundTasks):
    """Start pipeline for a single tour. Returns run_id immediately."""
    run_id = str(uuid.uuid4())[:12]
    tour_input = req.model_dump()

    _runs[run_id] = {
        "run_id": run_id,
        "status": "queued",
        "tour_name": req.tour_name,
        "destination": req.destination,
        "created_at": datetime.utcnow().isoformat(),
    }
    _run_events[run_id] = []

    background_tasks.add_task(
        asyncio.get_event_loop().run_in_executor,
        None,
        _run_pipeline_sync,
        run_id,
        tour_input,
    )

    return {"run_id": run_id, "status": "queued"}


@app.post("/api/batch")
async def run_batch(req: BatchRunRequest, background_tasks: BackgroundTasks):
    """Start pipeline for all tours from an upload."""
    upload_key = f"upload_{req.upload_id}"
    upload = _runs.get(upload_key)
    if not upload:
        raise HTTPException(404, f"Upload '{req.upload_id}' not found")

    tours = upload.get("tours", [])
    if req.tour_ids:
        tours = [t for t in tours if t.get("tour_name") in req.tour_ids]

    run_ids = []
    for tour in tours:
        run_id = str(uuid.uuid4())[:12]
        _runs[run_id] = {
            "run_id": run_id,
            "status": "queued",
            "tour_name": tour.get("tour_name"),
            "destination": tour.get("destination"),
            "created_at": datetime.utcnow().isoformat(),
            "batch_upload_id": req.upload_id,
        }
        _run_events[run_id] = []
        background_tasks.add_task(
            asyncio.get_event_loop().run_in_executor,
            None,
            _run_pipeline_sync,
            run_id,
            tour,
        )
        run_ids.append(run_id)

    return {"run_ids": run_ids, "total": len(run_ids), "status": "queued"}


@app.get("/api/run/{run_id}")
def get_run(run_id: str):
    """Get run status and result."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, f"Run '{run_id}' not found")
    return run


@app.get("/api/run/{run_id}/stream")
async def stream_run(run_id: str):
    """
    SSE stream — client receives real-time events as the pipeline progresses.
    Connect with: EventSource('/api/run/{run_id}/stream')
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        sent_idx = 0
        timeout = 300  # 5 min max
        start = time.time()

        while time.time() - start < timeout:
            events = _run_events.get(run_id, [])
            while sent_idx < len(events):
                ev = events[sent_idx]
                yield f"event: {ev['event']}\ndata: {json.dumps(ev['data'])}\n\n"
                sent_idx += 1

            run = _runs.get(run_id, {})
            if run.get("status") in ("complete", "error"):
                yield "event: done\ndata: {}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/runs")
def list_runs(limit: int = 20):
    """List recent pipeline runs."""
    runs = [
        v for k, v in _runs.items()
        if not k.startswith("upload_") and isinstance(v, dict)
    ]
    runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return {"runs": runs[:limit], "total": len(runs)}


@app.get("/api/tours")
def list_tours(limit: int = 50):
    """List published tours from PostgreSQL."""
    try:
        import psycopg2
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        cur.execute("""
            SELECT id, tour_name, destination, title, tagline,
                   quality_score, model_used, cost_usd, is_active, created_at
            FROM published_tours
            WHERE is_active = true
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM published_tours WHERE is_active=true")
        total = cur.fetchone()[0]
        cur.close(); conn.close()
        return {"tours": rows, "total": total}
    except Exception as e:
        return {"tours": [], "total": 0, "error": str(e)}


@app.get("/api/tours/{tour_id}")
def get_tour(tour_id: str):
    """Get full tour content by ID."""
    try:
        import psycopg2
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        cur.execute("SELECT * FROM published_tours WHERE id = %s", (tour_id,))
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            raise HTTPException(404, "Tour not found")
        return dict(zip(cols, row))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/stats")
def get_stats():
    """Dashboard stats."""
    runs = [v for k, v in _runs.items() if not k.startswith("upload_")]
    completed = [r for r in runs if r.get("status") == "complete"]
    scores = [r.get("result", {}).get("quality_score", 0) for r in completed if r.get("result")]
    costs = [r.get("result", {}).get("cost_usd", 0) for r in completed if r.get("result")]

    return {
        "total_runs": len(runs),
        "completed": len(completed),
        "running": len([r for r in runs if r.get("status") == "running"]),
        "errors": len([r for r in runs if r.get("status") == "error"]),
        "avg_quality_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "total_cost_usd": round(sum(costs), 4),
        "avg_cost_per_tour": round(sum(costs) / len(costs), 4) if costs else 0,
    }


@app.get("/api/eval/latest")
def get_latest_eval():
    """Get the most recent eval run results."""
    import glob
    files = sorted(glob.glob("eval/results/run_*.json"))
    if not files:
        return {"available": False, "message": "No eval runs yet. Run: python -m eval.run_eval run"}
    with open(files[-1]) as f:
        data = json.load(f)
    return {"available": True, "file": files[-1], **data}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8080, reload=True)
