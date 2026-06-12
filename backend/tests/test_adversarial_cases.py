from __future__ import annotations

import asyncio
import random

from app.models import ClaimInput
from app.orchestrator import ClaimOrchestrator


def run_claim(payload: dict):
    return asyncio.run(ClaimOrchestrator().process(ClaimInput(**payload)))


def base_consultation(**overrides):
    payload = {
        "member_id": "EMP001",
        "policy_id": "PLUM_GHI_2024",
        "claim_category": "CONSULTATION",
        "treatment_date": "2024-11-01",
        "claimed_amount": 1500,
        "documents": [
            {
                "file_id": "P1",
                "actual_type": "PRESCRIPTION",
                "content": {
                    "doctor_name": "Dr. Arun Sharma",
                    "doctor_registration": "KA/45678/2015",
                    "patient_name": "Rajesh Kumar",
                    "diagnosis": "Viral Fever",
                },
            },
            {
                "file_id": "B1",
                "actual_type": "HOSPITAL_BILL",
                "content": {
                    "patient_name": "Rajesh Kumar",
                    "hospital_name": "City Clinic",
                    "total": 1500,
                    "line_items": [{"description": "Consultation Fee", "amount": 1500}],
                },
            },
        ],
    }
    payload.update(overrides)
    return payload


def test_unknown_member_blocks() -> None:
    response = run_claim(base_consultation(member_id="EMP999"))
    assert response.decision == "BLOCKED"
    assert "MEMBER_NOT_FOUND" in response.trace[0].checks[0].rule_id


def test_wrong_policy_id_blocks() -> None:
    response = run_claim(base_consultation(policy_id="INVALID_POLICY"))
    assert response.decision == "BLOCKED"
    assert response.trace[0].checks[0].rule_id == "POLICY_ID_MISMATCH"


def test_unknown_claim_category_blocks_without_key_error() -> None:
    response = run_claim(base_consultation(claim_category="SPACE_SURGERY"))
    assert response.decision == "BLOCKED"
    assert response.trace[0].checks[0].rule_id == "UNKNOWN_CLAIM_CATEGORY"


def test_empty_documents_blocks_with_missing_required_documents() -> None:
    response = run_claim(base_consultation(documents=[]))
    assert response.decision == "BLOCKED"
    assert response.trace[0].checks[0].rule_id == "REQUIRED_DOCUMENTS"
    assert "no documents" in response.reason


def test_claim_amount_mismatch_routes_to_manual_review() -> None:
    response = run_claim(base_consultation(claimed_amount=50000))
    assert response.decision == "MANUAL_REVIEW"
    fraud = next(event for event in response.trace if event.agent == "FraudAgent")
    assert any(check.rule_id == "CLAIM_AMOUNT_MATCH" and check.result == "WARNING" for check in fraud.checks)


def test_high_value_claim_routes_to_manual_review() -> None:
    payload = base_consultation(claimed_amount=30000)
    payload["documents"][1]["content"]["total"] = 30000
    payload["documents"][1]["content"]["line_items"] = [{"description": "Treatment Package", "amount": 30000}]
    response = run_claim(payload)
    assert response.decision == "MANUAL_REVIEW"
    fraud = next(event for event in response.trace if event.agent == "FraudAgent")
    assert any(check.rule_id == "HIGH_VALUE_CLAIM" and check.result == "WARNING" for check in fraud.checks)


def test_annual_opd_limit_partial_approval() -> None:
    response = run_claim({
        "member_id": "EMP002",
        "policy_id": "PLUM_GHI_2024",
        "claim_category": "DENTAL",
        "treatment_date": "2024-10-15",
        "claimed_amount": 3000,
        "ytd_claims_amount": 49000,
        "documents": [
            {
                "file_id": "D1",
                "actual_type": "HOSPITAL_BILL",
                "content": {
                    "patient_name": "Priya Singh",
                    "total": 3000,
                    "line_items": [{"description": "Root Canal Treatment", "amount": 3000}],
                },
            }
        ],
    })
    assert response.decision == "PARTIAL"
    assert response.approved_amount == 1000
    assert "policy limit" in response.reason


