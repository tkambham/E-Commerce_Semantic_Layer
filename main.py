import os
import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import google.generativeai as genai

from orchastrator import orchestrate

# ── Bootstrap ─────────────────────────────────────────────────

load_dotenv()

# Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
gemini = genai.GenerativeModel("gemini-2.0-flash")

# SQLAlchemy engine (SQL Server via pyodbc)
_conn_str = (
    f"mssql+pyodbc://{os.getenv('DB_USERNAME')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_SERVER')}/{os.getenv('DB_DATABASE')}"
    f"?driver={os.getenv('DB_DRIVER', 'ODBC+Driver+17+for+SQL+Server')}"
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
    response = gemini.generate_content(prompt)
    raw = response.text.strip().strip("```json").strip("```").strip()
    parsed = json.loads(raw)
    return parsed.get("type", "table"), parsed.get("config", {})


# ── Query execution ───────────────────────────────────────────

def run_query(sql: str) -> tuple[list[str], list[list[Any]]]:
    """Execute the refined SQL and return (columns, rows)."""
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchall()]
    return columns, rows


# ── Endpoint ──────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Accept a natural language question.
    Returns: table data (columns + rows) and the best visualization type.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Step 1 + 2: orchestrate (KPI selection + SQL refinement)
    try:
        result = orchestrate(request.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(e)}")

    refined_sql   = result["refined_query"]
    kpi_set_id    = result["kpi_set_id"]
    kpi_set_name  = result["kpi_set_name"]

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
    except Exception:
        # Non-fatal: fall back to table if visualization selection fails
        viz_type, viz_config = "table", {}

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
    return {"status": "ok"}