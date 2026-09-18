"""
check_game.py — run a whole class session offline and check that it behaves.

No browser and no Streamlit: this script drives the same room logic the app
uses (rooms.py + engine.py), prints what the big screen would show day by
day, checks a list of invariants, and saves the logs as CSV files.

Examples
    python check_game.py                          # 15 groups, 20 days, defaults
    python check_game.py --groups 20 --days 25 --seed 7
    python check_game.py --resupply fixed --every 5
    python check_game.py --packs my_packs.csv     # your own backpacks
    python check_game.py --quiet                  # only the checks and the results

my_packs.csv has three columns, one row per item:
    group,item,qty
    1,sleeping_bag,1
    1,water_2L,2
    2,four_season_tent,1
Item ids are the `id` column of data/items.csv. Groups not in the file get a
random backpack. A backpack over the limits is rejected, exactly as in the app.
"""

import argparse
import math
import random
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd

import engine
import rooms

# keep this check's rooms away from the app's rooms
rooms.SNAP_DIR = Path(tempfile.mkdtemp(prefix="rw_check_"))

D = engine.load_data()
PROBLEMS = []


def check(ok, message):
    if not ok:
        PROBLEMS.append(message)
    return ok


def name(item_ids):
    return ", ".join(engine.item_names(item_ids, D))


# ---------------------------------------------------------------------------
# Backpacks
# ---------------------------------------------------------------------------

def random_pack(rng, params):
    """Random order, sometimes several copies, until nothing else fits."""
    ids = list(D["items"])
    rng.shuffle(ids)
    inv = {}
    for i in ids:
        q = rng.choice([1, 1, 1, 2, 3]) if D["items"][i]["category"] in ("food", "water") else 1
        inv[i] = q
        while inv[i] > 0 and not engine.is_feasible(inv, D, params):
            inv[i] -= 1
        if inv[i] == 0:
            inv.pop(i)
    return inv


def load_packs(path):
    df = pd.read_csv(path)
    packs = {}
    for r in df.itertuples():
        if r.item not in D["items"]:
            print(f"  ! unknown item id '{r.item}' for group {r.group}, ignored")
            continue
        packs.setdefault(str(int(r.group)), {})[r.item] = int(r.qty)
    return packs


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def show_day(room, quiet):
    if quiet:
        return
    day = room["day"]
    ev = D["events"][room["event_log"][-1]]
    head = f"Day {day}: {ev['name']}  (unprotected HP {ev['base_hp']:+d}"
    prot = engine.protection_text(ev, D)
    head += f"; protected by {prot}" if prot else "; no protection"
    head += ")"
    if day in room["resupply_days"]:
        head += "   [RESUPPLY DAY]"
    print("\n" + head)
    for g in sorted(room["groups"].values(), key=lambda x: int(x["group"])):
        h = g["state"]["history"][-1]
        if h["day"] != day:
            continue
        print(f"  G{g['group']:>2} {D['locations'][g['location']]['name'][:13]:13s}"
              f" {D['traits'][g['trait']]['name'][:17]:17s} dHP {h['dhp']:+d}  HP {h['hp']:3}"
              f"  water {h['water']:5.1f}  food {h['food']:6}  {h['notes']}")


# ---------------------------------------------------------------------------
# Invariant checks
# ---------------------------------------------------------------------------

def check_setup(room, n_groups):
    locs = Counter(g["location"] for g in room["groups"].values())
    max_use = math.ceil(n_groups / len(D["locations"]))
    check(all(g["location"] for g in room["groups"].values()), "a group has no location")
    check(max(locs.values()) <= max_use, f"a location was used more than {max_use} times: {dict(locs)}")
    traits = Counter(g["trait"] for g in room["groups"].values())
    if n_groups <= len(D["traits"]):
        check(max(traits.values()) == 1, f"trait cards repeated with only {n_groups} groups: {dict(traits)}")
    for g in room["groups"].values():
        inv = g["submitted"] or {}
        check(engine.is_feasible(inv, D, room["params"]), f"group {g['group']} has an over-limit backpack")


