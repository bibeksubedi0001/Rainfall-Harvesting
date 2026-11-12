"""Checks of the rainfall handling and the tank water balance."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rwh import (daily_rainfall, design_chart, quality_report, rainfall_statistics, record_years,  # noqa: E402
                 rescale_to_annual_total, roof_inflow, simulate, smallest_capacity)
from rwh.data import WORLD_RECORD_ANNUAL_MM  # noqa: E402


def sample_rain(days=365, seed=1):
    rng = np.random.default_rng(seed)
    wet = rng.random(days) < 0.3
    return np.where(wet, rng.gamma(0.8, 12.0, days), 0.0)


class InflowTests(unittest.TestCase):
    def test_one_millimetre_on_one_square_metre_is_one_litre(self):
        self.assertEqual(roof_inflow([1.0], 1.0, runoff_coefficient=1.0)[0], 1.0)

    def test_coefficient_first_flush_and_shape(self):
        inflow = roof_inflow([0.5, 3.0, 10.0], [100.0, 200.0], runoff_coefficient=0.9, first_flush_mm=1.0)
        self.assertEqual(inflow.shape, (3, 2))
        np.testing.assert_allclose(inflow, [[0.0, 0.0], [180.0, 360.0], [810.0, 1620.0]])


class TankTests(unittest.TestCase):
    def setUp(self):
        self.inflow = roof_inflow(sample_rain(), 120.0)
        self.capacities = np.array([0.0, 500.0, 2000.0, 8000.0, 50000.0])
        self.grid = np.repeat(self.inflow[:, None], len(self.capacities), axis=1)

    def test_mass_balance_closes(self):
        for rule in ("YAS", "YBS"):
            for spin_up in (False, True):
                result = simulate(self.grid, 400.0, self.capacities, rule=rule, spin_up=spin_up)
                np.testing.assert_allclose(result.balance_error, 0.0, atol=1e-6)
                self.assertTrue((result.storage >= -1e-9).all())
                self.assertTrue((result.storage <= self.capacities + 1e-9).all())
                self.assertTrue((result.supplied <= 400.0 + 1e-9).all())

    def test_spin_up_ends_where_it_started(self):
        result = simulate(self.grid, 400.0, self.capacities)
        np.testing.assert_allclose(result.storage[-1], result.initial_storage, atol=1e-6)

    def test_yas_is_never_above_ybs(self):
        yas = simulate(self.grid, 400.0, self.capacities, rule="YAS").volumetric_reliability
        ybs = simulate(self.grid, 400.0, self.capacities, rule="YBS").volumetric_reliability
        self.assertTrue((yas <= ybs + 1e-12).all())

    def test_zero_capacity(self):
        yas = simulate(self.inflow, 400.0, 0.0, rule="YAS")
        ybs = simulate(self.inflow, 400.0, 0.0, rule="YBS")
        self.assertEqual(yas.supplied.sum(), 0.0)
        np.testing.assert_allclose(ybs.supplied[:, 0], np.minimum(self.inflow, 400.0))

    def test_reliability_grows_with_capacity(self):
        result = simulate(self.grid, 400.0, self.capacities)
        self.assertTrue((np.diff(result.volumetric_reliability) >= -1e-12).all())
        self.assertTrue((np.diff(result.time_reliability) >= -1e-12).all())

    def test_large_tank_meets_a_demand_below_the_inflow(self):
        demand = 0.8 * self.inflow.mean()
        result = simulate(self.inflow, demand, 1e12)
        self.assertAlmostEqual(result.volumetric_reliability[0], 1.0, places=9)
        self.assertAlmostEqual(result.time_reliability[0], 1.0, places=9)

    def test_supply_cannot_exceed_inflow_in_steady_state(self):
        demand = 1.5 * self.inflow.mean()
        result = simulate(self.inflow, demand, 1e12)
        self.assertAlmostEqual(result.volumetric_reliability[0], 1 / 1.5, places=6)

    def test_scaling_all_volumes_leaves_reliability_unchanged(self):
        base = simulate(self.grid, 400.0, self.capacities)
        scaled = simulate(40.0 * self.grid, 40.0 * 400.0, 40.0 * self.capacities)
        np.testing.assert_allclose(base.volumetric_reliability, scaled.volumetric_reliability, rtol=1e-9)
        np.testing.assert_allclose(base.overflow_fraction, scaled.overflow_fraction, rtol=1e-9, atol=1e-12)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            simulate(self.inflow, 400.0, 1000.0, rule="mean")
        with self.assertRaises(ValueError):
            simulate(self.inflow, -1.0, 1000.0)

    def test_smallest_capacity(self):
        self.assertAlmostEqual(smallest_capacity([0, 10, 20], [0.2, 0.6, 1.0], 0.8), 15.0)
        self.assertEqual(smallest_capacity([5, 10], [0.9, 1.0], 0.5), 5.0)
        self.assertTrue(np.isnan(smallest_capacity([5, 10], [0.2, 0.3], 0.5)))

    def test_design_chart_matches_a_dimensional_run(self):
        rain = sample_rain()
        area, coefficient = 150.0, 0.85
        annual_inflow = coefficient * area * rain.sum()
        chart = design_chart(rain, [0.01, 0.05, 0.2], [0.5])
        direct = simulate(np.repeat(roof_inflow(rain, area, coefficient)[:, None], 3, axis=1),
                          0.5 * annual_inflow / len(rain), np.array([0.01, 0.05, 0.2]) * annual_inflow)
        np.testing.assert_allclose(chart[0], direct.volumetric_reliability, rtol=1e-9)


class RainfallTests(unittest.TestCase):
    def setUp(self):
        index = pd.date_range("2025-01-01", "2025-12-31 23:00", freq="h")
        rng = np.random.default_rng(3)
        values = np.where(rng.random(len(index)) < 0.1, rng.gamma(1.0, 2.0, len(index)), 0.0)
        self.hourly = pd.Series(values, index=index)

    def test_record_years(self):
        self.assertEqual(record_years(365), 1.0)
        self.assertEqual(record_years(366), 1.0)
        self.assertEqual(record_years(3653), 10.0)
        self.assertAlmostEqual(record_years(500), 500 / 365.25)

    def test_daily_totals_and_coverage(self):
        gappy = self.hourly.drop(self.hourly.index[24 * 40 + 1: 24 * 41])
        daily = daily_rainfall(gappy)
        self.assertEqual(len(daily), 365)
        self.assertAlmostEqual(daily["Daily_Rainfall_mm"].sum(), gappy.sum())
        self.assertEqual(daily["Hours_Recorded"].iloc[40], 1)
        report = quality_report(gappy, daily)
        self.assertEqual(report["incomplete_days"], 1)
        self.assertAlmostEqual(report["hourly_coverage"], (8760 - 23) / 8760)
        self.assertEqual(len(report["warnings"]), 1)

    def test_implausible_total_is_flagged(self):
        huge = self.hourly * (3 * WORLD_RECORD_ANNUAL_MM / self.hourly.sum())
        report = quality_report(huge, daily_rainfall(huge))
        self.assertAlmostEqual(report["ratio_to_world_record"], 3.0, places=6)
        self.assertTrue(any("world record" in w for w in report["warnings"]))

    def test_rescaling_reaches_the_target(self):
        daily = daily_rainfall(self.hourly)
        scaled, factor = rescale_to_annual_total(daily, 1500.0)
        self.assertAlmostEqual(scaled["Daily_Rainfall_mm"].sum(), 1500.0, places=6)
        self.assertAlmostEqual(factor, 1500.0 / self.hourly.sum())
        self.assertAlmostEqual(daily["Daily_Rainfall_mm"].sum(), self.hourly.sum())

    def test_statistics(self):
        daily = daily_rainfall(self.hourly)
        stats = rainfall_statistics(daily)
        self.assertAlmostEqual(stats["monthly"]["Rainfall_mm"].sum(), self.hourly.sum())
        self.assertAlmostEqual(stats["seasonal_share"].sum(), 1.0)
        self.assertGreaterEqual(stats["precipitation_concentration_index"], 100 / 12)
        uniform = daily.assign(Daily_Rainfall_mm=2.0)
        self.assertEqual(rainfall_statistics(uniform)["longest_dry_spell_days"], 0)
        dry = daily.assign(Daily_Rainfall_mm=0.0)
        dry.iloc[100, dry.columns.get_loc("Daily_Rainfall_mm")] = 5.0
        self.assertEqual(rainfall_statistics(dry)["longest_dry_spell_days"], 364)


if __name__ == "__main__":
    unittest.main()
