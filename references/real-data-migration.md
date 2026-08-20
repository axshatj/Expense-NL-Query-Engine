# Real Data Migration Plan

This project currently runs on synthetic data (see `ingestion.md`) plus, optionally, Setu's **AA sandbox** — test data from mock banks, no real regulatory approval needed. This file is the plan for what changes if the goal becomes ingesting your own *real* transactions (or, further out, other real users' data) instead of synthetic/sandbox data. Nothing here has been built yet — treat this as a roadmap to execute deliberately, not a set of assumptions already baked into the current build.

**One clarification worth being explicit about, since it came up while reviewing what Setu Bridge actually returns:** Setu offers multiple distinct products under one platform, and they are not interchangeable:

- **Account Aggregator (AA)** — the RBI-licensed framework for pulling a *user's own bank transaction history* with their consent. This is the product this whole project is designed around, and it's the one to use.
- **BBPS (Bharat BillPay Bill Payment/Collections)** — a *biller-side* product for a business to receive and reconcile bill payments made *to* them (loan EMIs, utility bills, etc.). Its API responses look structurally similar to a transaction feed (amounts, dates, payment references) but represent a fundamentally different thing — payments received by a biller, not a personal account's transaction history. **This is not the product to integrate for this project.** If a Setu sandbox response ever comes back with fields like `platformBillID`, `billerBillID`, `billerMCC`, or `bpcTotal`, that's the BBPS product, not AA — worth double-checking which product a sandbox key is actually provisioned for before building against it, since the two are easy to conflate but solve opposite problems (collecting payments vs. reading someone's own spending).

Everything below assumes **AA** is the target integration, consistent with `ingestion.md`.

## What "real data" actually requires, layer by layer

### 1. Real SMS ingestion (lower effort, do this first)

What's already scoped in `ingestion.md` — regex parsing against 2-3 real sender formats — mostly *is* the real-data version already; SMS doesn't require external registration the way AA does. The gap between where the project is now and a real-data version is:

- **Actual message export**: reading from a real phone's SMS history (Android: via an export app or, if building an Android companion, direct `SmsManager`/content-provider access with runtime permissions; iOS: no equivalent API exists for third-party apps to read SMS — this is an Apple platform restriction, not a project gap, so an iOS path would need a different ingestion mechanism, e.g. manually forwarding bank alert emails instead).
- **Broader sender coverage**: once real messages are in hand, expect to discover more sender ID variations than the 2-3 assumed in `ingestion.md` (banks often use multiple sender IDs for different message types). Extend the `PATTERNS` dict incrementally as real formats surface — don't try to anticipate all of them upfront.
- **Handling real noise**: real inboxes have far more promotional/OTP volume than a curated test set. The keyword denylist in `ingestion.md` needs tuning against a real inbox, not just imagined against sample messages.

### 2. Real AA integration — the bigger lift

This is where "swap synthetic for real" stops being a small step. The sandbox flow already documented in `ingestion.md` (consent request → user approval → fetch → decrypt → map) is architecturally the same flow used in production — the code doesn't fundamentally change. What changes is everything *around* it:

**a) FIU registration path.** Setu's AA sandbox requires no registration; real production AA access requires becoming (or partnering with) a **registered FIU (Financial Information User)** — an RBI-governed status. Concretely, this means either:
- Going through Setu's own onboarding as a business customer for production AA access (Setu itself is a licensed AA-ecosystem participant and offers production access without the requesting party needing to independently register as an FIU, but does require a business/KYC onboarding process, a signed agreement, and typically a live-use case review), or
- If Setu's business onboarding isn't the intended path, direct RBI FIU registration is a considerably heavier regulatory process not realistically scoped for a personal portfolio project.

For a resume project, **(a) is the realistic path**, and it's still real work: business KYC, defining the actual use case Setu will review, and likely a minimum viable production agreement. This is a deliberate scope decision to make explicitly, not slide into — see the "what to decide before starting" section below.

