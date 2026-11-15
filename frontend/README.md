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

## Structure

| Path | Contents |
|---|---|
| `src/App.tsx` | App shell: sidebar, shared page heading and the three pages |
| `src/pages/Dashboard.tsx` | Mode 1 state: check-in drafts, results, examples, Mars-ready link simulation |
| `src/pages/RadiationHistory.tsx` | Mission Environment page: date range, radiation timeline, May 20 event card, limitations |
| `src/pages/NasaDataset.tsx` | Mode 2 page: crew, panel, biomarker and visit selection, history chart, trajectories |
| `src/components/` | `DailyCheckIn`, `BodyMap` and `Astronaut3D` (three.js viewer with the body marker), `MonitoringDetail` (evidence panel), `PassportSummary` (A4), `RadiationChart` (SVG timeline with gaps, event band, hover and drag-to-zoom), `Sidebar`, `PageHeader`, `TopBar`, `DataNotes`, `StatusLabel` |
| `src/services/` | `api.ts` (base URL), `monitoring.ts` (Mode 1 requests), `dataset.ts` and `datasetResponse.ts` (Mode 2 requests and shape checks), `radiation.ts` (Mission Environment requests), `report.ts` (local PDF export) |
| `src/types/` | View-model and dataset types |
| `src/assets/fonts/` | Inter font files |
| `public/models/astronaut/` | 3D model and textures |
| `public/licenses/` | Licence notices for the 3D model and the font |

## How data is shown

- **Mode 1** (Daily check-in, Body & systems):
  - The form sends the exact request from `engine/MODE1_CONTRACT.md` to `POST /api/monitoring/assess`. The backend's statuses map to green, amber or grey for display only.
  - A marker appears on the astronaut only where the backend returns `body_marker`.
  - Example buttons fill labelled demo values; they are sent as a manual check-in (see the open points in [docs/mode1-api.md](../docs/mode1-api.md)).
- **Mode 2** (NASA lab data):
  - All values come from the `/datasets/osd575/...` endpoints. The page keeps decimal strings and nulls, converts numbers only for display, and shows gaps for missing readings.
  - The A4 passport labels "laboratory comparison unavailable" separately from missing readings.
- **Mission Environment** (Mars Radiation History):
  - The chart draws the API's readings as they are: no interpolation. The line breaks where readings are more than 3 hours apart, and a dashed line marks where the export ends.
  - The event card reads every number from `/api/environment/radiation/events/may-20-2024`. The tab never affects a health status.
- **Errors:** API failures show a message, never fallback data, and a page that cannot load offers Retry. Results stay in memory until the page is reloaded.
