# Local Setup

## Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.api:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

Run tests:

```bash
cd backend
.venv/bin/pytest
```

Generate eval report:

```bash
cd backend
.venv/bin/python run_eval.py
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://127.0.0.1:5173
```
