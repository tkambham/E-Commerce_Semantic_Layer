# Semantic Layer — Project Description

## 1. Overview

This semantic layer sits between a user's natural language question and a refined SQL query ready for execution. It uses an AI-driven orchestration flow to select the right KPI set, then refine a pre-built SQL query using embedded schema context.

---

## 2. Folder Structure

```
semantic_layer/
│
├── AI_SYSTEM_PROMPT.md       ← Instructions for the AI query refinement agent
├── orchestrator.py           ← Python orchestration layer (Steps 2 & 3)
├── PROJECT_DESCRIPTION.md    ← This file
│
├── schema_filters.json       ← KPI sets: descriptions, KPIs, base queries, table context
└── schema.json               ← Full DB schema (single source of truth)
```

---

## 3. Step-by-Step Flow

```
User
│
│  "Show me revenue and order count for Q1 2025"
▼
orchestrator.py [STEP 2 — KPI Set Selection]
│
│  Loads schema_filters.json
│  Builds a summary of all KPI sets (id, name, description, KPI names)
│  Sends user question + KPI set summaries to Gemini
│  Gemini returns the best-fit kpi_set_id → "revenue_kpis"
│  Loads the full KPI set entry (base_query + table_context + parameters)
▼
orchestrator.py [STEP 3 — Query Refinement]
│
│  Packages: user question + base_query + table_context + parameters + AI_SYSTEM_PROMPT
│  Sends to Gemini for refinement
│  Gemini trims columns, removes unused joins, injects date parameters
▼
Refined SQL Query
│
│  Returned to the calling system
▼
External System [STEP 4 — outside scope]
│
│  Executes query against SQL Server
│  Fetches result set
│  Generates report (chart, table, PDF, etc.)
▼
Report delivered to User
```

---

## 4. schema_filters.json Format

This is the single file that replaces both `report_registry.json` and all domain JSON files. It contains all KPI sets.

### Top-level structure

```json
{
  "kpi_sets": [ ...array of KPI set objects... ]
}
```

### KPI set object fields

| Field | Description |
|---|---|
| `kpi_set_id` | Unique snake_case identifier. Used internally to match AI selection. |
| `kpi_set_name` | Human-readable name of the KPI set. |
| `description` | Plain-English description of what this KPI set covers and when to use it. This is what the AI reads to make its selection. |
| `kpis` | Array of KPI objects, each with a `name` and `description`. |
| `parameters` | Dynamic inputs the AI must inject into the query (dates, filters). |
| `base_query` | Full T-SQL query with ALL relevant columns and joins. The AI trims this down. |
| `table_context` | Embedded table and column descriptions. Replaces domain JSON files. |

### Example entry (abbreviated)

```json
{
  "kpi_set_id": "revenue_kpis",
  "kpi_set_name": "Revenue KPIs",
  "description": "Covers total sales, order count, revenue by period...",
  "kpis": [
    { "name": "Total Revenue", "description": "Sum of all order totals." }
  ],
  "parameters": [
    { "name": "start_date", "type": "date", "required": true, "description": "Start of the reporting period." }
  ],
  "base_query": "SELECT o.orderId, o.orderTotal, ... FROM Orders o JOIN ...",
  "table_context": {
    "Orders": {
      "table_comment": "Core orders table. Each row is one order.",
      "columns": {
        "orderId": "Unique order identifier. Primary key.",
        "orderTotal": "Total monetary value of the order."
      }
    }
  }
}
```

---

## 5. schema.json

A single JSON file containing the full database schema — all tables, columns, data types, keys, and relationships. This is the master reference for the database structure. It does not drive the orchestration flow directly but serves as the source of truth when building or updating KPI sets in `schema_filters.json`.

---

## 6. orchestrator.py Responsibilities

`orchestrator.py` is the bridge between the user's intent and the AI's query refinement. It handles Steps 2 and 3 only.

### Step 2 — AI-driven KPI Set Selection
- Loads `schema_filters.json`
- Builds a lightweight summary of all KPI sets (id, name, description, KPI names)
- Sends the user question + summary to Gemini (`gemini-2.0-flash`)
- Gemini returns the `kpi_set_id` of the best-fit set
- Loads the full KPI set entry

### Step 3 — Query Refinement
- Packages the base query + embedded `table_context` + user question + `AI_SYSTEM_PROMPT`
- Sends to Gemini for refinement
- Returns the refined SQL query to the calling system

### What orchestrator.py does NOT do
- Execute SQL queries
- Connect to the database
- Generate or render reports
- Handle user authentication or session management

---

## 7. AI_SYSTEM_PROMPT.md Purpose

Contains model-agnostic instructions for the query refinement agent. Tells the AI to trim the base query, inject parameters, preserve join integrity, and return only valid T-SQL. Used in Step 3 only.

---

## 8. Key Design Decisions

| Decision | Rationale |
|---|---|
| AI-driven KPI set selection | More flexible than keyword matching — handles varied phrasing and intent without maintaining keyword lists. |
| KPI sets replace report_registry + domain files | Single file per concern. Keeps base query, KPIs, and table context co-located. Easier to maintain. |
| Table context embedded in KPI set | The AI only receives context for tables relevant to the selected KPI set — reduces noise and token usage. |
| Base queries include ALL columns | Ensures no relevant data is missed. The AI trims down rather than guessing what to add. |
| schema.json as master DB reference | Single source of truth for the full schema. Used when authoring or updating KPI sets, not at runtime. |
| orchestrator.py handles Steps 2 & 3 only | Keeps the semantic layer decoupled from execution. Any query runner can plug in. |
