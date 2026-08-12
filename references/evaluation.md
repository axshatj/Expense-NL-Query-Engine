# Evaluation

## Philosophy

Grade two things separately, because they fail independently:

1. **Did prompt 1 understand the question?** (IR field accuracy) — a wrong category filter is a prompt-1 bug.
2. **Is the final answer actually correct?** (grounding fidelity) — even with a perfect IR, prompt 2 could still misreport a number.

Reporting only end-to-end accuracy hides which of the two prompts to actually go fix. Reporting only IR accuracy misses grounding failures. Track both.

## Benchmark format

```json
{
  "id": 1,
  "question": "How much did I spend on dining last month?",
  "expected_ir": {
    "intent": "aggregate", "metric": "sum",
    "filters": {"category": ["dining"], "transaction_type": "debit", "exclude_transfers": true}
  },
  "expected_answer_contains": [12450.00]
}
```

`expected_ir` only needs the fields that matter for that question (partial match, not exact-object match — `date_range` will differ run to run since "today" moves). `expected_answer_contains` is computed once by running the equivalent raw SQL directly against the DB — that's the ground truth, not a hand-typed guess.

## Three metrics

1. **IR field accuracy** — for each question, what fraction of the checked `expected_ir` fields matched? Average across the set.
2. **Numeric accuracy** — does the final NL answer's number(s) match `expected_answer_contains` within a small tolerance?
3. **Hallucination rate** — fraction of answers where `verify_grounded` (see nl-query-and-grounding.md) failed and had to fall back to the template. This should trend toward zero as prompt 2 improves; if it's not near zero, that's the thing to fix before anything else, since it's the trust-breaking failure mode.

## Starter set (20 questions)

Covers all four intents, both simple and compound filters, and a few genuinely ambiguous ones on purpose — those are the most informative failures.

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

Questions 12, 17, 18, 21, and 22 are the ones to watch closest — 12, 17, and 18 need `group_by` or `compare_date_range` used correctly, while 21 and 22 verify that the domain guardrail reliably rejects off-topic queries.

## Computing ground truth

For each question, hand-write (once) the direct SQL a competent engineer would write to answer it, run it against a snapshot of the DB, and store the result as `expected_answer_contains`. This is slower up front than eyeballing whether an answer "looks right," but it's the only way the accuracy number on the resume is actually defensible if someone asks how it was measured.

**Which DB snapshot**: per the build order in `build-plan-and-resume.md`, this benchmark gets built and iterated on against synthetic data first (week 6), since real ingestion may not be fully validated yet at that point — synthetic data is perfectly fine for tuning the prompts and getting the harness itself working. Once real SMS/AA ingestion is solid (week 7), recompute ground truth against a snapshot of the real DB and re-run the benchmark. The number that goes on the resume should be the one measured against real data — say so if asked, since claiming a synthetic-data accuracy number as if it reflects real usage would be misleading.