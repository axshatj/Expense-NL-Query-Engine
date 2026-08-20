# Evaluation

## Philosophy

Grade three things separately, because they fail independently — this expands the original two-way split after a real bug showed a third failure mode neither metric caught:

1. **Did prompt 1 understand the question?** (IR field accuracy) — a wrong category filter is a prompt-1 bug.
2. **Is the final answer numerically grounded in the query result?** (grounding fidelity) — even with a perfect IR, prompt 2 could still misreport a number.
3. **Did the query actually answer the question that was asked?** (question fidelity) — this is the one that was missing. A question like "how much did I spend on perfumes?" can pass both of the above checks — a valid IR gets produced, and the final number is genuinely grounded in real query results — while still being *wrong*, because the model silently substituted "perfumes" for "shopping" without disclosing it. Grounding fidelity only checks that a number came from real data; it says nothing about whether it's data for the right question. Track this separately or this exact class of bug won't show up in the metrics at all.

Reporting only end-to-end accuracy hides which of the three to actually go fix. Reporting only IR and grounding accuracy — the original two-metric design — actively hid the perfumes/subscriptions bug, since both of those checks passed while the answer was still wrong. Track all three.

## Benchmark format

```json
{
  "id": 1,
  "question": "How much did I spend on dining last month?",
  "expected_ir": {
    "intent": "aggregate", "metric": "sum",
    "filters": {"category": ["dining"], "transaction_type": "debit", "exclude_transfers": true}
  },
  "expected_answer_contains": [12450.00],
  "expected_category_mapping_note": null,
  "expected_unmatched_term": null
}
```

`expected_ir` only needs the fields that matter for that question (partial match, not exact-object match — `date_range` will differ run to run since "today" moves). `expected_answer_contains` is computed once by running the equivalent raw SQL directly against the DB — that's the ground truth, not a hand-typed guess. `expected_category_mapping_note` and `expected_unmatched_term` default to `null` and are only set on questions specifically testing the mapping/unmatched paths (see below) — for those, check that the actual IR's field is non-null (a mapping was disclosed) or matches expectation, not exact string equality, since natural phrasing of the note can vary.

## Four metrics

1. **IR field accuracy** — for each question, what fraction of the checked `expected_ir` fields matched? Average across the set.
2. **Numeric accuracy** — does the final NL answer's number(s) match `expected_answer_contains` within a small tolerance?
3. **Hallucination rate** — fraction of answers where `verify_grounded` (see nl-query-and-grounding.md) failed and had to fall back to the template. This should trend toward zero as prompt 2 improves; if it's not near zero, that's the thing to fix before anything else, since it's the trust-breaking failure mode.
4. **Question-fidelity rate** (new) — for the subset of questions that reference a non-taxonomy term (see #23-24 below plus the additional cases), what fraction correctly either (a) disclosed the mapping in the final answer text, or (b) correctly returned the no-match response instead of guessing? A number can be 100% grounded and still fail this metric — that's the point of tracking it separately.

## Starter set (24 questions)

Covers all four intents, both simple and compound filters, off-topic refusal, and — following the real bug found in testing — explicit category-mapping and unmatched-term cases, since those weren't represented in the original 20-question set at all and that gap is exactly why the bug shipped unnoticed.

1. How much did I spend last month?
2. How much did I spend on groceries this month?
3. What's my biggest expense category this year?
4. Compare my spending this month vs last month
5. How much did I spend on Swiggy in the last 3 months?
6. Show me all transactions above ₹5,000 in July
7. What subscriptions am I paying for?
8. How many transactions did I make at Amazon last month?
9. What did I spend on transport this week?
10. How much have I spent on dining out this quarter?
11. Show me my top 5 largest transactions this year
12. Did I spend more on food or shopping last month?
13. How much money came into my account last month? *(should NOT exclude transfers — tests that the model correctly flips `exclude_transfers`)*
14. What's my average transaction size at Zomato?
15. How much have I spent total this year so far?
16. List my last 10 debit transactions
17. How much did I spend on entertainment vs travel this year?
18. Am I spending more this month than the same time last month?
19. What's the most I've ever spent in a single month?
20. How much did I spend excluding subscriptions last month?
21. Write a Python script to sort a list of numbers *(out-of-domain: tests that intent resolves to "unrelated" and returns refusal)*
22. What is the capital of France? *(out-of-domain: tests domain guardrail refusal)*
23. How much did I spend on perfumes? *(category-mapping test — real bug repro. `expected_category_mapping_note`: non-null, category should map to `shopping`. Passing this question means the final answer text explicitly states the mapping, not just a correct number.)*
24. How much are all my subscription costs? *(subscription-detection test — real bug repro. `expected_ir.is_subscription_query`: `true`. Ground truth for this one must be computed via the recurrence-detection query, not a plain `category = 'subscriptions'` filter, or the "ground truth" itself repeats the original bug.)*

A few additional category-mapping and unmatched-term cases worth adding once the above are passing reliably, since one example of each isn't enough to trust the behavior generalizes:
- "How much did I spend at the gym?" *(should map to `healthcare` or `fees_charges` depending on taxonomy judgment call — either is acceptable as long as it's disclosed)*
- "How much have I spent on my pet's vet bills?" *(no reasonable mapping exists in the current taxonomy — should trigger `unmatched_term`, not a forced guess)*
- "What have I spent on cabs?" *(should map to `transport`, disclosed)*

Questions 12, 17, and 18 need `group_by` or `compare_date_range` used correctly. Questions 21 and 22 verify the domain guardrail reliably rejects genuinely off-topic queries. Questions 23 and 24 are the ones to watch closest of all — they're the two that previously passed IR-accuracy and grounding-fidelity checks while still being wrong, so they're the direct regression test for that bug class. If either starts failing again after a prompt change, that's a strong signal the change re-introduced the silent-guess behavior.

## Computing ground truth

For each question, hand-write (once) the direct SQL a competent engineer would write to answer it, run it against a snapshot of the DB, and store the result as `expected_answer_contains`. This is slower up front than eyeballing whether an answer "looks right," but it's the only way the accuracy number on the resume is actually defensible if someone asks how it was measured.

For question 24 (subscriptions) specifically: ground truth must be computed via the same recurrence-detection logic the fixed system uses (same merchant + amount, ≥2 consecutive months), not via `WHERE category = 'subscriptions'`. Computing ground truth with the simpler, buggy query would make the benchmark validate the bug instead of catching it.

**Which DB snapshot**: per the build order in `build-plan-and-resume.md`, this benchmark gets built and iterated on against synthetic data first (week 6), since real ingestion may not be fully validated yet at that point — synthetic data is perfectly fine for tuning the prompts and getting the harness itself working. Once real SMS/AA ingestion is solid (week 7), recompute ground truth against a snapshot of the real DB and re-run the benchmark. The number that goes on the resume should be the one measured against real data — say so if asked, since claiming a synthetic-data accuracy number as if it reflects real usage would be misleading.