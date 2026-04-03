import os
import json
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from orchastrator import orchestrate
from logger import api_logger, sql_logger, error_logger

# ── Bootstrap ─────────────────────────────────────────────────

load_dotenv()

# Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
gemini = genai.GenerativeModel("gemini-1.5-flash")

def _call_gemini(prompt: str, retries: int = 4, backoff: float = 5.0) -> str:
    for attempt in range(retries):
        try:
            return gemini.generate_content(prompt).text.strip()
        except ResourceExhausted:
            if attempt == retries - 1:
                raise
            wait = backoff * (2 ** attempt)
            print(f"[Gemini] Rate limited. Retrying in {wait:.0f}s... (attempt {attempt + 1}/{retries})")
            time.sleep(wait)
    raise RuntimeError("Gemini call failed after all retries.")

# SQLAlchemy engine (SQL Server via pyodbc)
from urllib.parse import quote_plus

_server   = os.getenv("DB_SERVER", "localhost")
_database = os.getenv("DB_NAME")
_user     = os.getenv("DB_USER")
_password = quote_plus(os.getenv("DB_PASSWORD", ""))  # encodes special chars e.g. @ → %40
_driver   = quote_plus(os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"))

_conn_str = (
    f"mssql+pyodbc://{_user}:{_password}"
    f"@{_server},1433/{_database}"
    f"?driver={_driver}"
    f"&TrustServerCertificate=yes"
    f"&Encrypt=no"
    f"&connection_timeout=30"
)
engine = create_engine(_conn_str, fast_executemany=True)

# ── App ───────────────────────────────────────────────────────

app = FastAPI(title="E-Commerce AI Query API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#Logging

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    api_logger.info(f"REQUEST  | {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        duration = round((time.time() - start_time) * 1000, 2)
        api_logger.info(f"RESPONSE | {request.method} {request.url.path} | status={response.status_code} | {duration}ms")
        return response
    except Exception as e:
        error_logger.exception(f"Unhandled error during {request.method} {request.url.path}: {e}")
        raise

# ── Models ────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    question:       str
    kpi_set_id:     str
    kpi_set_name:   str
    refined_sql:    str
    columns:        list[str]
    rows:           list[list[Any]]
    visualization:  str          # e.g. "bar_chart", "line_chart", "pie_chart", "table"
    visualization_config: dict   # axis / label hints for the frontend

# ── Visualization selector ────────────────────────────────────

_VIZ_PROMPT = """
You are a data visualization advisor.

Given the following context, return a JSON object with exactly two keys:
- "type": one of ["bar_chart", "line_chart", "pie_chart", "area_chart", "scatter_chart", "table"]
- "config": a JSON object with hints for the frontend, containing:
    - "x_axis": column name to use on the x-axis (or null if not applicable)
    - "y_axis": list of column names to plot on the y-axis (or empty list)
    - "label": column name to use as a label/category (or null)
    - "title": a short chart title
    - "reason": one sentence explaining why this visualization fits

Rules:
- Use "line_chart" for time-series or trend data (dates on x-axis).
- Use "bar_chart" for comparing categories or groups.
- Use "pie_chart" only if there are 2–6 slices and the data represents parts of a whole.
- Use "area_chart" for cumulative or volume-over-time data.
- Use "scatter_chart" for correlations between two numeric columns.
- Use "table" when the data is transactional, has many columns, or has no clear visual pattern.
- Return ONLY valid JSON. No markdown, no explanation outside the JSON.

Context:
- User question: {question}
- KPI set: {kpi_set_name}
- Columns returned: {columns}
- Row count: {row_count}
- Sample rows (first 3): {sample_rows}
""".strip()


def select_visualization(
    question: str,
    kpi_set_name: str,
    columns: list[str],
    rows: list[list[Any]],
) -> tuple[str, dict]:
    """Ask Gemini to pick the best visualization for the result set."""
    prompt = _VIZ_PROMPT.format(
        question=question,
        kpi_set_name=kpi_set_name,
        columns=json.dumps(columns),
        row_count=len(rows),
        sample_rows=json.dumps(rows[:3]),
    )
    raw = _call_gemini(prompt).strip("```json").strip("```").strip()
    parsed = json.loads(raw)
    return parsed.get("type", "table"), parsed.get("config", {})


# ── Query execution ───────────────────────────────────────────

def run_query(sql: str) -> tuple[list[str], list[list[Any]]]:
    sql_logger.info(f"EXECUTING SQL:\n{sql}")
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]
        sql_logger.info(f"SQL SUCCESS | rows_returned={len(rows)} | columns={columns}")
        return columns, rows
    except Exception as e:
        error_logger.exception(f"SQL EXECUTION FAILED:\n{sql}\nError: {e}")
        raise


# ── Endpoint ──────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    api_logger.info(f"QUERY RECEIVED | question='{request.question}'")

    if not request.question.strip():
        error_logger.warning("Empty question received.")
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Step 1 + 2: orchestrate (KPI selection + SQL refinement)
    try:
        result = orchestrate(request.question)
        api_logger.info(f"ORCHESTRATION SUCCESS | kpi_set='{result['kpi_set_name']}'")
    except Exception as e:
        error_logger.exception(f"Orchestration failed for question='{request.question}': {e}")
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")

    refined_sql   = result["refined_query"]
    kpi_set_id    = result["kpi_set_id"]
    kpi_set_name  = result["kpi_set_name"]

    # Guard: make sure we actually got SQL back, not a question or explanation
    first_word = refined_sql.strip().split()[0].upper() if refined_sql.strip() else ""
    if first_word not in ("SELECT", "WITH", "EXEC", "DECLARE"):
        error_logger.error(f"Invalid SQL returned by orchestration: {refined_sql[:200]}")
        raise HTTPException(
            status_code=500,
            detail=f"Orchestration returned invalid SQL: {refined_sql[:200]}"
        )

    # Step 3: execute query
    try:
        columns, rows = run_query(refined_sql)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

    # Step 4: pick best visualization
    try:
        viz_type, viz_config = select_visualization(
            question=request.question,
            kpi_set_name=kpi_set_name,
            columns=columns,
            rows=rows,
        )
        api_logger.info(f"VISUALIZATION SELECTED | type='{viz_type}'")
    except Exception:
        # Non-fatal: fall back to table if visualization selection fails
        error_logger.warning("Visualization selection failed. Falling back to table.")
        viz_type, viz_config = "table", {}

    api_logger.info(f"QUERY COMPLETE | question='{request.question}' | rows={len(rows)} | viz='{viz_type}'")
    return QueryResponse(
        question=request.question,
        kpi_set_id=kpi_set_id,
        kpi_set_name=kpi_set_name,
        refined_sql=refined_sql,
        columns=columns,
        rows=rows,
        visualization=viz_type,
        visualization_config=viz_config,
    )


# ── Health check ──────────────────────────────────────────────

@app.get("/health")
async def health():
    api_logger.info("Health check called.")
    return {"status": "ok"}