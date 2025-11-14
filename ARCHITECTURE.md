# Architecture Overview

This project is a CLI-first incident-analysis pipeline that orchestrates multiple Gemini agents, deterministic tools, and a shared conversation state to transform noisy production logs into executive-ready reports.

                 ┌────────────────────────────┐
                 │          User CLI          │
                 │  Typer + Rich (main.py)    │
                 └──────────────┬─────────────┘
                                │
                                ▼
                     ┌──────────────────────┐
                     │  Orchestrator Engine │
                     │  (engine.py)         │
                     ├──────────┬───────────┤
                     │ToolRouter│State Mgmt │
                     └────┬─────┴─────┬─────┘
                          │           │
          ┌───────────────▼───┐   ┌───▼──────────────┐
          │ Analyzer Agent    │   │ Critic Agent     │
          │ (Gemini client)   │   │ (Gemini client)  │
          └────────────┬──────┘   └──────┬───────────┘
                       │                │
                       │ LLM Calls      │
                       │                │
                 ┌─────▼────────────────▼─────┐
                 │      Gemini API (SDK)      │
                 └─────┬────────────────┬─────┘
                       │                │
         ┌─────────────▼───┐     ┌──────▼───────────┐
         │ parse_logs tool │     │ grep_error tool  │
         │ (log parsing)   │     │ (code search)    │
         └─────────────────┘     └──────────────────┘


---

## Core Components

- **CLI / UX**  
  `src/orchestrator/main.py` (Typer + Rich). Handles argument parsing, validates files/config, streams live events, and renders summary/metrics tables.

- **Orchestrator**  
  `src/orchestrator/engine.py`, `state.py`, `tool_router.py`. Coordinates chunking/redaction, ConversationState, multi-round Analyzer→Critic loop, and tool routing with event hooks.

- **Agents**  
  `src/agents/base.py`, `analyzer.py`, `critic.py` (plus prompt markdown). Analyzer drafts hypotheses and tool plans; Critic challenges them, optionally calls tools, and produces the final markdown report.

- **Tools**  
  `src/tools/parse_logs.py`, `src/tools/grep_error.py`, `src/utils/chunking.py`, `src/utils/redaction.py`. Deterministic helpers for structured log parsing, clustering, PII scrubbing, and contextual code search.

- **Vendors**  
  `src/vendors/genai_sdk_client.py`, `gemini_client_rest.py`. Gemini SDK and REST clients providing JSON-only output, tool/function calling, and token accounting.

- **Outputs & Config**  
  `src/config/settings.yaml`, `out/`. YAML controls model/limits/pricing; the pipeline emits markdown reports, metrics JSON (timings/tokens/cost), and raw conversation transcripts.

---

## Data Flow

1. **Input Validation** – CLI ensures the log file and referenced code files exist, then loads `settings.yaml` (or a user-specified config).
2. **Log Preparation** – Engine reads raw logs, runs `parse_logs` to build structured entries, groups by request IDs/error clusters, and selects the most relevant chunk via `select_best_chunk`. Sensitive strings are scrubbed with `redact_logs`.
3. **Context Assembly** – Code snippets are trimmed to stay under the configured char limit and added to the conversation context alongside a concise log summary (counts, sample errors, chunk metadata).
4. **Multi-Round Reasoning**  
   - Analyzer receives the conversation history, proposes a hypothesis (`Hypothesis` model), optional assumptions/questions, and optional tool calls (e.g., `grep_error`).  
   - Any requested tools execute via `ToolRouter`, and results are appended to the conversation history (with truncation to contain token usage).  
   - Critic reviews the updated context, challenges gaps, optionally triggers more tools, and either confirms or requests another round until `min_rounds`/`max_rounds` limits resolve.
5. **Report Generation** – Critic’s final markdown report plus Analyzer’s structured hypothesis feed into `IncidentReport`. Validation ensures minimum evidence quality. Timings, token usage, conversation logs, and cost estimates are persisted to `out/`.

---

## Observability & Safety

- **Conversation Traceability** – Every agent/tool message is stored in `ConversationState`, exported as JSON, and optionally streamed live using Rich for demos.
- **Token & Cost Metrics** – Gemini clients expose usage counts that are aggregated into the metrics JSON file with cost estimation based on config.
- **PII Protection** – Redaction patterns cover emails, API keys, tokens, credit cards, etc., before data reaches Gemini.
- **Confidence Thresholds** – Pipeline enforces configurable `min_confidence`/`critical_confidence`; low-confidence runs emit warnings in metrics for human review.

---

## Extensibility Hooks

- Add more tools by dropping new functions under `src/tools/`, registering them in `ToolRouter`, and updating `config/tool_schemas.json`.
- Swap to REST backend by setting `gemini.backend` to `"rest"`; both clients share the same interface defined in `LLMClient`.
- Plug different front ends (e.g., Streamlit, Slack bot) by reusing `run_pipeline` while replacing the Typer CLI.

---
