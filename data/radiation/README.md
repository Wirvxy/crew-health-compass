# Curiosity RAD radiation history (Mission Environment)

Source data for the **Mars Radiation History** tab: absorbed dose rates measured on the Martian surface by the Radiation Assessment Detector (RAD) of NASA's Curiosity rover, 7 March to 20 May 2024.

| | |
|---|---|
| File | `nasa_curiosity_rad_2024-03-07_to_2024-05-20.csv` |
| Exported by | Ayman El Kerboubi (B), from the NASA CDAWeb archive `MSL_RAD_OBS-L2` |
| Dataset | [NASA data catalogue](https://data.nasa.gov/dataset/mars-science-laboratory-msl-radiation-assessment-detector-rad-level-2-observation-dosimetr) |
| Columns | `timestamp_utc`, `absorbed_dose_rate_ugy_per_day`, `detector`, `nasa_cdf_url` |
| Content | 5,971 readings from detector E, on all 75 UTC dates |
| SHA-256 | `d514a88fdc9a539a3b470b57a4d28c95cec6b1494474c696a27d629cda1cdea5` |

- **Unit:** µGy/day is a dose **rate**, not an accumulated dose. These values describe the Martian radiation environment, not any astronaut's personal exposure.
- **Line endings:** the file keeps its original Windows line endings (see `.gitattributes`), so its SHA-256 is the same on every computer.
- **Do not move it.** `engine/radiation_history.py` reads this path by default, and the API passes it explicitly (`CREW_HEALTH_RAD_CSV` overrides it).
- **Details:** the full description and limitations are in [engine/RADIATION_HISTORY.md](../../engine/RADIATION_HISTORY.md).
