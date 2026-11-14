# Mode 1 personal statistical detection

Build a `HistoryIndex` once from M1 observations and rebuild it when the source history changes. Pass a manual payload to `assess_check_in` or a synthetic row to `assess_observation`. Both return a JSON-ready dictionary accepted by `validate_assessment`.

```python
from engine.mode1_detection import HistoryIndex, assess_check_in, assess_observation
from engine.mode1_ingestion import load_monitoring_data

observations = load_monitoring_data("path/to/iss-synthetic-3000.zip")
history = HistoryIndex(observations)
simulated_result = assess_observation(observations[-1], history)
# manual_result = assess_check_in(decoded_request, history)
```

History matches the exact astronaut ID, activity context, source protocol, reading kind, and unit. Only valid finite values strictly earlier than the input timestamp qualify. The index normalizes times to UTC and rejects duplicate timestamps within a valid series. The 150 observations per crew member and context support a default window of the latest 14 readings. Seven qualifying readings are required for a statistical comparison.

| Manual context | Supported historical comparison |
|---|---|
| `morning_check` | Apollo 10 average heart rate |
| `inflight_vitals_check` | Apollo–Soyuz mean heart rate and breathing rate |
| `rest`, `exercise`, `recovery` | Skylab mean heart rate and both blood pressures within the exact context |
| `other` | No mapped comparison |

Use a comparable sampling protocol for manually entered values. For example, choose `exercise` for comparison with the archived level-3 cycling protocol only when the input was collected under comparable conditions. The manual contract carries broad context labels and does not verify the protocol itself. Breathing rate and ventilation have distinct keys. Synthetic replay keeps peak, average, and mean readings in their original series. Sleep has no mapped historical reference. Mood keeps its category and has no numerical score.

## Statistics and status

`DetectionConfig` sets the minimum and window, the robust score threshold, the numerical MAD floor ratio, and the indicator and body-marker mappings. The default score is `0.6745 * (current - median) / MAD`, where MAD is the median absolute deviation of history from its median. A score qualifies as unusual when its absolute value is strictly greater than 3.5. The value is an exploratory statistical cutoff. Zero MAD or MAD below `max(abs(median), 1) * 1e-12` leaves the comparison indeterminate. The floor protects against division by very small variability.

Theil–Sen is the median pairwise slope using actual UTC time differences. Its unit is the indicator unit per day. The slope and history span are available from two prior samples and describe history only. Calculations use 34 significant decimal digits. The JSON payload preserves input decimal strings and computed precision.

An independent replay of all 13,200 indicators confirmed 1,209 zero-MAD windows. Only 16 windows had identical readings throughout. In the other 1,193, more than half of the readings equaled the median, even though other values varied. For example, Flight Engineer 1's prior Apollo–Soyuz mean heart rates were 67, 71, 71, 71, 70, 71, and 74 bpm. Four of seven readings equaled the median of 71 bpm, so the median absolute deviation was zero. The current reading differed from the median in 715 of the 1,209 cases. Zero MAD leaves the robust score and anomaly flag unavailable in all of these cases.

Overall status is `unusual` when any supported indicator is unusual, `normal` when at least one comparison is supported and all supported comparisons are normal, and `insufficient_data` when none can be evaluated. Check `insufficient_data` even when the overall status is `normal`. Affected systems and the body marker come from unusual indicators. The first mapped affected system supplies the single contract marker. Trends never change status. M2 emits null rule, protocol, and ML fields.

## Contract changelog for C and D

M1 requests and existing assessment fixtures remain valid. M2 adds optional `statistics` and `category` fields within an evidence item. `category` carries self-reported mood. `statistics` carries `mad`, `absolute_deviation`, `robust_z`, `status`, nullable `anomaly`, `observation_count`, `history_span_days`, `trend_slope_per_day`, and `history_origins`. The top-level `data_origin` applies to the current input. For example, a manual assessment can have `data_origin="user"` with `history_origins=["synthetic"]` in its evidence. Use [the emitted replay example](mode1_examples/statistical_assessment.json) for display testing.

Evaluation labels are outside the history index and scoring interfaces. The replay verifies behavior on fictional observations. Protocol and cohort differences limit comparisons with real manual readings.
