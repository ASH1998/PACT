# PACT — Static Demo

A **backend-free** copy of the PACT dashboard, deployed to GitHub Pages at
**https://ash1998.github.io/PACT/**. It exists purely to show the UI and a
snapshot of run history to people who don't have the backend running.

The production app lives in [`../frontend`](../frontend) and is **not modified
by this directory** — `demo/` is a standalone copy with three differences:

| | `frontend/` (real app) | `demo/` (this) |
|---|---|---|
| Data source | live FastAPI backend via `/api` | static JSON in `public/data/` |
| Router | `BrowserRouter` | `HashRouter` (deep links work on Pages) |
| Vite `base` | `/` | `/PACT/` |

## How it works

- `src/api/client.ts` defaults to **static mode** (`VITE_STATIC` ≠ `"false"`).
  Every GET is mapped to a captured snapshot under `public/data/`; the two
  mutations (`runScenario`, `tamperLedger`) are synthesized client-side so the
  demo buttons still do something visible.
- Snapshots are a point-in-time capture of a real backend. Refresh them with:

  ```bash
  source .venv/bin/activate
  uv run --project backend --active uvicorn app.main:app --app-dir backend --port 8000   # terminal 1
  ./demo/scripts/capture-snapshots.sh              # terminal 2
  ```

## Deploy

Pushing changes under `demo/**` to `main` triggers
[`.github/workflows/deploy-demo.yml`](../.github/workflows/deploy-demo.yml),
which builds `demo/` and publishes `demo/dist` to GitHub Pages.

**One-time setup:** repo **Settings → Pages → Source → "GitHub Actions"**.

## Local development

```bash
cd demo
npm install
npm run dev          # static demo at http://localhost:5173
npm run build        # outputs demo/dist
npm run preview      # serve the built site at /PACT/
```

To run the demo UI against a live local backend instead of snapshots, start the
backend and run `VITE_STATIC=false npm run dev`.
