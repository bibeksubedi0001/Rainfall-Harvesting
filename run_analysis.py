"""Rainfall quality control, tank simulation and building summary; writes plots/, results/ and two CSV files."""
from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rwh import (daily_rainfall, design_chart, load_hourly_rainfall, load_rooftops, quality_report,
                 rainfall_statistics, record_years, rescale_to_annual_total, roof_inflow, simulate, smallest_capacity)
from rwh.data import SEASON_ORDER, WET_DAY_MM, WORLD_RECORD_ANNUAL_MM

# Liberation Serif has the metrics of Times New Roman and stands in where that font is not installed
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"]})

HERE = Path(__file__).resolve().parent
PLOTS, RESULTS = HERE / "plots", HERE / "results"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TARGETS = (0.5, 0.8, 0.9, 0.95)
COEFFICIENTS = (0.6, 0.7, 0.8, 0.9)
DEMAND_FRACTIONS = (0.2, 0.4, 0.6, 0.8, 1.0)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rainfall", default=HERE / "Precipitation_Data.csv", help="hourly rainfall CSV")
    parser.add_argument("--rooftops", default=HERE / "Building_Rooftop_Area_Data.csv", help="rooftop area CSV")
    parser.add_argument("--annual-total", type=float, default=None,
                        help="rescale the rainfall series to this annual total in mm (default: use it as recorded)")
    parser.add_argument("--occupants", type=float, default=5.0, help="people per household")
    parser.add_argument("--demand", type=float, default=100.0, help="litres per person per day")
    parser.add_argument("--runoff", type=float, default=0.9, help="roof runoff coefficient")
    parser.add_argument("--first-flush", type=float, default=1.0, help="mm of each rain day diverted from the tank")
    parser.add_argument("--tank", type=float, default=5000.0, help="reference tank volume in litres")
    return parser.parse_args()


def finish(fig, name):
    fig.tight_layout()
    fig.savefig(PLOTS / name, dpi=150)
    plt.close(fig)


def plot_rainfall(daily, stats, label):
    rain = daily["Daily_Rainfall_mm"]
    monthly = stats["monthly"]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(MONTHS, monthly["Rainfall_mm"], color="tab:blue")
    ax.bar_label(bars, labels=[f"{d:.0f} d" for d in monthly["Wet_Days"]], fontsize=8, padding=2)
    ax.set(ylabel="rainfall (mm)", title=f"Monthly rainfall and wet days (at least {WET_DAY_MM:g} mm), {label}")
    ax.grid(axis="y", alpha=0.3)
    finish(fig, "monthly_rainfall.png")

    share = 100 * stats["seasonal_share"]
    fig, ax = plt.subplots(figsize=(7, 3.5))
    bars = ax.barh(SEASON_ORDER[::-1], share[SEASON_ORDER[::-1]], color="tab:blue")
    ax.bar_label(bars, fmt="%.1f %%", padding=3)
    ax.set(xlabel="share of annual rainfall (%)", xlim=(0, 110),
           title="Seasonal share: winter Dec-Feb, pre-monsoon Mar-May,\nmonsoon Jun-Sep, post-monsoon Oct-Nov")
    finish(fig, "seasonal_contribution.png")

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(daily.index, rain.cumsum(), color="tab:blue")
    ax.set(ylabel="cumulative rainfall (mm)", title=f"Cumulative rainfall, {label}")
    ax.grid(alpha=0.3)
    finish(fig, "cumulative_rainfall.png")

    wet = rain[rain >= WET_DAY_MM]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(wet, bins=np.geomspace(WET_DAY_MM, max(wet.max(), 2 * WET_DAY_MM), 25), color="tab:blue", edgecolor="white")
    ax.set(xscale="log", xlabel="daily rainfall (mm)", ylabel="number of days",
           title=f"Rainfall on the {len(wet)} wet days, {label}")
    ax.grid(alpha=0.3)
    finish(fig, "rainfall_distribution.png")

    groups = [wet[wet.index.month == m].to_numpy() for m in range(1, 13)]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.boxplot([g if len(g) else [np.nan] for g in groups])
    ax.set_xticklabels(MONTHS)
    ax.set(yscale="log", ylabel="wet-day rainfall (mm)", title=f"Wet-day rainfall by month, {label}")
    ax.grid(axis="y", alpha=0.3)
    finish(fig, "rainfall_boxplot.png")


