# Frontend

React + Vite + TypeScript interface for both modes. It shows the backend's results and does no health assessment of its own.

## Run

The backend must be running first (see the [root README](../README.md#run-it-locally)). Then:

```powershell
cd frontend
npm ci
npm run dev
```

In development, Vite forwards `/api` and `/datasets` to the API at `http://127.0.0.1:8000`, so the browser talks to one origin and no CORS is needed.

## Settings

Copy [`.env.example`](.env.example) to `frontend/.env.local` (Git ignores it) to change:

- `DATASET_PROXY_TARGET`: where the dev server forwards API calls, for example when the API runs on another port.
- `VITE_API_BASE_URL`: the backend URL baked into a build. Leave it empty to use the same origin. Another origin would need the server to allow it.

## Checks

```powershell
npm run build
```

This checks TypeScript and builds the app into `dist/`. ESLint is not configured. CI also runs `npm audit --audit-level=high`.

```powershell
npm test
```

This runs the "Plan for today" day-rule tests in `tests/` with Node's built-in test runner (Node 24; no extra dependency). CI does not run it yet. The plan's progress rules run on the backend (`api/tests/test_personal.py`).

## Structure

| Path | Contents |
|---|---|
| `src/App.tsx` | Session states (checking, start page, workspace). Each profile session gets a fresh workspace (sidebar, shared heading, four pages), opening on Daily check-in. It re-checks the session on reload, focus, Back/Forward and when another tab changes it |
| `src/pages/ProfilePicker.tsx` | Start page: click a crew profile (demo access control, no passwords) |
| `src/pages/Dashboard.tsx` | The signed-in astronaut's Mode 1 workspace: draft, examples, latest result and saved history. Late answers are dropped when it closes |
| `src/pages/RadiationHistory.tsx` | Mission Environment page: date range, radiation timeline, May 20 event card, limitations |
| `src/pages/NasaDataset.tsx` | Mode 2 page: crew, panel, biomarker and visit selection, history chart, trajectories |
| `src/components/` | `DailyCheckIn`, `BodyMap` and `Astronaut3D` (three.js viewer with the body marker), `MonitoringDetail` (evidence panel), `PassportSummary` (A4), `RadiationChart` (SVG timeline with gaps, event band, hover and drag-to-zoom), `PlanForToday` (daily checklist beside the check-in form), `RecentCheckIns` (the profile's saved check-ins), `Brand` (logo link), `Sidebar` (page list, signed-in name, Log out), `PageHeader`, `TopBar`, `DataNotes`, `StatusLabel` |
| `src/services/` | `api.ts` (base URL), `monitoring.ts` (Mode 1 requests), `dataset.ts` and `datasetResponse.ts` (Mode 2 requests and shape checks), `radiation.ts` (Mission Environment requests), `report.ts` (local PDF export), `session.ts` (profile sessions; every personal answer must name the open profile), `personal.ts` (saved check-ins and plan), `dailyPlan.ts` (the UTC day rule) |
| `src/types/` | View-model and dataset types |
| `src/assets/fonts/` | Inter font files |
| `src/assets/brand/` | The logo, unchanged from the original PNG (see `NOTICE`) |
| `src/assets/profiles/` | One photo per crew profile, named by profile ID (`ProfilePhoto` shows it on the start page, the sidebar and the top bar). Source and licence not yet documented: see `NOTICE` |
| `tests/` | Tests for the "Plan for today" rules (`npm test`) |
| `public/models/astronaut/` | 3D model and textures |
| `public/licenses/` | Licence notices for the 3D model and the font |

## How data is shown

- **Mode 1** (Daily check-in, Body & systems):
  - The form sends the exact request from `engine/MODE1_CONTRACT.md` to `POST /api/monitoring/assess`. The backend's statuses map to green, amber or grey for display only.
  - A marker appears on the astronaut only where the backend returns `body_marker`.
  - Example buttons fill labelled demo values; they are sent as a manual check-in (see the open points in [docs/mode1-api.md](../docs/mode1-api.md)).
- **Plan for today** (beside the check-in form):
  - Four tasks per astronaut: complete today's check-in, include sleep duration, include a mood, and review today's result.
  - The first three are done automatically, only after the backend has assessed a check-in, and the optional ones only when that check-in included the value. The last one is ticked by the user.
  - Progress resets at 00:00 UTC by the computer's clock, also while the page is open. It is saved on the backend for the signed-in profile only; the browser stores nothing.
- **Mode 2** (NASA lab data):
  - All values come from the `/datasets/osd575/...` endpoints. The page keeps decimal strings and nulls, converts numbers only for display, and shows gaps for missing readings.
  - The A4 passport labels "laboratory comparison unavailable" separately from missing readings.
- **Mission Environment** (Mars Radiation History):
  - The chart draws the API's readings as they are: no interpolation. The line breaks where readings are more than 3 hours apart, and a dashed line marks where the export ends.
  - The event card reads every number from `/api/environment/radiation/events/may-20-2024`. The tab never affects a health status.
- **Errors:** API failures show a message, never fallback data, and a page that cannot load offers Retry. Check-ins and results are saved per profile on the backend; drafts stay in memory until reload or logout.
