---
name: expense-nl-query-engine
description: Reference for Akshat's end-to-end AI-powered expense tracker with a natural language query engine, built entirely from scratch — SMS parsing, Account Aggregator (Setu Bridge) integration, transaction normalization, and the two-stage LLM query layer on top. Captures the complete architecture, database schema, ingestion design, the NL-to-structured-query-to-grounded-answer pipeline, anti-hallucination guardrails, evaluation harness, and build/resume plan for this specific project. Consult this whenever building, extending, or debugging this project, reasoning about a design tradeoff in it, prepping for an interview where it will come up, or drafting resume or portfolio copy about it — it holds the actual decisions already made so they don't need to be re-derived from scratch each time.
---

# Expense NL Query Engine

An expense tracker built from zero, where the payoff feature is a natural-language interface over your own transaction data. A user asks something like *"how much did I spend on dining last month?"* or *"what subscriptions can I cancel?"* in plain English, and gets back an answer grounded in real transactions — not an LLM guess.

This is a **full-stack project**: nothing is assumed to exist already. That means real ingestion work (SMS parsing, AA integration) comes before the AI layer, not after — and that ingestion work is exactly the kind of "real engineering underneath the AI" that makes this project credible rather than a thin API wrapper. Don't skip ahead to the LLM parts; the data layer is half the story an interviewer will actually care about.

## Why this design (read before writing any code)

Four decisions shape everything else here, and they're the ones worth being able to defend in an interview:

1. **Ingestion is scoped deliberately small.** A solo, from-scratch build doesn't need to replicate a production fintech pipeline. SMS parsing covers a handful of common bank/UPI sender formats (not every bank in India), and AA integration uses one sandbox FIU flow, not a multi-provider abstraction. Small and working beats broad and half-finished — see `ingestion.md` for exactly how small.

2. **The LLM never generates SQL directly.** It generates a small, fixed JSON object (an "intermediate representation," or IR) describing the query — intent, date range, category, merchant, metric. Plain code then turns that IR into a parameterized query. This is safer (no injection surface, no risk of a malformed or destructive query), and — just as importantly — it's *testable*: you can assert on IR fields directly instead of only on final prose.

3. **The LLM never invents numbers.** The answer-generation step is only ever shown the actual rows/aggregate that came back from the database, is instructed to use only those, and a cheap post-hoc check re-extracts every number in the generated answer and confirms it appears in the retrieved data. If it doesn't, the answer is rejected and rebuilt from a template instead. This single guardrail is what makes the project trustworthy enough to actually use with real money data.

4. **There's an eval set from early on, not bolted on at the end.** A ~24-question benchmark with known-correct answers (computed by running the equivalent query directly against the DB) is what turns "I built an AI expense assistant" into "I built an AI expense assistant that's 90%+ accurate on a 24-query benchmark" — the second one is the resume line and the interview story.

5. **Off-topic refusal and category-mapping transparency are two separate guardrails, not one.** Early testing surfaced a real bug where in-domain questions ("how much did I spend on perfumes?", "how much are all my subscription costs?") returned wrong numbers — not refusals. It was tempting to "fix" this by tightening the off-topic refusal, which would have been the wrong fix entirely: those questions were never off-topic. The actual bug was that the model was forced to always guess a category from the fixed taxonomy with no way to say "this doesn't map cleanly" or "let me tell you I mapped this." The fix added two explicit escape hatches (`category_mapping_note` for a disclosed best-guess mapping, `unmatched_term` for admitting no confident match) instead of one silent forced guess — see `nl-query-and-grounding.md` for the full writeup, since this is exactly the kind of failure mode worth being able to explain precisely in an interview: numeric grounding and question fidelity are different properties, and a system can have one without the other.

## Architecture at a glance

```
Raw SMS inbox export ─┐
                       ├─► [A] Parser → normalizer → transactions table   (see ingestion.md)
AA / Setu sandbox ─────┘
                                          │
                                          ▼
                       User question (NL)
                                          │
                                          ▼
                       [1] NL → structured query IR      (LLM call #1 — see nl-query-and-grounding.md)
                                          │            (includes domain check + category-mapping/unmatched-term handling)
                                          ▼
                       [2] IR → parameterized DB query   (plain code, no LLM — see architecture-and-schema.md)
                                          │            (or subscription recurrence query, or refusal/no-match short-circuit)
                                          ▼
                       [3] Query result (rows / aggregate)
                                          │
                                          ▼
                       [4] Result → grounded NL answer   (LLM call #2 + numeric verification — see nl-query-and-grounding.md)
                                          │            (discloses category mapping when one was made)
                                          ▼
                       Answer shown to user
```

Only [1] and [4] touch an LLM. [A] and [2] are deterministic, ordinary code — keep it that way, since that's the part that's cheap to test exhaustively and the part that shows you can engineer, not just prompt.

## Where to look for what

| Need | Go to |
|---|---|
| Building SMS parsing and AA/Setu integration from zero, sandbox setup, what to scope out | `references/ingestion.md` |
| DB schema, merchant/category normalization, connecting ingestion output to the query layer | `references/architecture-and-schema.md` |
| The structured query IR schema, both prompt templates (with few-shot examples), the anti-hallucination check, the domain-refusal guardrail, category-mapping/unmatched-term handling, ambiguous-date/merchant handling | `references/nl-query-and-grounding.md` |
| Eval harness design, the 4 metrics, a ready-to-use 24-question starter benchmark (includes regression tests for the category-mapping bug) | `references/evaluation.md` |
| Tech stack rationale, week-by-week build order (ingestion included), resume bullet templates, likely interview questions | `references/build-plan-and-resume.md` |
| What real production integration would require beyond the sandbox/synthetic setup — Setu product selection, FIU registration path, compliance, cost | `references/real-data-migration.md` |

## Assumptions baked into this design

- **Language/stack**: examples use Python + SQLite for concreteness, since that's a low-friction choice for parsing-heavy, single-user projects. Nothing here is Python-specific — the IR schema, prompts, and eval format are all just JSON/SQL/text and port directly to Node or anything else. If the real stack differs, only `build-plan-and-resume.md`'s tooling section needs adjusting.
- **LLM provider**: prompts are written provider-agnostic (they'd work against the Claude API or an OpenAI-compatible one). No provider-specific features are assumed.
- **Data source for early development**: real SMS/AA access takes setup time (sandbox approval, real bank SMS history to test against). `ingestion.md` covers building against synthetic/sample data first so the rest of the pipeline isn't blocked waiting on that setup.
- **Scale**: designed for one person's transaction history (thousands, not millions, of rows) — the point is to keep the middle layer (query execution) plain, fast, boring code rather than needing a vector DB or anything exotic. If that assumption changes, revisit before adding infrastructure.

If any of these turn out to be wrong for the actual build, update this section — it's the fastest way for a future session to get back up to speed on what changed and why.
