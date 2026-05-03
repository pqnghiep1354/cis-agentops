"""CIS AgentOps — Export Node: writes validated content to PostgreSQL."""
from __future__ import annotations
import os
import time
import uuid
import psycopg2
from agent.state import CISState
from observability.tracer import get_tracer

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://cis:cis_local_pass@localhost:5432/cis_local")


def export_node(state: CISState) -> dict:
    tracer = get_tracer()
    span_id = tracer.start_span(
        trace_id=state["trace_id"],
        name="export",
        input={"tour": state["tour_input"]["tour_name"]}
    )
    start = time.time()

    content = state.get("generated_content") or {}
    vr = state.get("validation_result") or {}
    tour = state["tour_input"]
    export_id = str(uuid.uuid4())

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO published_tours (
                id, tour_name, destination, title, tagline, description,
                highlights, seo_meta_title, seo_meta_description,
                quality_score, model_used, cost_usd, is_active
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (tour_name, destination) DO UPDATE SET
                title=EXCLUDED.title,
                tagline=EXCLUDED.tagline,
                description=EXCLUDED.description,
                quality_score=EXCLUDED.quality_score,
                is_active=true
        """, (
            export_id,
            tour["tour_name"],
            tour["destination"],
            content.get("title"),
            content.get("tagline"),
            content.get("description"),
            str(content.get("highlights", [])),
            content.get("seo_meta_title"),
            content.get("seo_meta_description"),
            vr.get("quality_score", 0),
            content.get("model_used"),
            content.get("cost_usd", 0),
            True,
        ))
        conn.commit()
        cur.close()
        conn.close()
        success = True
    except Exception as e:
        export_id = f"ERROR:{str(e)[:50]}"
        success = False

    elapsed_ms = (time.time() - start) * 1000
    timings = dict(state.get("stage_timings", {}))
    timings["export"] = elapsed_ms

    tracer.end_span(span_id, output={"export_id": export_id, "success": success})
    return {"export_id": export_id, "stage_timings": timings}
