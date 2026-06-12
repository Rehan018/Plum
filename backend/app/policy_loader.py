from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "policy_terms.json"
TEST_CASES_PATH = ROOT / "test_cases.json"


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def load_test_cases() -> list[dict[str, Any]]:
    with TEST_CASES_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)["test_cases"]


def get_member(policy: dict[str, Any], member_id: str) -> dict[str, Any] | None:
    for member in policy.get("members", []):
        if member.get("member_id") == member_id:
            return member
    return None
