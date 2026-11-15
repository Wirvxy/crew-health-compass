# NASA OSD-575 data files

Source data for **Mode 2 (NASA Biological Passport)**: blood serum measurements of the four Inspiration4 crew members (C001–C004), from the NASA Open Science Data Repository study [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575). The files keep their original NASA names.

**Do not rename or move them.** A's engine reads this folder by default (`DEFAULT_DATA_DIR` in `engine/nasa_ingestion.py`). To make the API read another folder, set `CREW_HEALTH_OSD575_DIR` (see `.env.example`).

| Files | What they are | Read by the app? |
|---|---|---|
| `LSDS-8_Comprehensive_Metabolic_Panel_CMP_TRANSFORMED.csv` | Metabolic panel (19 analytes) | **Yes** |
| `LSDS-8_Multiplex_serum_cardiovascular_EvePanel_TRANSFORMED.csv` | Cardiovascular cytokine panel | **Yes** |
| `LSDS-8_Multiplex_serum_immune_EvePanel_TRANSFORMED.csv` | Immune cytokine panel (Eve) | **Yes** |
| `LSDS-8_Multiplex_serum.immune.AlamarPanel_TRANSFORMED.csv` | Immune panel (Alamar) | **Yes** |
| `*_SUBMITTED.csv`, `*_SUBMITTED.xlsx` | The same panels as originally submitted to NASA | No: kept as source references |
| `OSD-575_metadata_OSD-575-ISA/` | Study metadata (ISA-Tab): investigation, study and assay descriptions | No: provenance only |

What these files state about the study, and what is still unverified, is in the [root README](../README.md#data-and-provenance).

**Owner:** Ayman El Kerboubi (B, *proposal*: see `AGENTS.md`). The unzipped metadata folder replaces the identical `.zip` that used to sit beside it.
