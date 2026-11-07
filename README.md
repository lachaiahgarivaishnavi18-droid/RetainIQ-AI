# RetainIQ AI

An explainable retail churn and retention research platform. FastAPI + SQLAlchemy + scikit-learn + SHAP + LangGraph, with a React/TypeScript/Vite dashboard. Works locally without paid API services. The repository was empty at inspection; this implementation was built from scratch.

## Hosted frontend

The full hosted demo is available at [retainiq-ai.vercel.app](https://retainiq-ai.vercel.app), connected to a persistent Railway backend. It contains 360 clearly labeled synthetic customers, a trained model, real SHAP attributions and a sample agent workflow awaiting review. Choose **Create account** to register an analyst account, or use the administrator credentials provided privately in the deployment chat. The local application and its accounts/data are separate. See [hosted deployment instructions](docs/DEPLOYMENT.md) and [hosted API verification](docs/hosted-verification.json). The prepared Render blueprint remains an alternative and has not been applied.

## Start here

Dependencies have been installed in this workspace. From the project folder, run this first command:

```powershell
.\scripts\start.ps1
```

Then open [RetainIQ](http://127.0.0.1:5174). Choose **First visit? Create a local account**. The first local account is admin; subsequent accounts are analysts. Choose your own password of at least 10 characters. No credentials are shipped. If servers are already running, open the link directly.

The dashboard starts empty. There are no hardcoded live metrics. For a demonstrable walkthrough, take these steps in order:

1. **Data Import** → **Create synthetic demo dataset**. This generates 360 clearly labeled synthetic customers and reconciled synthetic transaction histories.
2. **Model Performance** → select that dataset → **Train & compare models**. See actual validation comparisons and the selected model’s held-out test metrics.
3. **Run batch prediction**. Executive Overview, risk directory and SHAP pages now show backend results.
4. **Customer Directory** → open a customer. Inspect the profile, run individual prediction, and view signed SHAP factors.
5. **Customer Segmentation** → **Run segmentation**. Inspect RFM assignments and annualized historical revenue proxies.
6. **Orchestrator Agent** → select a customer → **Run customer workflow**. Inspect real node outputs and tool-call logs. The workflow pauses at human review. Admin/reviewer can approve or reject; this records review, not communication delivery.
7. **Personalized Retention Strategies** → generate and review a strategy. Actions use observed customer behavior, model attributions and policy. Expected objectives are not measured successes.
8. **Retention Campaign Management** → draft a campaign. Admin/reviewer approves or rejects. Email campaigns require consent for every audience member. No email is actually sent. Open an approved campaign to record an externally observed outcome, time, cost and evidence.
9. **Retail AI Assistant** → ask a suggested question. Without provider keys it explicitly uses a local tool router. Customer-specific questions use the selected ID. Returned evidence includes actual application records.
10. **Reports** → generate → export JSON or CSV. Reports retain model version and limitations.

All 52 requested navigation entries are available through shared functional domain workspaces. Sidebar groups expand for deeper views. Light/dark mode, search, risk filters, pagination, validation errors, empty/loading states and notifications are provided.

## Fresh installation

Requires Python **3.12**, Node.js **22+**, and pnpm **10 or 11**. The system Python 3.15 is not the supported ML runtime. From the root, run `scripts/setup.ps1` first, then `scripts/start.ps1`. The setup script supports the bundled environment tooling in this Codex workspace.

For manual installation on any OS, create a Python 3.12 virtual environment, install `backend/requirements.txt`, then run `pnpm install --frozen-lockfile` inside `frontend`. Run `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` from `backend`, and `pnpm run dev` from `frontend`. API docs are at [localhost:8000/docs](http://127.0.0.1:8000/docs). The frontend uses a same-origin Vite proxy. Port 5174 is deliberate because another local application occupies 5173.

To stop local servers, stop their owning terminal sessions or their process IDs. The launch script uses hidden processes and does not alter other applications. It should only be run once while ports are free.

## Data contract

Required snapshot columns: `customer_id,total_orders,total_spend,days_since_last_purchase`. Optional supported fields are listed in `backend/app/data.py`. For training supply binary `churn_label` describing a future observation window. Do not derive labels from the same recency field used as a predictor. All feature values must precede the target observation window. When multiple snapshot dates are present, supply `snapshot_date` and `label_observed_at`; training purges overlapping future labels at time boundaries.

Uploads support CSV and JSON arrays of records, up to 10 MB and 20,000 rows. Column mapping is JSON such as `{"ClientID":"customer_id","Revenue":"total_spend"}`. Missing feature values use a training-fitted imputer. Duplicate IDs within one import keep the first row; IDs already in the database are rejected to preserve prediction evidence. Unknown/protected columns are ignored and reported. Uploaded aggregate snapshots do not invent transaction history. The three-row CSV in `data/samples` illustrates the schema; use the demo generator for a trainable dataset.

## Optional provider

Set `LLM_BASE_URL` (including `/v1` where required), `LLM_API_KEY`, and `LLM_MODEL` in the backend environment. No secrets are exposed by settings endpoints. Provider calls use a bounded OpenAI-compatible tool loop with transport timeouts. Live provider integration has not been verified without credentials. This code uses HTTP directly; LangChain is not required for provider calls. LangGraph handles deterministic specialized analytical agents, not nine separate paid LLM personas.

Install `backend/requirements-optional.txt` if you want XGBoost candidate comparison and imbalanced-learn available. Core models use class weighting; no SMOTE is applied. Optional packages are not required for local acceptance.

## Validation

From `backend`, run `..\.venv\Scripts\python.exe -m pytest tests -q`. Tests use a temporary SQLite database and runtime directory, independent of your application data.

From `frontend`, run `pnpm run test` and `pnpm run build`. With local backend/frontend servers running, run `pnpm run test:e2e`. The browser workflow creates a test account and synthetic records in the running development database; use an isolated runtime/database when testing with real customer records. It uses installed Google Chrome by default. On a machine without Chrome, install Playwright Chromium and set `PLAYWRIGHT_CHANNEL=chromium`. The test wrapper avoids the old TS ESM loader on Node 24 using a CommonJS test suite. See [verification record](docs/VERIFICATION.md) for checks actually executed here.

## Docker and PostgreSQL

Copy `.env.example` to `.env` and set unique database and JWT secrets. Run `docker compose up --build`. Open [localhost:8080](http://localhost:8080). Compose uses PostgreSQL, Alembic migrations, a persistent artifact/checkpoint volume, and nginx as the frontend/API proxy. Docker was not available in the implementation environment, so this path requires deployment testing. For production set `ENVIRONMENT=production`, use a random 48+ character `JWT_SECRET`, and provision the initial account using `docker compose exec backend python -m app.admin`. Public registration is disabled in production.

Local development creates tables at startup. Alembic is also available: run `python -m alembic upgrade head` from `backend` on a new database. The initial migration creates the current initial schema; future schema changes require new explicit migrations. Do not downgrade a database containing data you need.

## Important scope limits

This is a functional academic implementation, not a completed production rollout. RFM rules and a revenue proxy are implemented; probabilistic CLV, K-Means/DBSCAN alternatives, a communication provider, randomized causal impact estimation, historical observed churn trends, and distributed job/graph infrastructure are not implemented. Some modules intentionally share a workspace and expose the same evidence with different task context. No fabricated historical series, campaign uplift, or retained-customer count is substituted for missing observations.

Production also needs TLS, managed secrets, backups, a shared rate limiter, asynchronous jobs, distributed graph checkpointing, deployment security and load testing, and governed real-world evaluation. The local mean-shift diagnostic does not establish model drift or performance decay. No SHAP attribution proves causation. Synthetic results do not establish real-world accuracy or fairness.

See [architecture and limitations](docs/ARCHITECTURE.md), [implementation plan](docs/IMPLEMENTATION.md), and [verification record](docs/VERIFICATION.md).

## Reference documentation

Implementation follows the official [FastAPI authentication guidance](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [scikit-learn permutation importance API](https://scikit-learn.org/stable/modules/generated/sklearn.inspection.permutation_importance.html), and [LangGraph human interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts). Version-specific APIs were checked against the installed libraries during testing.
