# Curiosity RAD radiation history

R1 serves historical measurements from Curiosity's Radiation Assessment Detector (RAD) on the Martian surface. The supplied CSV is Person B's export of the NASA CDAWeb Level 2 archive. Every reading carries the original NASA CDF URL, and each response identifies the CSV and its SHA-256. [NASA dataset catalogue](https://data.nasa.gov/dataset/mars-science-laboratory-msl-radiation-assessment-detector-rad-level-2-observation-dosimetr)

## Data and provenance

The default path is `raw data/NASA Curiosity radiation/nasa_curiosity_rad_2024-03-07_to_2024-05-20.csv` from the repository root. The same export is on Person B's `origin/data` branch. Pass a local file path explicitly if the branch being used for integration lacks the default path. The inspected local CSV has SHA-256 `d514a88fdc9a539a3b470b57a4d28c95cec6b1494474c696a27d629cda1cdea5`. Line endings may affect the hash.

The four columns are `timestamp_utc`, `absorbed_dose_rate_ugy_per_day`, `detector`, and `nasa_cdf_url`. The export has 5,971 valid detector E readings and no duplicate detector/timestamp pairs. The range is 2024-03-07 00:14:58 to 2024-05-20 23:56:36 UTC, with readings on all 75 UTC dates. The most frequent interval is 17 min 6 sec, with intervals varying from 7 min 49 sec to 20 h 39 min 16 sec. There are 75 distinct CDF URLs. The original CDF variable name, quality flags, detector live time, and uncertainties are absent from this export, so quality-filter status cannot be confirmed from the CSV.

The unit **µGy/day** is a rate as reported in the source column. Each point is one reading at its recorded UTC timestamp. Descriptive means and medians weight readings equally. A peak is the largest observed value in a detector and filter window, with the earliest reading used for ties.

## Python interfaces

```python
load_radiation_history(path: str | Path = DEFAULT_CSV_PATH) -> RadiationHistory
radiation_timeline(
    history: RadiationHistory, *, start_date: str | None = None, end_date: str | None = None,
    detector: str | None = None, include_statistics: bool = False,
) -> dict[str, object]
may_20_event_summary(
    history: RadiationHistory, *, detector: str | None = None,
) -> dict[str, object]
```

Load the CSV once and reuse the resulting immutable history. Structural errors, duplicate rows, unknown detector filters, and invalid date filters raise `ValueError`. A missing file raises `FileNotFoundError`. Date filters are inclusive UTC dates in `YYYY-MM-DD` format. A valid range with no observations returns zero rows. Missing markers and invalid numbers keep their original text, status and timestamp, with a null value. Computed statistics use Decimal arithmetic and are emitted as decimal strings.

The engine reads local files only. To exercise the real archive in the tests, set `CREW_HEALTH_RAD_CSV` to its local path if the default repository file is unavailable.

## Timeline JSON excerpt

```json
{
  "dataset_id": "MSL_RAD_OBS-L2",
  "data_origin": "historical_nasa_observations",
  "mission": "Mars Science Laboratory (Curiosity)",
  "instrument": "Radiation Assessment Detector (RAD)",
  "measurement": "absorbed_dose_rate",
  "unit": "µGy/day",
  "series": [{
    "detector": "E",
    "observations": [{
      "timestamp_utc": "2024-03-07T00:14:58.000Z",
      "detector": "E",
      "value": "160.92029",
      "value_status": "valid",
      "raw_value": "160.92029",
      "source_line": 2,
      "nasa_cdf_url": "https://cdaweb.gsfc.nasa.gov/sp_phys/data/msl/rad/cdf/obs-l2/2024/msl_rad_obs-l2_2024067_v03.cdf"
    }],
    "statistics": null
  }]
}
```

## May 20 event JSON excerpt

```json
{
  "event_date": "2024-05-20",
  "title": "May 20, 2024 Mars solar radiation event",
  "unit": "µGy/day",
  "evidence_available": true,
  "series": [{
    "detector": "E",
    "observation_count": 139,
    "statistics": {
      "median": "1153.6759",
      "mean": "1881.04975",
      "peak": {
        "timestamp_utc": "2024-05-20T06:15:19.000Z",
        "value": "8377.913",
        "source_line": 5857,
        "nasa_cdf_url": "https://cdaweb.gsfc.nasa.gov/sp_phys/data/msl/rad/cdf/obs-l2/2024/msl_rad_obs-l2_2024141_v04.cdf"
      }
    },
    "preceding_week_comparison": {
      "start_date": "2024-05-13",
      "end_date": "2024-05-19",
      "valid_sample_count": 579,
      "observed_date_count": 7,
      "median": "148.34653"
    }
  }]
}
```

NASA reported charged particles arriving at the Martian surface and a sharp rise measured by RAD. The numeric statistics above come from Person B's CSV. The comparison uses available samples from the same detector across the seven preceding UTC dates and requires valid samples on all seven dates. The May 20 sample median is about 7.78 times the reference median. Sampling intensity and gaps affect these descriptive statistics, and the extract ends on the event date. Estimating accumulated dose, event duration, or personal exposure requires other inputs. [NASA event report](https://science.nasa.gov/resource/curiosity-sees-streaks-and-specks-during-2024-solar-storm/)

## Integration

**Person D.** The proposed read-only routes are `GET /mission-environment/radiation-history` with optional `start_date`, `end_date`, `detector`, and `include_statistics` queries, and `GET /mission-environment/radiation-history/events/2024-05-20` with optional `detector`. Load the configured CSV at startup and return the function dictionaries directly. Report an unavailable local dataset on those routes if loading fails.

**Person C.** Under **Mission Environment → Radiation History**, label the data as historical. Plot each detector separately using `series[].observations[].timestamp_utc` on a continuous UTC axis and `value` on the Y axis. Keep raw strings for tooltips and convert values for chart coordinates as needed. Show null readings as gaps, leave gaps across long intervals, and display the detector and `unit` on the chart. Use `series[].statistics.peak`, `preceding_week_comparison`, and `source_reference` for the May 20 callout. Use `evidence_available` to control the measurement panel and keep the event source link visible.
