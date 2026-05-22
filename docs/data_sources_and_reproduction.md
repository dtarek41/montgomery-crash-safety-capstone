# Data Sources And Reproduction

## Included In This Repo
- `data/reference/Community_Equity_Index_CEI.geojson`
- `data/reference/MDOT_SHA_Annual_Average_Daily_Traffic.geojson`
- `data/reference/tl_2024_24031_roads.zip`
- `data/segments_priority.geojson`
- `data/segments_hin.geojson`
- `data/segments_exposure.geojson`
- `assets/chart_*.png`
- `notebooks_or_analysis/Notebook.ipynb`

## Raw Crash Files Not Included
The full crash CSV files are too large for a clean GitHub portfolio repo. Download them from Montgomery County Open Data and place them in `data/raw/`, or set `MONTGOMERY_RAW_DATA_DIR` to a folder containing:

- `Crash_Reporting_-_Incidents_Data_20250802.csv`
- `Crash_Reporting_-_Drivers_Data_20250802.csv`
- `Crash_Reporting_-_Non-Motorists_Data_20250802.csv`

## Public Sources
- Crash Reporting - Incidents Data: https://data.montgomerycountymd.gov/Public-Safety/Crash-Reporting-Incidents-Data/bhju-22kf
- Crash Reporting - Drivers Data: https://data.montgomerycountymd.gov/Public-Safety/Crash-Reporting-Drivers-Data/mmzv-x632
- Crash Reporting - Non-Motorists Data: https://data.montgomerycountymd.gov/Public-Safety/Crash-Reporting-Non-Motorists-Data/n7fk-dce5
- Community Equity Index: https://data.montgomerycountymd.gov/stories/s/Community-Equity-Index/s6xy-n56j/
- MDOT SHA Annual Average Daily Traffic: https://opendata.maryland.gov/Transportation/Annual-Average-Daily-Traffic-Volume/2997-4217
- U.S. Census TIGER/Line Roads: https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html

## Rebuild Steps
1. Install dependencies with `pip install -r requirements.txt`.
2. Add the raw crash CSVs to `data/raw/` or set `MONTGOMERY_RAW_DATA_DIR`.
3. Run `python scripts/build_analysis_assets.py`.
4. Run `python scripts/create_report_notebook.py`.
5. Run `python scripts/update_presentation.py`.

The rebuild writes intermediate local files to `output/`, which is ignored by Git.
