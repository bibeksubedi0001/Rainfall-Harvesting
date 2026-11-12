"""Rooftop rainwater harvesting: rainfall quality control and tank water balance."""
from .data import (daily_rainfall, load_hourly_rainfall, load_rooftops, quality_report, rainfall_statistics,
                   record_years, rescale_to_annual_total)
from .model import TankResult, design_chart, roof_inflow, simulate, smallest_capacity

__all__ = ["daily_rainfall", "load_hourly_rainfall", "load_rooftops", "quality_report", "rainfall_statistics",
           "record_years", "rescale_to_annual_total", "TankResult", "design_chart", "roof_inflow", "simulate",
           "smallest_capacity"]
