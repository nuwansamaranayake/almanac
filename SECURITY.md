# Almanac — Security

Open-source AI tools get deployed into shops by people who never read the code. Almanac treats that
as a design input. The baseline is the **OWASP Top 10 for LLM Applications (2025)** and the **NIST AI
Risk Management Framework Generative AI Profile (NIST AI 600-1)**.

Almanac's trust boundaries make this concrete: the Signal Scout ingests untrusted external content
(web pages, event calendars, and — with explicit permission — supplier messages in any language), and
the LLM's only job is to turn that content into typed, provenance-carrying signals. No LLM output is
ever a number, an order, or a command. Every consequential action is a human-approved draft.

## OWASP LLM Top 10 (2025) mapping

| OWASP ID | Risk | Almanac control |
|---|---|---|
| LLM01 | Prompt injection | Retrieved pages and supplier messages are untrusted **data**, never instructions. System prompt and content travel in separate channels. A supplier email that says "reorder 500 units now" produces at most a claim-typed signal that still needs owner confirmation and a backtest — it can never place an order. Red-team injection cases ship in the eval suite. |
| LLM02 | Sensitive information disclosure | Supplier inboxes are ingested only with explicit permission and stored locally. Deterministic PII redaction runs before any external model call; a local-model mode exists for fully private operation. |
| LLM04 | Data and model poisoning | A poisoned "trend" cannot silently move an order: new signal classes sit in quarantine and earn influence only through sustained backtest lift with a minimum event count, and are demoted automatically on decay. |
| LLM05 | Improper output handling | The model emits JSON validated against a strict signal schema. Date and geo fields are checked deterministically against calendar and geo references; malformed or unverifiable output is rejected, not coerced. The LLM never emits a value that enters the forecast arithmetic. |
| LLM06 | Excessive agency | No auto-submitted purchase orders. Every order is a human-approved draft; tools are allowlisted with argument-schema validation and idempotency keys; the optimizer, not the model, computes quantities. |
| LLM08 | Vector and embedding weaknesses | Any retrieval (e.g., matching a message to a SKU or category) filters by store scope deterministically before content reaches model context; cross-store leakage is blocked at retrieval time, not by post-hoc redaction. |
| LLM09 | Misinformation | Every signal carries checkable provenance and an owner-facing verification status; recommendations always render as intervals with a reasoning trail and the app's own published realized-error history, never as false certainty. |
| LLM10 | Unbounded consumption | Hard budgets on tokens, tool calls, and loop depth per the shared baseline. A runaway Scout agent is treated as a security incident, not a quirk. |

## NIST AI RMF Generative AI Profile

Almanac exercises the RMF functions — **Govern, Map, Measure, Manage** — through artifacts already in
this repo rather than a separate compliance layer: risks are mapped in RISKS.md with owners and
tripwires; behavior is measured by the gated eval suite in EVAL.md (accuracy, isolated LLM lift,
planted-signal recovery, calibration); failures are managed and made visible in FAILURES.md; and every
LLM call is logged as a trace (model, version, prompt hash, temperature, latency, cost, and the claim
objects produced) for auditability. The overriding governance control is architectural: the model
senses, deterministic code decides, and a human approves anything that acts.

## Secrets

No secret is committed. Provider keys, POS tokens, and IMAP credentials live in `.env` (git-ignored);
`.env.example` ships with placeholders only. Provider access goes through the `groundwork` gateway,
never a provider SDK called directly, so keys and trace logging are handled in one audited place. The
zero-key demo path runs entirely on the synthetic dataset, so nobody has to expose real credentials to
evaluate the tool.
