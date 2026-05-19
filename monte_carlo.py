"""
monte_carlo.py — Run 1000 simulations per strategy, compare outcomes.

Strategies:
  1. Random feasible backpack
  2. Stockpile heavy (max food + water)
  3. Greedy balanced (survival core + best mitigation items)
  4. MILP optimal (PuLP solver, single-period expected-loss + survival constraints)

Usage:
    cd survival_game/
    python3 monte_carlo.py
"""

import random
import statistics
import time
from gamedata import load_all, mitigates, inventory_summary, coverage_report, GameData
from simulator import simulate_game

# ============================================================================
# STRATEGIES
# ============================================================================

def random_feasible(data: GameData, rng: random.Random) -> set:
    """Randomly pick items until weight/volume caps are reached."""
    items = list(data.items.keys())
    rng.shuffle(items)
    inv = set()
    w, v = 0.0, 0.0
    p = data.parameters
    for i in items:
        it = data.items[i]
        if w + it.weight_kg <= p["weight_cap_kg"] and v + it.volume_L <= p["volume_cap_L"]:
            inv.add(i)
            w += it.weight_kg
            v += it.volume_L
    return inv


def stockpile_heavy(data: GameData) -> set:
    """Maximise carried kcal and litres, fill remainder with lightest items."""
    inv = set()
    w, v = 0.0, 0.0
    p = data.parameters

    # food items by kcal/kg descending
    food = [(k, it) for k, it in data.items.items() if it.kcal > 0]
    food.sort(key=lambda x: -x[1].kcal / max(x[1].weight_kg, 0.01))
    for k, it in food:
        if k not in inv and w + it.weight_kg <= p["weight_cap_kg"] and v + it.volume_L <= p["volume_cap_L"]:
            inv.add(k); w += it.weight_kg; v += it.volume_L

    # water items by litres/kg descending
    water = [(k, it) for k, it in data.items.items() if it.litres > 0]
    water.sort(key=lambda x: -x[1].litres / max(x[1].weight_kg, 0.01))
    for k, it in water:
        if k not in inv and w + it.weight_kg <= p["weight_cap_kg"] and v + it.volume_L <= p["volume_cap_L"]:
            inv.add(k); w += it.weight_kg; v += it.volume_L

    # add filter_bottle for water collection
    if "filter_bottle" not in inv:
        it = data.items["filter_bottle"]
        if w + it.weight_kg <= p["weight_cap_kg"] and v + it.volume_L <= p["volume_cap_L"]:
            inv.add("filter_bottle"); w += it.weight_kg; v += it.volume_L

    # fill remainder by weight ascending
    rest = [(k, it) for k, it in data.items.items() if k not in inv]
    rest.sort(key=lambda x: x[1].weight_kg)
    for k, it in rest:
        if w + it.weight_kg <= p["weight_cap_kg"] and v + it.volume_L <= p["volume_cap_L"]:
            inv.add(k); w += it.weight_kg; v += it.volume_L
    return inv


def greedy_balanced(data: GameData) -> set:
    """Ensure survival with food/water core, then maximise mitigation coverage."""
    inv = set()
    w, v = 0.0, 0.0
    p = data.parameters

    # survival core: food items + water + filter
    survival = [
        "dry_food", "energy_bars", "peanut_butter", "protein_biscuits",
        "dried_fruit_nuts", "chocolate_bars", "hard_crackers", "instant_noodles",
        "water_5L", "water_2L", "filter_bottle", "water_purif_tabs",
    ]
    for k in survival:
        if k in data.items:
            it = data.items[k]
            if w + it.weight_kg <= p["weight_cap_kg"] and v + it.volume_L <= p["volume_cap_L"]:
                inv.add(k); w += it.weight_kg; v += it.volume_L

    # compute expected HP saved per kg for each mitigation item
    def hp_saved_per_kg(item_id):
        it = data.items[item_id]
        saved = 0
        for ev in data.events.values():
            if item_id in ev.mit_set:
                unmit_hp = ev.base_hp  # negative = damage
                mit_hp = ev.mit_hp
                saved += ev.raw_prob * (mit_hp - unmit_hp)  # positive = improvement
        return saved / max(it.weight_kg, 0.01)

    candidates = [(k, it) for k, it in data.items.items()
                   if k not in inv and it.kcal == 0 and it.litres == 0]
    scored = [(k, it, hp_saved_per_kg(k)) for k, it in candidates]
    scored.sort(key=lambda x: -x[2])

    for k, it, _ in scored:
        if w + it.weight_kg <= p["weight_cap_kg"] and v + it.volume_L <= p["volume_cap_L"]:
            inv.add(k); w += it.weight_kg; v += it.volume_L
    return inv


