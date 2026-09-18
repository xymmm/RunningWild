"""
engine.py — rules of the Running Wild classroom game.

Everything that decides an outcome lives here, so the same code drives the
Streamlit app, any Monte Carlo study, and the teaching note.

Data files (folder `data/`) are the single source of truth:
    items.csv        id, name, weight_kg, volume_L, category, kcal, litres, ...
    events.csv       id, name, category, tags, base_hp, mitigation, need_water, mit_hp,
                     weight, water_change, food_change, extra_water, extra_food,
                     boost_item, boost_mult
                     `mitigation` lists alternatives separated by "|"; items inside one
                     alternative are joined by "+" and must all be carried.
                     `need_water` is the water (L) the group must have on hand.
    locations.json   location cards: card text + machine-readable rules
    traits.json      trait cards: card text (rules are coded in `_apply_trait`)
    parameters.json  initial HP / water / food, capacities, daily consumption ...

Conventions (documented for the teaching note):
  C1  One event per day, drawn with probability proportional to `weight`,
      and the same event applies to every group.
  C2  An event is mitigated when at least one alternative in `mitigation` is
      fully carried and the group holds at least `need_water` litres at the
      start of the day.  Damage events (base_hp <= 0): if mitigated the HP
      change is mit_hp, otherwise base_hp.  Bonus events (base_hp > 0): the
      bonus needs the listed items, if any, otherwise it is 0.
  C3  Location and trait HP modifiers act only on unmitigated damage events,
      unless a rule is marked "always".  Within one card, when several rules
      match the same event, only the largest one in absolute value applies.
  C4  A modifier never turns a damage event into a gain: final HP change <= 0.
  C5  Water/food gains always happen; water/food losses happen only if the
      event is not mitigated.
  C6  Daily order: event HP -> event resources -> drink and eat -> daily trait
      effects -> elimination check.
  C7  Holding several copies of an item never mitigates more than one copy;
      copies only add weight, volume, water and food.
  C8  Food items with a `needs` entry (e.g. rice, noodles) give no kcal unless
      the listed cooking items are also packed.
  C9  On a resupply day every surviving group receives the resupply water and
      food before the day's event.  A zero-tag location or trait rule (e.g.
      Old Trail for calm wildlife) sets the event's HP change to 0 whatever
      its sign.
"""

import json
import math
import random
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_data(data_dir=DATA_DIR):
    d = Path(data_dir)
    items = pd.read_csv(d / "items.csv").fillna({"needs": ""})
    events = pd.read_csv(d / "events.csv").fillna({"mitigation": "", "tags": "", "boost_item": ""})
    ev_list = []
    for r in events.to_dict("records"):
        r["alts"] = [[x for x in a.split("+") if x] for a in str(r["mitigation"]).split("|") if a]
        r["tags"] = [s for s in str(r["tags"]).split("|") if s]
        ev_list.append(r)
    return {
        "items": {r["id"]: r for r in items.to_dict("records")},
        "items_df": items,
        "events": {e["id"]: e for e in ev_list},
        "locations": json.load(open(d / "locations.json")),
        "traits": json.load(open(d / "traits.json")),
        "params": json.load(open(d / "parameters.json")),
    }


# ---------------------------------------------------------------------------
# Draws
# ---------------------------------------------------------------------------

def draw_cards(group_ids, deck, rng):
    """Equal-probability draws without repetition. When there are more groups
    than cards, a fresh shuffled deck is started, so each card is used at most
    ceil(groups / cards) times."""
    out, pile = {}, []
    for g in group_ids:
        if not pile:
            pile = list(deck)
            rng.shuffle(pile)
        out[g] = pile.pop()
    return out


def resupply_days(params, seed, days):
    """Days on which every group receives water and food.
    fixed : every `resupply_every` days (not on the last day)
    random: `resupply_count` distinct days between day 3 and the second-last day,
            unannounced to students
    off   : none"""
    mode = params.get("resupply_mode", "off")
    if mode == "fixed":
        k = max(1, int(params["resupply_every"]))
        return list(range(k, days, k))
    if mode == "random":
        pool = list(range(3, days))
        rng = random.Random(f"{seed}-resupply")
        n = min(int(params["resupply_count"]), len(pool))
        return sorted(rng.sample(pool, n))
    return []


