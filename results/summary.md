# Results

Command: `python run_analysis.py --annual-total 1500`

## Rainfall record as supplied

| | |
|---|---|
| Period | 2025-01-01 to 2025-12-31 (365 days) |
| Hourly records | 8,484 (96.8 % of hours) |
| Days with fewer than 24 hourly records | 12 |
| Annual total | 64,383 mm (2.43 times the world record of 26,470 mm) |
| Largest hourly value | 49.97 mm |
| Largest daily total | 776.8 mm |

- 12 days have fewer than 24 hourly records; their totals are taken as recorded
- the annual total of 64,383 mm is 2.4 times the world record of 26,470 mm, so the magnitudes cannot be an observed record

## Rainfall series used in the analysis

The recorded series multiplied by 0.02330 so that it totals 1,500 mm per year.

| | |
|---|---|
| Annual total | 1,500 mm |
| Wet days (at least 1 mm) | 189 |
| Mean rainfall on a wet day | 7.7 mm |
| Largest daily total | 18.1 mm |
| Longest dry spell, with the record repeated end to end | 152 days |
| Precipitation concentration index | 21.8 |

| Month | Rainfall (mm) | Wet days | Largest daily total (mm) |
|---|---|---|---|
| Jan | 0.8 | 0 | 0.1 |
| Feb | 2.4 | 0 | 0.2 |
| Mar | 9.3 | 0 | 0.7 |
| Apr | 27.0 | 10 | 1.6 |
| May | 64.3 | 30 | 3.4 |
| Jun | 194.8 | 29 | 9.4 |
| Jul | 462.0 | 30 | 18.1 |
| Aug | 420.4 | 31 | 16.6 |
| Sep | 223.1 | 29 | 10.1 |
| Oct | 83.3 | 30 | 4.0 |
| Nov | 10.7 | 0 | 0.7 |
| Dec | 2.0 | 0 | 0.1 |

| Season | Share of annual rainfall |
|---|---|
| Winter | 0.3 % |
| Pre-monsoon | 6.7 % |
| Monsoon | 86.7 % |
| Post-monsoon | 6.3 % |

## Reference household

Roof 174 m2, 5 people at 100 L per person per day, runoff coefficient 0.9, first flush 1 mm, series rescaled to 1,500 mm/yr. Tank 5,000 L, yield-after-spillage rule.

| | |
|---|---|
| Roof inflow | 198.9 m3 per year |
| Demand | 182.5 m3 per year |
| Supplied from the tank | 78.6 m3 per year |
| Share of demand supplied | 43.1 % |
| Days fully supplied | 37.8 % |
| Share of roof inflow that overflows | 60.5 % |
| Share of demand supplied under the YBS rule | 43.6 % |

| Share of demand supplied | Tank volume needed |
|---|---|
| 50 % | 17.6 m3 |
| 80 % | 72.4 m3 |
| 90 % | 90.6 m3 |
| 95 % | 99.8 m3 |

| Runoff coefficient | Roof inflow (m3/yr) | Supplied (m3/yr) | Share of demand supplied |
|---|---|---|---|
| 0.6 | 132.6 | 73.9 | 40.5 % |
| 0.7 | 154.7 | 75.5 | 41.4 % |
| 0.8 | 176.8 | 77.0 | 42.2 % |
| 0.9 | 198.9 | 78.6 | 43.1 % |

## All buildings

Every building with the same household demand and a 5,000 L tank.

| | |
|---|---|
| Buildings | 20,000 |
| Total rooftop area | 3.48 km2 |
| Total roof inflow | 3.98 million m3 per year |
| Total supplied from the tanks | 1.55 million m3 per year |
| Share of roof inflow that is used | 38.9 % |
| Share of total demand supplied | 42.4 % |
