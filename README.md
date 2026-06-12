# Plum AI Engineer Assignment

## Overview

This package contains everything you need to complete the Health Insurance Claims Processing assignment for the AI Engineer role at Plum.


## Implemented Solution

This submission implements a trace-first, agent-based claims pipeline:

```text
DocumentVerificationAgent
-> ExtractionAgent
-> PolicyAgent
-> FraudAgent
-> DecisionAgent
```

Policy adjudication is deterministic and reads from `policy_terms.json`. Document extraction is implemented behind a structured extractor contract using the mock document content from `test_cases.json`, with the architecture documented for future OCR/vision LLM replacement.

## Local Setup

Backend:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.api:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Run backend tests:

```bash
cd backend
.venv/bin/pytest
```

Generate the eval report:

```bash
cd backend
.venv/bin/python run_eval.py
```

Docs:

- `docs/architecture.md`
- `docs/contracts.md`
- `docs/eval_report.md`
- `docs/setup.md`


## Render Deployment

This repo includes a single-service Render blueprint in `render.yaml`. Render builds the React app, serves it from FastAPI, and exposes both the UI and API from one web service.

Run the deploy helper:

```bash
./scripts/deploy_render.sh
```

The script runs backend tests, builds the frontend, commits pending changes, pushes to GitHub, and triggers a Render deploy hook if `RENDER_DEPLOY_HOOK_URL` is set.

First-time Render setup:

1. Open Render Dashboard
2. Create a new Blueprint
3. Connect `github.com/Rehan018/Plum`
4. Render will read `render.yaml`

After first setup, copy the Render Deploy Hook URL and run:

```bash
RENDER_DEPLOY_HOOK_URL="https://api.render.com/deploy/srv-..." ./scripts/deploy_render.sh
```

## Package Contents

```
multi_agent_claims_pipeline/
│
├── README.md                  # This file
├── assignment.md              # Full assignment — read this first
├── policy_terms.json          # Policy configuration, coverage rules, member roster
├── test_cases.json            # 12 test scenarios with expected outcomes
└── sample_documents_guide.md  # Indian medical document formats and extraction guidance
```

## Getting Started

Read `assignment.md` in full before writing a single line of code. Understand the problem before you reach for a solution.

## Timeline

2-3 days from receipt.
