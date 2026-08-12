# Build Plan & Resume

## Tech stack (default, swappable)

- **Language**: Python — low-friction choice for regex-heavy SMS parsing, DB access, and LLM API calls all in one codebase.
- **DB**: SQLite for a single-user local project; swap to Postgres only if this is ever deployed for multiple users.
- **LLM**: Claude API (or any OpenAI-compatible endpoint) — the prompts in `nl-query-and-grounding.md` don't depend on provider-specific features.
- **Externalize prompts**: keep both prompt templates in their own files, not inline strings scattered through the code — makes iterating on and diffing changes to them far easier, and it's a small thing that reads well in a code review or interview.

## Build order (8 weeks, adjust to actual pace)

Ingestion (weeks 1-2) and the AI query layer (weeks 3-6) are sequenced so the query layer isn't blocked waiting on real SMS/AA access — see `ingestion.md`'s synthetic-data-first approach. If AA sandbox approval or SMS export takes longer than expected, that's fine: weeks 3+ proceed on synthetic data regardless, and real ingestion output gets swapped in whenever it's ready since both feed the identical `transactions` schema.

1. **Week 1 — schema + synthetic data + SMS parsing.** `transactions` + `merchant_aliases` tables built (see `architecture-and-schema.md`). Write the synthetic data generator so weeks 3+ are never blocked. Start SMS parsing against 2-3 real sender formats from your own message history (see `ingestion.md`). Done when: the schema is finalized and synthetic data is flowing into it.
2. **Week 2 — AA/Setu sandbox integration.** Sandbox signup, consent flow, FI data fetch, decrypt, map into the schema. This is usually the slowest week because of external setup (sandbox approval, reading Setu's docs) — don't let it block week 3 from starting on synthetic data in parallel. Done when: at least one real sandbox transaction fetch round-trips into `transactions` successfully.
3. **Week 3 — normalization.** Merchant alias table populated (regex-first, LLM-fallback-batched per `architecture-and-schema.md`), category taxonomy assigned across whatever data exists so far (synthetic + real). Done when: querying the DB directly with hand-written SQL gives correct answers to a handful of questions.
4. **Week 4 — NL → IR.** Prompt 1, few-shot examples, manual testing against ~10 questions. Done when: IR output is syntactically valid JSON matching the schema for every test question (correctness comes later — this week is about the pipe not being broken).
5. **Week 5 — execution & grounding.** IR → SQL builder, prompt 2, the `verify_grounded` check and templated fallback. Done when: end-to-end, a question produces a correctly-grounded answer for the easy cases.
6. **Week 6 — eval harness.** Build the 20-question benchmark, compute ground truth, run the three metrics, iterate on whichever prompt the numbers point at. Done when: there's a real accuracy number worth stating out loud.
7. **Week 7 — swap in real data, re-validate.** If weeks 3-6 were developed against synthetic data, re-run the eval benchmark against real (SMS + AA) transactions now that ingestion is solid. Real data usually surfaces normalization gaps synthetic data didn't (inconsistent merchant strings, SMS formats the parser missed) — expect to go back and add a few more `merchant_aliases` rows or regex patterns.
8. **Week 8 — polish + write-up.** README, resume bullet, optional stretch (proactive weekly insight summary).

## Resume bullet templates

One project, but it's worth two bullets if space allows — the ingestion/pipeline work and the AI query layer are genuinely different skills and both are worth surfacing separately rather than burying ingestion as a footnote to the AI part:

> Built an end-to-end personal expense tracker from scratch: SMS parsing (regex + LLM-fallback extraction) and Account Aggregator (Setu Bridge sandbox) integration feeding a normalized transaction pipeline with automated merchant/category classification.

> Built a natural-language query engine on top of that pipeline, translating free-form questions into structured queries via a constrained JSON intermediate representation and grounding LLM-generated answers strictly in retrieved data; achieved [X]% field accuracy and [Y]% numeric accuracy on a 20-question benchmark, with hallucination rate under [Z]%.

Fill in the real numbers once week 6 is done — don't round up or guess.

Single-bullet variant if space is tight:

> Designed and built an AI-powered expense tracker from scratch — SMS + Account Aggregator ingestion feeding a natural-language query engine with a constrained-schema query layer and an anti-hallucination grounding check; evaluated on a 20-question benchmark achieving [X]%+ accuracy.

## Likely interview questions (and where the answer lives)

- *"Why not just have the LLM write SQL directly?"* → injection risk, and an unbounded output space is much harder to eval than a fixed IR schema. See "Why this design" in `SKILL.md` and the IR schema in `nl-query-and-grounding.md`.
- *"How do you stop it from hallucinating numbers?"* → the grounding prompt + `verify_grounded` post-hoc numeric check + templated fallback. Walk through the actual function.
- *"How did you evaluate it?"* → the two-metric split (IR accuracy vs numeric/grounding accuracy) and why ground truth was computed via direct SQL, not eyeballed.
- *"How did you handle SMS parsing across different banks?"* → be honest about the scope: 2-3 real sender formats via regex, LLM-fallback batching for the rest, explicitly not a universal parser. Explaining *why* that scope is reasonable for a solo project (see `ingestion.md`) reads as good judgment, not as a gap.
- *"Why sandbox AA and not production?"* → production FIU registration is a regulatory/business process, not an engineering task solvable in a portfolio project timeline. Sandbox demonstrates the same integration mechanics (consent flow, encrypted fetch, data mapping) without pretending to be something it isn't.
- *"What was the hardest part?"* → honest answer is almost certainly either date-range ambiguity, merchant normalization, or getting the AA consent flow working end-to-end for the first time — all have a concrete design decision documented in the relevant reference file worth being able to explain, not just wave at.