def plot_tank(capacities, curves, sizing, reference, daily, demand, tank, description):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for rule, style in (("YAS", "-"), ("YBS", "--")):
        ax.plot(capacities / 1000, 100 * curves[rule].volumetric_reliability, style, color="tab:blue",
                label=f"volume supplied, {rule}")
        ax.plot(capacities / 1000, 100 * curves[rule].time_reliability, style, color="tab:orange",
                label=f"days fully supplied, {rule}")
    for target, volume in sizing.items():
        if np.isfinite(volume):
            ax.plot(volume / 1000, 100 * target, "ko", ms=4)
            ax.annotate(f"{volume / 1000:.1f} m3", (volume / 1000, 100 * target), textcoords="offset points",
                        xytext=(6, -10), fontsize=8)
    ax.set(xscale="log", xlabel="tank volume (m3)", ylabel="reliability (%)", ylim=(0, 102))
    ax.set_title("Reliability against tank volume\n" + textwrap.fill(description, 95), fontsize=9)
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8)
    finish(fig, "tank_sizing.png")

    fig, axes = plt.subplots(3, 1, figsize=(9, 7), sharex=True)
    axes[0].bar(daily.index, daily["Daily_Rainfall_mm"], width=1.0, color="tab:blue")
    axes[0].set(ylabel="rain (mm/day)")
    axes[0].set_title(f"Daily balance with a {tank / 1000:g} m3 tank\n" + textwrap.fill(description, 95), fontsize=9)
    axes[1].plot(daily.index, reference.storage[:, 0] / 1000, color="tab:green")
    axes[1].set(ylabel="tank storage, end of day (m3)")
    axes[2].bar(daily.index, demand - reference.supplied[:, 0], width=1.0, color="tab:red")
    axes[2].set(ylabel="unmet demand (L/day)")
    for ax in axes:
        ax.grid(alpha=0.3)
    finish(fig, "storage_trace.png")


def plot_sensitivity(sensitivity, annual_demand, tank):
    labels = [f"{row['runoff_coefficient']:g}" for row in sensitivity]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(x - 0.2, [row["annual_inflow_l"] / 1000 for row in sensitivity], 0.4, color="tab:blue", label="roof inflow")
    bars = ax.bar(x + 0.2, [row["annual_yield_l"] / 1000 for row in sensitivity], 0.4, color="tab:green",
                  label=f"supplied from a {tank / 1000:g} m3 tank")
    ax.bar_label(bars, labels=[f"{100 * row['volumetric_reliability']:.0f} %" for row in sensitivity], fontsize=8)
    ax.axhline(annual_demand / 1000, color="0.3", ls=":", label="annual demand")
    ax.set(xticks=x, xticklabels=labels, xlabel="runoff coefficient", ylabel="volume (m3 per year)",
           title="Effect of the runoff coefficient (labels: share of demand supplied)")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(fontsize=8)
    finish(fig, "efficiency_simulation.png")


def plot_design_chart(storage_fractions, chart):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for fraction, row in zip(DEMAND_FRACTIONS, chart):
        ax.plot(storage_fractions, 100 * row, label=f"demand = {fraction:g} x annual inflow")
    ax.set(xscale="log", xlabel="tank volume / mean annual roof inflow", ylabel="share of demand supplied (%)",
           ylim=(0, 102), title="Design chart for this rainfall pattern (independent of the rainfall total)")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8)
    finish(fig, "design_chart.png")


def plot_buildings(per_area, annual_demand, tank):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(per_area["Rooftop_Area_m2"], per_area["Annual_Inflow_L"] / 1000, color="tab:blue", label="roof inflow")
    ax.plot(per_area["Rooftop_Area_m2"], per_area["Annual_Yield_L"] / 1000, color="tab:green",
            label=f"supplied from a {tank / 1000:g} m3 tank")
    ax.axhline(annual_demand / 1000, color="0.3", ls=":", label="annual demand")
    ax.set(xlabel="rooftop area (m2)", ylabel="volume (m3 per year)", title="Roof inflow and usable supply by rooftop area")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    finish(fig, "yield_vs_roof_area.png")


