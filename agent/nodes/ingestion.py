"""
CIS AgentOps — Ingestion Node
Validates Excel/dict input against TourInput schema before pipeline entry.

Excel required columns (accepts aliases):
  tour_name   | name
  destination | country
  duration    | duration_days
  raw_description | summary | description
  price_usd   | price
  highlights  (optional, comma-separated)
  inclusions  (optional, comma-separated)
  supplier_name (optional, default: 'Adventure Asia')

Returns IngestionResult with valid tours + row-level errors.
"""
from __future__ import annotations
import re
import time
from typing import Optional
from agent.state import CISState, TourInput
from observability.tracer import get_tracer

# ── Schema definition ──────────────────────────────────────────────────────

REQUIRED_COLUMNS = {
    "tour_name":        ["tour_name", "name", "title", "tour"],
    "destination":      ["destination", "country", "location", "region"],
    "duration_days":    ["duration_days", "duration", "days", "nights"],
    "raw_description":  ["raw_description", "summary", "description", "overview", "content"],
    "price_usd":        ["price_usd", "price", "cost", "rate"],
}

OPTIONAL_COLUMNS = {
    "highlights":    ["highlights", "key_highlights", "features"],
    "inclusions":    ["inclusions", "included", "includes"],
    "supplier_name": ["supplier_name", "supplier", "operator", "company"],
}

MIN_DESCRIPTION_WORDS = 20
MAX_DESCRIPTION_WORDS = 2000
MIN_PRICE = 0
MAX_PRICE = 500_000
MIN_DURATION = 1
MAX_DURATION = 365


# ── Column detection ────────────────────────────────────────────────────────

def _find_column(row: dict, aliases: list[str]) -> Optional[str]:
    """Find the first matching column alias in row keys."""
    row_lower = {k.lower().strip().replace(" ", "_"): k for k in row}
    for alias in aliases:
        if alias in row_lower:
            return row_lower[alias]
    return None


def _detect_column_map(headers: list[str]) -> dict:
    """Map logical field names to actual column names in the file."""
    header_dict = {h: h for h in headers}
    col_map = {}
    for field, aliases in {**REQUIRED_COLUMNS, **OPTIONAL_COLUMNS}.items():
        matched = _find_column(header_dict, aliases)
        if matched:
            col_map[field] = matched
    return col_map


# ── Row validation ──────────────────────────────────────────────────────────

def _parse_duration(raw: str) -> Optional[int]:
    """Parse '11 days / 10 nights', '7', '3-day' → int."""
    if not raw:
        return None
    s = str(raw).strip()
    # Try direct int
    if s.isdigit():
        return int(s)
    # Extract first number
    match = re.search(r"(\d+)", s)
    return int(match.group(1)) if match else None


def _parse_price(raw) -> Optional[float]:
    """Parse '$3,400', '3400', '3400.00' → float."""
    if raw is None or str(raw).strip() == "":
        return None
    s = str(raw).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _parse_list(raw) -> list[str]:
    """Parse comma/newline separated string → list."""
    if not raw:
        return []
    s = str(raw)
    # Split on comma or newline
    parts = re.split(r"[,\n]+", s)
    return [p.strip() for p in parts if p.strip()]


def validate_row(row: dict, col_map: dict, row_num: int) -> tuple[Optional[TourInput], list[str]]:
    """
    Validate a single data row.
    Returns (TourInput, []) on success or (None, [errors]) on failure.
    """
    errors = []

    def get(field, default=None):
        col = col_map.get(field)
        return row.get(col, default) if col else default

    # ── Required fields ────────────────────────────────────────────────────
    tour_name = str(get("tour_name", "")).strip()
    if not tour_name:
        errors.append(f"Row {row_num}: 'tour_name' is empty or missing")

    destination = str(get("destination", "")).strip()
    if not destination:
        errors.append(f"Row {row_num}: 'destination' is empty or missing")

    raw_dur = get("duration_days", "")
    duration_days = _parse_duration(raw_dur)
    if duration_days is None:
        errors.append(f"Row {row_num}: 'duration' could not be parsed from '{raw_dur}'")
    elif not (MIN_DURATION <= duration_days <= MAX_DURATION):
        errors.append(f"Row {row_num}: duration {duration_days} out of range [{MIN_DURATION}-{MAX_DURATION}]")

    raw_desc = str(get("raw_description", "")).strip()
    if not raw_desc:
        errors.append(f"Row {row_num}: 'description/summary' is empty or missing")
    else:
        word_count = len(raw_desc.split())
        if word_count < MIN_DESCRIPTION_WORDS:
            errors.append(f"Row {row_num}: description too short ({word_count} words, min {MIN_DESCRIPTION_WORDS})")
        elif word_count > MAX_DESCRIPTION_WORDS:
            errors.append(f"Row {row_num}: description too long ({word_count} words, max {MAX_DESCRIPTION_WORDS})")

    raw_price = get("price_usd")
    price_usd = _parse_price(raw_price)
    if price_usd is None:
        errors.append(f"Row {row_num}: 'price_usd' could not be parsed from '{raw_price}'")
    elif not (MIN_PRICE <= price_usd <= MAX_PRICE):
        errors.append(f"Row {row_num}: price ${price_usd:,.0f} out of range")

    if errors:
        return None, errors

    # ── Optional fields ────────────────────────────────────────────────────
    highlights = _parse_list(get("highlights"))
    inclusions = _parse_list(get("inclusions"))
    supplier_name = str(get("supplier_name", "Adventure Asia")).strip() or "Adventure Asia"

    tour_input: TourInput = {
        "tour_name":       tour_name,
        "destination":     destination,
        "duration_days":   duration_days,
        "raw_description": raw_desc,
        "highlights":      highlights,
        "inclusions":      inclusions,
        "price_usd":       price_usd,
        "supplier_name":   supplier_name,
    }
    return tour_input, []


