"""Create the polished portfolio notebook."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import nbformat as nbf
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "notebooks_or_analysis" / "Notebook.ipynb"
ANALYSIS_DIR = ROOT / "output" / "analysis"
SUMMARY_PATH = ANALYSIS_DIR / "summary.json"

TABLE_FILES = {
    "annual": "annual_summary.csv",
    "top_ksi": "top_ksi_segments.csv",
    "top_exposure": "top_exposure_segments.csv",
    "top_priority": "top_priority_segments.csv",
}

CLEANED_SAMPLE_COLUMNS = [
    "report_no",
    "crash_datetime",
    "year",
    "route_type_clean",
    "weather_clean",
    "surface_clean",
    "light_clean",
    "road_name_final",
    "any_ksi_crash",
    "fatal_crash",
    "any_vru",
    "any_dui",
    "crash_kabco",
    "societal_cost_2024usd",
    "nearest_road_m",
]


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(textwrap.dedent(text).strip())


def code(text: str) -> nbf.NotebookNode:
    lines = text.strip("\n").splitlines()
    base_indent = " " * 12
    lines = [line[len(base_indent) :] if line.startswith(base_indent) else line for line in lines]
    return nbf.v4.new_code_cell(textwrap.dedent("\n".join(lines)).strip())


def fmt_billions(value: float) -> str:
    return f"${value / 1_000_000_000:.1f}B"


def records_from_csv(path: Path, columns: list[str] | None = None, nrows: int | None = None) -> list[dict[str, object]]:
    if not path.exists():
        return []
    df = pd.read_csv(path, usecols=columns, nrows=nrows)
    df = df.astype(object).where(pd.notna(df), None)
    return df.to_dict("records")


def embedded_table_records() -> dict[str, list[dict[str, object]]]:
    return {
        name: records_from_csv(ANALYSIS_DIR / filename)
        for name, filename in TABLE_FILES.items()
    }


def embedded_cleaned_sample() -> list[dict[str, object]]:
    path = ANALYSIS_DIR / "crash_analysis_2020_2024.csv"
    return records_from_csv(path, CLEANED_SAMPLE_COLUMNS, nrows=10)


def build_notebook() -> nbf.NotebookNode:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    tables = embedded_table_records()
    cleaned_sample = embedded_cleaned_sample()

    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nb.metadata["language_info"] = {"name": "python", "pygments_lexer": "ipython3"}

    nb.cells = [
        md(
            f"""
            # Montgomery County Crash Severity and High-Injury Network

            **Portfolio analysis by Abdulla Tarek**

            This notebook identifies where severe crash harm is concentrated in Montgomery County and ranks corridors for safety investment using crash severity, exposure, vulnerable road user risk, and the Community Equity Index (CEI).

            **Executive Summary**

            - Analysis window: **{summary['analysis_years']}**
            - Crashes reviewed: **{summary['total_crashes']:,}**
            - KSI crashes: **{summary['ksi_crashes']:,}**
            - Fatal crashes: **{summary['fatal_crashes']:,}**
            - VRU KSI crashes: **{summary['vru_ksi_crashes']:,}**
            - DUI-involved KSI crashes: **{summary['dui_ksi_crashes']:,}**
            - Estimated societal cost: **{fmt_billions(summary['estimated_societal_cost_2024usd'])}**
            - Core HIN: **{summary['core_hin_mile_pct']:.1f}%** of road miles accounts for roughly 50% of KSI crashes.
            """
        ),
        md(
            """
            ## 1. Data Sources And Configuration

            **Objective.** Build a reproducible crash safety pipeline without local absolute paths.

            **Inputs.** Montgomery County crash incidents, drivers, non-motorists, CEI tracts, MDOT SHA AADT points, and TIGER/Line roads.

            **Repository behavior.** The notebook loads saved portfolio outputs by default. Set `RUN_FULL_REBUILD=1` to regenerate all outputs from the raw crash CSVs.
            """
        ),
        code(
            f"""
            import json
            import os
            import sys
            from pathlib import Path

            import geopandas as gpd
            import pandas as pd
            from IPython.display import Image, display

            PROJECT_ROOT = Path.cwd().resolve()
            if PROJECT_ROOT.name == "notebooks_or_analysis":
                PROJECT_ROOT = PROJECT_ROOT.parent
            sys.path.insert(0, str(PROJECT_ROOT))

            from scripts.build_analysis_assets import PipelineConfig, run_pipeline

            FALLBACK_SUMMARY = json.loads(r'''{json.dumps(summary, indent=4, allow_nan=False)}''')
            FALLBACK_TABLES = json.loads(r'''{json.dumps(tables, indent=4, allow_nan=False)}''')
            FALLBACK_CLEANED_SAMPLE = json.loads(r'''{json.dumps(cleaned_sample, indent=4, allow_nan=False)}''')
            """
        ),
        md(
            """
            ## 2. Load Or Rebuild Outputs

            **Default path.** Load the regenerated assets so the notebook opens quickly in GitHub and local viewers.

            **Full rebuild path.** With `RUN_FULL_REBUILD=1`, the notebook calls the same pipeline used to regenerate the committed GeoJSON files, charts, and presentation visuals.
            """
        ),
        code(
            """
            analysis_dir = PROJECT_ROOT / "output" / "analysis"

            if os.environ.get("RUN_FULL_REBUILD") == "1":
                summary = run_pipeline(PipelineConfig(project_root=PROJECT_ROOT))
            else:
                summary_path = analysis_dir / "summary.json"
                if summary_path.exists():
                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
                else:
                    summary = FALLBACK_SUMMARY

            summary_table = pd.DataFrame(
                [
                    ("Crashes reviewed", f"{summary['total_crashes']:,}"),
                    ("KSI crashes", f"{summary['ksi_crashes']:,}"),
                    ("Fatal crashes", f"{summary['fatal_crashes']:,}"),
                    ("VRU KSI crashes", f"{summary['vru_ksi_crashes']:,}"),
                    ("DUI-involved KSI crashes", f"{summary['dui_ksi_crashes']:,}"),
                    ("Estimated societal cost", f"${summary['estimated_societal_cost_2024usd'] / 1_000_000_000:.1f}B"),
                    ("Priority segments with CEI contribution", f"{summary['priority_segments_with_equity']:,}"),
                ],
                columns=["Metric", "Value"],
            )
            display(summary_table)
            """
        ),
        code(
            """
            def load_table(name, filename):
                path = analysis_dir / filename
                if path.exists():
                    return pd.read_csv(path)
                return pd.DataFrame(FALLBACK_TABLES[name])


            annual = load_table("annual", "annual_summary.csv")
            top_ksi = load_table("top_ksi", "top_ksi_segments.csv")
            top_exposure = load_table("top_exposure", "top_exposure_segments.csv")
            top_priority = load_table("top_priority", "top_priority_segments.csv")

            segments_hin = gpd.read_file(PROJECT_ROOT / "data" / "segments_hin.geojson")
            segments_exposure = gpd.read_file(PROJECT_ROOT / "data" / "segments_exposure.geojson")
            segments_priority = gpd.read_file(PROJECT_ROOT / "data" / "segments_priority.geojson")
            """
        ),
        md(
            """
            ## 3. Data Loading And Validation

            **Objective.** Confirm the analysis is using the expected committed reference layers and identify whether the private raw crash files are available for a full rebuild.
            """
        ),
        code(
            """
            expected_raw = [
                "Crash_Reporting_-_Incidents_Data_20250802.csv",
                "Crash_Reporting_-_Drivers_Data_20250802.csv",
                "Crash_Reporting_-_Non-Motorists_Data_20250802.csv",
            ]
            raw_dir = Path(os.environ.get("MONTGOMERY_RAW_DATA_DIR", PROJECT_ROOT / "data" / "raw"))

            inventory_rows = [
                ("CEI tracts", PROJECT_ROOT / "data" / "reference" / "Community_Equity_Index_CEI.geojson"),
                ("AADT points", PROJECT_ROOT / "data" / "reference" / "MDOT_SHA_Annual_Average_Daily_Traffic.geojson"),
                ("TIGER roads", PROJECT_ROOT / "data" / "reference" / "tl_2024_24031_roads.zip"),
                ("HIN output", PROJECT_ROOT / "data" / "segments_hin.geojson"),
                ("Exposure output", PROJECT_ROOT / "data" / "segments_exposure.geojson"),
                ("Priority output", PROJECT_ROOT / "data" / "segments_priority.geojson"),
            ]
            inventory = pd.DataFrame(
                [
                    (label, path.exists(), round(path.stat().st_size / 1_000_000, 2) if path.exists() else None)
                    for label, path in inventory_rows
                ],
                columns=["Asset", "Available", "Size MB"],
            )
            raw_status = pd.DataFrame(
                [(name, (raw_dir / name).exists()) for name in expected_raw],
                columns=["Raw file", "Available for full rebuild"],
            )

            display(inventory)
            display(raw_status)
            """
        ),
        md(
            """
            ## 4. Cleaning And Feature Engineering

            **Objective.** Convert raw crash records into analysis-ready crash flags, roadway matches, exposure measures, and CEI-aware priority inputs.

            **Finding.** The output is a crash-level table plus three segment-level GeoJSON layers used by the visuals, maps, rankings, and slides.
            """
        ),
        code(
            """
            cleaning_steps = pd.DataFrame(
                [
                    ("Schema", "Normalize raw column names and report numbers.", "Stable joins across incidents, drivers, and non-motorists."),
                    ("Time window", "Parse crash timestamps and keep 2020-2024 crashes.", "analysis_years, year, crash_datetime."),
                    ("Location QA", "Coerce latitude/longitude and null coordinates outside Montgomery County bounds.", "Valid crash points for spatial joins."),
                    ("Categories", "Standardize route type, weather, surface, light, municipality, and intersection fields.", "Clean grouped categories for charts."),
                    ("Severity", "Map injury severity to KABCO and create crash-level KSI/fatal flags.", "any_ksi_crash, fatal_crash, crash_kabco."),
                    ("VRU and DUI", "Aggregate driver and non-motorist records to crash-level VRU and DUI flags.", "any_vru, any_dui, vru_ksi_cnt."),
                    ("Cost", "Apply KABCO unit cost assumptions in 2024 dollars.", "societal_cost_2024usd."),
                    ("Road match", "Join crash points to nearest TIGER/Line road geometry within the match tolerance.", "road_name_final, road_linearid, nearest_road_m."),
                    ("CEI", "Join KSI crash points to CEI tracts and flag categories ending in '- Disadvantaged'.", "ksi_disadv_cnt, n_equity."),
                    ("Exposure", "Attach nearest MDOT SHA AADT and calculate VMT-based KSI rates.", "AADT, VMT, ksi_rate_100M."),
                    ("Priority", "Normalize KSI, VRU, CEI, and exposure components into one corridor score.", "priority_score."),
                ],
                columns=["Stage", "Decision", "Output"],
            )
            display(cleaning_steps)
            """
        ),
        code(
            """
            cleaned_path = analysis_dir / "crash_analysis_2020_2024.csv"
            sample_columns = [
                "report_no",
                "crash_datetime",
                "year",
                "route_type_clean",
                "weather_clean",
                "surface_clean",
                "light_clean",
                "road_name_final",
                "any_ksi_crash",
                "fatal_crash",
                "any_vru",
                "any_dui",
                "crash_kabco",
                "societal_cost_2024usd",
                "nearest_road_m",
            ]
            if cleaned_path.exists():
                cleaned_sample = pd.read_csv(cleaned_path, usecols=sample_columns).head(10)
            else:
                cleaned_sample = pd.DataFrame(FALLBACK_CLEANED_SAMPLE)
            display(cleaned_sample)
            """
        ),
        md(
            """
            ## 5. Analysis QA

            **Objective.** Validate the corrected CEI logic, ranking inputs, and duplicate-geometry handling before interpreting the visuals.
            """
        ),
        code(
            """
            priority_geom_keys = segments_priority.geometry.to_wkb(hex=True)
            qa_checks = pd.DataFrame(
                [
                    ("CEI tracts", summary["cei_tracts"]),
                    ("Disadvantaged CEI tracts", summary["disadvantaged_cei_tracts"]),
                    ("Priority segments", len(segments_priority)),
                    ("Priority segments with nonzero CEI KSI count", int((segments_priority["ksi_disadv_cnt"] > 0).sum())),
                    ("Priority segments with nonzero normalized equity score", int((segments_priority["n_equity"] > 0).sum())),
                    ("Exact duplicate priority geometries", int(priority_geom_keys.duplicated().sum())),
                    ("Core HIN mile share", f"{summary['core_hin_mile_pct']:.1f}%"),
                    ("Tier-65 HIN mile share", f"{summary['tier65_hin_mile_pct']:.1f}%"),
                ],
                columns=["Check", "Result"],
            )
            display(qa_checks)
            """
        ),
        md(
            """
            ## 6. Crash Severity Findings

            **Finding.** KSI crashes remain a persistent safety burden even when total crash counts fluctuate. Vulnerable road users and DUI-involved crashes have higher severity rates and higher average societal costs.
            """
        ),
        code(
            """
            display(annual)

            for chart in [
                "assets/chart_01_annual_crashes.png",
                "assets/chart_02_route_ksi_share.png",
                "assets/chart_03_vru_dui_ksi_share.png",
                "assets/chart_04_average_cost.png",
            ]:
                display(Image(filename=str(PROJECT_ROOT / chart)))
            """
        ),
        md(
            """
            ## 7. High-Injury Network And Exposure

            **Finding.** The HIN ranks corridors by KSI burden and confirms that severe crashes are concentrated on a small share of roadway mileage. Exposure-adjusted rates add context by accounting for traffic volume and segment length.
            """
        ),
        code(
            """
            display(top_ksi)
            display(top_exposure)

            for chart in [
                "assets/chart_05_hin_map.png",
                "assets/chart_06_hin_concentration.png",
                "assets/chart_07_top_ksi_segments.png",
                "assets/chart_08_exposure_rate.png",
            ]:
                display(Image(filename=str(PROJECT_ROOT / chart)))
            """
        ),
        md(
            """
            ## 8. CEI-Aware Priority Scoring

            **Objective.** Identify corridors where severe crash burden, vulnerable road user risk, exposure-adjusted risk, and disadvantaged CEI tract impacts overlap.

            **Scoring formula.** `priority_score = normalized(1.00*KSI + 0.50*VRU_KSI + 0.25*KSI_rate + 0.25*KSI_in_disadvantaged_CEI_tracts)`.
            """
        ),
        code(
            """
            display(top_priority)

            for chart in [
                "assets/chart_09_priority_score.png",
                "assets/chart_10_cei_priority_map.png",
            ]:
                display(Image(filename=str(PROJECT_ROOT / chart)))
            """
        ),
        md(
            """
            ## 9. Recommendations

            1. Prioritize the top CEI-aware corridors for near-term safety investment.
            2. Use quick-build treatments first where feasible: daylighting, leading pedestrian intervals, speed management, and crossing visibility.
            3. Advance corridor redesigns on the Core HIN where KSI burden persists after low-cost treatments.
            4. Re-score corridors every two to three years and track KSI, VRU KSI, CEI contribution, and exposure-adjusted rates.
            """
        ),
        md(
            """
            ## 10. Limitations

            - Police-reported crash data can contain missing or inconsistent fields.
            - AADT is used as a proxy for exposure and may not capture year-by-year traffic changes.
            - Road matching uses nearest-road logic, so complex intersections and ramps require manual review before project design.
            - CEI is a planning equity indicator, not a substitute for community engagement.
            """
        ),
        md(
            """
            ## 11. References

            - Montgomery County Open Data: Crash Reporting Incidents, Drivers, and Non-Motorists
            - Maryland DOT State Highway Administration: Annual Average Daily Traffic
            - U.S. Census Bureau: TIGER/Line Roads
            - Montgomery County: Community Equity Index
            - USDOT and FHWA: Safe System Approach and Proven Safety Countermeasures
            """
        ),
    ]
    return nb


if __name__ == "__main__":
    notebook = build_notebook()
    NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(notebook, NOTEBOOK_PATH)
    print(f"Wrote {NOTEBOOK_PATH}")
