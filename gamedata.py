"""
gamedata.py

Loads the game data files into Python dataclasses and provides helper
functions for typical queries: mitigation check, location modifier
application, etc.

Usage:
    from gamedata import load_all, mitigates, effective_hp

    data = load_all()
    inv = {"sleeping_bag", "down_jacket", "compass_map"}
    event = data.events["cold_wave"]
    print(mitigates(inv, event))                                  # True/False
    print(effective_hp(inv, event, data.locations["glacier_ridge"]))  # int
"""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Item:
    id: str
    name: str
    weight_kg: float
    volume_L: float
    category: str
    kcal: int
    litres: float
    is_wearable: bool


@dataclass
class Event:
    id: str
    name: str
    category: str
    base_hp: int
    mit_logic: str           # "ANY", "ALL", or "NONE"
    mit_set: List[str]       # list of item ids
    mit_hp: int              # HP when fully mitigated
    raw_prob: float          # per-day Bernoulli probability


@dataclass
class Location:
    id: str
    display_name: str
    hp_modifiers: Dict[str, int] = field(default_factory=dict)
    water_gain_mult: Dict[str, float] = field(default_factory=dict)
    food_gain_bonus: int = 0
    requires_stove_for_water: bool = False
    water_purif_required: bool = False
    set_to_zero_categories: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Trait:
    id: str
    name: str
    raw: dict                # the original dict — trait mechanics vary widely


@dataclass
class GameData:
    items: Dict[str, Item]
    events: Dict[str, Event]
    locations: Dict[str, Location]
    traits: Dict[str, Trait]
    parameters: dict


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_items(path: Path) -> Dict[str, Item]:
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out[row["id"]] = Item(
                id=row["id"],
                name=row["name"],
                weight_kg=float(row["weight_kg"]),
                volume_L=float(row["volume_L"]),
                category=row["category"],
                kcal=int(row["kcal"]),
                litres=float(row["litres"]),
                is_wearable=row["is_wearable"].strip().lower() == "true",
            )
    return out


def _load_events(path: Path) -> Dict[str, Event]:
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            mset = row["mit_set"].split("|") if row["mit_set"] else []
            mset = [s for s in mset if s]
            out[row["id"]] = Event(
                id=row["id"],
                name=row["name"],
                category=row["category"],
                base_hp=int(row["base_hp"]),
                mit_logic=row["mit_logic"],
                mit_set=mset,
                mit_hp=int(row["mit_hp"]),
                raw_prob=float(row["raw_prob"]),
            )
    return out


def _load_locations(path: Path) -> Dict[str, Location]:
    raw = json.load(open(path))
    out = {}
    for lid, d in raw.items():
        out[lid] = Location(
            id=lid,
            display_name=d.get("display_name", lid),
            hp_modifiers=d.get("hp_modifiers", {}),
            water_gain_mult=d.get("water_gain_mult", {}),
            food_gain_bonus=d.get("food_gain_bonus", 0),
            requires_stove_for_water=d.get("requires_stove_for_water", False),
            water_purif_required=d.get("water_purif_required", False),
            set_to_zero_categories=d.get("set_to_zero_categories", []),
            notes=d.get("notes", ""),
        )
    return out


def _load_traits(path: Path) -> Dict[str, Trait]:
    raw = json.load(open(path))
    return {tid: Trait(id=tid, name=d["name"], raw=d) for tid, d in raw.items()}


def load_all(data_dir: str = ".") -> GameData:
    p = Path(data_dir)
    return GameData(
        items=_load_items(p / "items.csv"),
        events=_load_events(p / "events.csv"),
        locations=_load_locations(p / "locations.json"),
        traits=_load_traits(p / "traits.json"),
        parameters=json.load(open(p / "parameters.json")),
    )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def mitigates(inventory: Set[str], event: Event) -> bool:
    """Return True iff `inventory` satisfies the event's mitigation requirement."""
    if event.mit_logic == "NONE":
        return False
    if event.mit_logic == "ANY":
        return any(j in inventory for j in event.mit_set)
    if event.mit_logic == "ALL":
        return all(j in inventory for j in event.mit_set)
    raise ValueError(f"Unknown mit_logic: {event.mit_logic}")


def effective_hp(inventory: Set[str], event: Event,
                 location: Optional[Location] = None,
                 trait: Optional[Trait] = None) -> int:
    """
    Compute the HP delta for `event` given `inventory`, optionally accounting
    for location and trait modifiers. Returns the final integer HP delta.

    Location/trait additive modifiers apply only to un-mitigated events.
    Set-to-zero rules override everything.
    """
    is_mit = mitigates(inventory, event)

    # location set-to-zero overrides
    if location and event.category in location.set_to_zero_categories:
        return 0

    # base
    hp = event.mit_hp if is_mit else event.base_hp

    # location additive
    if location and not is_mit:
        hp += location.hp_modifiers.get(event.category, 0)

    # trait additive (simple per-category modifier; oneshots etc. need state)
    if trait and not is_mit:
        tmod = trait.raw.get("hp_modifiers", {})
        hp += tmod.get(event.category, 0)

    return hp


def inventory_summary(inventory: Set[str], items: Dict[str, Item]) -> dict:
    """Total weight, volume, kcal, litres carried."""
    chosen = [items[i] for i in inventory if i in items]
    return {
        "n_items": len(chosen),
        "weight_kg": round(sum(it.weight_kg for it in chosen), 2),
        "volume_L": round(sum(it.volume_L for it in chosen), 2),
        "kcal": sum(it.kcal for it in chosen),
        "litres": round(sum(it.litres for it in chosen), 2),
    }


def feasible(inventory: Set[str], data: GameData) -> tuple:
    """Check weight and volume caps. Returns (is_feasible, reason)."""
    s = inventory_summary(inventory, data.items)
    p = data.parameters
    if s["weight_kg"] > p["weight_cap_kg"]:
        return False, f"over weight cap ({s['weight_kg']} > {p['weight_cap_kg']})"
    if s["volume_L"] > p["volume_cap_L"]:
        return False, f"over volume cap ({s['volume_L']} > {p['volume_cap_L']})"
    return True, "ok"


def coverage_report(inventory: Set[str], data: GameData,
                    location: Optional[Location] = None) -> dict:
    """
    For a given inventory, how many events does it mitigate, and what's the
    expected per-day HP loss?
    """
    n_total = len(data.events)
    n_mit = 0
    expected_loss = 0.0
    for ev in data.events.values():
        if mitigates(inventory, ev):
            n_mit += 1
        hp = effective_hp(inventory, ev, location)
        expected_loss += ev.raw_prob * hp  # negative numbers reduce HP

    return {
        "events_total": n_total,
        "events_mitigated": n_mit,
        "fraction_mitigated": round(n_mit / n_total, 3),
        "expected_daily_hp_delta": round(expected_loss, 3),
        "expected_50day_hp_delta": round(expected_loss * 50, 1),
    }
