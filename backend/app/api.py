from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .eval_runner import run_all_cases, run_case
from .models import ClaimInput
from .orchestrator import ClaimOrchestrator
from .policy_loader import load_policy, load_test_cases


app = FastAPI(title="Plum Claims AI Pipeline")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/policy")
async def get_policy() -> dict:
    return load_policy()


@app.get("/api/test-cases")
async def get_test_cases() -> list[dict]:
    return load_test_cases()


@app.post("/api/claims/process")
async def process_claim(claim: ClaimInput):
    return await ClaimOrchestrator().process(claim)


@app.post("/api/eval/run-all")
async def eval_all():
    results = await run_all_cases(write_report=True)
    return [
        {
            "case_id": result["case_id"],
            "passed": result["passed"],
            "expected_decision": result["expected_decision"],
            "actual_decision": result["actual_decision"],
            "approved_amount": result["approved_amount"],
            "confidence_score": result["confidence_score"],
            "reason": result["reason"],
        }
        for result in results
    ]


@app.post("/api/eval/run/{case_id}")
async def eval_one(case_id: str):
    for test_case in load_test_cases():
        if test_case["case_id"] == case_id:
            return await run_case(test_case)
    return {"error": f"Unknown case_id {case_id}"}
