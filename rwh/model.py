"""Daily water balance of a rooftop rainwater tank."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .data import record_years

# yield after spillage (conservative) and yield before spillage (optimistic), after Fewkes and Butler (2000)
RULES = {"YAS": 0.0, "YBS": 1.0}


def roof_inflow(rain_mm, area_m2, runoff_coefficient=0.9, first_flush_mm=0.0):
    """Litres reaching the tank each day; 1 mm of rain on 1 m2 of roof is 1 litre. Shape: days x areas."""
    net_rain = np.clip(np.asarray(rain_mm, dtype=float) - first_flush_mm, 0.0, None)
    return runoff_coefficient * np.multiply.outer(net_rain, np.asarray(area_m2, dtype=float))


@dataclass
class TankResult:
    """Daily series in litres with shape (days, n); initial_storage has shape (n,)."""

    inflow: np.ndarray
    demand: np.ndarray
    supplied: np.ndarray
    overflow: np.ndarray
    storage: np.ndarray
    initial_storage: np.ndarray

    @property
    def volumetric_reliability(self):
        """Share of the demand volume that the tank supplied."""
        total = self.demand.sum(axis=0)
        return np.divide(self.supplied.sum(axis=0), total, out=np.ones_like(total), where=total > 0)

    @property
    def time_reliability(self):
        """Share of days on which the full demand was supplied."""
        return np.mean(self.supplied >= self.demand - 1e-9, axis=0)

    @property
    def overflow_fraction(self):
        """Share of the roof inflow that spilled."""
        total = self.inflow.sum(axis=0)
        return np.divide(self.overflow.sum(axis=0), total, out=np.zeros_like(total), where=total > 0)

    @property
    def balance_error(self):
        """Inflow minus supply, overflow and storage change; zero when mass is conserved."""
        change = self.storage[-1] - self.initial_storage
        return self.inflow.sum(axis=0) - self.supplied.sum(axis=0) - self.overflow.sum(axis=0) - change


def simulate(inflow, demand, capacity, rule="YAS", spin_up=True, max_passes=20):
    """Tank balance for inflow (days,) or (days, n), demand scalar, (n,) or (days, n), capacity scalar or (n,)."""
    if rule not in RULES:
        raise ValueError("rule must be 'YAS' (yield after spillage) or 'YBS' (yield before spillage)")
    theta = RULES[rule]
    inflow = np.asarray(inflow, dtype=float)
    if inflow.ndim == 1:
        inflow = inflow[:, None]
    demand = np.broadcast_to(np.asarray(demand, dtype=float), inflow.shape)
    capacity = np.broadcast_to(np.asarray(capacity, dtype=float), inflow.shape[1:])
    if (inflow < 0).any() or (demand < 0).any() or (capacity < 0).any():
        raise ValueError("inflow, demand and capacity must not be negative")

    start = np.zeros(inflow.shape[1])
    # with spin-up the record is repeated until the tank starts each pass at the level it ended the last one
    for _ in range(max_passes if spin_up else 1):
        level = start.copy()
        storage, supplied, overflow = np.empty_like(inflow), np.empty_like(inflow), np.empty_like(inflow)
        for t in range(inflow.shape[0]):
            taken = np.minimum(demand[t], level + theta * inflow[t])
            filled = level + inflow[t] - theta * taken
            overflow[t] = np.clip(filled - capacity, 0.0, None)
            level = np.minimum(filled, capacity) - (1.0 - theta) * taken
            storage[t], supplied[t] = level, taken
        if not spin_up or np.allclose(level, start, rtol=1e-9, atol=1e-6):
            break
        start = level
    return TankResult(inflow, demand, supplied, overflow, storage, start)


def smallest_capacity(capacities, reliability, target):
    """Smallest capacity whose reliability reaches the target (linear interpolation); NaN if it is never reached."""
    capacities = np.asarray(capacities, dtype=float)
    reliability = np.asarray(reliability, dtype=float)
    reached = np.nonzero(reliability >= target)[0]
    if reached.size == 0:
        return float("nan")
    i = int(reached[0])
    if i == 0:
        return float(capacities[0])
    step = (target - reliability[i - 1]) / (reliability[i] - reliability[i - 1])
    return float(capacities[i - 1] + step * (capacities[i] - capacities[i - 1]))


def design_chart(rain_mm, storage_fractions, demand_fractions, rule="YAS"):
    """Volumetric reliability with storage and annual demand as fractions of the mean annual roof inflow."""
    rain = np.asarray(rain_mm, dtype=float)
    years = record_years(len(rain))
    unit_inflow = rain / rain.sum() * years
    storage, demand = np.meshgrid(np.asarray(storage_fractions, dtype=float), np.asarray(demand_fractions, dtype=float))
    result = simulate(np.repeat(unit_inflow[:, None], storage.size, axis=1), demand.ravel() * years / len(rain),
                      storage.ravel(), rule=rule)
    return result.volumetric_reliability.reshape(storage.shape)