def markdown_summary(summary, stats):
    qc, used, ref, city = summary["rainfall_as_supplied"], summary["rainfall_used"], summary["reference_household"], summary["all_buildings"]
    lines = ["# Results", "", f"Command: `{summary['command']}`", "", "## Rainfall record as supplied", "", "| | |", "|---|---|",
             f"| Period | {qc['start']} to {qc['end']} ({qc['record_days']} days) |",
             f"| Hourly records | {qc['hourly_records']:,} ({100 * qc['hourly_coverage']:.1f} % of hours) |",
             f"| Days with fewer than 24 hourly records | {qc['incomplete_days']} |",
             f"| Annual total | {qc['annual_total_mm']:,.0f} mm ({qc['ratio_to_world_record']:.2f} times the world record of {WORLD_RECORD_ANNUAL_MM:,.0f} mm) |",
             f"| Largest hourly value | {qc['max_hourly_mm']:.2f} mm |",
             f"| Largest daily total | {qc['max_daily_mm']:,.1f} mm |", ""]
    lines += [f"- {w}" for w in qc["warnings"]]
    lines += ["", "## Rainfall series used in the analysis", "", used["description"], "", "| | |", "|---|---|",
              f"| Annual total | {used['annual_total_mm']:,.0f} mm |",
              f"| Wet days (at least {WET_DAY_MM:g} mm) | {used['wet_days_per_year']:.0f} |",
              f"| Mean rainfall on a wet day | {used['mean_wet_day_mm']:.1f} mm |",
              f"| Largest daily total | {used['max_daily_mm']:.1f} mm |",
              f"| Longest dry spell, with the record repeated end to end | {used['longest_dry_spell_days']} days |",
              f"| Precipitation concentration index | {used['precipitation_concentration_index']:.1f} |", "",
              "| Month | Rainfall (mm) | Wet days | Largest daily total (mm) |", "|---|---|---|---|"]
    lines += [f"| {MONTHS[m - 1]} | {row.Rainfall_mm:.1f} | {row.Wet_Days:.0f} | {row.Max_Daily_mm:.1f} |"
              for m, row in stats["monthly"].iterrows()]
    lines += ["", "| Season | Share of annual rainfall |", "|---|---|"]
    lines += [f"| {season} | {100 * share:.1f} % |" for season, share in stats["seasonal_share"].items()]
    lines += ["", "## Reference household", "", ref["description"], "", "| | |", "|---|---|",
              f"| Roof inflow | {ref['annual_inflow_l'] / 1000:.1f} m3 per year |",
              f"| Demand | {ref['annual_demand_l'] / 1000:.1f} m3 per year |",
              f"| Supplied from the tank | {ref['annual_yield_l'] / 1000:.1f} m3 per year |",
              f"| Share of demand supplied | {100 * ref['volumetric_reliability']:.1f} % |",
              f"| Days fully supplied | {100 * ref['time_reliability']:.1f} % |",
              f"| Share of roof inflow that overflows | {100 * ref['overflow_fraction']:.1f} % |",
              f"| Share of demand supplied under the YBS rule | {100 * ref['volumetric_reliability_ybs']:.1f} % |", "",
              "| Share of demand supplied | Tank volume needed |", "|---|---|"]
    lines += [f"| {key} | {'not reached below 200 m3' if value is None else f'{value / 1000:.1f} m3'} |"
              for key, value in ref["tank_for_reliability_l"].items()]
    lines += ["", "| Runoff coefficient | Roof inflow (m3/yr) | Supplied (m3/yr) | Share of demand supplied |", "|---|---|---|---|"]
    lines += [f"| {row['runoff_coefficient']:g} | {row['annual_inflow_l'] / 1000:.1f} | {row['annual_yield_l'] / 1000:.1f} | "
              f"{100 * row['volumetric_reliability']:.1f} % |" for row in summary["runoff_sensitivity"]]
    lines += ["", "## All buildings", "", city["description"], "", "| | |", "|---|---|",
              f"| Buildings | {city['buildings']:,} |",
              f"| Total rooftop area | {city['total_area_m2'] / 1e6:.2f} km2 |",
              f"| Total roof inflow | {city['annual_inflow_l'] / 1e9:.2f} million m3 per year |",
              f"| Total supplied from the tanks | {city['annual_yield_l'] / 1e9:.2f} million m3 per year |",
              f"| Share of roof inflow that is used | {100 * city['annual_yield_l'] / city['annual_inflow_l']:.1f} % |",
              f"| Share of total demand supplied | {100 * city['annual_yield_l'] / city['annual_demand_l']:.1f} % |", ""]
    return "\n".join(lines)


