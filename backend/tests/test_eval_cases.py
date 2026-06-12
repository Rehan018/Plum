from __future__ import annotations

import asyncio

from app.eval_runner import run_all_cases


def test_all_assignment_cases_pass() -> None:
    results = asyncio.run(run_all_cases(write_report=False))
    failures = [result for result in results if not result["passed"]]
    assert not failures, [
        {
            "case_id": item["case_id"],
            "expected": item["expected_decision"],
            "actual": item["actual_decision"],
            "approved_amount": item["approved_amount"],
            "reason": item["reason"],
        }
        for item in failures
    ]


def test_trace_contains_agent_health() -> None:
    results = asyncio.run(run_all_cases(write_report=False))
    tc011 = next(item for item in results if item["case_id"] == "TC011")
    response = tc011["response"]
    assert response.agent_health["FraudAgent"] == "FAILED"
    assert response.confidence_score < 1.0
    assert response.decision == "APPROVED"


def test_waiting_period_reason_names_eligible_date() -> None:
    results = asyncio.run(run_all_cases(write_report=False))
    tc005 = next(item for item in results if item["case_id"] == "TC005")
    response = tc005["response"]
    assert "Eligible from: 2024-11-30" in response.reason


def test_pre_auth_next_action_is_actionable() -> None:
    results = asyncio.run(run_all_cases(write_report=False))
    tc007 = next(item for item in results if item["case_id"] == "TC007")
    response = tc007["response"]
    assert "pre-authorization" in response.reason.lower()
    assert response.next_action is not None
    assert "obtain valid pre-authorization" in response.next_action.lower()


def test_member_not_found_blocks_before_adjudication() -> None:
    from app.models import ClaimInput
    from app.orchestrator import ClaimOrchestrator

    claim = ClaimInput(
        member_id="UNKNOWN",
        policy_id="PLUM_GHI_2024",
        claim_category="CONSULTATION",
        treatment_date="2024-11-01",
        claimed_amount=1000,
        documents=[
            {"file_id": "F1", "actual_type": "PRESCRIPTION"},
            {"file_id": "F2", "actual_type": "HOSPITAL_BILL"},
        ],
    )
    response = asyncio.run(ClaimOrchestrator().process(claim))
    assert response.decision == "BLOCKED"
    assert "not found" in response.reason


def test_doctor_registration_validation_is_traced() -> None:
    results = asyncio.run(run_all_cases(write_report=False))
    tc004 = next(item for item in results if item["case_id"] == "TC004")
    extraction = next(event for event in tc004["trace"] if event.agent == "ExtractionAgent")
    assert any(check.rule_id == "DOCTOR_REGISTRATION_FORMAT" for check in extraction.checks)
