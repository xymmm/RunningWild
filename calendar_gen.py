"""
calendar_gen.py

Generates a deterministic 50-day calendar from a seed.

The calendar specifies, for each day, one of:
  - "rest"      : no random events, no consumption, HP +1
  - "fortune"   : a specific bonus event from the day's pool
  - "normal"    : Scheme A random draw over the random event pool

Usage:
    from calendar_gen import generate_calendar
    cal = generate_calendar(seed=42, horizon=50)
    for entry in cal:
        print(entry)
"""

import json
import random
from pathlib import Path
from typing import List, Dict


def generate_calendar(seed: int = 0,
                      horizon: int = 50,
                      data_dir: str = ".") -> List[Dict]:
    """
    Build a per-day calendar.

    Returns a list of dicts of length `horizon`, indexed by day-1.
    Each dict has:
        day:        int (1-indexed)
        type:       "rest" | "fortune" | "normal"
        scheduled:  event id (str) if type in {rest, fortune}, else None
    """
    rng = random.Random(seed)
    p = Path(data_dir)
    params = json.load(open(p / "parameters.json"))
    scheduled = json.load(open(p / "scheduled_events.json"))

    rest_days = set(params["calendar"]["rest_days"])
    fortune_pools = {int(k): v for k, v in params["calendar"]["fortune_days"].items()}
    fortune_meta = scheduled["fortune_events"]

    calendar = []
    for d in range(1, horizon + 1):
        if d in rest_days:
            calendar.append({"day": d, "type": "rest", "scheduled": "rest_day"})
        elif d in fortune_pools:
            pool = fortune_pools[d]
            # weighted choice
            weights = [fortune_meta[eid].get("weight_in_pool", 1.0) for eid in pool]
            chosen = rng.choices(pool, weights=weights, k=1)[0]
            calendar.append({"day": d, "type": "fortune", "scheduled": chosen})
        else:
            calendar.append({"day": d, "type": "normal", "scheduled": None})
    return calendar


def summarise_calendar(calendar):
    """Print human-readable calendar summary."""
    print(f"Calendar — {len(calendar)} days")
    print("-" * 50)
    type_counts = {"rest": 0, "fortune": 0, "normal": 0}
    for e in calendar:
        type_counts[e["type"]] += 1
        if e["type"] != "normal":
            print(f"  Day {e['day']:2d}: {e['type']:8s}  -> {e['scheduled']}")
    print("-" * 50)
    for k, v in type_counts.items():
        print(f"  {k:8s}: {v} days")


if __name__ == "__main__":
    import sys
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    cal = generate_calendar(seed=seed)
    summarise_calendar(cal)

    print()
    print("=" * 50)
    print("Comparison with a different seed:")
    print("=" * 50)
    cal2 = generate_calendar(seed=seed + 1)
    summarise_calendar(cal2)
