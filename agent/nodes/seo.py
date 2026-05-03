"""
CIS AgentOps — SEO Intelligence Node
Real DataForSEO API integration:
  - Keywords Data API v3 (search volume + CPC)
  - SERP API v3 (People Also Ask)
  - Redis cache layer (TTL 7 days) to avoid repeat API calls

Set MOCK_SEO=true to use mock data without DataForSEO credentials.
"""
from __future__ import annotations
import os
import json
import time
import hashlib
import logging
import requests
from base64 import b64encode

from agent.state import CISState, SEOContext
from observability.tracer import get_tracer

log = logging.getLogger(__name__)

MOCK_SEO = os.getenv("MOCK_SEO", "false").lower() == "true"
DATAFORSEO_LOGIN = os.getenv("DATAFORSEO_LOGIN", "")
DATAFORSEO_PASSWORD = os.getenv("DATAFORSEO_PASSWORD", "")
DATAFORSEO_BASE = "https://api.dataforseo.com/v3"

# Simple in-process cache (replace with Redis in prod)
_cache: dict = {}
CACHE_TTL = 7 * 24 * 3600  # 7 days


def _cache_key(destination: str, tour_name: str) -> str:
    raw = f"{destination.lower()}:{tour_name.lower()}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_auth_header() -> str:
    creds = b64encode(f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}".encode()).decode()
    return f"Basic {creds}"


def _fetch_keywords(destination: str, tour_name: str) -> tuple[list, int]:
    """
    DataForSEO Keywords Data API — search volume for 5 target keywords.
    Returns (keywords_list, search_volume_for_primary).
    """
    primary_keyword = f"luxury {destination.lower()} tour"
    keywords = [
        primary_keyword,
        f"{destination.lower()} private expedition",
        f"exclusive {destination.lower()} travel",
        f"{tour_name.lower().replace(' ', '-')} tour",
        f"bespoke {destination.lower()} journey",
    ]

    payload = [{
        "keywords": keywords,
        "language_code": "en",
        "location_code": 2840,  # United States
    }]

    try:
        resp = requests.post(
            f"{DATAFORSEO_BASE}/keywords_data/google_ads/search_volume/live",
            headers={
                "Authorization": _get_auth_header(),
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        data = resp.json()
        results = data.get("tasks", [{}])[0].get("result", []) or []

        # Sort by volume descending, return top keywords
        results.sort(key=lambda x: x.get("search_volume") or 0, reverse=True)
        top_keywords = [r["keyword"] for r in results if r.get("keyword")]
        primary_vol = results[0].get("search_volume", 0) if results else 0

        return top_keywords if top_keywords else keywords, primary_vol

    except Exception as e:
        log.warning(f"DataForSEO keywords API error: {e}")
        return keywords, 0


def _fetch_serp_paa(destination: str) -> tuple[list, list]:
    """
    DataForSEO SERP API — People Also Ask + competitor analysis.
    Returns (paa_questions, competitor_angles).
    """
    keyword = f"luxury {destination.lower()} travel"

    payload = [{
        "keyword": keyword,
        "language_code": "en",
        "location_code": 2840,
        "device": "desktop",
        "os": "windows",
        "depth": 10,
    }]

    paa = []
    angles = []

    try:
        resp = requests.post(
            f"{DATAFORSEO_BASE}/serp/google/organic/live/advanced",
            headers={
                "Authorization": _get_auth_header(),
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
        data = resp.json()
        items = data.get("tasks", [{}])[0].get("result", [{}])[0].get("items", []) or []

        for item in items:
            itype = item.get("type", "")
            if itype == "people_also_ask":
                for q in item.get("items", []):
                    if q.get("title"):
                        paa.append(q["title"])
            elif itype == "organic":
                # Extract competitor angle from title
                title = item.get("title", "")
                if title and len(title) > 10:
                    angles.append(title[:80])

        return paa[:5], angles[:4]

    except Exception as e:
        log.warning(f"DataForSEO SERP API error: {e}")
        return [], []


def _real_seo(destination: str, tour_name: str) -> SEOContext:
    """Call real DataForSEO APIs."""
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        raise ValueError("DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD required when MOCK_SEO=false")

    keywords, search_volume = _fetch_keywords(destination, tour_name)
    paa, competitor_angles = _fetch_serp_paa(destination)

    return {
        "keywords": keywords,
        "people_also_ask": paa,
        "search_volume": search_volume,
        "competitor_angles": competitor_angles,
    }


def _mock_seo(destination: str, tour_name: str) -> SEOContext:
    """Mock SEO data — deterministic, no API calls."""
    dest_lower = destination.lower()
    return {
        "keywords": [
            f"luxury {dest_lower} tour",
            f"{dest_lower} private expedition",
            f"exclusive {dest_lower} travel",
            f"{tour_name.lower()} experience",
            f"bespoke {dest_lower} journey",
        ],
        "people_also_ask": [
            f"What is the best time to visit {destination}?",
            f"How much does a luxury tour of {destination} cost?",
            f"What makes {destination} unique for discerning travelers?",
        ],
        "search_volume": 2400,
        "competitor_angles": [
            "small group exclusivity",
            "local expert guides",
            "off-the-beaten-path access",
            "private vehicle throughout",
        ],
    }


def seo_node(state: CISState) -> dict:
    tracer = get_tracer()
    span_id = tracer.start_span(
        trace_id=state["trace_id"],
        name="seo-intelligence",
        input={"destination": state["tour_input"]["destination"], "mock": MOCK_SEO},
    )

    start = time.time()
    destination = state["tour_input"]["destination"]
    tour_name = state["tour_input"]["tour_name"]

    # Check in-process cache
    ckey = _cache_key(destination, tour_name)
    if ckey in _cache:
        cached_ts, cached_seo = _cache[ckey]
        if time.time() - cached_ts < CACHE_TTL:
            log.info(f"SEO cache hit for {destination}")
            seo = cached_seo
            source = "cache"
        else:
            del _cache[ckey]
            seo = None
            source = None
    else:
        seo = None
        source = None

    if seo is None:
        if MOCK_SEO:
            seo = _mock_seo(destination, tour_name)
            source = "mock"
        else:
            try:
                seo = _real_seo(destination, tour_name)
                source = "dataforseo"
            except Exception as e:
                log.warning(f"Real SEO failed ({e}), falling back to mock")
                seo = _mock_seo(destination, tour_name)
                source = "mock_fallback"
        _cache[ckey] = (time.time(), seo)

    elapsed_ms = (time.time() - start) * 1000
    timings = dict(state.get("stage_timings", {}))
    timings["seo"] = elapsed_ms

    tracer.end_span(span_id, output={
        "keywords_count": len(seo["keywords"]),
        "paa_count": len(seo["people_also_ask"]),
        "search_volume": seo["search_volume"],
        "source": source,
        "elapsed_ms": elapsed_ms,
    })

    return {"seo_context": seo, "stage_timings": timings}