def milp_optimal(data: GameData, location_id: str = None) -> set:
    """
    Solve the single-period expected-HP-loss MILP with PuLP.
    Includes survival constraints for minimum food and water.
    """
    try:
        import pulp
    except ImportError:
        print("PuLP not available, falling back to greedy_balanced")
        return greedy_balanced(data)

    p = data.parameters
    loc = data.locations.get(location_id) if location_id else None
    T = p["horizon_days"]
    rest_days = len(p["calendar"]["rest_days"])
    consuming_days = T - rest_days

    items = list(data.items.values())
    events = list(data.events.values())

    prob = pulp.LpProblem("survival_knapsack", pulp.LpMaximize)

    # decision variables
    x = {it.id: pulp.LpVariable(f"x_{it.id}", cat="Binary") for it in items}
    y = {ev.id: pulp.LpVariable(f"y_{ev.id}", cat="Binary") for ev in events}
    ovw = pulp.LpVariable("overweight", lowBound=0)

    # objective: maximise expected HP over horizon
    # = T * Σ_e p_e * [y_e * mit_hp + (1-y_e) * (base_hp + loc_mod)]
    #   - T * α * overweight
    #   + food_bonus + water_bonus (approx)
    obj_terms = []
    for ev in events:
        loc_mod = 0
        if loc:
            loc_mod = loc.hp_modifiers.get(ev.category, 0)

        # for bonus_morale requirement events, invert
        if ev.category == "bonus_morale" and ev.mit_logic != "NONE":
            good_hp = ev.base_hp
            bad_hp = ev.mit_hp
        else:
            good_hp = ev.mit_hp
            bad_hp = ev.base_hp + loc_mod

        # expected HP contribution = p * [y * good + (1-y) * bad]
        #                          = p * [bad + y * (good - bad)]
        obj_terms.append(T * ev.raw_prob * bad_hp)
        obj_terms.append(T * ev.raw_prob * (good_hp - bad_hp) * y[ev.id])

    # carrying penalty
    obj_terms.append(-T * p["carrying_penalty_hp_per_kg_per_day"] * ovw)

    # approximate food/water bonus in objective
    # food bonus: min(cap, kcal_carried / rate)
    # linearise crudely: add λ * kcal_carried
    lam_food = 0.5 * p["endgame_food_hp_cap"] / max(1, 20000)  # rough scaling
    lam_water = 0.5 * p["endgame_water_hp_cap"] / max(1, 10)
    for it in items:
        if it.kcal > 0:
            obj_terms.append(lam_food * it.kcal * x[it.id])
        if it.litres > 0:
            obj_terms.append(lam_water * it.litres * x[it.id])

    prob += pulp.lpSum(obj_terms)

    # constraints
    prob += pulp.lpSum(it.weight_kg * x[it.id] for it in items) <= p["weight_cap_kg"], "weight"
    prob += pulp.lpSum(it.volume_L * x[it.id] for it in items) <= p["volume_cap_L"], "volume"
    prob += ovw >= pulp.lpSum(it.weight_kg * x[it.id] for it in items) - p["carrying_threshold_kg"], "ovw_link"

    # survival: minimum food
    min_food = consuming_days * p["baseline_food_kcal_per_day"] - p["food_initial_kcal"]
    # subtract expected fortune food gains (~3000 kcal across 5 fortune days)
    min_food -= 3000
    min_food = max(0, min_food)
    prob += pulp.lpSum(it.kcal * x[it.id] for it in items) >= min_food, "min_food"

    # survival: minimum water
    min_water = consuming_days * p["baseline_water_L_per_day"] - p["water_initial_L"]
    min_water -= 3.0  # fortune + water_collection expected gains
    min_water = max(0, min_water)
    prob += pulp.lpSum(it.litres * x[it.id] for it in items) >= min_water, "min_water"

    # mitigation linking
    for ev in events:
        if ev.mit_logic == "NONE":
            prob += y[ev.id] == 0
        elif ev.mit_logic == "ANY":
            relevant = [x[j] for j in ev.mit_set if j in x]
            if relevant:
                prob += y[ev.id] <= pulp.lpSum(relevant)
            else:
                prob += y[ev.id] == 0
        elif ev.mit_logic == "ALL":
            for j in ev.mit_set:
                if j in x:
                    prob += y[ev.id] <= x[j]

    # solve
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if prob.status != 1:
        print(f"MILP status: {pulp.LpStatus[prob.status]}, falling back to greedy")
        return greedy_balanced(data)

    inv = {it.id for it in items if x[it.id].varValue and x[it.id].varValue > 0.5}
    return inv


