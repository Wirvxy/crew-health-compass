# NASA biological passport

`build_biological_passport` combines a selected OSD-575 postflight visit from A2 with longitudinal classifications from A3. It carries forward A2 values, units, baseline results, laboratory comparisons, and source coordinates. It uses the standard library and runs offline.

```python
def build_biological_passport(
    comparisons: Iterable[BiomarkerAnalysis],
    trajectories: Iterable[BiomarkerTrajectory] = (),
    *,
    astronaut_id: str,
    selected_visit: str,
    max_findings: int = 8,
) -> dict[str, object]: ...
```

The current dataset supports C001–C004 and R+1, R+45, R+82, and R+194. A malformed or preflight visit code raises `ValueError`. A selection absent from the supplied data raises `LookupError`. Duplicate or mismatched upstream records raise `ValueError`. Omit A3 input to return the visit snapshot with a trajectory coverage limitation.

## Person D

Build and retain A2 and A3 results when loading the NASA dataset. Use the same A2 result set for both steps so visits, units, and baselines agree. Return the dictionary directly from a read-only handler. Query strings must encode the literal plus, for example `visit=R%2B45`.

```python
from engine.biological_passport import build_biological_passport
from engine.biomarker_analysis import analyze_postflight
from engine.nasa_ingestion import load_osd575
from engine.trajectory_analysis import analyze_trajectories

comparisons = analyze_postflight(load_osd575())
trajectories = analyze_trajectories(comparisons)

def visit_passport(astronaut_id: str, visit: str) -> dict[str, object]:
    return build_biological_passport(
        comparisons, trajectories, astronaut_id=astronaut_id, selected_visit=visit,
    )
```

The [complete C002 R+45 response](biological_passport_examples/c002_r45.json) is generated from the NASA files and checked against the live engine in the tests. Decimal fields are strings and unavailable fields are JSON null.

## Person C

- Render visit-level counts and the `panels` array. `group` organizes metabolic, cardiovascular, and immune panels. Use `panel` as the identifier, including for the two separate immune panels.
- Show `selected_findings` in response order. The order is outside an available lab bound, selected CMP changes, notable A3 patterns, and data gaps. The CMP selection uses a fixed list of glucose, creatinine, sodium, potassium, and albumin. Ties use the stable panel and biomarker order. The default limit is eight findings. Full counts and limitations remain available even when findings are capped.
- Use the original units. `source` is the CSV file, one-based line, and value column. `source_references.samples` lists the unique CSV rows and sample IDs for the selected visit. The study URL supplies its NASA provenance.
- Display `trajectories.label` (“Full historical trajectory”) beside A3 classifications, including classifications in selected findings. When `includes_later_observations` is true, the supplied A3 series include valid observations after the selected visit. Read `trajectories.panels[panel][biomarker]` for the classification and use the existing A3 trajectory response for chart points.
- Show `measurement_status_counts` for missing or invalid readings. Display lab `unavailable` as “Laboratory comparison unavailable.” The nested `coverage` counts describe supplied bounds independently of reading status. Show one-sided comparisons as comparisons with the available bound.

The four postflight samples are irregularly spaced and provide a sparse research record. The summary describes recorded changes and supplied reference limits. Its evidence order does not grade medical risk, and full-series classifications do not establish recovery or causality.
