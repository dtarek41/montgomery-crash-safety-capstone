"""Rebuild Montgomery crash safety analysis outputs and visuals.

The script expects large raw crash CSV files outside Git. Reference geospatial
layers are committed in data/reference so the HIN, exposure, and CEI steps are
repeatable without local absolute paths.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import Point


MD_METRIC = "EPSG:6487"
ANALYSIS_YEARS = range(2020, 2025)
MAX_ROAD_MATCH_M = 150
MAX_AADT_MATCH_M = 250
MIN_VMT_FOR_RATE = 500_000

KABCO_COST_2024 = {
    "K": 12_200_000,
    "A": 690_000,
    "B": 210_000,
    "C": 130_000,
    "O": 14_000,
}

CHART_SIZE = (10, 5.5)
COLORS = {
    "red": "#c43b3b",
    "orange": "#df7f2a",
    "blue": "#2f6f9f",
    "teal": "#3b8f83",
    "gray": "#737373",
    "light_gray": "#d9d9d9",
    "dark": "#222222",
    "cream": "#f7f4ee",
}


@dataclass(frozen=True)
class PipelineConfig:
    project_root: Path
    raw_dir: Path | None = None

    @property
    def data_dir(self) -> Path:
        return self.project_root / "data"

    @property
    def reference_dir(self) -> Path:
        return self.data_dir / "reference"

    @property
    def assets_dir(self) -> Path:
        return self.project_root / "assets"

    @property
    def output_dir(self) -> Path:
        return self.project_root / "output" / "analysis"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_raw_dir(config: PipelineConfig) -> Path:
    candidates = []
    if config.raw_dir:
        candidates.append(config.raw_dir)
    if os.environ.get("MONTGOMERY_RAW_DATA_DIR"):
        candidates.append(Path(os.environ["MONTGOMERY_RAW_DATA_DIR"]))
    candidates.append(config.data_dir / "raw")

    required = [
        "Crash_Reporting_-_Incidents_Data_20250802.csv",
        "Crash_Reporting_-_Drivers_Data_20250802.csv",
        "Crash_Reporting_-_Non-Motorists_Data_20250802.csv",
    ]
    for candidate in candidates:
        if candidate and all((candidate / name).exists() for name in required):
            return candidate

    checked = "\n".join(f"- {p}" for p in candidates if p)
    raise FileNotFoundError(
        "Raw crash CSV files were not found. Set MONTGOMERY_RAW_DATA_DIR "
        "or place the files in data/raw.\nChecked:\n" + checked
    )


def normalize_column(name: str) -> str:
    name = re.sub(r"[^0-9A-Za-z]+", "_", name.strip()).strip("_")
    return name.lower()


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return "Unknown"
    text = re.sub(r"\s+", " ", str(value).strip())
    if not text or text.lower() in {"nan", "none", "n/a", "unknown"}:
        return "Unknown"
    return text.title()


def normalize_road_name(value: object) -> str:
    text = normalize_text(value)
    if text == "Unknown":
        return text
    text = re.sub(r"\s*\([NESW]B/L\)", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    replacements = {
        " St": " Street",
        " Rd": " Road",
        " Ave": " Avenue",
        " Hwy": " Highway",
        " Blvd": " Boulevard",
    }
    for old, new in replacements.items():
        if text.endswith(old):
            text = text[: -len(old)] + new
    return text.title()


def clean_category(value: object, mapping: dict[str, str] | None = None) -> str:
    text = normalize_text(value)
    key = text.upper()
    if mapping and key in mapping:
        return mapping[key]
    return text


def severity_to_kabco(value: object) -> str:
    text = normalize_text(value).upper()
    if "FATAL" in text or text == "K":
        return "K"
    if "SERIOUS" in text or text == "A":
        return "A"
    if "MINOR" in text or text == "B":
        return "B"
    if "POSSIBLE" in text or text == "C":
        return "C"
    return "O"


def max_kabco(values: pd.Series) -> str:
    order = {"O": 0, "C": 1, "B": 2, "A": 3, "K": 4}
    cleaned = [value for value in values.dropna().astype(str) if value in order]
    if not cleaned:
        return "O"
    return max(cleaned, key=lambda value: order[value])


def is_vru_text(value: object) -> bool:
    text = normalize_text(value).lower()
    return bool(re.search(r"pedestr|bicycl|cyclist|scooter|skate|conveyance", text))


def is_dui_text(value: object) -> bool:
    text = normalize_text(value).lower()
    tokens = [token.strip() for token in re.split(r"[,;/]", text) if token.strip()]
    positive_patterns = (
        r"\bsuspect of alcohol use\b",
        r"\bsuspect of drug use\b",
        r"\balcohol present\b",
        r"\balcohol contributed\b",
        r"\billegal drug present\b",
        r"\billegal drug contributed\b",
        r"\bcombined substance present\b",
        r"\bcombination contributed\b",
    )
    for token in tokens:
        if token in {"unknown", "n/a", "none detected"}:
            continue
        if "not suspect" in token:
            continue
        if any(re.search(pattern, token) for pattern in positive_patterns):
            return True
    return False


def is_distracted_text(value: object) -> bool:
    text = normalize_text(value).lower()
    if text in {"unknown", "not distracted", "no driver present"}:
        return False
    return bool(text)


def route_type(value: object) -> str:
    mapping = {
        "MARYLAND (STATE)": "State Route",
        "MARYLAND (STATE) ROUTE": "State Route",
        "US (STATE)": "US Route",
        "US (STATE) ROUTE": "US Route",
        "INTERSTATE (STATE)": "Interstate",
        "COUNTY": "County Road",
        "COUNTY ROUTE": "County Road",
        "MUNICIPALITY": "Municipal Road",
        "MUNICIPALITY ROUTE": "Municipal Road",
    }
    return clean_category(value, mapping)


def light_group(value: object) -> str:
    text = normalize_text(value).lower()
    if "daylight" in text:
        return "Daylight"
    if "dark" in text and ("light" in text or "street" in text):
        return "Dark - Lighted"
    if "dark" in text:
        return "Dark - Unlighted"
    if "dawn" in text:
        return "Dawn"
    if "dusk" in text:
        return "Dusk"
    return "Unknown"


def weather_group(value: object) -> str:
    text = normalize_text(value).lower()
    if "clear" in text:
        return "Clear"
    if "rain" in text:
        return "Rain"
    if "snow" in text or "sleet" in text:
        return "Snow"
    if "cloud" in text:
        return "Cloudy"
    if "fog" in text:
        return "Fog"
    return "Unknown"


def surface_group(value: object) -> str:
    text = normalize_text(value).lower()
    if "dry" in text:
        return "Dry"
    if "wet" in text:
        return "Wet"
    if "ice" in text or "snow" in text or "slush" in text:
        return "Snow/Ice"
    return "Unknown"


def _read_raw_csvs(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inc = pd.read_csv(raw_dir / "Crash_Reporting_-_Incidents_Data_20250802.csv", low_memory=False)
    drv = pd.read_csv(raw_dir / "Crash_Reporting_-_Drivers_Data_20250802.csv", low_memory=False)
    nmo = pd.read_csv(raw_dir / "Crash_Reporting_-_Non-Motorists_Data_20250802.csv", low_memory=False)
    for df in (inc, drv, nmo):
        df.columns = [normalize_column(c) for c in df.columns]
    return inc, drv, nmo


def _prepare_crash_tables(inc: pd.DataFrame, drv: pd.DataFrame, nmo: pd.DataFrame) -> pd.DataFrame:
    inc = inc.copy()
    drv = drv.copy()
    nmo = nmo.copy()

    inc["report_no"] = inc["report_number"].astype(str).str.strip()
    drv["report_no"] = drv["report_number"].astype(str).str.strip()
    nmo["report_no"] = nmo["report_number"].astype(str).str.strip()

    inc["crash_datetime"] = pd.to_datetime(inc["crash_date_time"], errors="coerce")
    inc["year"] = inc["crash_datetime"].dt.year
    inc = inc[inc["year"].isin(ANALYSIS_YEARS)].copy()

    inc["latitude"] = pd.to_numeric(inc["latitude"], errors="coerce")
    inc["longitude"] = pd.to_numeric(inc["longitude"], errors="coerce")
    inc.loc[~inc["latitude"].between(38.7, 39.5), "latitude"] = np.nan
    inc.loc[~inc["longitude"].between(-77.7, -76.7), "longitude"] = np.nan

    inc["route_type_clean"] = inc["route_type"].map(route_type)
    inc["weather_clean"] = inc["weather"].map(weather_group)
    inc["surface_clean"] = inc["surface_condition"].map(surface_group)
    inc["light_clean"] = inc["light"].map(light_group)
    inc["road_name_clean"] = inc["road_name"].map(normalize_road_name)
    inc["municipality_clean"] = inc["municipality"].map(normalize_text)
    inc["intersection_clean"] = inc["intersection_type"].map(normalize_text)

    inc["fatal_report"] = inc["acrs_report_type"].map(lambda x: "fatal" in normalize_text(x).lower())
    inc["related_vru"] = inc["related_non_motorist"].map(is_vru_text)
    inc["driver_dui_reported"] = inc["driver_substance_abuse"].map(is_dui_text)
    inc["non_motorist_dui_reported"] = inc["non_motorist_substance_abuse"].map(is_dui_text)

    drv["driver_kabco"] = drv.get("injury_severity", pd.Series(index=drv.index, dtype=object)).map(severity_to_kabco)
    drv["driver_is_ksi"] = drv["driver_kabco"].isin(["K", "A"])
    drv["driver_is_fatal"] = drv["driver_kabco"].eq("K")
    drv["driver_dui"] = drv.get("driver_substance_abuse", pd.Series(index=drv.index, dtype=object)).map(is_dui_text)
    drv["driver_distracted"] = drv.get("driver_distracted_by", pd.Series(index=drv.index, dtype=object)).map(is_distracted_text)

    drv_agg = (
        drv.groupby("report_no", as_index=False)
        .agg(
            driver_ksi=("driver_is_ksi", "max"),
            driver_fatal=("driver_is_fatal", "max"),
            any_dui_driver=("driver_dui", "max"),
            any_distracted=("driver_distracted", "max"),
            driver_max_kabco=("driver_kabco", max_kabco),
        )
    )

    nmo["nmo_kabco"] = nmo.get("injury_severity", pd.Series(index=nmo.index, dtype=object)).map(severity_to_kabco)
    nmo["nmo_is_ksi"] = nmo["nmo_kabco"].isin(["K", "A"])
    nmo["nmo_is_fatal"] = nmo["nmo_kabco"].eq("K")
    nmo["nmo_is_vru"] = nmo.get("pedestrian_type", pd.Series(index=nmo.index, dtype=object)).map(is_vru_text) | nmo.get(
        "related_non_motorist", pd.Series(index=nmo.index, dtype=object)
    ).map(is_vru_text)
    nmo["nmo_dui"] = nmo.get("non_motorist_substance_abuse", pd.Series(index=nmo.index, dtype=object)).map(is_dui_text)

    nmo_agg = (
        nmo.groupby("report_no", as_index=False)
        .agg(
            nmo_ksi=("nmo_is_ksi", "max"),
            nmo_fatal=("nmo_is_fatal", "max"),
            any_vru_nmo=("nmo_is_vru", "max"),
            any_dui_nmo=("nmo_dui", "max"),
            nmo_max_kabco=("nmo_kabco", max_kabco),
        )
    )

    out = inc.merge(drv_agg, on="report_no", how="left").merge(nmo_agg, on="report_no", how="left")
    bool_cols = [
        "driver_ksi",
        "driver_fatal",
        "any_dui_driver",
        "any_distracted",
        "nmo_ksi",
        "nmo_fatal",
        "any_vru_nmo",
        "any_dui_nmo",
    ]
    for col in bool_cols:
        out[col] = out[col].fillna(False).astype(bool)

    out["any_ksi_crash"] = out["fatal_report"] | out["driver_ksi"] | out["nmo_ksi"]
    out["fatal_crash"] = out["fatal_report"] | out["driver_fatal"] | out["nmo_fatal"]
    out["any_vru"] = out["related_vru"] | out["any_vru_nmo"]
    out["any_dui"] = out["driver_dui_reported"] | out["non_motorist_dui_reported"] | out["any_dui_driver"] | out["any_dui_nmo"]

    kabco_order = {"O": 0, "C": 1, "B": 2, "A": 3, "K": 4}
    def crash_kabco(row: pd.Series) -> str:
        values = ["K" if row["fatal_report"] else "O", row.get("driver_max_kabco", "O"), row.get("nmo_max_kabco", "O")]
        return max(values, key=lambda k: kabco_order.get(k, 0))

    out["crash_kabco"] = out.apply(crash_kabco, axis=1)
    out["societal_cost_2024usd"] = out["crash_kabco"].map(KABCO_COST_2024).fillna(KABCO_COST_2024["O"])
    return out


def _is_generic_route(name: str) -> bool:
    return bool(re.match(r"^(STATE HWY|STATE ROUTE|US HWY|US ROUTE|I-|INTERSTATE|COUNTY HWY)\b", name.upper()))


def _load_reference_layers(config: PipelineConfig) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    roads_path = config.reference_dir / "tl_2024_24031_roads.zip"
    cei_path = config.reference_dir / "Community_Equity_Index_CEI.geojson"
    aadt_path = config.reference_dir / "MDOT_SHA_Annual_Average_Daily_Traffic.geojson"

    roads = gpd.read_file(roads_path)
    roads = roads.to_crs("EPSG:4326")
    roads = roads[roads.geometry.notna() & ~roads.geometry.is_empty].copy()
    roads["display_name"] = roads["FULLNAME"].map(normalize_road_name)
    roads = roads[roads["display_name"] != "Unknown"].copy()
    roads["geom_key"] = roads.geometry.to_wkb(hex=True)
    roads["generic_route"] = roads["display_name"].map(_is_generic_route)
    roads = roads.sort_values(["geom_key", "generic_route", "display_name"])
    roads = roads.drop_duplicates("geom_key", keep="first").drop(columns=["geom_key", "generic_route"])

    cei = gpd.read_file(cei_path).to_crs("EPSG:4326")
    cei["cat_cei"] = cei["cat_cei"].astype(str)
    cei["is_disadvantaged"] = cei["cat_cei"].str.strip().str.endswith("- Disadvantaged")

    aadt_data = json.loads(aadt_path.read_text(encoding="utf-8"))
    aadt = gpd.GeoDataFrame.from_features(aadt_data["features"], crs="EPSG:4326").to_crs("EPSG:4326")
    aadt = aadt[aadt["COUNTY_DESC"].astype(str).str.upper().eq("MONTGOMERY")].copy()
    aadt["AADT_VALUE"] = pd.to_numeric(aadt.get("AADT_2023", aadt.get("AADT")), errors="coerce")
    aadt = aadt[aadt["AADT_VALUE"].notna() & (aadt["AADT_VALUE"] > 0)].copy()
    return roads, cei, aadt


def _attach_roads(crashes: pd.DataFrame, roads: gpd.GeoDataFrame) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    valid = crashes[crashes["latitude"].notna() & crashes["longitude"].notna()].copy()
    pts = gpd.GeoDataFrame(valid, geometry=gpd.points_from_xy(valid["longitude"], valid["latitude"]), crs="EPSG:4326")

    roads_m = roads[["display_name", "LINEARID", "geometry"]].to_crs(MD_METRIC).reset_index(drop=True)
    pts_m = pts.to_crs(MD_METRIC)
    matched = gpd.sjoin_nearest(
        pts_m,
        roads_m,
        how="left",
        max_distance=MAX_ROAD_MATCH_M,
        distance_col="nearest_road_m",
    )
    attach = matched[["report_no", "display_name", "LINEARID", "nearest_road_m"]].rename(
        columns={"display_name": "road_name_final", "LINEARID": "road_linearid"}
    )
    enriched = crashes.merge(attach, on="report_no", how="left")
    enriched["road_name_final"] = enriched["road_name_final"].fillna(enriched["road_name_clean"])
    enriched["road_name_final"] = enriched["road_name_final"].map(normalize_road_name)
    return enriched, pts


def _build_segment_outputs(
    crashes: pd.DataFrame,
    roads: gpd.GeoDataFrame,
    cei: gpd.GeoDataFrame,
    aadt: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    segments = roads[["display_name", "LINEARID", "geometry"]].copy().reset_index(drop=True)
    segments = segments.rename(columns={"display_name": "seg_label", "LINEARID": "linearid"})
    segments["name_norm"] = segments["seg_label"].str.upper()
    segments_m = segments.to_crs(MD_METRIC)
    segments["length_m"] = segments_m.length
    segments["length_mi"] = segments["length_m"] / 1609.344

    valid = crashes[crashes["latitude"].notna() & crashes["longitude"].notna()].copy()
    pts = gpd.GeoDataFrame(valid, geometry=gpd.points_from_xy(valid["longitude"], valid["latitude"]), crs="EPSG:4326")

    cei_small = cei[["GEOID20", "cat_cei", "cei", "is_disadvantaged", "geometry"]].copy()
    pts_cei = gpd.sjoin(pts, cei_small, how="left", predicate="within")
    pts_cei["is_disadvantaged"] = pts_cei["is_disadvantaged"].fillna(False).astype(bool)
    pts_cei = pts_cei.drop(columns=[col for col in ("index_right", "index_left") if col in pts_cei.columns])

    seg_m = segments[["geometry"]].to_crs(MD_METRIC).reset_index(drop=True)
    pts_m = pts_cei.to_crs(MD_METRIC)
    joined = gpd.sjoin_nearest(
        pts_m,
        seg_m,
        how="left",
        max_distance=MAX_ROAD_MATCH_M,
        distance_col="dist_segment_m",
    )
    joined = joined[joined["index_right"].notna()].copy()
    joined["segment_ix"] = joined["index_right"].astype(int)

    ksi_counts = joined[joined["any_ksi_crash"]].groupby("segment_ix").size()
    vru_counts = joined[joined["any_ksi_crash"] & joined["any_vru"]].groupby("segment_ix").size()
    disadv_counts = joined[joined["any_ksi_crash"] & joined["is_disadvantaged"]].groupby("segment_ix").size()

    segments["ksi_cnt"] = np.zeros(len(segments), dtype=int)
    segments["vru_ksi_cnt"] = np.zeros(len(segments), dtype=int)
    segments["ksi_disadv_cnt"] = np.zeros(len(segments), dtype=int)
    segments.loc[ksi_counts.index, "ksi_cnt"] = ksi_counts.values
    segments.loc[vru_counts.index, "vru_ksi_cnt"] = vru_counts.values
    segments.loc[disadv_counts.index, "ksi_disadv_cnt"] = disadv_counts.values

    aadt_m = aadt[["AADT_VALUE", "geometry"]].to_crs(MD_METRIC)
    aadt_join = gpd.sjoin_nearest(
        seg_m,
        aadt_m,
        how="left",
        max_distance=MAX_AADT_MATCH_M,
        distance_col="dist_aadt_m",
    )
    segments["AADT"] = pd.to_numeric(aadt_join["AADT_VALUE"].to_numpy(), errors="coerce")
    segments["dist_aadt_m"] = pd.to_numeric(aadt_join["dist_aadt_m"].to_numpy(), errors="coerce")
    segments["VMT"] = segments["AADT"] * segments["length_mi"] * 365 * len(list(ANALYSIS_YEARS))
    segments["ksi_rate_100M"] = np.where(
        segments["VMT"] >= MIN_VMT_FOR_RATE,
        segments["ksi_cnt"] / segments["VMT"] * 100_000_000,
        np.nan,
    )

    hin = segments.sort_values(["ksi_cnt", "length_mi"], ascending=[False, False]).copy()
    total_ksi = max(float(hin["ksi_cnt"].sum()), 1.0)
    total_mi = max(float(hin["length_mi"].sum()), 1.0)
    hin["cum_ksi"] = hin["ksi_cnt"].cumsum()
    hin["cum_ksi_pct"] = hin["cum_ksi"] / total_ksi * 100
    hin["cum_mi"] = hin["length_mi"].cumsum()
    hin["cum_mi_pct"] = hin["cum_mi"] / total_mi * 100
    hin["hin_tier"] = np.select(
        [hin["cum_ksi_pct"] <= 50, hin["cum_ksi_pct"] <= 65],
        ["Core HIN", "Tier 2 HIN"],
        default="Other",
    )

    priority = segments.copy()
    priority["ksi_rate_100M"] = priority["ksi_rate_100M"].fillna(0.0)
    priority["n_ksi"] = minmax(priority["ksi_cnt"])
    priority["n_rate"] = minmax(priority["ksi_rate_100M"])
    priority["n_vru"] = minmax(priority["vru_ksi_cnt"])
    priority["n_equity"] = minmax(priority["ksi_disadv_cnt"])
    raw_score = (
        1.0 * priority["n_ksi"]
        + 0.5 * priority["n_vru"]
        + 0.25 * priority["n_rate"]
        + 0.25 * priority["n_equity"]
    )
    priority["priority_score"] = minmax(raw_score)
    priority = priority[priority["AADT"].notna() & (priority["VMT"] >= MIN_VMT_FOR_RATE)].copy()
    priority["seg_no"] = np.arange(1, len(priority) + 1)

    exposure = segments.copy()
    return hin.to_crs("EPSG:4326"), exposure.to_crs("EPSG:4326"), priority.to_crs("EPSG:4326")


def minmax(values: pd.Series | np.ndarray) -> pd.Series:
    series = pd.Series(values).astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    low = series.min()
    high = series.max()
    if high <= low:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - low) / (high - low)


def _write_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(path, driver="GeoJSON")


def _style_ax(ax, title: str | None = None) -> None:
    ax.set_facecolor("white")
    if title:
        ax.set_title(title, loc="left", fontsize=14, fontweight="bold", color=COLORS["dark"])
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.grid(axis="x", color="#e6e6e6", linewidth=0.8)


def _save_fig(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _barh(series: pd.Series, title: str, xlabel: str, path: Path, color: str = COLORS["orange"]) -> None:
    data = series.sort_values()
    fig, ax = plt.subplots(figsize=CHART_SIZE)
    ax.barh(data.index.astype(str), data.values, color=color)
    _style_ax(ax, title)
    ax.set_xlabel(xlabel)
    for y, value in enumerate(data.values):
        ax.text(value, y, f" {value:,.1f}", va="center", fontsize=9)
    _save_fig(fig, path)


def _build_charts(
    crashes: pd.DataFrame,
    hin: gpd.GeoDataFrame,
    exposure: gpd.GeoDataFrame,
    priority: gpd.GeoDataFrame,
    cei: gpd.GeoDataFrame,
    assets_dir: Path,
) -> dict[str, str]:
    paths: dict[str, str] = {}

    annual = crashes.groupby("year").agg(total=("report_no", "count"), ksi=("any_ksi_crash", "sum")).reset_index()
    fig, ax = plt.subplots(figsize=CHART_SIZE)
    ax.plot(annual["year"], annual["total"], marker="o", label="Total crashes", color=COLORS["gray"])
    ax2 = ax.twinx()
    ax2.plot(annual["year"], annual["ksi"], marker="o", label="KSI crashes", color=COLORS["red"])
    _style_ax(ax, "Crash volume and KSI trend, 2020-2024")
    ax.set_ylabel("Total crashes")
    ax2.set_ylabel("KSI crashes")
    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [line.get_label() for line in lines], loc="upper left")
    path = assets_dir / "chart_01_annual_crashes.png"
    _save_fig(fig, path)
    paths["annual"] = str(path)

    factor = (
        crashes[crashes["route_type_clean"] != "Unknown"]
        .groupby("route_type_clean")["any_ksi_crash"]
        .mean()
        .mul(100)
        .sort_values(ascending=False)
        .head(8)
    )
    path = assets_dir / "chart_02_route_ksi_share.png"
    _barh(factor, "KSI share by route type", "KSI share of crashes (%)", path, COLORS["blue"])
    paths["route_ksi"] = str(path)

    vru_rates = pd.Series(
        {
            "Pedestrian/bicycle/VRU": crashes.loc[crashes["any_vru"], "any_ksi_crash"].mean() * 100,
            "Non-VRU": crashes.loc[~crashes["any_vru"], "any_ksi_crash"].mean() * 100,
            "DUI involved": crashes.loc[crashes["any_dui"], "any_ksi_crash"].mean() * 100,
            "No DUI flag": crashes.loc[~crashes["any_dui"], "any_ksi_crash"].mean() * 100,
        }
    )
    path = assets_dir / "chart_03_vru_dui_ksi_share.png"
    _barh(vru_rates, "VRU and DUI crashes carry higher severity", "KSI share of crashes (%)", path, COLORS["red"])
    paths["vru_dui"] = str(path)

    cost_rates = pd.Series(
        {
            "VRU crashes": crashes.loc[crashes["any_vru"], "societal_cost_2024usd"].mean() / 1_000_000,
            "Non-VRU crashes": crashes.loc[~crashes["any_vru"], "societal_cost_2024usd"].mean() / 1_000_000,
            "DUI involved": crashes.loc[crashes["any_dui"], "societal_cost_2024usd"].mean() / 1_000_000,
            "No DUI flag": crashes.loc[~crashes["any_dui"], "societal_cost_2024usd"].mean() / 1_000_000,
        }
    )
    path = assets_dir / "chart_04_average_cost.png"
    _barh(cost_rates, "Average societal cost per crash", "2024 USD, millions", path, COLORS["orange"])
    paths["cost"] = str(path)

    fig, ax = plt.subplots(figsize=(9, 7))
    hin.plot(ax=ax, color=COLORS["light_gray"], linewidth=0.35)
    hin[hin["hin_tier"].eq("Tier 2 HIN")].plot(ax=ax, color=COLORS["blue"], linewidth=1.0)
    hin[hin["hin_tier"].eq("Core HIN")].plot(ax=ax, color=COLORS["red"], linewidth=1.3)
    ax.set_axis_off()
    ax.set_title("High Injury Network: 50% and 65% KSI tiers", loc="left", fontsize=14, fontweight="bold")
    path = assets_dir / "chart_05_hin_map.png"
    _save_fig(fig, path)
    paths["hin_map"] = str(path)

    hin_curve = hin.sort_values(["ksi_cnt", "length_mi"], ascending=[False, False]).copy()
    fig, ax = plt.subplots(figsize=CHART_SIZE)
    ax.plot(hin_curve["cum_mi_pct"], hin_curve["cum_ksi_pct"], color=COLORS["red"], linewidth=2)
    ax.axhline(50, color=COLORS["gray"], linewidth=1, linestyle="--")
    ax.axhline(65, color=COLORS["blue"], linewidth=1, linestyle="--")
    _style_ax(ax, "A small share of roadway miles carries most KSI crashes")
    ax.set_xlabel("Cumulative roadway miles (%)")
    ax.set_ylabel("Cumulative KSI crashes (%)")
    path = assets_dir / "chart_06_hin_concentration.png"
    _save_fig(fig, path)
    paths["hin_concentration"] = str(path)

    top_ksi = hin[hin["ksi_cnt"] > 0].sort_values("ksi_cnt", ascending=False).head(10)
    path = assets_dir / "chart_07_top_ksi_segments.png"
    _barh(top_ksi.set_index("seg_label")["ksi_cnt"], "Top road segments by KSI crashes", "KSI crashes", path, COLORS["red"])
    paths["top_ksi"] = str(path)

    top_rate = exposure[exposure["ksi_rate_100M"].fillna(0) > 0].sort_values("ksi_rate_100M", ascending=False).head(10)
    path = assets_dir / "chart_08_exposure_rate.png"
    _barh(
        top_rate.set_index("seg_label")["ksi_rate_100M"],
        "Top exposure-adjusted KSI rates",
        "KSI per 100M vehicle miles",
        path,
        COLORS["blue"],
    )
    paths["exposure_rate"] = str(path)

    top_priority = priority.sort_values("priority_score", ascending=False).head(10)
    path = assets_dir / "chart_09_priority_score.png"
    _barh(
        top_priority.set_index("seg_label")["priority_score"],
        "Top CEI-aware priority scores",
        "Normalized priority score",
        path,
        COLORS["orange"],
    )
    paths["priority"] = str(path)

    fig, ax = plt.subplots(figsize=(9, 7))
    cei[~cei["is_disadvantaged"]].plot(ax=ax, color=COLORS["light_gray"], edgecolor="white", linewidth=0.2)
    cei[cei["is_disadvantaged"]].plot(ax=ax, color="#f1b182", edgecolor="white", linewidth=0.25)
    top_priority_map = priority.sort_values("priority_score", ascending=False).head(30)
    if not top_priority_map.empty:
        top_priority_map.plot(ax=ax, color=COLORS["red"], linewidth=1.0)
    ax.set_axis_off()
    ax.set_title("Priority corridors over CEI disadvantaged tracts", loc="left", fontsize=14, fontweight="bold")
    path = assets_dir / "chart_10_cei_priority_map.png"
    _save_fig(fig, path)
    paths["cei_map"] = str(path)

    fig = plt.figure(figsize=(12.8, 7.2), facecolor="white")
    fig.suptitle("Montgomery County Crash Safety Prioritization", fontsize=22, fontweight="bold", x=0.05, ha="left")
    fig.text(
        0.05,
        0.88,
        f"{len(crashes):,} crashes | {int(crashes['any_ksi_crash'].sum()):,} KSI crashes | "
        f"{int((priority['ksi_disadv_cnt'] > 0).sum()):,} CEI-contributing priority segments",
        fontsize=12,
        color=COLORS["dark"],
    )
    ax1 = fig.add_axes([0.05, 0.12, 0.43, 0.68])
    hin.plot(ax=ax1, color=COLORS["light_gray"], linewidth=0.25)
    hin[hin["hin_tier"].eq("Tier 2 HIN")].plot(ax=ax1, color=COLORS["blue"], linewidth=0.8)
    hin[hin["hin_tier"].eq("Core HIN")].plot(ax=ax1, color=COLORS["red"], linewidth=1.1)
    ax1.set_title("High Injury Network", loc="left", fontsize=13, fontweight="bold")
    ax1.set_axis_off()

    ax2 = fig.add_axes([0.56, 0.18, 0.39, 0.58])
    overview_top = priority.sort_values("priority_score", ascending=False).head(8).sort_values("priority_score")
    ax2.barh(overview_top["seg_label"], overview_top["priority_score"], color=COLORS["orange"])
    _style_ax(ax2, "CEI-aware priority score")
    ax2.set_xlabel("Normalized score")
    path = assets_dir / "project_visual.png"
    _save_fig(fig, path)
    paths["project_visual"] = str(path)
    return paths


def _write_tables(
    crashes: pd.DataFrame,
    hin: gpd.GeoDataFrame,
    exposure: gpd.GeoDataFrame,
    priority: gpd.GeoDataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "top_ksi_segments": hin[hin["ksi_cnt"] > 0].sort_values("ksi_cnt", ascending=False).head(10),
        "top_exposure_segments": exposure[exposure["ksi_rate_100M"].fillna(0) > 0].sort_values("ksi_rate_100M", ascending=False).head(10),
        "top_priority_segments": priority.sort_values("priority_score", ascending=False).head(10),
    }
    saved: dict[str, Path] = {}
    keep = [
        "seg_label",
        "length_mi",
        "ksi_cnt",
        "vru_ksi_cnt",
        "ksi_disadv_cnt",
        "AADT",
        "ksi_rate_100M",
        "priority_score",
    ]
    for name, table in tables.items():
        cols = [col for col in keep if col in table.columns]
        path = output_dir / f"{name}.csv"
        table[cols].to_csv(path, index=False)
        saved[name] = path

    annual = crashes.groupby("year").agg(total=("report_no", "count"), ksi=("any_ksi_crash", "sum"), fatal=("fatal_crash", "sum"))
    annual.to_csv(output_dir / "annual_summary.csv")
    saved["annual_summary"] = output_dir / "annual_summary.csv"
    return saved


def _summary(
    crashes: pd.DataFrame,
    hin: gpd.GeoDataFrame,
    exposure: gpd.GeoDataFrame,
    priority: gpd.GeoDataFrame,
    cei: gpd.GeoDataFrame,
    chart_paths: dict[str, str],
    output_dir: Path,
) -> dict[str, object]:
    top_priority = priority.sort_values("priority_score", ascending=False).head(10)
    total_ksi = int(crashes["any_ksi_crash"].sum())
    core = hin[hin["hin_tier"].eq("Core HIN")]
    tier = hin[hin["hin_tier"].isin(["Core HIN", "Tier 2 HIN"])]
    relative_chart_paths = {
        name: str(Path(path).resolve().relative_to(output_dir.parents[1]))
        for name, path in chart_paths.items()
    }
    summary = {
        "analysis_years": "2020-2024",
        "total_crashes": int(len(crashes)),
        "ksi_crashes": total_ksi,
        "fatal_crashes": int(crashes["fatal_crash"].sum()),
        "vru_ksi_crashes": int((crashes["any_ksi_crash"] & crashes["any_vru"]).sum()),
        "dui_ksi_crashes": int((crashes["any_ksi_crash"] & crashes["any_dui"]).sum()),
        "estimated_societal_cost_2024usd": float(crashes["societal_cost_2024usd"].sum()),
        "cei_tracts": int(len(cei)),
        "disadvantaged_cei_tracts": int(cei["is_disadvantaged"].sum()),
        "segments_hin": int(len(hin)),
        "segments_exposure": int(len(exposure)),
        "segments_priority": int(len(priority)),
        "priority_segments_with_equity": int((priority["ksi_disadv_cnt"] > 0).sum()),
        "core_hin_mile_pct": float(core["length_mi"].sum() / hin["length_mi"].sum() * 100),
        "tier65_hin_mile_pct": float(tier["length_mi"].sum() / hin["length_mi"].sum() * 100),
        "top_priority_segment": str(top_priority.iloc[0]["seg_label"]) if len(top_priority) else None,
        "chart_paths": relative_chart_paths,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def run_pipeline(config: PipelineConfig | None = None) -> dict[str, object]:
    config = config or PipelineConfig(project_root=_repo_root())
    config.assets_dir.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = resolve_raw_dir(config)
    inc, drv, nmo = _read_raw_csvs(raw_dir)
    crashes = _prepare_crash_tables(inc, drv, nmo)
    roads, cei, aadt = _load_reference_layers(config)
    crashes, _ = _attach_roads(crashes, roads)
    hin, exposure, priority = _build_segment_outputs(crashes, roads, cei, aadt)

    _write_geojson(hin, config.data_dir / "segments_hin.geojson")
    _write_geojson(exposure, config.data_dir / "segments_exposure.geojson")
    _write_geojson(priority, config.data_dir / "segments_priority.geojson")

    crashes.to_csv(config.output_dir / "crash_analysis_2020_2024.csv", index=False)
    _write_tables(crashes, hin, exposure, priority, config.output_dir)
    chart_paths = _build_charts(crashes, hin, exposure, priority, cei, config.assets_dir)
    summary = _summary(crashes, hin, exposure, priority, cei, chart_paths, config.output_dir)
    return summary


if __name__ == "__main__":
    result = run_pipeline()
    print(json.dumps(result, indent=2))
