"""
tests/test_rules.py — checks the engine against the worked examples in the
Lecture 10 slides and the printed location and trait cards.
Run from the project folder:  python -m pytest -q tests   (or: python tests/test_rules.py)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine

D = engine.load_data()
P = dict(D["params"], resupply_mode="off")


def hp(event, inv=(), loc="lakeside_neutral", trait=None, water=10.0):
    """HP change of one event for one group."""
    inv = {i: 1 for i in inv}
    locs = dict(D["locations"])
    locs["lakeside_neutral"] = {"name": "Neutral", "card": "", "hp_rules": []}
    data = dict(D, locations=locs)
    st = engine.init_team_state(inv, loc, trait, data, P)
    st["water"], st["hp"], st["history"] = water, 20, []
    team = {"inv": inv, "location": loc, "trait": trait, "state": st, "resupply_days": []}
    rec = engine.resolve_day(team, event, 1, data, P)
    extra = 0
    if trait == "light_pack_expert" and st["pack_weight"] <= 15:
        extra = 1
    return rec["dhp"] - extra


CASES = [
    # (event, items, location, trait, water, expected HP change, source)
    ("cold_wave", [], None, None, 10, -3, "slide day 1 base"),
    ("cold_wave", [], "glacier_ridge", None, 10, -4, "slide day 1 Glacier"),
    ("cold_wave", [], "valley_floor", None, 10, -2, "slide day 1 Valley"),
    ("cold_wave", ["down_jacket"], "glacier_ridge", None, 10, 0, "slide day 1 mitigated"),
    ("cold_wave", [], "glacier_ridge", "cold_sensitive", 10, -5, "slide day 1 Cold Sensitive"),
    ("deep_stream", [], None, "old_rope", 10, -2, "slide day 2 Old Rope"),
    ("deep_stream", ["trekking_pole"], None, None, 10, 0, "slide day 2 mitigated"),
    ("food_poisoning", [], None, None, 10, -3, "slide day 3 base"),
    ("food_poisoning", ["adv_medkit"], None, None, 10, -1, "slide day 3 mitigated"),
    ("melted_snow", [], None, None, 10, -1, "slide day 4 base"),
    ("melted_snow", [], "boggy_hollow", None, 10, -2, "slide day 4 Boggy"),
    ("melted_snow", ["water_purif_tabs"], "boggy_hollow", None, 10, 0, "slide day 4 Boggy purified"),
    ("nightingale_sings", ["sleeping_bag"], None, None, 10, 1, "slide day 5 base"),
    ("nightingale_sings", ["sleeping_bag"], "old_trail", None, 10, 0, "slide day 5 Old Trail"),
    ("nightingale_sings", ["sleeping_bag"], None, "animal_friend", 10, 0, "slide day 5 Animal Friend"),
    ("insect_swarm", [], None, None, 10, -2, "slide day 6 base"),
    ("insect_swarm", [], "deep_forest", None, 10, -3, "slide day 6 Deep Forest"),
    ("insect_swarm", [], "boggy_hollow", None, 10, -3, "slide day 6 Boggy"),
    ("insect_swarm", [], "deep_forest", "allergy_prone", 10, -4, "slide day 6 Allergy Prone"),
    ("hot_tea", ["stove_fuel", "cooking_pot"], None, None, 10, 1, "slide day 7"),
    ("hot_tea", [], None, None, 10, 0, "slide day 7 no stove"),
    ("hot_tea", ["stove_fuel", "cooking_pot"], None, "hot_drink_lover", 10, 2, "slide day 7 trait"),
    ("rain_at_night", [], None, None, 10, -1, "slide day 8 base"),
    ("rain_at_night", [], "valley_floor", None, 10, 0, "slide day 8 Valley"),
    ("rain_at_night", [], None, "backup_hammock", 10, 0, "slide day 8 Backup Hammock"),
    ("wet_food_mold", [], "deep_forest", None, 10, -2, "slide day 9 Deep Forest"),
    ("wet_food_mold", [], "cave_mouth", None, 10, -2, "slide day 9 Cave Mouth"),
    ("lost_at_night", [], "valley_floor", None, 10, 0, "slide day 10 Valley"),
    ("lost_at_night", [], "high_plateau", None, 10, 0, "slide day 10 Plateau"),
    ("lost_at_night", [], "cave_mouth", None, 10, -2, "Cave Mouth card, no headlamp"),
    ("heat_exhaustion", [], None, None, 10, -1, "slide day 12 mitigated by 2 L on hand"),
    ("heat_exhaustion", [], None, None, 1.5, -3, "slide day 12 base (too little water)"),
    ("heat_exhaustion", [], "lakeside", None, 1.5, -2, "slide day 12 Lakeside"),
    ("heat_exhaustion", [], "valley_floor", None, 1.5, -2, "slide day 12 Valley"),
    ("heat_exhaustion", [], "high_plateau", None, 1.5, -4, "slide day 12 Plateau"),
    ("heat_exhaustion", [], "high_plateau", "heat_resistant", 1.5, -3, "slide day 12 Heat Resistant"),
    ("night_frost", [], "glacier_ridge", None, 10, -2, "slide day 13 Glacier"),
    ("night_frost", [], "valley_floor", None, 10, 0, "slide day 13 Valley"),
    ("night_frost", [], "cave_mouth", None, 10, 0, "slide day 13 Cave"),
    ("bee_sting", [], "deep_forest", None, 10, -2, "slide day 14 Deep Forest"),
    ("bee_sting", [], "deep_forest", "allergy_prone", 10, -3, "slide day 14 Allergy Prone"),
    ("severe_dehydration", ["electrolyte"], None, None, 10, -2, "slide day 16 mitigated"),
    ("severe_dehydration", ["electrolyte"], None, None, 2, -4, "slide day 16 only 2 L"),
    ("severe_dehydration", [], "lakeside", None, 10, -3, "slide day 16 Lakeside"),
    ("severe_dehydration", [], "high_plateau", None, 10, -5, "slide day 16 Plateau"),
    ("slippery_trail", [], "glacier_ridge", None, 10, -2, "slide day 18 Glacier"),
    ("slippery_trail", [], "scree_slope", None, 10, -2, "slide day 18 Scree"),
    ("slippery_trail", [], None, "climber", 10, 0, "slide day 18 Climber"),
    ("hypothermia_warn", ["bivy_bag"], None, None, 10, -1, "slide day 19 mitigated"),
    ("hypothermia_warn", [], "glacier_ridge", None, 10, -4, "slide day 19 Glacier"),
    ("fine_afternoon", ["sleeping_bag"], None, None, 10, 1, "printed table: needs sleeping bag"),
    ("cliff_edge", ["climbing_rope"], None, None, 10, -1, "slide day 21 mitigated"),
    ("cliff_edge", [], None, "old_rope", 10, -3, "slide day 21 Old Rope"),
    ("windstorm", [], "wind_pass", None, 10, -5, "Wind Pass card: wind +2"),
    ("thunderstorm", [], "wind_pass", None, 10, -3, "Wind Pass card: storm +1"),
    ("black_ice_slip", [], "glacier_ridge", None, 10, -3, "Glacier: cold and slip, largest rule only"),
    ("tent_peg_lost", [], "scree_slope", None, 10, -1, "Scree card: equipment +1"),
    ("path_disappears", [], "old_trail", None, 10, 0, "Old Trail: -2 reduction capped at 0"),
    ("snowstorm", ["four_season_tent", "winter_sleeping_bag"], None, None, 10, 0, "new items substitute"),
    ("mild_fever", ["wilderness_medkit"], None, None, 10, 0, "full medical kit covers medical kit"),
]


def test_cases():
    bad = []
    for e, inv, loc, tr, w, want, src in CASES:
        got = hp(e, inv, loc or "lakeside_neutral", tr, w)
        if got != want:
            bad.append(f"{src}: {e} expected {want}, got {got}")
    assert not bad, "\n".join(bad)


def test_water_gain_by_location():
    """Clear stream gives 1.5 L before location effects."""
    def gain(loc, inv):
        st = engine.init_team_state(inv, loc, None, D, P)
        st["water"] = 10.0
        team = {"inv": inv, "location": loc, "trait": None, "state": st, "resupply_days": []}
        engine.resolve_day(team, "clear_stream", 1, D, P)
        return round(st["water"] - 10.0 + P["baseline_water_L_per_day"], 2)
    assert gain("lakeside", {}) == 2.5                         # 1.5 x 1.5 = 2.25, rounded up to 2.5
    assert gain("valley_floor", {}) == 1.8                     # 1.5 x 1.2
    assert gain("glacier_ridge", {}) == 0.0                    # no stove, no water
    assert gain("glacier_ridge", {"stove_fuel": 1}) == 1.5
    assert gain("valley_floor", {"water_container": 1}) == 2.7  # container x1.5 on streams


def test_cooking_needs():
    assert engine.pack_totals({"rice_bag": 1}, D)["kcal"] == 0
    assert engine.pack_totals({"rice_bag": 1, "cooking_pot": 1, "stove_fuel": 1}, D)["kcal"] == 3600


if __name__ == "__main__":
    test_cases(); test_water_gain_by_location(); test_cooking_needs()
    print(f"all {len(CASES)} rule cases pass")
