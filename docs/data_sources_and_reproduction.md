# Data Sources And Reproduction

## Why sampled data is included
The original project used very large raw files (some >100 MB and several hundreds of MB). To keep this portfolio repo fast and GitHub-friendly, this repo includes sampled extracts.

## Included in this repo
- `data/sample_drivers.csv`
- `data/sample_incidents.csv`
- `data/sample_non_motorists.csv`
- `data/segments_priority.geojson`
- `data/segments_hin.geojson`
- `data/segments_exposure.geojson`

## Full local source files used in project
- `Capstone/Datasets/Crash_Reporting_-_Drivers_Data_20250802.csv`
- `Capstone/Datasets/Crash_Reporting_-_Incidents_Data_20250802.csv`
- `Capstone/Datasets/Crash_Reporting_-_Non-Motorists_Data_20250802.csv`
- Additional contextual files in `Capstone/Datasets/` and `Capstone/final/raw_data/`

## Reproduction outline
1. Load full incidents/drivers/non-motorists datasets.
2. Standardize join keys and date/location fields.
3. Build KSI-centric aggregation and exposure-adjusted metrics.
4. Generate HIN and priority corridor outputs.
5. Export geojson outputs for mapping and presentation.
