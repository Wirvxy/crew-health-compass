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

Add API models after the team supplies its contracts. No health rules or sample medical values are included.

## Atmospheric dashboard

The approved atmospheric prototype is implemented as React components:

- `src/pages/Dashboard.tsx`: shared view state, role presentation and simulation controls
- `src/components/TopBar.tsx`: product, crew, mission context and simulation label
- `src/components/DailyCheckIn.tsx`: session-local form and validation
- `src/components/BodyMap.tsx`: SVG system map and mission visits
- `src/components/SystemDetail.tsx` and `TrendChart.tsx`: evidence and trends
- `src/services/assessment.ts`: mock-response loader and presentation adapter
- `src/services/report.ts`: local text-only PDF export
- `src/index.css`: embedded Inter fonts, responsive layout and atmospheric theme

`public/mock/assessment.json` is a provisional frontend fixture, not a shared team contract. Recorded OSD-575 assay measurements remain source-labelled; system statuses and drift hints are simulated fixtures. Clinical rules await the team catalogue. The daily form starts blank, with an explicit synthetic example action. Submissions and drafts exist only in memory until reload. Mars sync is simulated, and role views are not access control.

No dependencies were added. ESLint is not configured in this starter; `npm run build` checks TypeScript and builds the application.

## Segmented muscle map

The atmospheric dashboard now uses 89 source-defined SVG regions from Body Muscles by Ivan Vulovic (Apache-2.0). Front/back geometry is in `src/data/muscles.ts`; the displayed path is also its click target. `BodyMap.tsx` handles selection and `MuscleReport.tsx` handles user-entered intensity, description and onset. Copyright and licence files are in `public/licenses/`.

Muscle reports are kept per crew in tab-session memory, support local JSON export, and are included in the crew PDF. Saving the same muscle/view updates that report. They are not inferred from serum measurements or submitted to the backend. Clinical statuses remain source-labelled mock fixtures.

### Proposed OSD-575 API preparation
`src/services/dataset.ts` owns all proposed dataset request construction. It is not called automatically until tested response examples and the launch URL arrive. Set the origin through `createDatasetService(origin)` at integration; empty origin means same-origin. Requests support AbortSignal. HTTP 404/422/503 are typed errors; network and cancellation failures propagate to the caller. No failure silently falls back to mock data.

Responses remain `unknown`: the final adapter must validate the tested backend shape and preserve original decimal strings/nulls, units, provenance, baseline status and laboratory status. `chartNumber` is for chart coordinates only. `DatasetComparisonView` is a frontend display model, not an API contract. The visible preview uses the existing local median baseline and labels API laboratory comparison as pending. Do not substitute the proposed backend baseline calculation with this local method.

Acceptance case when backend is available: C001 / cmp / glucose / R+1 => 90 mg/dL, baseline approximately 77.33, change approximately +12.67, laboratory status within. This example is not injected into the existing dataset. Organ effects remain independent of laboratory comparisons.
