# Data

All the data the app reads, one folder per part of the app. The API reads these files from disk once at startup. Nothing is downloaded at runtime.

| Folder | Used by | Origin | What it is |
|---|---|---|---|
| [`mode1/`](mode1/README.md) | Mode 1: Mission Health Monitor | Synthetic, shown as **SIMULATED** | Dataset `iss-synthetic-3000`: 4 fictional crew members and 3,000 generated readings, in the column formats of historical NASA tables |
| [`mode2/`](mode2/README.md) | Mode 2: NASA Biological Passport | Real NASA data (`dataset:OSD-575`) | NASA study OSD-575: blood serum panels of the 4 Inspiration4 crew members, with the study metadata |
| [`radiation/`](radiation/README.md) | Mission Environment: Mars Radiation History | Real NASA data (`MSL_RAD_OBS-L2`) | Curiosity RAD dose rates on the Martian surface, 7 March to 20 May 2024 |

- **Do not move or rename these files.** The engine reads these folders by default (`engine/mode1_ingestion.py`, `engine/nasa_ingestion.py` and `engine/radiation_history.py`). To read data from another place, set the variables listed in `.env.example`.
- **Sources:** each folder's README describes its files. The citations are in `NOTICE` and in the [root README](../README.md#data-and-provenance).
- **Owner:** Ayman El Kerboubi (B).
