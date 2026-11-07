# Vercel frontend and persistent backend

## Live Railway backend

A separate Railway project `retainiq-ai-backend` (`0fbb2ade-5ca8-4f15-883c-a972dae6847f`) and API service `retainiq-api` (`01ee5b3b-7d63-4894-a9ec-27624c2301c3`) have been created. A persistent volume is mounted at `/app/runtime`. No local customer records or accounts are copied.

The Docker entrypoint initializes mounted-volume ownership, drops root privileges before running migrations and the API, and respects the hosting port. Optional `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` hosting secrets can provision the first administrator only; they never change an existing account or its password. Production public registration is opt-in through `ALLOW_PUBLIC_REGISTRATION=true`. The hosted demo now enables this at the user’s request; all public production signups are analysts, including the first signup in an empty database. The frontend shows Create account when `VITE_ALLOW_REGISTRATION=true`.

Backend URL: https://retainiq-api-production.up.railway.app. Initial administrator and JWT secrets were explicitly approved and configured through Railway secret settings. Deployment `54ceea66-c979-4bb3-8af1-dc170a4a39d3` built successfully. Hosted login, CORS, synthetic data creation, model training, batch scoring, SHAP, segmentation, agent execution, assistant tools and report export passed. A restart was issued to verify persistence before browser testing. The Vercel production frontend now has `VITE_API_BASE_URL` pointing to this backend. The prepared Render blueprint below is an alternative and has not been applied.

Frontend production URL: https://retainiq-ai.vercel.app

Vercel project: `resume-project3/retainiq-ai`. Deployment completed with `readyState: READY` on 5 November 2026. Existing Vercel authentication/protection settings were preserved. The user can manage this project from https://vercel.com/resume-project3/retainiq-ai.

The frontend is deployed on Vercel and the backend on Railway. Source-only uploads excluded the local database, customer records, model artifacts and credentials. A fresh synthetic dataset was generated on the hosted backend. Vercel uploads remain restricted to the frontend directory; environment files and test artifacts are excluded.

## Frontend

Deploy with the Vercel project root set to `frontend`. `frontend/vercel.json` configures a Vite production build, static output, SPA routes and basic security headers. The default cloud build shows an explicit backend connection screen. Local development continues to use `/api` through the Vite proxy and is unaffected.

After hosting the backend, add this public build-time environment variable in the Vercel project:

```text
VITE_API_BASE_URL=https://your-api-host.example.com/api
```

Set it for Production (and Preview only when that environment has a backend), then redeploy. The connection screen becomes the sign-in screen. Never place database credentials, JWT secrets or LLM API keys in `VITE_*` variables: Vite embeds them in the browser bundle.

The production frontend calls the backend directly over HTTPS. Backend `CORS_ORIGINS` must list the exact frontend origin, without a trailing slash. Authorize preview domains individually rather than enabling an unrestricted wildcard.

## Prepared Render backend

`render.yaml` is a deployment blueprint, not a provisioned service. Its standard compute plan and persistent disk are paid hosting resources; review them in your Render account before creation. Docker/PostgreSQL hosting through the existing Compose file remains another option.

1. Push this repository to your own Git host. Create a Render Blueprint from `render.yaml`. There is currently no Git remote configured by this task.
2. Supply a unique `JWT_SECRET` of at least 48 characters and `CORS_ORIGINS=https://retainiq-ai.vercel.app`. Generate a secret with a password manager or locally using Python's `secrets.token_urlsafe(48)`; put it directly in the hosting secret settings.
3. The image runs Alembic before Uvicorn and uses the hosting `PORT` value. `/api/health` is the health check. Mount `/app/runtime` as a writable persistent volume for the application user. This directory stores the SQLite application database, Joblib models and SQLite LangGraph checkpoints.
4. Keep one service instance. A shared filesystem is not a replacement for distributed database/checkpoint infrastructure. The blueprint deliberately avoids ephemeral files for durable application state.
5. With `ENVIRONMENT=production`, public registration is disabled. Use the Render service shell to run `python -m app.admin` and provision your own administrator. No existing local/test account is deployed.
6. Verify `https://your-service.onrender.com/api/health`, set the Vercel environment variable above, and redeploy the frontend.
7. Sign in, create a synthetic dataset, train, predict, inspect SHAP and run the orchestrator. Review campaign drafts before recording externally observed outcomes. No customer messages are sent by this application.

Leave LLM environment variables absent for the local tool router. Add `LLM_BASE_URL`, `LLM_API_KEY` and `LLM_MODEL` only on the backend when a provider is desired. Model training runs within request handlers in this academic implementation; use a persistent host with sufficient memory and a suitable request timeout. Larger real workloads require a background job system.

For PostgreSQL, provide `DATABASE_URL=postgresql+psycopg://...` through backend secret settings and keep the artifact/checkpoint disk. Normalize any provider's `postgres://` connection string to SQLAlchemy's psycopg form. Do not remove persistent storage until the model artifact and graph checkpoint architecture has been migrated too.

## Verification boundaries

The frontend build and connection-screen test can be verified without backend hosting. The Render blueprint has not been applied. Docker is unavailable locally, but Railway built and ran the backend image remotely. Hosted API verification is recorded in docs/hosted-verification.json; browser/persistence verification results are recorded in docs/VERIFICATION.md.

Official references: [Vercel Vite deployments](https://vercel.com/docs/frameworks/frontend/vite), [Vercel Python runtime/filesystem constraints](https://vercel.com/docs/functions/runtimes), [Render blueprint specification](https://render.com/docs/blueprint-spec), and [Docker on Render](https://render.com/docs/docker).