def check_run(room):
    p = room["params"]
    for g in room["groups"].values():
        s, gid = g["state"], g["group"]
        hist = s["history"]
        # HP bookkeeping: every day's HP is yesterday's HP plus that day's change
        for a, b in zip(hist, hist[1:]):
            check(b["hp"] == a["hp"] + b["dhp"], f"group {gid} day {b['day']}: HP does not add up")
            check(b["water"] >= 0 and b["food"] >= 0, f"group {gid} day {b['day']}: negative water or food")
            check(b["event"] == room["event_log"][b["day"] - 1],
                  f"group {gid} day {b['day']}: different event from the rest of the class")
        # nothing happens after elimination
        if not s["alive"]:
            check(hist[-1]["day"] == s["death_day"], f"group {gid} was updated after elimination")
            cause = s["death_cause"]
            if cause == "HP reached 0":
                check(hist[-1]["hp"] <= 0, f"group {gid} eliminated for HP but HP > 0")
            if cause == "dehydration":
                dry = [h["water"] <= 0 for h in hist[1:]][-p["dehydration_days_max"]:]
                check(all(dry), f"group {gid} eliminated for dehydration without {p['dehydration_days_max']} dry days")
        else:
            check(hist[-1]["hp"] > 0, f"group {gid} is alive with HP <= 0")
            check(len(hist) - 1 == room["day"], f"group {gid} missed a day")
            # final score follows the rule in parameters.json
            fs = engine.final_score(s, p)
            wd = int(s["water"] // p["baseline_water_L_per_day"])
            fd = int(s["food"] // p["baseline_food_kcal_per_day"])
            bonus = min(wd, fd, p["endgame_reserve_cap"])
            check(fs["hp_final"] == s["hp"] + bonus, f"group {gid}: final score does not follow the rule")
            check(bonus <= p["endgame_reserve_cap"], f"group {gid}: bonus above the cap")
        # resupply is noted on exactly the resupply days the group lived through
        noted = {h["day"] for h in hist[1:] if "resupply" in h["notes"]}
        lived = {h["day"] for h in hist[1:]}
        check(noted == set(room["resupply_days"]) & lived, f"group {gid}: resupply days do not match")


def check_selection_rules(store, params):
    """The timer rules, on a small separate room."""
    code = store.create("0000", 3, params)
    store.join(code, 1)
    store.join(code, 2)
    store.draw_locations(code)
    store.start_selection(code, 10)
    heavy = {"water_5L": 5}
    ok, _ = store.submit(code, "1", heavy)
    check(not ok, "an over-limit backpack was accepted")
    store.save_draft(code, "2", {"tent": 1})
    store.save_draft(code, "2", {"tent": 1, "water_5L": 5})   # over the limit, not kept as valid
    store.close_selection(code)
    r = store.get(code)
    check(r["groups"]["2"]["submitted"] == {"tent": 1}, "time-up did not submit the last valid backpack")
    check(r["groups"]["1"]["submitted"] == {}, "a group with no valid draft did not get an empty backpack")
    ok, _ = store.join(code, 3)
    check(not ok, "a group could join after the game started")
    store.delete(code)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Offline check of a full Running Wild session")
    ap.add_argument("--groups", type=int, default=15)
    ap.add_argument("--days", type=int, default=D["params"]["default_days"])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--resupply", choices=["random", "fixed", "off"], default=D["params"]["resupply_mode"])
    ap.add_argument("--every", type=int, default=D["params"]["resupply_every"])
    ap.add_argument("--packs", help="CSV with columns group,item,qty")
    ap.add_argument("--out", default="check_output", help="folder for the CSV logs")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    random.seed(a.seed)
    params = dict(D["params"], resupply_mode=a.resupply, resupply_every=a.every)
    store = rooms.RoomStore(D)

    print("Rule examples from the slides and cards ...", end=" ")
    try:
        import tests.test_rules as tr
        tr.test_cases()
        tr.test_water_gain_by_location()
        tr.test_cooking_needs()
        print(f"{len(tr.CASES)} cases pass")
    except AssertionError as e:
        PROBLEMS.append("rule examples failed:\n" + str(e))
        print("FAILED")

    check_selection_rules(store, params)

    # ---- a full session
    code = store.create("1234", a.days, params)
    for g in range(1, a.groups + 1):
        store.join(code, g)
    store.draw_locations(code)
    store.start_selection(code, 30)
    rng = random.Random(a.seed)
    own = load_packs(a.packs) if a.packs else {}
    for g in range(1, a.groups + 1):
        gid = str(g)
        inv = own.get(gid) or random_pack(rng, params)
        ok, msg = store.submit(code, gid, inv)
        if not ok:
            print(f"  ! group {gid}: {msg} It gets an empty backpack.")
    store.close_selection(code)
    store.draw_traits(code)
    room = store.get(code)
    check_setup(room, a.groups)

    if not a.quiet:
        print(f"\nRoom {code}: {a.groups} groups, {a.days} days, resupply {a.resupply}"
              f" on days {room['resupply_days'] or 'none'}")
        for g in sorted(room["groups"].values(), key=lambda x: int(x["group"])):
            t = engine.pack_totals(g["submitted"], D)
            print(f"  G{g['group']:>2} {D['locations'][g['location']]['name']:13s} "
                  f"{D['traits'][g['trait']]['name']:18s} {t['weight']:5.2f} kg {t['volume']:5.1f} L  "
                  f"start HP {g['state']['hp']}, water {g['state']['water']} L, food {g['state']['food']} kcal")

    while room["phase"] != "finished":
        store.next_day(code)
        room = store.get(code)
        show_day(room, a.quiet)
    check_run(room)

    # ---- results
    rows = []
    for g in room["groups"].values():
        s = g["state"]
        fs = engine.final_score(s, room["params"])
        rows.append({"group": int(g["group"]), "location": D["locations"][g["location"]]["name"],
                     "trait": D["traits"][g["trait"]]["name"], "alive": s["alive"],
                     "out_on_day": s["death_day"], "cause": s["death_cause"], "hp_end": s["hp"],
                     "water": s["water"], "food": s["food"],
                     "final_hp": fs["hp_final"] if fs else None})
    res = pd.DataFrame(rows).sort_values(["alive", "final_hp", "out_on_day"], ascending=[False, False, False])
    print("\nFinal results")
    print(res.to_string(index=False))

    out = Path(a.out)
    out.mkdir(exist_ok=True)
    res.to_csv(out / "results.csv", index=False)
    log = []
    for g in room["groups"].values():
        for h in g["state"]["history"]:
            log.append({"group": int(g["group"]), "location": g["location"], "trait": g["trait"],
                        **h, "event_name": D["events"][h["event"]]["name"] if h["event"] in D["events"] else h["event"]})
    pd.DataFrame(log).sort_values(["day", "group"]).to_csv(out / "day_by_day.csv", index=False)
    packs = [{"group": int(g["group"]), "item": i, "name": D["items"][i]["name"], "qty": q}
             for g in room["groups"].values() for i, q in (g["submitted"] or {}).items()]
    pd.DataFrame(packs).sort_values(["group", "item"]).to_csv(out / "backpacks.csv", index=False)
    print(f"\nLogs saved in {out.resolve()}: results.csv, day_by_day.csv, backpacks.csv")

    shutil.rmtree(rooms.SNAP_DIR, ignore_errors=True)
    print("\n" + ("ALL CHECKS PASSED" if not PROBLEMS else f"{len(PROBLEMS)} PROBLEM(S):"))
    for p_ in PROBLEMS:
        print("  - " + p_)


if __name__ == "__main__":
    main()
