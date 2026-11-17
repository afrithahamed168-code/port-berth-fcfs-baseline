"""
Project 1 -- Multi-Factor Scheduling Simulator
Week 3 check: deterministic FCFS baseline, built in SimPy.

This mirrors the FCFS_Baseline sheet in the Excel workbook, row for row:
  - same berth-eligibility rule (vessel size rank <= berth's max rank)
  - same tie-break rule (lowest-numbered berth wins when equally free)
  - same service-time formula
The only difference is *how* it's expressed: instead of spreadsheet rows,
each vessel is a SimPy process, and each berth is a SimPy Resource.

Usage:
    python fcfs_baseline_simpy.py                # reads ./data
    python fcfs_baseline_simpy.py path/to/data   # or any folder with the 3 input files
"""

import sys
from pathlib import Path
from datetime import datetime

import simpy
from openpyxl import load_workbook

# Folder holding vessel_arrivals.xlsx, port_configuration.xlsx, service_profiles.xlsx
DATA_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "data"

REFERENCE_EPOCH = datetime(2024, 1, 1, 0, 0, 0)   # t=0 in the simulation clock
# "free since before the sim started"
SEED_HOURS = -24.0
# same role as the Excel seed date 2023-12-31

VESSEL_RANK = {
    "Handysize": 1,
    "Handymax": 2,
    "Supramax/Ultramax": 3,
    "Panamax/Kamsarmax": 4,
}
# order = tie-break priority, same as the Excel nested IF
BERTH_ORDER = ["B1", "B2", "B3", "B4"]


def to_hours(timestamp):
    """Convert an arrival/target timestamp into hours since the reference epoch.
    Accepts either a text timestamp ("2024-01-01T00:00:00Z") or an actual
    datetime -- Excel often auto-converts ISO date text into real date cells
    when a CSV is opened and re-saved as .xlsx, so both forms can show up."""
    if isinstance(timestamp, datetime):
        dt = timestamp.replace(tzinfo=None)
    else:
        dt = datetime.fromisoformat(str(timestamp).replace(
            "Z", "+00:00")).replace(tzinfo=None)
    return (dt - REFERENCE_EPOCH).total_seconds() / 3600.0


def read_xlsx_rows(path):
    """Read the first sheet of an .xlsx file into a list of dicts, keyed by
    the header row -- the .xlsx equivalent of csv.DictReader. Stops at the
    first fully-blank row so trailing empty rows in the sheet don't get in."""
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    headers = [str(h).strip() for h in next(rows)]
    records = []
    for row in rows:
        if all(v is None for v in row):
            continue
        records.append(dict(zip(headers, row)))
    wb.close()
    return records


def load_data():
    arrivals = read_xlsx_rows(DATA_DIR / "vessel_arrivals.xlsx")

    berth_max_rank = {
        row["berth_id"]: VESSEL_RANK[row["maximum_vessel_class"]]
        for row in read_xlsx_rows(DATA_DIR / "port_configuration.xlsx")
    }

    profiles = {
        (row["berth_id"], row["vessel_class"], row["cargo_class"]): row
        for row in read_xlsx_rows(DATA_DIR / "service_profiles.xlsx")
    }

    return arrivals, berth_max_rank, profiles


class Berth:
    """One berth. resource is the real SimPy object that holds/releases it;
    free_at is our own bookkeeping of when it becomes available -- this is
    the exact same role as the free_before/free_after columns in Excel."""

    def __init__(self, env, berth_id):
        self.id = berth_id
        self.resource = simpy.Resource(env, capacity=1)
        self.free_at = SEED_HOURS


def vessel_process(env, call, berth_max_rank, profiles, berths, results):
    arrival_h = to_hours(call["arrival_utc"])
    if arrival_h > env.now:
        yield env.timeout(arrival_h - env.now)

    # ---- decision step: identical logic to the Excel sheet's H:U columns ----
    vrank = VESSEL_RANK[call["vessel_class"]]
    eligible = [b for b in berths if vrank <= berth_max_rank[b.id]]

    # pick the eligible berth that's free soonest; ties go to the lower berth id
    # (same as Excel's nested IF checking B1, then B2, then B3, then B4)
    # IMPORTANT: compare max(arrival, free_at) -- the actual moment the vessel
    # could start -- not raw free_at. A berth that's been idle a long time and
    # one that just freed up are both simply "available now"; ranking them by
    # how long ago they freed up (instead of tying them) was the bug here.
    chosen = min(eligible, key=lambda b: (
        max(arrival_h, b.free_at), BERTH_ORDER.index(b.id)))

    start_h = max(arrival_h, chosen.free_at)
    wait_h = start_h - arrival_h

    prof = profiles[(chosen.id, call["vessel_class"], call["cargo_class"])]
    setup_h = float(prof["setup_hours"])
    rate = float(prof["nominal_handling_rate_mt_per_day"])
    qty = float(call["cargo_quantity_tonnes"])
    service_h = setup_h + (qty / rate) * 24

    completion_h = start_h + service_h
    # same moment the Excel sheet's free_after column updates
    chosen.free_at = completion_h

    # ---- advance the simulated clock and actually hold the SimPy Resource ----
    # (this is what makes it a genuine SimPy model rather than a plain loop --
    # the Resource's own state now correctly reflects "B2 busy from hour X to Y")
    if start_h > env.now:
        yield env.timeout(start_h - env.now)
    with chosen.resource.request() as req:
        yield req
        yield env.timeout(service_h)

    results.append({
        "call_id": call["call_id"],
        "berth": chosen.id,
        "arrival_h": arrival_h,
        "wait_h": wait_h,
        "service_h": service_h,
        "completion_h": completion_h,
    })


def run_baseline():
    arrivals, berth_max_rank, profiles = load_data()

    env = simpy.Environment()
    berths = [Berth(env, bid) for bid in BERTH_ORDER]
    results = []

    for call in arrivals:
        env.process(vessel_process(
            env, call, berth_max_rank, profiles, berths, results))

    env.run()
    # restore arrival order for reporting
    results.sort(key=lambda r: r["arrival_h"])
    return results


def summarize(results):
    waits = sorted(r["wait_h"] for r in results)
    n = len(waits)
    avg = sum(waits) / n
    median = waits[n //
                   2] if n % 2 else (waits[n // 2 - 1] + waits[n // 2]) / 2
    p95_pos = 0.95 * (n - 1)
    lo, hi = int(p95_pos), min(int(p95_pos) + 1, n - 1)
    p95 = waits[lo] + (waits[hi] - waits[lo]) * (p95_pos - lo)
    span_days = max(r["completion_h"] for r in results) / \
        24 - min(r["arrival_h"] for r in results) / 24
    throughput_month = n / span_days * 30.44

    print(f"Vessels processed:            {n}")
    print(f"Average waiting time:         {avg:.2f} hours")
    print(f"Median waiting time:          {median:.2f} hours")
    print(f"95th-percentile waiting time: {p95:.2f} hours")
    print(f"Maximum waiting time:         {max(waits):.2f} hours")
    print(
        f"Throughput:                   {throughput_month:.2f} vessels/month")


if __name__ == "__main__":
    results = run_baseline()
    summarize(results)

    print("\nFirst 5 calls:")
    for r in sorted(results, key=lambda r: r["arrival_h"])[:5]:
        print(f"  {r['call_id']}: berth={r['berth']}, wait={r['wait_h']:.2f}h, "
              f"service={r['service_h']:.2f}h")
