"""Loading, quality control and summary statistics of the rainfall and rooftop data."""
from __future__ import annotations

import numpy as np
import pandas as pd

# WMO World Weather and Climate Extremes Archive: Cherrapunji, India, August 1860 to July 1861.
WORLD_RECORD_ANNUAL_MM = 26470.0
WET_DAY_MM = 1.0
SEASONS = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Pre-monsoon", 4: "Pre-monsoon", 5: "Pre-monsoon",
           6: "Monsoon", 7: "Monsoon", 8: "Monsoon", 9: "Monsoon", 10: "Post-monsoon", 11: "Post-monsoon"}
SEASON_ORDER = ["Winter", "Pre-monsoon", "Monsoon", "Post-monsoon"]


def record_years(n_days):
    """Length of a daily record in years; records within 1 % of whole years count as whole years."""
    years = n_days / 365.25
    return float(round(years)) if round(years) >= 1 and abs(years - round(years)) < 0.01 else years


def load_hourly_rainfall(path, time_column="DateTime", rain_column="Rainfall (mm/hr)"):
    """Read an hourly rainfall record (mm in each hour) as a series indexed by time."""
    frame = pd.read_csv(path)
    series = pd.Series(frame[rain_column].to_numpy(dtype=float), index=pd.to_datetime(frame[time_column]), name="rain_mm")
    if series.index.duplicated().any():
        raise ValueError("the rainfall record contains duplicate time stamps")
    if series.isna().any() or (series < 0).any():
        raise ValueError("the rainfall record contains missing or negative values")
    return series.sort_index()


def daily_rainfall(hourly):
    """Daily totals (mm) with the number of hourly records behind each day."""
    day = hourly.index.normalize()
    daily = pd.DataFrame({"Daily_Rainfall_mm": hourly.groupby(day).sum(), "Hours_Recorded": hourly.groupby(day).size()})
    daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max(), freq="D"))
    daily["Daily_Rainfall_mm"] = daily["Daily_Rainfall_mm"].fillna(0.0)
    daily["Hours_Recorded"] = daily["Hours_Recorded"].fillna(0).astype(int)
    daily["Month"] = daily.index.month
    daily["Season"] = daily["Month"].map(SEASONS)
    daily.index.name = "Date"
    return daily


def longest_run(flags):
    """Length of the longest run of True values."""
    best = run = 0
    for flag in flags:
        run = run + 1 if flag else 0
        best = max(best, run)
    return best


def quality_report(hourly, daily):
    """Coverage and plausibility checks of a rainfall record."""
    rain = daily["Daily_Rainfall_mm"]
    annual = float(rain.sum() / record_years(len(daily)))
    incomplete = daily.index[daily["Hours_Recorded"] < 24]
    report = {
        "start": str(daily.index.min().date()),
        "end": str(daily.index.max().date()),
        "record_days": int(len(daily)),
        "hourly_records": int(len(hourly)),
        "hourly_coverage": float(len(hourly) / (24 * len(daily))),
        "incomplete_days": int(len(incomplete)),
        "incomplete_day_examples": [str(d.date()) for d in incomplete[:5]],
        "annual_total_mm": annual,
        "max_hourly_mm": float(hourly.max()),
        "max_daily_mm": float(rain.max()),
        "ratio_to_world_record": annual / WORLD_RECORD_ANNUAL_MM,
        "warnings": [],
    }
    if len(incomplete):
        report["warnings"].append(f"{len(incomplete)} days have fewer than 24 hourly records; their totals are taken as recorded")
    if annual > WORLD_RECORD_ANNUAL_MM:
        report["warnings"].append(
            f"the annual total of {annual:,.0f} mm is {annual / WORLD_RECORD_ANNUAL_MM:.1f} times the world record of "
            f"{WORLD_RECORD_ANNUAL_MM:,.0f} mm, so the magnitudes cannot be an observed record")
    return report


def rescale_to_annual_total(daily, annual_total_mm):
    """Scale the daily series so that its mean annual total equals the given value; returns the frame and factor."""
    current = daily["Daily_Rainfall_mm"].sum() / record_years(len(daily))
    if current <= 0:
        raise ValueError("the rainfall record is empty")
    factor = float(annual_total_mm / current)
    scaled = daily.copy()
    scaled["Daily_Rainfall_mm"] = daily["Daily_Rainfall_mm"] * factor
    return scaled, factor


def rainfall_statistics(daily):
    """Monthly and seasonal totals, wet-day counts, dry spells and the precipitation concentration index."""
    rain = daily["Daily_Rainfall_mm"]
    years = record_years(len(daily))
    wet = rain >= WET_DAY_MM
    monthly = pd.DataFrame({
        "Rainfall_mm": rain.groupby(daily["Month"]).sum() / years,
        "Wet_Days": wet.groupby(daily["Month"]).sum() / years,
        "Max_Daily_mm": rain.groupby(daily["Month"]).max(),
    }).reindex(range(1, 13), fill_value=0.0)
    seasonal = (rain.groupby(daily["Season"]).sum() / rain.sum()).reindex(SEASON_ORDER, fill_value=0.0)
    totals = monthly["Rainfall_mm"].to_numpy()
    dry = ~wet.to_numpy()
    # the tank simulation repeats the record, so a dry spell may run across its end
    dry_spell = len(dry) if dry.all() else longest_run(np.concatenate([dry, dry]))
    return {
        "annual_total_mm": float(rain.sum() / years),
        "wet_days_per_year": float(wet.sum() / years),
        "mean_wet_day_mm": float(rain[wet].mean()) if wet.any() else 0.0,
        "max_daily_mm": float(rain.max()),
        "longest_dry_spell_days": int(dry_spell),
        "precipitation_concentration_index": float(100 * np.sum(totals**2) / np.sum(totals) ** 2),
        "monthly": monthly,
        "seasonal_share": seasonal,
    }


def load_rooftops(path):
    """Read building identifiers and rooftop areas (m2) from the first two columns of a CSV file."""
    frame = pd.read_csv(path)
    rooftops = pd.DataFrame({"Building_ID": frame.iloc[:, 0], "Rooftop_Area_m2": frame.iloc[:, 1].astype(float)})
    if rooftops["Rooftop_Area_m2"].isna().any() or (rooftops["Rooftop_Area_m2"] <= 0).any():
        raise ValueError("rooftop areas must be positive numbers")
    return rooftops
