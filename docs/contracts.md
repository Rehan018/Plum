# Component Contracts

## Shared Models

### ClaimInput

Input accepted by the API and orchestrator.

Fields:

- `member_id`
- `policy_id`
- `claim_category`
- `treatment_date`
- `claimed_amount`
- `documents`
- `ytd_claims_amount`
- `hospital_name`
- `claims_history`
- `simulate_component_failure`

### ClaimContext

Mutable pipeline object passed between agents.

Contains:

- original claim
- policy
- member
- extracted document facts
- policy evaluation
- fraud evaluation
- evidence
- warnings
- trace
- final decision

### TraceEvent

Emitted by every agent.

Fields:

- `agent`
- `status`: `SUCCESS`, `PARTIAL`, `FAILED`, `BLOCKED`, `SKIPPED`
- `summary`
- `checks`
- `confidence_delta`
- `warnings`
- `errors`

### RuleResult

Common contract for policy rules.

Fields:

- `rule_id`
- `status`: `PASSED`, `FAILED`, `WARNING`
- `reason`
- `evidence`
- `approved_amount`
- `rejected_amount`
- `rejection_reason`
- `line_item_results`
- `confidence_delta`

## Extractor Interfaces

### DocumentExtractor

Input: `ClaimContext`

Output: `ExtractionResult`

Implementations:

- `MockStructuredExtractor`: assignment/test implementation using structured document content
- `LLMDocumentExtractor`: production replacement point for OCR/vision LLM extraction and schema validation

## Agents

### DocumentVerificationAgent

Input: `ClaimContext`

Output: updated `ClaimContext`

Responsibilities:

- Confirm the submitted policy ID matches the active policy
- Confirm the submitted member exists in `policy_terms.json`
- Confirm the claim category is supported by policy document requirements
- Check required document types from `policy_terms.json`
- Block unreadable documents
- Detect patient-name mismatch across documents after normalizing case and whitespace
- Stop before adjudication for intake/document issues

Errors:

- Does not raise expected business errors
- Unexpected exceptions are caught by the orchestrator

Trace:

- `REQUIRED_DOCUMENTS`
- `DOCUMENT_READABILITY`
- `PATIENT_NAME_CONSISTENCY`

### ExtractionAgent

Input: `ClaimContext`

Output: `ClaimContext.extracted`

Responsibilities:

- Extract patient, diagnosis, treatment, provider, doctor, tests, medicines, line items, and total
- Normalize simple tags such as `diabetes`, `mri`, and `obesity_treatment`
- Validate doctor registration number format from `sample_documents_guide.md`
- Provide `DocumentExtractor`, `MockStructuredExtractor`, and `LLMDocumentExtractor` contracts

Errors:

- Unexpected extraction failures are caught by the orchestrator

Trace:

- `STRUCTURED_EXTRACTION`

### PolicyAgent

Input: `ClaimContext` with extracted facts

Output: `ClaimContext.policy_evaluation`

Responsibilities:

- Run deterministic policy rules
- Apply rejection, partial approval, discounts, and co-pay
- Emit rule-level evidence

Rules:

- `WaitingPeriodRule`
- `ExclusionRule`
- `PreAuthRule`
- `LimitRule`
- `CopayRule`

Errors:

- Unexpected rule errors are caught by the orchestrator

Trace:

- One trace check per `RuleResult`

### FraudAgent

Input: `ClaimContext`

Output: `ClaimContext.fraud_evaluation`

Responsibilities:

- Check same-day claim frequency
- Check claim amount against extracted bill total
- Check high-value claim threshold from `policy_terms.json`
- Flag suspicious claim patterns
- Route to manual review instead of auto-rejecting

Errors:

- TC011 simulates a component failure here
- Orchestrator records failure and continues

Trace:

- `SAME_DAY_CLAIM_LIMIT`
- `AGENT_FAILURE` when simulated failure occurs

### DecisionAgent

Input: `ClaimContext` with verification, extraction, policy, and fraud outputs

Output: `DecisionResponse`

Responsibilities:

- Return one of `BLOCKED`, `APPROVED`, `PARTIAL`, `REJECTED`, `MANUAL_REVIEW`
- Include approved amount, reason, confidence, evidence, next action, trace, and agent health
- Recommend manual review when a component failed but enough data remains

Errors:

- Unexpected errors are caught by the orchestrator, but this agent should be last and minimal

Trace:

- `FINAL_DECISION`

## Rules

### WaitingPeriodRule

Checks condition-specific waiting periods, such as diabetes.

Failure result:

- `rejection_reason`: `WAITING_PERIOD`

### ExclusionRule

Checks excluded treatments and line-item exclusions.

Failure result:

- `rejection_reason`: `EXCLUDED_CONDITION`

Warning result:

- Dental cosmetic line items are rejected while covered line items remain payable

### PreAuthRule

Checks high-value diagnostic pre-authorization.

Failure result:

- `rejection_reason`: `PRE_AUTH_MISSING`

### LimitRule

Checks per-claim and annual OPD limits.

Failure result:

- `rejection_reason`: `PER_CLAIM_EXCEEDED`

### CopayRule

Applies network discount first, then co-pay.

For TC010:

```text
Rs 4500
- 20% network discount = Rs 3600
- 10% co-pay = Rs 3240 approved
```
