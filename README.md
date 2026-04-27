# Montgomery Crash Safety Capstone

Data analysis capstone focused on identifying high-risk crash corridors in Montgomery County and prioritizing systemic safety interventions.

## Project Goal
Translate road safety data into an actionable prioritization framework that supports evidence-based decisions for severe crash reduction.

## Problem Statement
Montgomery County Vision Zero efforts require targeted interventions, but crash risk is unevenly distributed across the network. This project identifies where severe crash burden is concentrated and ranks corridors for action.

## Methodology
- Integrated crash-related datasets (incidents, drivers, non-motorists) with exposure/context features.
- Standardized and cleaned keys used for joining and geographic analysis.
- Built a **High Injury Network (HIN)** view to detect concentrated KSI (killed/seriously injured) patterns.
- Applied exposure-aware logic to avoid over-prioritizing high-volume roads only.
- Produced corridor-level outputs and decision-ready presentation materials.

## KPI Logic
- **KSI Concentration KPI:** share of severe crashes concentrated in a small share of segments.
- **Exposure-Adjusted Risk KPI:** severe crash burden normalized by traffic exposure where applicable.
- **Priority Score KPI:** weighted corridor prioritization combining crash burden, vulnerable user risk, and equity-informed context.

## Key Recommendations
- Prioritize interventions on top-ranked HIN corridors.
- Expand systemic treatments (visibility, speed management, intersection safety design).
- Use periodic data refreshes to monitor corridor rank movement and intervention effectiveness.

## Repository Structure
- `data/`: curated geojson outputs + sampled crash datasets.
- `assets/`: project visuals.
- `deliverables/`: final presentation.
- `docs/`: source notes and references.
- `notebooks_or_analysis/`: analysis and reproducibility notes.

## How To Review
1. Start with `deliverables/montgomery_crash_safety_presentation.pptx` for project narrative.
2. Review `data/segments_priority.geojson` and `data/segments_hin.geojson` for output artifacts.
3. Read `docs/data_sources_and_reproduction.md` for full-data sourcing and rebuild guidance.

## Data Policy
This public portfolio repo includes representative samples for portability. Large raw source files were intentionally excluded from GitHub.

See `docs/data_sources_and_reproduction.md` for full dataset references.
