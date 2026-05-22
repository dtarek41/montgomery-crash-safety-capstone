# Montgomery Crash Safety Capstone

Portfolio analysis identifying high-risk crash corridors in Montgomery County and ranking safety investments with crash severity, exposure, vulnerable road user risk, and the Community Equity Index (CEI).

## Results
- Analysis window: **2020-2024**
- Crashes reviewed: **59,476**
- KSI crashes: **1,400**
- Fatal crashes: **244**
- VRU KSI crashes: **455**
- Estimated societal cost: **$7.1B**
- Core HIN: **8.7%** of roadway miles accounts for roughly 50% of KSI crashes.

## Methodology
- Cleaned and joined incidents, drivers, and non-motorist crash records at crash level.
- Matched crash points to TIGER/Line road segments and MDOT SHA AADT observations.
- Built a High Injury Network (HIN) from KSI concentration.
- Computed exposure-adjusted KSI rates using vehicle miles traveled.
- Added CEI disadvantaged tract counts and vulnerable road user KSI counts to the priority score.
- Removed exact duplicate road geometries so route aliases are not double-counted in top corridor rankings.

## Priority Score
The final score combines normalized:
- KSI crash burden
- VRU KSI burden
- Exposure-adjusted KSI rate
- KSI crashes in CEI disadvantaged tracts

## How To Review
1. Open `notebooks_or_analysis/Notebook.ipynb` for the polished analysis report.
2. Open `deliverables/montgomery_crash_safety_presentation.pptx` for the presentation narrative.
3. Review `data/segments_priority.geojson`, `data/segments_hin.geojson`, and `data/segments_exposure.geojson` for geospatial outputs.
4. Read `docs/data_sources_and_reproduction.md` to rebuild the analysis locally.

## Rebuild
Install dependencies:

```bash
pip install -r requirements.txt
```

Place the large raw crash CSVs in `data/raw/` or set `MONTGOMERY_RAW_DATA_DIR`, then run:

```bash
python scripts/build_analysis_assets.py
python scripts/create_report_notebook.py
python scripts/update_presentation.py
```

## Data Policy
Small public reference layers are included in `data/reference/`. Large raw crash CSVs are intentionally excluded from GitHub.