# ============================================================================
# MONTE CARLO RUNNER
# ============================================================================

def run_mc(name, inv, data, n=1000, randomise_inv=False):
    """Run n simulations with given inventory. Returns list of SimResults."""
    results = []
    loc_ids = list(data.locations.keys())
    trait_ids = list(data.traits.keys())

    for i in range(n):
        seed = i * 7 + 13

        if randomise_inv:
            rng_inv = random.Random(seed * 3 + 42)
            inv_i = random_feasible(data, rng_inv)
        else:
            inv_i = inv

        # random location and trait per sim
        loc_id = loc_ids[seed % len(loc_ids)]
        tr_id = trait_ids[(seed // 10) % len(trait_ids)]

        r = simulate_game(inv_i, loc_id, tr_id, seed, data)
        results.append(r)
    return results


def print_summary(name, results):
    alive = [r for r in results if r.alive]
    dead = [r for r in results if not r.alive]
    n = len(results)
    sr = len(alive) / n

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    print(f"  Survival rate : {sr:.1%}  ({len(alive)}/{n})")

    if alive:
        hps = sorted([r.final_hp for r in alive])
        print(f"  Final HP (survivors):")
        print(f"    median = {statistics.median(hps):.1f}")
        print(f"    mean   = {statistics.mean(hps):.1f}")
        print(f"    Q25    = {hps[len(hps)//4]:.1f}")
        print(f"    Q75    = {hps[3*len(hps)//4]:.1f}")
        print(f"    min    = {hps[0]:.1f}")
        print(f"    max    = {hps[-1]:.1f}")

    if dead:
        days = [r.death_day for r in dead]
        causes = {}
        for r in dead:
            causes[r.death_cause] = causes.get(r.death_cause, 0) + 1
        print(f"  Death stats:")
        print(f"    avg death day = {statistics.mean(days):.1f}")
        print(f"    causes: {causes}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    data = load_all(".")
    p = data.parameters
    N = 1000

    print("Building strategies...")
    t0 = time.time()

    inv_stockpile = stockpile_heavy(data)
    inv_balanced = greedy_balanced(data)
    inv_milp = milp_optimal(data)

    # print strategy summaries
    for name, inv in [("Stockpile", inv_stockpile),
                      ("Balanced", inv_balanced),
                      ("MILP", inv_milp)]:
        s = inventory_summary(inv, data.items)
        cr = coverage_report(inv, data)
        print(f"\n  [{name}]")
        print(f"    items={s['n_items']}  weight={s['weight_kg']}kg  vol={s['volume_L']}L")
        print(f"    food={s['kcal']}kcal  water={s['litres']}L")
        print(f"    events mitigated={cr['events_mitigated']}/{cr['events_total']}")
        print(f"    exp 50-day HP delta (events only)={cr['expected_50day_hp_delta']}")

    print(f"\nStrategy build time: {time.time()-t0:.1f}s")
    print(f"\nRunning Monte Carlo ({N} sims per strategy)...")
    t0 = time.time()

    res_random = run_mc("Random", None, data, N, randomise_inv=True)
    res_stock = run_mc("Stockpile", inv_stockpile, data, N)
    res_balanced = run_mc("Balanced", inv_balanced, data, N)
    res_milp = run_mc("MILP", inv_milp, data, N)

    print(f"Simulation time: {time.time()-t0:.1f}s")

    print_summary("Random feasible backpack", res_random)
    print_summary("Stockpile heavy", res_stock)
    print_summary("Greedy balanced", res_balanced)
    print_summary("MILP optimal (single-period)", res_milp)

    # calibration target check
    print(f"\n{'='*60}")
    print(f"  CALIBRATION TARGET CHECK")
    print(f"{'='*60}")
    targets = {
        "Random":    (0.20, 0.35),
        "Stockpile": (0.25, 0.40),
        "Balanced":  (0.75, 0.90),
        "MILP":      (0.90, 0.99),
    }
    actuals = {
        "Random":    len([r for r in res_random if r.alive]) / N,
        "Stockpile": len([r for r in res_stock if r.alive]) / N,
        "Balanced":  len([r for r in res_balanced if r.alive]) / N,
        "MILP":      len([r for r in res_milp if r.alive]) / N,
    }
    for strat, (lo, hi) in targets.items():
        act = actuals[strat]
        ok = "OK" if lo <= act <= hi else "MISS"
        print(f"  {strat:12s}: target [{lo:.0%}-{hi:.0%}], actual {act:.1%}  [{ok}]")


if __name__ == "__main__":
    main()