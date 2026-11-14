# Crew Health Compass · Long-duration ISS simulation

This package provides 3,000 new rows for context-aware health monitoring and anomaly detection. It follows four fictional astronauts across 180 days, with observations on 150 days. Each of the three CSVs preserves its corresponding reference header, column order, numeric types, and observed measurement bounds. All 3,000 rows are synthetic.

| CSV | New rows | Measurements and context |
|---|---:|---|
| `apollo10_heart_rate_iss_synthetic.csv` | 600 | Morning health check heart rate. |
| `apollo_soyuz_inflight_vitals_iss_synthetic.csv` | 600 | Mean and peak heart rate and breathing rate during routine and high-workload checks. |
| `skylab4_inflight_exercise_iss_synthetic.csv` | 1,800 | Heart rate, systolic and diastolic blood pressure, ventilation, oxygen uptake, and carbon dioxide output at rest, during cycling, and during recovery. |

## Load and replay

1. Import each CSV using its existing schema. The file names refer to the source schemas. All observations represent fictional ISS operations.
2. Load the matching `*_timeline.json` when replaying the mission. Each timeline entry links to its CSV via `csv_row`, the one-based data row number excluding the header. Join by row number before sorting, filtering, or appending the CSV. Use `timestamp_utc` to replay observations and `crew_role` to look up the stable profile in `crew_profiles.json`. This also resolves the capitalized roles in the Apollo 10 format.
3. Keep the scenario labels available for evaluation. The simulator assigns **2,905 normal rows**, **92 mild rows**, and **3 critical-priority drill rows**. These are row counts for software testing. The three drill rows represent persistent exertion-like heart rate and ventilation during recovery, judged relative to each fictional crew member's previous sessions. They do not establish medical emergency criteria or event rates.
4. Use separate measurement series for breathing rate (breaths/min) and minute ventilation (L/min). Oxygen uptake (L/min) describes gas exchange. SpO₂ (%), body temperature, sleep, bone density, muscle mass, radiation dose, and repeat body mass measurements have no columns in these schemas. The crew profiles supply fixed demographics and simulated preflight mass.

## Simulation basis

- ISS context uses an approximately six-month mission with cycle-exercise and recovery monitoring. Source anchors come from historical astronaut summary tables. The code applies a crew-specific baseline, a small early-flight adjustment that tapers, evolving workload, and linked exercise and recovery responses. The size and timing of those effects are modeling choices. [NASA ISS health care](https://www.nasa.gov/missions/station/faq-the-real-story-about-astronaut-health-care-in-space/) · [NASA exercise overview](https://www.nasa.gov/ochmo-tb-031-exercise-overview-2/)
- Each CSV keeps the numerical range of its own input. Study significance marks are blank in synthetic exercise rows. The Apollo 10 source URL identifies the historical comparison table, and the Apollo–Soyuz `synthetic_available` status marks available modeled values. [Apollo 10 Table 10-I](https://www.nasa.gov/wp-content/uploads/2025/11/a10-missionreport.pdf#page=181) · [Apollo–Soyuz Table 3-I](https://ntrs.nasa.gov/api/citations/19770023791/downloads/19770023791.pdf) · [Skylab M171 Tables III–V](https://ntrs.nasa.gov/api/citations/19750006309/downloads/19750006309.pdf)
- The timing is a demo calendar. Individual radiation, confinement, sleep, and musculoskeletal effects cannot be quantified from these inputs. The simulated joint distributions and anomaly labels have no validation against continuous ISS telemetry.
