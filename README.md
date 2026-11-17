# Port Berth Scheduling: FCFS Baseline (SimPy)

A deterministic **first-come-first-served (FCFS)** berth scheduling baseline for a dry-bulk port, built as a discrete-event simulation in Python with [SimPy](https://simpy.readthedocs.io/).

This is my individual-phase work for the industrial project in **SUTD 40.318 Supply Chain Digitalisation and Design**, run with **Cargill Ocean Transportation**. The wider project builds a simulator that stress-tests berth scheduling rules under disruption (bad weather, congestion surges, berth outages). This baseline is the reference that every other rule and scenario gets compared against.

Full write-up: [afrithahamed168-code.github.io/projects/port-scheduling-simulator.html](https://afrithahamed168-code.github.io/projects/port-scheduling-simulator.html)

## What it does

- Loads **432 dry-bulk vessel arrivals** over one year, **4 berths** and **78 service profiles**.
- Sends each ship to the earliest-available berth that can fit it. Ties go to the lowest-numbered berth.
- Calculates service time as `setup hours + cargo tonnes / handling rate (t/day) × 24`.
- Models each ship as a SimPy process and each berth as a SimPy `Resource`.
- Reports average, median, 95th-percentile and maximum waiting time, plus throughput.

## Validation

I built the same baseline twice: once as a formula-only Excel model (one row per ship, no macros) and once here in SimPy. The two produce **identical results**, row for row.

Comparing them also caught a bug in my first Python version. When two berths were both free, it preferred the one that had been empty longest, instead of treating them as tied. The fix (comparing `max(arrival, free_at)`, not raw `free_at`) is commented in `vessel_process`.

## Results (baseline, no disruption)

| Metric | Value |
|---|---|
| Vessels processed | 432 |
| Average wait | 6.71 h |
| Median wait | 0.00 h |
| 95th-percentile wait | 27.18 h |
| Maximum wait | 71.30 h |
| Throughput | 35.81 vessels / month |

236 of 432 ships (55%) berth with no wait. But the delays aren't spread evenly: the largest ships can only use 2 of the 4 berths, and those berths are busy over 90% of the year.

| Ship size | Berths it can use | Avg. wait | 95th-pct wait |
|---|---|---|---|
| Handysize | 4 | 1.2 h | 8.4 h |
| Handymax | 4 | 7.1 h | 22.2 h |
| Supramax / Ultramax | 3 | 7.0 h | 27.3 h |
| Panamax / Kamsarmax | 2 | 11.6 h | 43.5 h |

## How to run

```bash
pip install -r requirements.txt
python fcfs_baseline_simpy.py path/to/data
```

The data folder needs three files: `vessel_arrivals.xlsx`, `port_configuration.xlsx` and `service_profiles.xlsx`. If you leave out the path, the script looks in `./data`.

## About the data

The input data is a coursework data pack supplied by Cargill for SUTD 40.318. It is **not included in this repository**. It is a manageable model of a dry-bulk terminal, not records of named Port of Rotterdam berths or real operations.

## Next steps (team phase, in progress)

- Hourly weather disruptions that slow or stop cargo handling
- Four operating scenarios: baseline, congestion surge, berth outage and combined shock
- Alternative scheduling rules (deadline-based and size-based priority), compared on average wait, tail wait and throughput

---

Afrith Ahamed · [Portfolio](https://afrithahamed168-code.github.io/) · [LinkedIn](https://www.linkedin.com/in/afrith-ahamed/)
