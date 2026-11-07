# Verification record — 5 November 2026

## Requested Create account option — deployed

The hosted sign-in page now includes Create account. Registration is explicitly enabled using backend `ALLOW_PUBLIC_REGISTRATION=true` and frontend `VITE_ALLOW_REGISTRATION=true`. Production signups always receive the analyst role, even in an empty database. They cannot choose their role, view administrator-only user management or approve campaigns. Existing administrator credentials are unchanged.

- Focused backend registration/bootstrap tests: **3 passed**.
- Frontend tests: **6 passed**; TypeScript and Vite production build passed.
- Railway deployment `05f65523-9c52-41db-851e-4815f1b791b1`: `SUCCESS`.
- Vercel deployment `dpl_zpy1TDnJkQ7Gh1Lzc1gx37NW3eJf`: `READY` at the existing production URL.
- Live Chrome test passed account creation, automatic analyst sign-in, restricted administrator access and subsequent sign-in. Test accounts use synthetic example.com addresses; no verification emails are sent.
- Screenshots: `frontend/test-results/create-account-option.png` and `frontend/test-results/create-account-form.png`.

## Full hosted demo — verified

- Frontend: https://retainiq-ai.vercel.app. Connected production deployment: `dpl_A4MjYJCZPAof8QyVrDbBU3gSxZ3J` (`READY`).
- Backend: https://retainiq-api-production.up.railway.app. Railway built the Docker image and deployed `54ceea66-c979-4bb3-8af1-dc170a4a39d3` with persistent storage mounted at `/app/runtime`.
- Initial administrator and signing-secret provisioning were explicitly approved by the user. Secrets were configured through stdin to the hosting CLI, excluded from source files, and not recorded in this document. Production registration remains disabled.
- Hosted API checks passed: health, authentication/unauthorized access, exact-origin CORS, synthetic dataset creation, four-model training/evaluation, 360 batch predictions, local/global SHAP, segmentation, LangGraph execution, tool-grounded local assistant, report creation/CSV export and analytics. Detailed non-secret results are in `hosted-verification.json`.
- The backend was restarted after seeding. Chrome browser checks then passed for login, persisted 360-customer analytics, prediction using the persisted model artifact, existing agent records and assistant retrieval.
- Desktop/mobile browser checks passed without horizontal page overflow or uncaught JavaScript errors. Screenshots: `frontend/test-results/hosted-dashboard-desktop.png` and `frontend/test-results/hosted-dashboard-mobile.png`.
- Final automated suites: **8 backend tests passed**, **4 frontend tests passed**, TypeScript/Vite build passed. External paid LLM integration, PostgreSQL/Compose and the alternative Render blueprint remain unverified. The hosted database is SQLite on the persistent volume, with a single API instance.
- The demo has a recommendation awaiting review. No customer communication was sent and no campaign outcome was invented.

## Persistent backend preparation follow-up

Earlier preparation record: Railway project, API service and persistent volume were created. The container startup and optional administrator bootstrap were tested, including first-account creation and prevention of account/password overwrite. Tests initialize their isolated database before any application imports. The subsequent completed cloud verification is recorded above.

## Vercel deployment follow-up

- Frontend deployed to https://retainiq-ai.vercel.app in project `resume-project3/retainiq-ai`; Vercel returned `READY` for deployment `dpl_5ukbi6fNt4D2QQKmtS7d8pFcTtea`.
- TypeScript/Vite production build passed with the cloud connection screen; frontend suite now has **4 passing tests**.
- Backend hosting is prepared in `render.yaml` and `docs/DEPLOYMENT.md`, not provisioned. The unconnected cloud frontend explicitly states this status. The local full-stack application continues to use the Vite API proxy.
- Render YAML parsed and required paths/settings were checked locally. Docker image execution and a hosted backend remain unverified.

## Executed successfully

- Python 3.12 isolated environment installed; FastAPI, SQLAlchemy, scikit-learn, SHAP and LangGraph imports executed.
- Backend pytest suite: **7 passed**. Covers JWT login and roles; CSV/JSON uploads; mapping, duplicates and protected-column exclusion; absent transaction history; target exclusion; four candidate models; validation selection and held-out metrics; predictions; actual local/global SHAP; RFM; persisted LangGraph execution and human approval/resume; local assistant evidence; denied reviewer tool calls and logging; consent-blocked campaigns; approved campaign outcomes; duplicate outcome prevention; reports/export; configurable thresholds; audit and mean-shift diagnostics; sparse optional columns; invalid target-window rejection.
- TypeScript compilation and Vite production build passed. React/chart vendor code split into separate chunks; final build had no chunk-size warning.
- Vitest / React Testing Library: **3 passed**. Missing values remain unavailable, drafts are labeled, and 52 module routes are unique.
- SQLite Alembic `upgrade head` executed successfully.
- Local API health and frontend HTTP endpoints each returned HTTP 200.
- Local UI opened in the in-app browser and customer directory visually inspected, including its legitimate empty state.

## Browser workflow

The Playwright suite in `frontend/e2e` completed: **1 passed** in approximately one minute using installed Google Chrome. It exercised account creation, synthetic import, model training, batch prediction, high-risk filtering, customer prediction, LangGraph execution, local assistant tool retrieval, report generation/download, and desktop/mobile rendering without horizontal page overflow or uncaught JavaScript errors. Screenshots are saved under `frontend/test-results`.

Early attempts uncovered a Node 24 / older Playwright TS ESM-loader hang, resolved with CommonJS config/tests and a wrapper disabling the unneeded TS ESM loader. A subsequent attempt found no downloaded Playwright headless browser; configuration now uses installed Google Chrome by default. Test assertion mistakes were corrected. A later browser run exposed directory latency after repeated demo imports; customer pagination now executes in SQL and segment lookups are batched. Customer context now persists across reloads. Failed earlier attempts are not counted as passed tests.

## Not verified

- Paid/live OpenAI-compatible provider: no credentials were supplied. Local tool mode was exercised.
- Docker build and PostgreSQL runtime: Docker is unavailable on this host. Compose, images and migration path are provided but not represented as tested.
- Optional XGBoost/imbalanced-learn: not installed during core verification. XGBoost is conditionally included in candidate comparison when available.
- Real-world prediction quality, fairness and retention benefit: no governed real dataset, randomized treatment groups or independent campaign outcomes were supplied. Synthetic data validates application mechanics only.

## Known non-failing dependency warnings

Starlette/AnyIO and LangGraph emit deprecation notices. scikit-learn 1.6.1 with the resolved newer SciPy emits an ignored `iprint` solver-option warning; fitting completed and all metric checks passed. Package versions actually installed are recorded in `backend/requirements-lock.txt`. Recharts 2 is a maintenance concern; migration to Recharts 3 is a follow-up before production rollout.
