"""Create the polished portfolio notebook."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "notebooks_or_analysis" / "Notebook.ipynb"
SUMMARY_PATH = ROOT / "output" / "analysis" / "summary.json"


def md(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(textwrap.dedent(text).strip())


def code(text: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(textwrap.dedent(text).strip())


def fmt_millions(value: float) -> str:
    return f"${value / 1_000_000_000:.1f}B"


def build_notebook() -> nbf.NotebookNode:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    nb = nbf.v4.new_notebook()
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nb.metadata["language_info"] = {"name": "python", "pygments_lexer": "ipython3"}

    nb.cells = [
        md(
            f"""
            # Montgomery County Crash Severity and High-Injury Network

            **Portfolio analysis by Abdulla Tarek**

            This notebook identifies where severe crash harm is concentrated in Montgomery County and ranks corridors for safety investment using crash severity, exposure, vulnerable road user risk, and the Community Equity Index (CEI).

            **Executive summary**

            - Analysis window: **{summary['analysis_years']}**
            - Total crashes reviewed: **{summary['total_crashes']:,}**
            - KSI crashes: **{summary['ksi_crashes']:,}**
            - Fatal crashes: **{summary['fatal_crashes']:,}**
            - VRU KSI crashes: **{summary['vru_ksi_crashes']:,}**
            - Estimated societal cost: **{fmt_millions(summary['estimated_societal_cost_2024usd'])}**
            - Core HIN: **{summary['core_hin_mile_pct']:.1f}%** of road miles accounts for roughly 50% of KSI crashes.
            """
        ),
        md(
            """
            ## Data Sources And Configuration

            The pipeline uses public Montgomery County crash files, MDOT SHA AADT locations, U.S. Census TIGER/Line roads, and Montgomery County CEI tracts.

            Large crash CSVs are intentionally excluded from GitHub. Place them in `data/raw/` or set `MONTGOMERY_RAW_DATA_DIR` before running the notebook.
            """
        ),
        code(
            """
            import json
            from pathlib import Path
            import os
            import sys

            import pandas as pd
            from IPython.display import Image, display

            PROJECT_ROOT = Path.cwd().resolve()
            if PROJECT_ROOT.name == "notebooks_or_analysis":
                PROJECT_ROOT = PROJECT_ROOT.parent
            sys.path.insert(0, str(PROJECT_ROOT))

            from scripts.build_analysis_assets import PipelineConfig, run_pipeline
            """
        ),
        md(
            """
            ## Load Or Rebuild Analysis Assets

            The repository includes regenerated GeoJSON outputs and chart assets. Set `RUN_FULL_REBUILD=1` to rebuild them from the full raw crash files during notebook execution.
            """
        ),
        code(
            """
            if os.environ.get("RUN_FULL_REBUILD") == "1":
                summary = run_pipeline(PipelineConfig(project_root=PROJECT_ROOT))
            else:
                summary_path = PROJECT_ROOT / "output" / "analysis" / "summary.json"
                if not summary_path.exists():
                    summary = run_pipeline(PipelineConfig(project_root=PROJECT_ROOT))
                else:
                    summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary
            """
        ),
        code(
            """
            analysis_dir = PROJECT_ROOT / "output" / "analysis"
            annual = pd.read_csv(analysis_dir / "annual_summary.csv")
            top_ksi = pd.read_csv(analysis_dir / "top_ksi_segments.csv")
            top_exposure = pd.read_csv(analysis_dir / "top_exposure_segments.csv")
            top_priority = pd.read_csv(analysis_dir / "top_priority_segments.csv")

            display(annual)
            """
        ),
        md(
            """
            ## Crash Severity Findings

            KSI crashes remain a persistent safety burden even when total crash counts fluctuate. Vulnerable road users and DUI-involved crashes have higher severity rates and higher average societal costs.
            """
        ),
        code(
            """
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
            ## High-Injury Network And Exposure

            The HIN ranks road segments by KSI burden and compares that concentration against roadway mileage. Exposure-adjusted rates use nearest MDOT SHA AADT observations to avoid ranking only by raw crash volume.
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
            ## CEI-Aware Priority Score

            The priority score combines normalized KSI burden, VRU KSI burden, exposure-adjusted KSI rate, and KSI crashes in CEI disadvantaged tracts. CEI disadvantaged tracts are defined from `cat_cei` categories ending in `- Disadvantaged`.
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
            ## Recommendations

            1. Prioritize the top CEI-aware corridors for near-term safety investment.
            2. Use quick-build treatments first where feasible: daylighting, leading pedestrian intervals, speed management, and crossing visibility.
            3. Advance corridor redesigns on the Core HIN where KSI burden persists after low-cost treatments.
            4. Re-score corridors every two to three years and track KSI, VRU KSI, equity contribution, and exposure-adjusted rates.
            """
        ),
        md(
            """
            ## Limitations

            - Police-reported crash data can contain missing or inconsistent fields.
            - AADT is used as a proxy for exposure and may not capture year-by-year traffic changes.
            - Road matching uses nearest-road logic, so complex intersections and ramps require manual review before project design.
            - CEI is used as a planning equity indicator, not as a substitute for community engagement.
            """
        ),
        md(
            """
            ## References

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
