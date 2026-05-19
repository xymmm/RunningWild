"""
example.py — Demonstrates typical queries against the game data.

Run from the data directory:
    python3 example.py
"""

from gamedata import load_all, mitigates, effective_hp, inventory_summary, feasible, coverage_report

# Load everything
data = load_all(".")

print("=" * 60)
print("CATALOGUE SIZES")
print("=" * 60)
print(f"  items     : {len(data.items)}")
print(f"  events    : {len(data.events)}")
print(f"  locations : {len(data.locations)}")
print(f"  traits    : {len(data.traits)}")
print()

print("=" * 60)
print("EXAMPLE 1: look up a specific event and item")
print("=" * 60)
ev = data.events["cold_wave"]
print(f"Event: {ev.name}")
print(f"  Category   : {ev.category}")
print(f"  Base HP    : {ev.base_hp}")
print(f"  Mitigation : {ev.mit_logic} of {ev.mit_set}")
print(f"  If mitigated, HP = {ev.mit_hp}")
print(f"  Per-day probability: {ev.raw_prob}")
print()

it = data.items["sleeping_bag"]
print(f"Item: {it.name}")
print(f"  Weight  : {it.weight_kg} kg")
print(f"  Volume  : {it.volume_L} L")
print(f"  Category: {it.category}")
print()

print("=" * 60)
print("EXAMPLE 2: build a backpack, check feasibility")
print("=" * 60)
inv = {
    "tent", "sleeping_bag", "rain_poncho", "fleece_jacket",
    "hiking_boots", "compass_map", "small_medkit",
    "stove_fuel", "cooking_pot", "dry_food", "water_5L",
    "filter_bottle", "bandages", "duct_tape",
}
ok, reason = feasible(inv, data)
summary = inventory_summary(inv, data.items)
print(f"Backpack: {sorted(inv)}")
print(f"  Items: {summary['n_items']}, Weight: {summary['weight_kg']} kg, Volume: {summary['volume_L']} L")
print(f"  Food carried: {summary['kcal']} kcal, Water: {summary['litres']} L")
print(f"  Feasible: {ok} ({reason})")
print()

print("=" * 60)
print("EXAMPLE 3: does the backpack mitigate cold_wave?")
print("=" * 60)
ev = data.events["cold_wave"]
print(f"  mitigates(inv, cold_wave) = {mitigates(inv, ev)}")
print(f"  HP delta (no location)    = {effective_hp(inv, ev)}")
print(f"  HP delta (Glacier Ridge)  = {effective_hp(inv, ev, data.locations['glacier_ridge'])}")
print(f"  HP delta (Valley Floor)   = {effective_hp(inv, ev, data.locations['valley_floor'])}")
print()

# what if I drop the sleeping bag?
inv2 = inv - {"sleeping_bag"}
print(f"After dropping sleeping_bag:")
print(f"  mitigates(inv2, cold_wave) = {mitigates(inv2, data.events['cold_wave'])}")
print(f"  HP delta (no location)     = {effective_hp(inv2, data.events['cold_wave'])}")
# down_jacket should still mitigate
print()

print("=" * 60)
print("EXAMPLE 4: snowstorm requires tent AND sleeping bag (ALL logic)")
print("=" * 60)
ev = data.events["snowstorm"]
print(f"  Event: {ev.name}, logic={ev.mit_logic}, set={ev.mit_set}")
print(f"  With full backpack:   mitigates = {mitigates(inv, ev)}")
print(f"  Drop tent only:       mitigates = {mitigates(inv - {'tent'}, ev)}")
print(f"  Drop sleeping_bag only: mitigates = {mitigates(inv - {'sleeping_bag'}, ev)}")
print()

print("=" * 60)
print("EXAMPLE 5: coverage report — how good is this backpack overall?")
print("=" * 60)
report = coverage_report(inv, data, data.locations["valley_floor"])
print(f"  Events mitigated: {report['events_mitigated']} / {report['events_total']}")
print(f"  Fraction        : {report['fraction_mitigated']:.1%}")
print(f"  Expected daily HP delta  : {report['expected_daily_hp_delta']}")
print(f"  Expected 50-day HP delta : {report['expected_50day_hp_delta']}")
print()
print("  Compare to a stockpile-heavy strategy (only food and water):")
stockpile_inv = {"dry_food", "dry_food", "water_5L", "water_5L", "water_5L", "energy_bars"}
# Set doesn't dedupe by repetition, so represent quantity differently if needed.
# For this demo just take the union of items it would include.
stockpile_inv = {"dry_food", "water_5L", "energy_bars", "peanut_butter", "filter_bottle"}
report2 = coverage_report(stockpile_inv, data, data.locations["valley_floor"])
print(f"  Stockpile backpack: {sorted(stockpile_inv)}")
print(f"  Events mitigated: {report2['events_mitigated']} / {report2['events_total']}")
print(f"  Expected 50-day HP delta : {report2['expected_50day_hp_delta']}")
print()

print("=" * 60)
print("EXAMPLE 6: iterate over all events in a category")
print("=" * 60)
print("All cold-weather events:")
for eid, ev in sorted(data.events.items()):
    if ev.category == "weather_cold":
        print(f"  {ev.name:30s} HP {ev.base_hp:+d}  mit={ev.mit_logic} {ev.mit_set}")