def main():
    args = parse_args()
    PLOTS.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)

    hourly = load_hourly_rainfall(args.rainfall)
    recorded = daily_rainfall(hourly)
    qc = quality_report(hourly, recorded)
    for warning in qc["warnings"]:
        print("WARNING:", warning)
    if args.annual_total:
        daily, factor = rescale_to_annual_total(recorded, args.annual_total)
        used = f"The recorded series multiplied by {factor:.5f} so that it totals {args.annual_total:,.0f} mm per year."
        label = f"series rescaled to {args.annual_total:,.0f} mm/yr"
    else:
        daily, factor = recorded, 1.0
        used = "The series as recorded."
        label = "series as recorded"
    rain = daily["Daily_Rainfall_mm"].to_numpy()
    years = record_years(len(daily))
    stats = rainfall_statistics(daily)

    rooftops = load_rooftops(args.rooftops)
    area = float(rooftops["Rooftop_Area_m2"].median())
    demand = args.occupants * args.demand
    annual_demand = demand * len(daily) / years
    description = (f"Roof {area:g} m2, {args.occupants:g} people at {args.demand:g} L per person per day, runoff coefficient "
                   f"{args.runoff:g}, first flush {args.first_flush:g} mm, {label}.")

    capacities = np.geomspace(100.0, 200_000.0, 80)
    inflow = roof_inflow(rain, area, args.runoff, args.first_flush)
    grid = np.repeat(inflow[:, None], len(capacities), axis=1)
    curves = {rule: simulate(grid, demand, capacities, rule=rule) for rule in ("YAS", "YBS")}
    sizing = {target: smallest_capacity(capacities, curves["YAS"].volumetric_reliability, target) for target in TARGETS}
    reference = simulate(inflow, demand, args.tank)
    reference_ybs = simulate(inflow, demand, args.tank, rule="YBS")

    sensitivity = []
    for coefficient in COEFFICIENTS:
        q = roof_inflow(rain, area, coefficient, args.first_flush)
        result = simulate(q, demand, args.tank)
        sensitivity.append({"runoff_coefficient": coefficient, "annual_inflow_l": float(q.sum() / years),
                            "annual_yield_l": float(result.supplied.sum() / years),
                            "volumetric_reliability": float(result.volumetric_reliability[0])})

    storage_fractions = np.geomspace(0.001, 1.0, 60)
    chart = design_chart(rain, storage_fractions, DEMAND_FRACTIONS)

    areas = np.sort(rooftops["Rooftop_Area_m2"].unique())
    q = roof_inflow(rain, areas, args.runoff, args.first_flush)
    city = simulate(q, demand, args.tank)
    per_area = pd.DataFrame({"Rooftop_Area_m2": areas, "Annual_Inflow_L": q.sum(axis=0) / years,
                             "Annual_Yield_L": city.supplied.sum(axis=0) / years,
                             "Volumetric_Reliability": city.volumetric_reliability})
    buildings = rooftops.merge(per_area, on="Rooftop_Area_m2", how="left")

    command = "python run_analysis.py" + (f" --annual-total {args.annual_total:g}" if args.annual_total else "")
    summary = {
        "command": command,
        "rainfall_as_supplied": qc,
        "rainfall_used": {"description": used, "scale_factor": factor,
                          **{k: v for k, v in stats.items() if k not in ("monthly", "seasonal_share")},
                          "monthly_rainfall_mm": stats["monthly"]["Rainfall_mm"].round(2).tolist(),
                          "seasonal_share": stats["seasonal_share"].round(4).to_dict()},
        "reference_household": {
            "description": description + f" Tank {args.tank:,.0f} L, yield-after-spillage rule.",
            "roof_area_m2": area, "demand_l_per_day": demand, "tank_l": args.tank,
            "annual_inflow_l": float(inflow.sum() / years), "annual_demand_l": float(annual_demand),
            "annual_yield_l": float(reference.supplied.sum() / years),
            "volumetric_reliability": float(reference.volumetric_reliability[0]),
            "time_reliability": float(reference.time_reliability[0]),
            "overflow_fraction": float(reference.overflow_fraction[0]),
            "volumetric_reliability_ybs": float(reference_ybs.volumetric_reliability[0]),
            "tank_for_reliability_l": {f"{100 * t:g} %": (v if np.isfinite(v) else None) for t, v in sizing.items()},
        },
        "runoff_sensitivity": sensitivity,
        "design_chart": {"storage_fraction": storage_fractions.round(5).tolist(), "demand_fraction": list(DEMAND_FRACTIONS),
                         "volumetric_reliability": chart.round(4).tolist()},
        "all_buildings": {
            "description": f"Every building with the same household demand and a {args.tank:,.0f} L tank.",
            "buildings": int(len(buildings)), "total_area_m2": float(buildings["Rooftop_Area_m2"].sum()),
            "annual_inflow_l": float(buildings["Annual_Inflow_L"].sum()),
            "annual_yield_l": float(buildings["Annual_Yield_L"].sum()),
            "annual_demand_l": float(annual_demand * len(buildings)),
        },
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (RESULTS / "summary.md").write_text(markdown_summary(summary, stats), encoding="utf-8")

    out = daily.reset_index()
    out.insert(1, "Recorded_Rainfall_mm", recorded["Daily_Rainfall_mm"].to_numpy())
    out["Date"] = out["Date"].dt.date
    out.round({"Recorded_Rainfall_mm": 3, "Daily_Rainfall_mm": 4}).to_csv(HERE / "daily_rainfall.csv", index=False)
    buildings.round({"Annual_Inflow_L": 0, "Annual_Yield_L": 0, "Volumetric_Reliability": 4}).to_csv(
        HERE / "rainwater_potential.csv", index=False)

    plot_rainfall(daily, stats, label)
    plot_tank(capacities, curves, sizing, reference, daily, demand, args.tank, description)
    plot_sensitivity(sensitivity, annual_demand, args.tank)
    plot_design_chart(storage_fractions, chart)
    plot_buildings(per_area, annual_demand, args.tank)
    print(markdown_summary(summary, stats))


if __name__ == "__main__":
    main()
