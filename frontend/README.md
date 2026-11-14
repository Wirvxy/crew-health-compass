# Frontend

React + Vite + TypeScript starter.

## Run

```powershell
cd frontend
npm install
npm run dev
```

## Check production build

```powershell
npm run build
```

## Folders

- `src/assets`: images and SVG assets
- `src/components`: reusable UI components
- `src/pages`: application screens
- `src/services`: API access
- `src/types`: types matching the shared contracts
- `public`: static files

Dataset response models follow the documented backend serializers. Daily check-in contracts and clinical rules are still pending.

## Atmospheric dashboard

The approved atmospheric prototype is implemented as React components:

- `src/pages/Dashboard.tsx`: shared view state, role presentation and simulation controls
- `src/components/TopBar.tsx`: product, crew, mission context and simulation label
- `src/components/DailyCheckIn.tsx`: session-local form and validation
- `src/components/BodyMap.tsx`: 3D body viewer, system cards and mission visits
- `src/components/SystemDetail.tsx` and `TrendChart.tsx`: evidence and trends
- `src/services/assessment.ts`: mock-response loader and presentation adapter
- `src/services/report.ts`: local text-only PDF export
- `src/index.css`: embedded Inter fonts, responsive layout and atmospheric theme

`public/mock/assessment.json` is a provisional frontend fixture, not a shared team contract. Recorded OSD-575 assay measurements remain source-labelled; system statuses and drift hints are simulated fixtures. Clinical rules await the team catalogue. The daily form starts blank, with an explicit synthetic example action. Submissions and drafts exist only in memory until reload. Mars sync is simulated, and role views are not access control.

No dependencies were added. ESLint is not configured in this starter; `npm run build` checks TypeScript and builds the application.

## Body visualization

The active body viewer is a neutral, rotatable 3D astronaut. Earlier segmented-muscle assets and their Apache-2.0 licence files remain in the repository but are not exposed by the current viewer. No dataset laboratory classification drives organ colors.

## NASA dataset integration (PR #13 response shapes)
The default **NASA laboratory data** workspace calls all six endpoints through `src/services/dataset.ts`. Consumed fields are validated in `datasetResponse.ts`; the complete raw response is retained. Trajectory and comparison response shapes in `docs/osd575-api.md` are accepted by the frontend. These remain provisional shared contracts; no backend or shared-contract files were changed.

Run the backend from the repository root as documented by D, then run `npm run dev` in frontend. Vite proxies `/datasets` to `http://127.0.0.1:8000`. If that port is unavailable, run uvicorn with `--port 8015` and set `DATASET_PROXY_TARGET=http://127.0.0.1:8015` in an ignored `frontend/.env.local`. Production hosting must route `/datasets` to the API on the same origin; this dev proxy is not a deployment configuration.

All visits supplied by the API, including R+194, are exposed. The dataset UI uses A's **preflight average**, never the old mock median. Decimal strings and nulls are retained; numbers are converted only for charting/display. Raw responses, source CSV row/column, units, baseline status, laboratory status, notes and evidence limitations remain inspectable. The chart uses equally spaced visit positions and leaves gaps for missing observations. Descriptive classifications never drive health colors or organ effects.

The existing check-in/body prototype remains a separate, visibly simulated workspace. It is not connected to the read-only dataset endpoints. Changing workspaces retains session-local check-ins. API/network/schema failures show an error with Retry, never mock fallback. Requests are canceled on selection changes to prevent old crew results overwriting the current selection.


Validation on 14 November 2026: production build passed; live-browser checks covered C001 glucose at R+1, R+194, preflight handling, C002 missing BUN/creatinine-ratio observations, four-crew comparison, all four panel response shapes, preserved exact decimals, rejected malformed numeric fields, HTTP 404/422/503, 503 retry without mock fallback, and 390/768/1440px layouts. No new frontend dependency was added. ESLint is not configured.