**b) Real consent flow, real bank participation.** Production AA only works with banks that are live participants in the AA ecosystem (most major Indian banks are, but not all, and coverage varies). The consent UX also changes — in production, the user is redirected to their actual AA app/website (e.g., their bank's AA-linked app, or a dedicated AA app) to approve access, not a sandbox mock screen. This needs to be tested against at least one real bank account.

**c) Real encrypted data handling.** The sandbox already exercises the same ECDH key-exchange/decryption flow production uses (Setu's SDK handles this in both cases), so this part of `ingestion.md`'s design shouldn't need rearchitecting — but it's worth explicitly re-testing against production endpoints rather than assuming sandbox behavior transfers perfectly, since key rotation policies, token lifetimes, and rate limits can differ between sandbox and production tiers.

**d) Data handling and storage obligations.** This is the part most likely to be underestimated. Once real bank transaction data is being stored (even just your own), it's worth treating it with real financial-data hygiene regardless of project scale:
- Encrypt the `transactions` table at rest (SQLite's built-in encryption extensions, or full-disk encryption at minimum) rather than storing plaintext financial data on disk.
- Never commit real transaction data, consent handles, or API credentials to a public repo — the current project structure should already be separating synthetic sample data from any real data directory, and that separation needs to be enforced (`.gitignore`, not just discipline) before real data ever touches the codebase.
- Define a real data-retention/deletion story, even a minimal one (e.g., a documented way to revoke AA consent and purge stored data) — this is both good practice and a legitimate thing to mention in an interview as evidence of production-mindedness.

### 3. What does NOT need to change

Everything downstream of the `transactions` table is source-agnostic by design (see `architecture-and-schema.md` and `ingestion.md`'s "both paths converge on the same normalizer" section) — the NL query engine, the IR schema, the SQL builder, the grounding/anti-hallucination check, and the eval harness should all work unmodified against real data, because they were built to consume the schema, not any particular data source. The one place real data is *expected* to surface new work is normalization (see below) — everything else should just work.

## What to decide before starting this migration

I don't want to assume answers here — these materially change scope and cost:

1. **Just your own data, or multiple users?** If it's just your own transaction history for portfolio/personal use, the FIU registration question above is much lighter (Setu's business onboarding for a single-use-case integration) than if the project is meant to eventually support other real users, which would push toward needing an actual registered FIU status or a formal partnership arrangement with Setu — a materially bigger undertaking.
2. **Is real financial data going in any shared/public repo, even indirectly?** If this project's code is public on GitHub (as it appears to be), real transaction data, real consent handles, and real API credentials must never enter that repo — worth setting up the separation (private data directory, environment-based secrets, `.gitignore` rules) before requesting real production access, not after.
3. **Budget for Setu's production tier.** Sandbox AA access is free; production AA access on Setu is a paid product with per-transaction or subscription-based pricing depending on volume — worth checking Setu's current pricing page directly before committing, since this isn't something to guess at.
4. **Timeline expectation.** FIU/business onboarding and bank participant testing realistically adds weeks, not days, on top of the 8-week build plan in `build-plan-and-resume.md` — this migration is worth treating as its own follow-on phase after the core project is complete and evaluated on synthetic/sandbox data, not something to fold into the original build timeline.

## Expected new work once real data starts flowing

Real data reliably surfaces gaps that synthetic data can't, because synthetic data is generated to already be clean:

- **Normalization gaps**: real merchant strings will include variants the `merchant_aliases` table hasn't seen — expect to spend real time populating it against actual data, same as `build-plan-and-resume.md`'s week 7 already anticipates for the sandbox-to-real transition.
- **Category-mapping and unmatched-term cases**: real spending will include categories of purchase the fixed taxonomy didn't anticipate — this is exactly the scenario the category-mapping guardrail in `nl-query-and-grounding.md` was built for, and real data is where that guardrail earns its keep rather than just passing a benchmark.
- **Re-run the eval benchmark against real data** once ingestion is solid, per `evaluation.md`'s existing guidance — the accuracy number that goes on the resume should reflect real data, not synthetic.

If any of the above turns out to be wrong for how you actually want to scope this (personal-only vs. multi-user, timeline, budget), that changes real decisions in this file — flag it and this gets revised rather than guessed at again.
