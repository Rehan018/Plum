# Architecture

## Objective

This system automates OPD claim intake and adjudication for the Plum assignment. It is designed as a trace-first, agent-based pipeline:

```text
DocumentVerificationAgent
-> ExtractionAgent
-> PolicyAgent
   -> WaitingPeriodRule
   -> ExclusionRule
   -> PreAuthRule
   -> LimitRule
   -> CopayRule
-> FraudAgent
-> DecisionAgent
```

The important design split is:

- AI-style document agents interpret messy documents and normalize facts.
- Deterministic policy rules decide eligibility, money, and rejection reasons.
- Trace events explain every check, rule source, evidence item, and confidence impact.

## Current Implementation

The assignment version runs fully in memory. It reads `policy_terms.json` and `test_cases.json`, processes a claim, and returns a `DecisionResponse` with:

- decision
- approved amount
- confidence score
- reason
- evidence
- next action
- agent health
- full trace

No database is used because persistence is not necessary for the 12 acceptance cases. In production, claims, decisions, traces, and uploaded document metadata would be stored in Postgres, while raw documents would live in object storage.

## AI Integration

The `ExtractionAgent` uses a `DocumentExtractor` contract. The assignment path uses `MockStructuredExtractor`, which reads the structured document content supplied by `test_cases.json`. A production-oriented `LLMDocumentExtractor` stub is present to show the replacement point for OCR and vision LLM extraction without changing downstream rules.

Production extraction would use:

- OCR for text-heavy bills and lab reports
- vision LLM for handwritten or photographed prescriptions
- structured JSON validation with retries
- low-confidence field marking instead of hard failure

The final adjudication remains deterministic because claim payouts must be reproducible and auditable.

## Intake Validation

The verification stage also validates that the submitted member exists in `policy_terms.json`. Unknown members are returned as `BLOCKED` intake failures, not claim rejections, because adjudication should not begin without a valid covered member.

The extraction stage validates doctor registration numbers against the Indian registration formats described in `sample_documents_guide.md`. Missing or malformed registration numbers produce a partial extraction trace and a confidence deduction instead of crashing the pipeline.

## Trace-First Design

Every agent appends a `TraceEvent`:

```json
{
  "agent": "PolicyAgent",
  "status": "SUCCESS",
  "checks": [
    {
      "rule_id": "COPAY_AND_NETWORK_DISCOUNT",
      "source": "policy_terms.json",
      "result": "PASSED",
      "details": "Discounts and co-pay applied according to policy terms.",
      "evidence": ["Network discount 20% deducted", "Co-pay 10% deducted"]
    }
  ],
  "confidence_delta": 0
}
```

This lets an operations reviewer reconstruct what happened without reading code.

## Confidence

Confidence represents certainty in the processing, not whether the outcome is favorable.

Examples:

- Clear waiting-period rejection: high confidence
- Clear exclusion rejection: high confidence
- Unreadable document: blocked with lower confidence
- Component failure: confidence decreases, pipeline continues
- Fraud signal: manual review with a modest confidence reduction

The implementation starts at `1.0`, sums `confidence_delta` values from trace events, then clamps to `0.0-1.0`.

## Robustness Checks

Beyond the 12 provided test cases, the backend includes adversarial coverage for:

- unknown member IDs
- invalid policy IDs
- unknown claim categories
- empty document submissions
- claim amount versus bill total mismatch
- high-value claims above the manual-review threshold
- annual OPD limit partial approval
- invalid doctor registration numbers
- network hospital case-insensitive matching
- 100 randomized valid-shape claims that must not crash

These checks reduce the risk that the system is merely tailored to the provided dataset.

## Failure Handling

The orchestrator wraps every agent call:

```python
try:
    context = await agent.execute(context)
except Exception:
    trace.add_failed_agent(...)
    confidence -= 0.20
    continue
```

This is designed specifically for graceful degradation. TC011 simulates a `FraudAgent` failure; the system records the failure, lowers confidence, recommends manual review, and still returns a decision.

## Scaling Plan

At 10x volume, the main changes would be:

- Store claims, decisions, traces, and documents in Postgres/object storage.
- Move extraction into an async queue because OCR/LLM calls are slow and failure-prone.
- Add idempotency keys for claim submissions.
- Add model/version metadata to extraction trace events.
- Add human review queues for `BLOCKED`, `MANUAL_REVIEW`, and low-confidence decisions.
- Add monitoring around agent failure rates, confidence distributions, and rule-trigger frequencies.

## Deliberate Non-Goals

The system avoids vector databases, RAG, Kafka, Kubernetes, and multi-model routing. None of the assignment cases require them, and they would reduce clarity within a 2-3 day build.
