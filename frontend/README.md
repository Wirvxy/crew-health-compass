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