def draw_event(data, seed, day):
    rng = random.Random(f"{seed}-day-{day}")
    ids = list(data["events"])
    weights = [data["events"][i]["weight"] for i in ids]
    return rng.choices(ids, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Inventory helpers
# ---------------------------------------------------------------------------

def has(inv, *item_ids):
    return all(inv.get(i, 0) > 0 for i in item_ids)


def has_any(inv, item_ids):
    return any(inv.get(i, 0) > 0 for i in item_ids)


def pack_totals(inv, data):
    it = data["items"]
    t = {"weight": 0.0, "volume": 0.0, "kcal": 0, "litres": 0.0}
    for i, q in inv.items():
        if q > 0 and i in it:
            t["weight"] += it[i]["weight_kg"] * q
            t["volume"] += it[i]["volume_L"] * q
            needs = [x for x in str(it[i]["needs"]).split("+") if x]
            if has(inv, *needs):
                t["kcal"] += int(it[i]["kcal"]) * q
            t["litres"] += float(it[i]["litres"]) * q
    t["weight"] = round(t["weight"], 2)
    t["volume"] = round(t["volume"], 2)
    t["litres"] = round(t["litres"], 2)
    return t


def is_feasible(inv, data, params):
    t = pack_totals(inv, data)
    return t["weight"] <= params["weight_cap_kg"] + 1e-9 and t["volume"] <= params["volume_cap_L"] + 1e-9


def mitigating_alt(inv, ev):
    """First alternative fully carried, or None."""
    for alt in ev["alts"]:
        if has(inv, *alt):
            return alt
    return None


def mitigated(inv, ev, water=None):
    if not ev["alts"] and ev["need_water"] <= 0:
        return False
    if ev["alts"] and mitigating_alt(inv, ev) is None:
        return False
    if ev["need_water"] > 0 and (water is None or water < ev["need_water"] - 1e-9):
        return False
    return True


def protection_text(ev, data):
    """Human-readable mitigation rule, e.g. 'Tent + Sleeping bag or Four-season tent; 1 L water on hand'."""
    parts = []
    if ev["alts"]:
        parts.append(" or ".join(" + ".join(item_names(a, data)) for a in ev["alts"]))
    if ev["need_water"] > 0:
        parts.append(f"{ev['need_water']:g} L water on hand")
    return "; ".join(parts)


def item_names(ids, data):
    return [data["items"][i]["name"] if i in data["items"] else i for i in ids]


# ---------------------------------------------------------------------------
# Team initialisation
# ---------------------------------------------------------------------------

def init_team_state(inv, location_id, trait_id, data, params):
    t = pack_totals(inv, data)
    hp = params["hp_initial"]
    food = params["food_initial_kcal"] + t["kcal"]
    notes = []
    if trait_id == "injured_at_start":
        hp -= 3
        notes.append("Injured at Start: HP -3")
    if trait_id == "lucky_ration":
        food += 600
        notes.append("Lucky Ration: +600 kcal")
    return {
        "hp": hp,
        "water": round(params["water_initial_L"] + t["litres"], 2),
        "food": food,
        "carried_litres": t["litres"],
        "pack_weight": t["weight"],
        "dry_days": 0,
        "hungry_days": 0,
        "alive": True,
        "death_day": None,
        "death_cause": None,
        "oneshots": [],
        "history": [{"day": 0, "hp": hp, "water": round(params["water_initial_L"] + t["litres"], 2),
                     "food": food, "event": "start", "dhp": 0, "notes": "; ".join(notes)}],
    }


# ---------------------------------------------------------------------------
# Daily resolution
# ---------------------------------------------------------------------------

def _location_hp(ev, inv, is_mit, hp, loc, notes):
    """Apply location card to a damage event (base_hp <= 0)."""
    for t in loc.get("zero_tags", []):
        if t in ev["tags"] and hp != 0:
            notes.append(f"{loc['name']}: becomes 0")
            return 0
    if ev["base_hp"] > 0:
        return hp
    best = None
    for rule in loc.get("hp_rules", []):
        if rule["tag"] not in ev["tags"]:
            continue
        if is_mit and not rule.get("always", False):
            continue
        if has_any(inv, rule.get("unless_items", [])):
            continue
        if best is None or abs(rule["delta"]) > abs(best["delta"]):
            best = rule
    if best:
        hp += best["delta"]
        notes.append(f"{loc['name']}: {best['delta']:+d}")
    return hp


def _oneshot(state, key):
    if key in state["oneshots"]:
        return False
    state["oneshots"].append(key)
    return True


def _apply_trait(trait_id, ev, inv, is_mit, hp, state, notes):
    tags, eid = ev["tags"], ev["id"]
    damage = ev["base_hp"] <= 0

    def add(delta, label):
        nonlocal hp
        hp += delta
        notes.append(f"{label}: {delta:+d}")

    if trait_id == "cold_sensitive" and damage and not is_mit and "cold" in tags and not has(inv, "down_jacket"):
        add(-1, "Cold Sensitive")
    elif trait_id == "heat_resistant" and damage and not is_mit and "sun" in tags and hp < 0:
        add(+1, "Heat Resistant")
    elif trait_id == "climber" and damage and not is_mit and "slip_fall" in tags and hp < 0:
        add(+1, "Climber")
    elif trait_id == "allergy_prone" and damage and not is_mit and "sting" in tags and not has(inv, "allergy_meds"):
        add(-1, "Allergy Prone")
    elif trait_id == "old_batteries" and eid == "headlamp_dead" and not has(inv, "spare_batteries") \
            and _oneshot(state, "old_batteries"):
        add(-1, "Old Batteries")
    elif trait_id == "hot_drink_lover" and "hot_drink" in tags and hp > 0 and has(inv, "stove_fuel", "cooking_pot"):
        add(+1, "Hot Drink Lover")
    elif trait_id == "clean_freak" and "scavenged" in tags and not has(inv, "disinfectant") \
            and _oneshot(state, "clean_freak"):
        add(-1, "Clean Freak")
    elif trait_id == "fragile_shoelaces" and eid == "boot_lace_snap" and not has(inv, "duct_tape") \
            and _oneshot(state, "fragile_shoelaces"):
        add(-1, "Fragile Shoelaces")
    elif trait_id == "repair_expert" and damage and not is_mit and "equipment" in tags and hp < 0 \
            and has(inv, "tent_repair_kit"):
        add(+1, "Repair Expert")
    elif trait_id == "animal_friend" and "wildlife_calm" in tags and hp != 0:
        notes.append("Animal Friend: becomes 0")
        hp = 0
    elif trait_id == "night_walker" and damage and not is_mit and "night_nav" in tags and hp < 0 \
            and has(inv, "headlamp"):
        add(+1, "Night Walker")
    elif trait_id == "coffee_bonus" and "fatigue" in tags and hp < 0 and has(inv, "coffee_press", "stove_fuel") \
            and _oneshot(state, "coffee_bonus"):
        notes.append("Coffee Bonus: becomes 0")
        hp = 0
    elif trait_id == "picky_eater" and "raw_food" in tags and not has(inv, "stove_fuel"):
        add(-1, "Picky Eater")
    elif trait_id == "backup_hammock" and damage and not is_mit and "rain_night" in tags and hp < 0 \
            and not has_any(inv, ["tent", "rain_tarp"]):
        add(+1, "Backup Hammock")
    elif trait_id == "old_rope" and "crossing" in tags and not has_any(inv, ["rope_tool_kit", "climbing_rope"]) \
            and _oneshot(state, "old_rope"):
        add(-1, "Old Rope")
    return hp


def resolve_day(team, event_id, day, data, params):
    """Apply one day to one team. `team` has keys inv, location, trait, state.
    Mutates team['state'] and returns the day's history record."""
    st = team["state"]
    if not st["alive"]:
        return None
    inv = team["inv"]
    ev = data["events"][event_id]
    loc = data["locations"][team["location"]]
    trait_id = team.get("trait")
    notes = []

    # ---- 0. Resupply (before the event)
    if day in team.get("resupply_days", []):
        st["water"] = round(st["water"] + params["resupply_water_L"], 2)
        st["food"] += params["resupply_food_kcal"]
        notes.append(f"resupply +{params['resupply_water_L']:g} L, +{params['resupply_food_kcal']} kcal")

    # ---- 1. HP from the event
    is_mit = mitigated(inv, ev, st["water"])
    alt = mitigating_alt(inv, ev)
    if ev["base_hp"] > 0:
        ok = (not ev["alts"] and ev["need_water"] <= 0) or is_mit
        hp = ev["base_hp"] if ok else 0
        if not ok:
            notes.append("bonus needs " + protection_text(ev, data))
    else:
        hp = ev["mit_hp"] if is_mit else ev["base_hp"]
        if is_mit:
            what = item_names(alt, data) if alt else []
            if ev["need_water"] > 0:
                what.append(f"{ev['need_water']:g} L water")
            notes.append("protected by " + " + ".join(what))
        elif ev["need_water"] > 0 and (not ev["alts"] or alt):
            notes.append(f"not enough water on hand (needs {ev['need_water']:g} L)")
    hp = _location_hp(ev, inv, is_mit, hp, loc, notes)
    if trait_id:
        hp = _apply_trait(trait_id, ev, inv, is_mit, hp, st, notes)
    if ev["base_hp"] <= 0:
        hp = min(hp, 0)

    # ---- 2. Water and food from the event
    wc, fc = float(ev["water_change"]), int(ev["food_change"])
    if wc > 0:
        if loc.get("water_gain_requires") and not has(inv, *loc["water_gain_requires"]):
            notes.append(f"{loc['name']}: no stove, no water")
            wc = 0.0
        elif loc.get("water_gain_mult"):
            wc *= loc["water_gain_mult"]
            step = loc.get("water_round_up_to")
            wc = math.ceil(wc / step - 1e-9) * step if step else round(wc, 1)
        if ev["boost_item"] and has(inv, ev["boost_item"]):
            wc = round(wc * ev["boost_mult"], 2)
            notes.append(f"{item_names([ev['boost_item']], data)[0]}: x{ev['boost_mult']:g}")
        st["water"] += wc
    elif wc < 0 and not is_mit:
        st["water"] += wc
        if trait_id == "leaky_backpack" and "water_loss" in ev["tags"] and not has(inv, "waterproof_bag"):
            st["water"] -= 1.0
            notes.append("Leaky Backpack: -1 L")
    if fc > 0:
        fc += loc.get("food_gain_bonus", 0)
        if ev["boost_item"] and has(inv, ev["boost_item"]):
            fc = int(fc * ev["boost_mult"])
            notes.append(f"{item_names([ev['boost_item']], data)[0]}: x{ev['boost_mult']:g}")
        st["food"] += fc
    elif fc < 0 and not is_mit:
        st["food"] += fc
    st["water"] = max(0.0, st["water"])
    st["food"] = max(0, st["food"])

    # ---- 3. Drink and eat
    need_w = params["baseline_water_L_per_day"] + float(ev["extra_water"])
    need_f = params["baseline_food_kcal_per_day"] + int(ev["extra_food"])
    drink = min(st["water"], need_w)
    eat = min(st["food"], need_f)
    st["water"] = round(st["water"] - drink, 2)
    st["food"] -= eat
    st["dry_days"] = st["dry_days"] + 1 if st["water"] <= 0 else 0
    st["hungry_days"] = st["hungry_days"] + 1 if eat < params["starvation_kcal_threshold"] else 0

    # ---- 4. Daily trait effects
    if trait_id == "light_pack_expert" and st["pack_weight"] <= 15:
        hp += 1
        notes.append("Light Pack Expert: +1")
    if trait_id == "water_hoarder" and params.get("water_hoarder_enabled", True) and st["carried_litres"] > 5:
        hp -= 1
        notes.append("Water Hoarder: -1")

    st["hp"] += hp

    # ---- 5. Elimination
    if st["hp"] <= 0:
        st["alive"], st["death_cause"] = False, "HP reached 0"
    elif st["dry_days"] >= params["dehydration_days_max"]:
        st["alive"], st["death_cause"] = False, "dehydration"
    elif st["hungry_days"] >= params["starvation_days_max"]:
        st["alive"], st["death_cause"] = False, "starvation"
    if not st["alive"]:
        st["death_day"] = day
        notes.append(f"ELIMINATED ({st['death_cause']})")

    rec = {"day": day, "hp": st["hp"], "water": st["water"], "food": st["food"],
           "event": event_id, "dhp": hp, "notes": "; ".join(notes)}
    st["history"].append(rec)
    return rec


# ---------------------------------------------------------------------------
# Final settlement
# ---------------------------------------------------------------------------

def final_score(state, params):
    if not state["alive"]:
        return None
    hw = int(state["water"] // params["endgame_water_L_per_hp"])
    hf = int(state["food"] // params["endgame_food_kcal_per_hp"])
    if params.get("endgame_water_hp_cap") is not None:
        hw = min(hw, int(params["endgame_water_hp_cap"]))
    if params.get("endgame_food_hp_cap") is not None:
        hf = min(hf, int(params["endgame_food_hp_cap"]))
    return {"hp_end": state["hp"], "hp_water": hw, "hp_food": hf, "hp_final": state["hp"] + hw + hf}