def test_invalid_doctor_registration_warns_and_reduces_confidence() -> None:
    payload = base_consultation()
    payload["documents"][0]["content"]["doctor_registration"] = "ABC123"
    response = run_claim(payload)
    extraction = next(event for event in response.trace if event.agent == "ExtractionAgent")
    assert extraction.status == "PARTIAL"
    assert response.confidence_score < 1.0


def test_network_hospital_matching_is_case_insensitive() -> None:
    for hospital in ["Apollo Hospitals", "apollo hospitals", "APOLLO HOSPITALS"]:
        payload = base_consultation(claimed_amount=4500, hospital_name=hospital)
        payload["documents"][1]["content"]["hospital_name"] = hospital
        payload["documents"][1]["content"]["total"] = 4500
        payload["documents"][1]["content"]["line_items"] = [{"description": "Consultation Fee", "amount": 4500}]
        response = run_claim(payload)
        assert response.decision == "APPROVED"
        assert response.approved_amount == 3240


def test_random_valid_shape_claims_do_not_crash() -> None:
    categories = {
        "CONSULTATION": ["PRESCRIPTION", "HOSPITAL_BILL"],
        "PHARMACY": ["PRESCRIPTION", "PHARMACY_BILL"],
        "DENTAL": ["HOSPITAL_BILL"],
    }
    for index in range(100):
        category = random.choice(list(categories))
        amount = random.randint(500, 6000)
        docs = []
        for doc_type in categories[category]:
            content = {
                "patient_name": "Rajesh Kumar",
                "doctor_registration": "KA/45678/2015",
                "diagnosis": random.choice(["Viral Fever", "Rare Syndrome XYZ", "Gastroenteritis"]),
                "total": amount,
                "line_items": [{"description": "Root Canal Treatment" if category == "DENTAL" else "Consultation Fee", "amount": amount}],
            }
            docs.append({"file_id": f"F{index}-{doc_type}", "actual_type": doc_type, "content": content})
        response = run_claim(base_consultation(claim_category=category, claimed_amount=amount, documents=docs))
        assert response is not None
        assert response.decision is not None
        assert response.trace
        assert 0 <= response.confidence_score <= 1


def patient_spacing_payload(name_a: str, name_b: str):
    return {
        "member_id": "EMP001",
        "policy_id": "PLUM_GHI_2024",
        "claim_category": "CONSULTATION",
        "treatment_date": "2024-10-10",
        "claimed_amount": 1500,
        "documents": [
            {
                "file_id": "P1",
                "actual_type": "PRESCRIPTION",
                "patient_name_on_doc": name_a,
                "content": {
                    "doctor_registration": "KA/45678/2015",
                    "diagnosis": "General Consultation",
                },
            },
            {
                "file_id": "B1",
                "actual_type": "HOSPITAL_BILL",
                "patient_name_on_doc": name_b,
                "content": {
                    "hospital_name": "City Clinic",
                    "total": 1500,
                    "line_items": [{"description": "Consultation Fee", "amount": 1500}],
                },
            },
        ],
    }


def test_patient_name_trailing_space_does_not_block() -> None:
    response = run_claim(patient_spacing_payload("Rajesh Kumar", "Rajesh Kumar "))
    assert response.decision == "APPROVED"


def test_patient_name_case_difference_does_not_block() -> None:
    response = run_claim(patient_spacing_payload("Rajesh Kumar", "RAJESH KUMAR"))
    assert response.decision == "APPROVED"


def test_patient_name_multiple_spaces_do_not_block() -> None:
    response = run_claim(patient_spacing_payload("Rajesh Kumar", "  Rajesh    Kumar"))
    assert response.decision == "APPROVED"


def test_true_patient_name_mismatch_still_blocks() -> None:
    response = run_claim(patient_spacing_payload("Rajesh Kumar", "Arjun Mehta"))
    assert response.decision == "BLOCKED"
    assert response.trace[0].checks[0].rule_id == "PATIENT_NAME_CONSISTENCY"
