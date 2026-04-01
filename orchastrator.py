import os
import json
import time
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR           = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILTERS     = os.path.join(BASE_DIR, "data/schema_filters.json")
SCHEMA_FILE        = os.path.join(BASE_DIR, "data/schema.json")
AI_SYSTEM_PROMPT   = os.path.join(BASE_DIR, "AI_SYSTEM_PROMPT.md")

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.5-flash")

print(model)

# ── Retry helper ──────────────────────────────────────────────

def _call_gemini(prompt: str, retries: int = 4, backoff: float = 5.0) -> str:
    """
    Call Gemini with exponential backoff on 429 rate-limit errors.
    Raises after `retries` failed attempts.
    """
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except ResourceExhausted as e:
            if attempt == retries - 1:
                raise
            wait = backoff * (2 ** attempt)   # 5s, 10s, 20s, 40s
            print(f"[Gemini] Rate limited. Retrying in {wait:.0f}s... (attempt {attempt + 1}/{retries})")
            time.sleep(wait)
    raise RuntimeError("Gemini call failed after all retries.")

# ── Loaders ───────────────────────────────────────────────────────────────────

def load_schema_filters() -> dict:
    with open(SCHEMA_FILTERS, "r", encoding="utf-8") as f:
        return json.load(f)

def load_schema() -> dict:
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_system_prompt() -> str:
    with open(AI_SYSTEM_PROMPT, "r", encoding="utf-8") as f:
        return f.read()

# ── Step 2: AI-driven KPI set selection ──────────────────────────────────────

def select_kpi_set(user_question: str, kpi_sets: list) -> dict:
    """
    Send the user question + all KPI set descriptions to Gemini.
    Gemini returns the kpi_set_id of the best-fit set.
    """
    kpi_index = [
        {
            "kpi_set_id":   s["kpi_set_id"],
            "kpi_set_name": s["kpi_set_name"],
            "description":  s["description"],
            "kpis":         [k["name"] for k in s["kpis"]],
        }
        for s in kpi_sets
    ]

    selection_prompt = f"""
You are a KPI routing agent. Your only job is to pick the single best-fit KPI set for the user's question.

Available KPI sets:
{json.dumps(kpi_index, indent=2)}

User question:
\"{user_question}\"

Rules:
- Return ONLY the kpi_set_id of the best matching set. Nothing else.
- Do not explain your choice.
- Do not return multiple ids.
- If no set clearly matches, return the closest one.
""".strip()

    selected_id = _call_gemini(selection_prompt).strip('"').strip("'")

    matched = next((s for s in kpi_sets if s["kpi_set_id"] == selected_id), None)
    if not matched:
        raise ValueError(
            f"Gemini returned unknown kpi_set_id '{selected_id}'. "
            f"Valid ids: {[s['kpi_set_id'] for s in kpi_sets]}"
        )

    return matched

# ── Step 3: Query refinement ──────────────────────────────────────────────────

def _is_valid_sql(text: str) -> bool:
    """Basic check — a valid response must start with a SQL keyword."""
    t = text.strip().lstrip("```sql").lstrip("```").strip().upper()
    return any(t.startswith(kw) for kw in ("SELECT", "WITH", "EXEC", "DECLARE"))


def refine_query(user_question: str, kpi_set: dict, system_prompt: str) -> str:
    """
    Pass the selected KPI set's base_query + embedded table_context
    to Gemini for query refinement.
    """
    refinement_prompt = f"""
{system_prompt}

---

User question:
\"{user_question}\"

KPI Set: {kpi_set['kpi_set_name']}
KPIs in scope: {json.dumps([k['name'] for k in kpi_set['kpis']], indent=2)}

Base SQL query (trim and refine this — do not rewrite from scratch):
{kpi_set['base_query']}

Table and column context (use this to understand the schema):
{json.dumps(kpi_set['table_context'], indent=2)}

Parameters available:
{json.dumps(kpi_set.get('parameters', []), indent=2)}

Instructions:
- Remove columns and joins not needed for this specific question.
- Inject parameter values extracted from the user question.
- For year-over-year or period comparison questions, use a single query with
  conditional aggregation (e.g. SUM(CASE WHEN YEAR(orderDate) = 2024 THEN ... END))
  so both periods are returned in one result set with clear column aliases.
- Always include a percentage change column when comparing two periods.
- Preserve all JOIN conditions and primary/foreign key columns.
- Return only the final refined T-SQL query. No explanation, no markdown, no questions.
""".strip()

    raw = _call_gemini(refinement_prompt)

    # Strip markdown code fences if Gemini wrapped the SQL
    clean = raw.strip().lstrip("```sql").lstrip("```").rstrip("```").strip()

    if not _is_valid_sql(clean):
        # Gemini returned a question or explanation — force a retry with stricter prompt
        retry_prompt = refinement_prompt + "\n\nCRITICAL: Your last response was not valid SQL. Return ONLY the SQL query, nothing else."
        clean = _call_gemini(retry_prompt).strip().lstrip("```sql").lstrip("```").rstrip("```").strip()
        if not _is_valid_sql(clean):
            raise ValueError(f"Gemini did not return valid SQL after retry. Got: {clean[:200]}")

    return clean

# ── Main orchestration entry point ────────────────────────────────────────────

def orchestrate(user_question: str) -> dict:
    """
    Full orchestration flow:
      1. Load schema_filters.json
      2. AI selects the best-fit KPI set
      3. AI refines the base query using embedded table context
      4. Return the refined query + metadata

    Returns:
        {
            "kpi_set_id":   str,
            "kpi_set_name": str,
            "kpis":         list,
            "refined_query": str
        }
    """
    # Load files
    schema_filters = load_schema_filters()
    system_prompt  = load_system_prompt()
    kpi_sets       = schema_filters["kpi_sets"]

    # Step 2 — AI-driven KPI set selection
    selected_kpi_set = select_kpi_set(user_question, kpi_sets)

    # Step 3 — Query refinement with embedded table context
    refined_query = refine_query(user_question, selected_kpi_set, system_prompt)

    return {
        "kpi_set_id":    selected_kpi_set["kpi_set_id"],
        "kpi_set_name":  selected_kpi_set["kpi_set_name"],
        "kpis":          selected_kpi_set["kpis"],
        "refined_query": refined_query,
    }


# ── CLI usage ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Enter your question: ")
    result = orchestrate(question)
    print("\n── Selected KPI Set ──────────────────────────")
    print(f"ID:   {result['kpi_set_id']}")
    print(f"Name: {result['kpi_set_name']}")
    print(f"KPIs: {', '.join(k['name'] for k in result['kpis'])}")
    print("\n── Refined SQL Query ─────────────────────────")
    print(result["refined_query"])