# ── Excel file validation ───────────────────────────────────────────────────

def validate_excel(filepath: str) -> dict:
    """
    Validate an uploaded Excel file.

    Returns:
    {
        "valid": bool,
        "col_map": dict,
        "missing_required": list[str],
        "tours": list[TourInput],   # valid rows
        "row_errors": list[str],    # row-level error messages
        "summary": str,
    }
    """
    try:
        import openpyxl
    except ImportError:
        return {"valid": False, "summary": "openpyxl not installed. Run: pip install openpyxl"}

    try:
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    except Exception as e:
        return {"valid": False, "summary": f"Cannot open file: {e}"}

    # Find sheet — prefer 'Golden Tours', else first sheet
    sheet_name = wb.sheetnames[0]
    for name in wb.sheetnames:
        if any(kw in name.lower() for kw in ["tour", "data", "main", "golden"]):
            sheet_name = name
            break
    ws = wb[sheet_name]

    # Read headers from row 1
    headers = []
    for cell in ws[1]:
        val = cell.value
        headers.append(str(val).strip() if val is not None else "")
    headers = [h for h in headers if h]  # drop empty

    if not headers:
        return {"valid": False, "summary": "No header row found in the Excel file"}

    col_map = _detect_column_map(headers)

    # Check all required columns are mapped
    missing_required = [
        field for field in REQUIRED_COLUMNS
        if field not in col_map
    ]
    if missing_required:
        return {
            "valid": False,
            "col_map": col_map,
            "missing_required": missing_required,
            "tours": [],
            "row_errors": [],
            "summary": f"Missing required columns: {', '.join(missing_required)}. "
                       f"Found headers: {', '.join(headers[:10])}",
        }

    # Validate rows
    tours = []
    row_errors = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        # Skip completely empty rows
        if all(v is None or str(v).strip() == "" for v in row):
            continue

        row_dict = dict(zip(headers, [v for v, _ in zip(row, headers)]))
        tour, errors = validate_row(row_dict, col_map, row_idx)

        if tour:
            tours.append(tour)
        else:
            row_errors.extend(errors)

    valid = len(tours) > 0 and len(row_errors) == 0

    summary = (
        f"{len(tours)} valid tours"
        + (f", {len(row_errors)} row errors" if row_errors else "")
        + f" from '{sheet_name}' sheet"
    )

    return {
        "valid": valid,
        "col_map": col_map,
        "missing_required": [],
        "tours": tours,
        "row_errors": row_errors,
        "summary": summary,
    }


# ── LangGraph node ──────────────────────────────────────────────────────────

def ingestion_node(state: CISState) -> dict:
    """
    Ingestion node: validates tour_input schema and enriches state.
    This node runs before seo_node as a schema gate.
    Input is already a TourInput dict (set by the caller / API).
    """
    tracer = get_tracer()
    span_id = tracer.start_span(
        trace_id=state["trace_id"],
        name="ingestion",
        input={"tour": state["tour_input"].get("tour_name", "unknown")},
    )

    start = time.time()
    tour = state["tour_input"]
    errors = []

    # Validate all required fields present and non-empty
    for field in ["tour_name", "destination", "duration_days", "raw_description", "price_usd"]:
        val = tour.get(field)
        if val is None or str(val).strip() == "":
            errors.append(f"'{field}' is required")

    # Type coercion + range checks
    try:
        dur = int(tour.get("duration_days", 0))
        if not (MIN_DURATION <= dur <= MAX_DURATION):
            errors.append(f"duration_days {dur} out of range")
    except (TypeError, ValueError):
        errors.append("duration_days must be an integer")

    try:
        price = float(tour.get("price_usd", 0))
        if price < MIN_PRICE:
            errors.append(f"price_usd {price} cannot be negative")
    except (TypeError, ValueError):
        errors.append("price_usd must be a number")

    desc = str(tour.get("raw_description", ""))
    wc = len(desc.split())
    if wc < MIN_DESCRIPTION_WORDS:
        errors.append(f"raw_description too short ({wc} words, min {MIN_DESCRIPTION_WORDS})")

    elapsed_ms = (time.time() - start) * 1000
    timings = dict(state.get("stage_timings", {}))
    timings["ingestion"] = elapsed_ms

    tracer.end_span(span_id, output={
        "valid": len(errors) == 0,
        "errors": errors,
        "elapsed_ms": elapsed_ms,
    })

    if errors:
        # Fail fast — route to HITL with validation error
        return {
            "stage_timings": timings,
            "validation_result": {
                "passed_rules": [],
                "failed_rules": [f"INGESTION: {e}" for e in errors],
                "quality_score": 0.0,
                "needs_hitl": True,
                "regeneration_count": 0,
            },
        }

    return {"stage_timings": timings}
