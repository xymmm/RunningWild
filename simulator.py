"""
simulator.py — Core game simulation engine for the Survival Knapsack Game.

Runs a single game given (inventory, location, trait, seed) and returns
a SimResult with full trajectory data.
"""

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Set, List, Dict
from gamedata import load_all, mitigates, GameData, Event, Location, Trait


@dataclass
class SimResult:
    alive: bool = True
    death_day: Optional[int] = None
    death_cause: Optional[str] = None
    final_hp: float = 0
    hp_history: List[float] = field(default_factory=list)
    water_history: List[float] = field(default_factory=list)
    food_history: List[int] = field(default_factory=list)
    events_fired: List[List[str]] = field(default_factory=list)


def _compute_hp_delta(inv: Set[str], ev: Event,
                      loc: Optional[Location],
                      trait: Optional[Trait]) -> float:
    """
    Compute HP delta for a single event, handling:
      - standard mitigation (ANY/ALL/NONE)
      - bonus_morale requirement inversion
      - location per-category modifiers
      - trait per-category modifiers
    """
    is_mit = mitigates(inv, ev)

    # bonus_morale with requirement items: logic is inverted
    # having items = good outcome (base_hp), not having = mit_hp
    if ev.category == "bonus_morale" and ev.mit_logic != "NONE":
        return ev.base_hp if is_mit else ev.mit_hp

    # location set-to-zero overrides
    if loc and ev.category in getattr(loc, 'set_to_zero_categories', []):
        return 0

    # base
    hp = ev.mit_hp if is_mit else ev.base_hp

    # location additive (unmitigated only)
    if loc and not is_mit:
        hp += loc.hp_modifiers.get(ev.category, 0)

    # trait per-category modifier (unmitigated only)
    if trait and not is_mit:
        tmod = trait.raw.get("hp_modifiers", {})
        hp += tmod.get(ev.category, 0)

    return hp


def simulate_game(inv: Set[str], location_id: str, trait_id: str,
                  seed: int, data: GameData, horizon: int = 50) -> SimResult:
    """Run one complete game simulation."""
    from calendar_gen import generate_calendar

    rng = random.Random(seed)
    params = data.parameters
    loc = data.locations.get(location_id)
    trait = data.traits.get(trait_id)
    calendar = generate_calendar(seed, horizon)

    p = Path(__file__).parent
    scheduled = json.load(open(p / "scheduled_events.json"))

    # initial state
    hp = float(params["hp_initial"])
    water = float(params["water_initial_L"])
    food = int(params["food_initial_kcal"])

    # trait init adjustments
    if trait:
        hp += trait.raw.get("hp_init_delta", 0)
        food += trait.raw.get("food_init_delta", 0)

    # carrying weight and penalty
    total_weight = sum(data.items[i].weight_kg for i in inv if i in data.items)
    penalty_per_day = params["carrying_penalty_hp_per_kg_per_day"] * max(0, total_weight - params["carrying_threshold_kg"])

    # trait-based daily effects
    trait_daily_hp = 0
    if trait:
        raw = trait.raw
        # light pack expert
        if raw.get("condition") == "total_weight <= 15" and total_weight <= 15:
            trait_daily_hp += raw.get("daily_hp_delta", 0)
        # water hoarder — checked per-day based on current water
        # (handled in loop)

    c_water = 0
    c_food = 0
    result = SimResult()

    for day_idx in range(horizon):
        cal = calendar[day_idx]
        day = day_idx + 1
        daily_kcal_consumed = 0
        day_events = []

        # ---- REST DAY ----
        if cal["type"] == "rest":
            hp += 1
            day_events.append("rest_day")

        # ---- FORTUNE DAY ----
        elif cal["type"] == "fortune":
            evt_id = cal["scheduled"]
            fdata = scheduled["fortune_events"].get(evt_id, {})

            skip = fdata.get("skip_consumption", False)
            if not skip:
                water = max(0, water - params["baseline_water_L_per_day"])
                consumed = min(food, params["baseline_food_kcal_per_day"])
                food -= consumed
                daily_kcal_consumed += consumed

            hp += fdata.get("hp_delta", 0)

            # water gain with conditional check
            w_gain = fdata.get("water_gain_L", 0)
            if "requires_items_pool" in fdata:
                has_req = any(i in inv for i in fdata["requires_items_pool"])
                if not has_req:
                    w_gain = fdata.get("fallback_water_gain_L", 0)
            water += w_gain
            food += fdata.get("food_gain_kcal", 0)
            day_events.append(evt_id)

        # ---- NORMAL DAY (Scheme A) ----
        else:
            # baseline consumption
            water = max(0, water - params["baseline_water_L_per_day"])
            consumed = min(food, params["baseline_food_kcal_per_day"])
            food -= consumed
            daily_kcal_consumed += consumed

            # per-event Bernoulli draw
            for ev in data.events.values():
                if rng.random() < ev.raw_prob:
                    hp_delta = _compute_hp_delta(inv, ev, loc, trait)
                    hp += hp_delta

                    # water collection events give water regardless of mitigation
                    if ev.category == "water_collection":
                        w_mult = 1.0
                        if loc:
                            w_mult = loc.water_gain_mult.get("water_collection", 1.0)
                            if loc.requires_stove_for_water and "stove_fuel" not in inv:
                                w_mult = 0.0
                        water += params["water_gain_base_L"] * w_mult

                    day_events.append(ev.id)

        # carrying penalty (every day)
        hp -= penalty_per_day

        # trait daily effects
        hp += trait_daily_hp

        # water hoarder: HP -1/day if carrying >5L water AND trait is water_hoarder
        if trait and trait.raw.get("condition") == "water_carried > 5":
            # check initial carried water (items only, not current supply)
            carried_litres = sum(data.items[i].litres for i in inv if i in data.items)
            if carried_litres > 5:
                hp += trait.raw.get("daily_hp_delta", 0)

        # update counters
        if water <= 0:
            c_water += 1
            water = 0
        else:
            c_water = 0

        if cal["type"] != "rest" and daily_kcal_consumed < params["starvation_kcal_threshold"]:
            c_food += 1
        else:
            c_food = 0

        # record
        result.hp_history.append(round(hp, 2))
        result.water_history.append(round(water, 2))
        result.food_history.append(food)
        result.events_fired.append(day_events)

        # elimination
        if hp <= 0:
            result.alive = False
            result.death_day = day
            result.death_cause = "hp_zero"
            break
        if c_water >= params["dehydration_days_max"]:
            result.alive = False
            result.death_day = day
            result.death_cause = "dehydration"
            break
        if c_food >= params["starvation_days_max"]:
            result.alive = False
            result.death_day = day
            result.death_cause = "starvation"
            break

    # end-game scoring
    if result.alive:
        w_bonus = min(params["endgame_water_hp_cap"],
                      int(water / params["endgame_water_L_per_hp"]))
        f_bonus = min(params["endgame_food_hp_cap"],
                      int(food / params["endgame_food_kcal_per_hp"]))
        result.final_hp = round(hp + w_bonus + f_bonus, 2)
    else:
        result.final_hp = float("-inf")

    return result
