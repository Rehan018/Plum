from __future__ import annotations

import asyncio

from app.eval_runner import run_all_cases


if __name__ == "__main__":
    results = asyncio.run(run_all_cases(write_report=True))
    passed = sum(1 for result in results if result["passed"])
    print(f"{passed}/{len(results)} cases passed")
