"""
calibrate.py — Monte Carlo check of the default settings.

Run:  python calibrate.py [days]

Strategies compared:
  random        : items added in random order until nothing else fits
  mitigation    : greedy on expected HP saved per kg, ignoring water and food;
                  this mimics the GAMS expected-HP-loss model
  mit + water   : extra water and a filter first, then the same greedy
Also reports how much the mitigation greedy would carry with no limit,
which shows whether the knapsack constraints bind.
"""
import random
import statistics
import sys

import engine

D = engine.load_data()
P = dict(D["params"])


def random_pack(rng):
    ids = list(D["items"])
    rng.shuffle(ids)
    inv = {}
    for i in ids:
        inv[i] = 1
        if not engine.is_feasible(inv, D, P):
            inv.pop(i)
    return inv


def greedy(start=None, cap=True):
    inv = dict(start or {})

    def gain(i):
        trial = dict(inv, **{i: 1})
        s = 0.0
        for e in D["events"].values():
            if e["base_hp"] <= 0 and not engine.mitigated(inv, e, 10) and engine.mitigated(trial, e, 10):
                s += e["weight"] * (e["mit_hp"] - e["base_hp"])
        return s / max(D["items"][i]["weight_kg"], 0.05)

    while True:
        cands = sorted(((gain(i), i) for i in D["items"] if i not in inv), reverse=True)
        cands = [c for c in cands if c[0] > 0]
        added = False
        for _, i in cands:
            inv[i] = 1
            if not cap or engine.is_feasible(inv, D, P):
                added = True
                break
            inv.pop(i)
        if not added:
            return inv


def run(packfn, days, n=400):
    alive, finals, causes, weights = 0, [], {}, []
    for s in range(n):
        rng = random.Random(s)
        loc = rng.choice(list(D["locations"]))
        tr = rng.choice(list(D["traits"]))
        inv = packfn(rng)
        weights.append(engine.pack_totals(inv, D)["weight"])
        team = {"inv": inv, "location": loc, "trait": tr,
                "state": engine.init_team_state(inv, loc, tr, D, P),
                "resupply_days": engine.resupply_days(P, s, days)}
        for d in range(1, days + 1):
            engine.resolve_day(team, engine.draw_event(D, s, d), d, D, P)
        st = team["state"]
        if st["alive"]:
            alive += 1
            finals.append(engine.final_score(st, P)["hp_final"])
        else:
            causes[st["death_cause"]] = causes.get(st["death_cause"], 0) + 1
    med = statistics.median(finals) if finals else None
    return (f"survive {alive / n:5.1%}  median final HP {med}  "
            f"mean pack {statistics.mean(weights):.1f} kg  deaths {causes}")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else P["default_days"]
    unlimited = greedy(cap=False)
    t = engine.pack_totals(unlimited, D)
    print(f"Mitigation greedy without limits wants {len(unlimited)} items, {t['weight']} kg, {t['volume']} L")
    mit = greedy()
    mitw = greedy({"water_5L": 1, "water_2L": 1, "gravity_filter": 1})
    print(f"{days} days, resupply {P['resupply_mode']}")
    print(" random      ", run(random_pack, days))
    print(" mitigation  ", run(lambda r: mit, days))
    print(" mit + water ", run(lambda r: mitw, days))
