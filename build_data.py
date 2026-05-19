"""
build_data.py

Defines the full catalogues for the Survival Knapsack game and writes them to
disk as CSV/JSON for downstream simulator / MILP use.

Run: python3 build_data.py
Outputs: items.csv, events.csv, locations.json, traits.json, parameters.yaml
"""

import csv
import json

# ----------------------------------------------------------------------------
# ITEMS — 89 items audited from SelectItem PDF
# Columns: id, display name, weight (kg), volume (L), category, kcal, litres,
#          is_wearable (jacket etc, volume excluded if worn)
# kcal / litres encode food / water content for food and water items only.
# ----------------------------------------------------------------------------

ITEMS = [
    # shelter
    ("tent",              "Lightweight tent",            2.5, 10.0, "shelter",  0,    0.0, False),
    ("sleeping_bag",      "Sleeping bag",                1.2,  6.0, "shelter",  0,    0.0, False),
    ("thermal_blanket",   "Emergency thermal blanket",   0.6,  3.0, "shelter",  0,    0.0, False),
    ("rain_tarp",         "Rain tarp",                   0.9,  4.0, "shelter",  0,    0.0, False),
    ("ground_tarp",       "Ground tarp",                 0.7,  3.0, "shelter",  0,    0.0, False),
    ("bivy_bag",          "Emergency bivy bag",          0.4,  2.0, "shelter",  0,    0.0, False),
    ("seat_pad",          "Camping seat pad",            0.2,  0.8, "shelter",  0,    0.0, False),
    # clothing (wearable)
    ("rain_poncho",       "Rain poncho",                 0.3,  1.0, "clothing", 0,    0.0, True),
    ("fleece_jacket",     "Fleece jacket",               0.8,  3.0, "clothing", 0,    0.0, True),
    ("down_jacket",       "Down jacket",                 1.1,  4.0, "clothing", 0,    0.0, True),
    ("winter_coat",       "Thick winter coat",           1.8,  5.0, "clothing", 0,    0.0, True),
    ("waterproof_jacket", "Waterproof jacket",           0.9,  4.0, "clothing", 0,    0.0, True),
    ("hiking_boots",      "Waterproof hiking boots",     1.2,  3.0, "clothing", 0,    0.0, True),
    ("extra_socks",       "Extra socks",                 0.15, 0.3, "clothing", 0,    0.0, False),
    ("thermal_socks",     "Thermal socks",               0.2,  0.4, "clothing", 0,    0.0, False),
    ("gloves",            "Gloves",                      0.2,  0.5, "clothing", 0,    0.0, False),
    ("wool_hat",          "Wool hat",                    0.15, 0.4, "clothing", 0,    0.0, False),
    ("sun_hat",           "Sun hat",                     0.2,  0.7, "clothing", 0,    0.0, False),
    ("sunglasses",        "Sunglasses",                  0.1,  0.2, "clothing", 0,    0.0, False),
    ("scarf",             "Scarf",                       0.2,  0.5, "clothing", 0,    0.0, False),
    # navigation & light
    ("headlamp",          "Headlamp with batteries",     0.25, 0.7, "nav_light",0,    0.0, False),
    ("spare_headlamp",    "Spare headlamp",              0.25, 0.7, "nav_light",0,    0.0, False),
    ("compass_map",       "Compass and map",             0.15, 0.5, "nav_light",0,    0.0, False),
    ("gps",               "GPS device",                  0.3,  1.0, "nav_light",0,    0.0, False),
    ("spare_batteries",   "Spare batteries",             0.5,  1.0, "nav_light",0,    0.0, False),
    ("solar_panel",       "Mini solar panel",            0.9,  2.5, "nav_light",0,    0.0, False),
    ("power_bank",        "Portable power bank",         0.4,  1.0, "nav_light",0,    0.0, False),
    # tools
    ("multi_tool",        "Multi-tool knife",            0.2,  0.3, "tools",    0,    0.0, False),
    ("hatchet",            "Small hatchet",              0.7,  2.0, "tools",    0,    0.0, False),
    ("saw",               "Lightweight saw",             0.45, 1.2, "tools",    0,    0.0, False),
    ("rope_tool_kit",     "Rope and tool kit",           0.8,  2.0, "tools",    0,    0.0, False),
    ("climbing_rope",     "Climbing rope 20m",           1.4,  5.0, "tools",    0,    0.0, False),
    ("tent_repair_kit",   "Tent repair kit",             0.2,  0.6, "tools",    0,    0.0, False),
    ("sewing_kit",        "Sewing repair kit",           0.1,  0.3, "tools",    0,    0.0, False),
    ("duct_tape",         "Duct tape",                   0.2,  0.8, "tools",    0,    0.0, False),
    ("trekking_pole",     "Trekking pole",               0.4,  1.5, "tools",    0,    0.0, False),
    ("small_shovel",      "Small shovel",                0.5,  1.5, "tools",    0,    0.0, False),
    ("folding_spade",     "Folding spade",               0.7,  2.0, "tools",    0,    0.0, False),
    ("pry_bar",           "Metal pry bar",               0.6,  2.0, "tools",    0,    0.0, False),
    # fire & cooking
    ("stove_fuel",        "Stove with fuel (3 days)",    1.8,  5.0, "fire_cook",0,    0.0, False),
    ("extra_fuel",        "Extra fuel (3 days)",         1.2,  3.0, "fire_cook",0,    0.0, False),
    ("fire_starter",      "Fire starter and lighter",    0.07, 0.1, "fire_cook",0,    0.0, False),
    ("matches",           "Waterproof matches",          0.1,  0.2, "fire_cook",0,    0.0, False),
    ("cooking_pot",       "Cooking pot",                 0.6,  2.0, "fire_cook",0,    0.0, False),
    ("metal_cup",         "Metal cup",                   0.2,  0.4, "fire_cook",0,    0.0, False),
    ("coffee_press",      "Portable coffee press",       0.3,  1.0, "fire_cook",0,    0.0, False),
    ("portable_cutlery",  "Portable cutlery",            0.2,  0.5, "fire_cook",0,    0.0, False),
    # food
    ("dry_food",          "Dry food pack 6000kcal",      2.0,  4.0, "food",     6000, 0.0, False),
    ("energy_bars",       "Energy bars (12)",            0.5,  1.0, "food",     2400, 0.0, False),
    ("protein_biscuits",  "Protein biscuits",            0.4,  1.0, "food",     1600, 0.0, False),
    ("dried_fruit_nuts",  "Dried fruit and nuts",        0.4,  0.8, "food",     1800, 0.0, False),
    ("hard_crackers",     "Hard crackers",               0.3,  0.8, "food",     1200, 0.0, False),
    ("chocolate_bars",    "Chocolate bars (pack)",       0.3,  0.8, "food",     1500, 0.0, False),
    ("peanut_butter",     "Peanut butter jar",           0.5,  0.6, "food",     2800, 0.0, False),
    ("instant_noodles",   "Instant noodles (5 packs)",   0.5,  1.5, "food",     1700, 0.0, False),
    ("insulated_food",    "Insulated food container",    0.7,  1.5, "food",     0,    0.0, False),
    ("electrolyte",       "Electrolyte powder (10 packs)",0.2, 0.5, "food",     0,    0.0, False),
    # water
    ("water_5L",          "Potable water 5L",            5.0,  5.0, "water",    0,    5.0, False),
    ("water_2L",          "Potable water 2L",            2.0,  2.0, "water",    0,    2.0, False),
    ("water_purif_tabs",  "Water purification tablets",  0.2,  1.0, "water",    0,    0.0, False),
    ("filter_bottle",     "Filter water bottle",         0.7,  3.0, "water",    0,    0.0, False),
    ("water_container",   "Foldable water container 5L", 0.1,  0.5, "water",    0,    0.0, False),
    # storage
    ("waterproof_box",    "Waterproof storage box",      0.6,  3.0, "storage",  0,    0.0, False),
    ("waterproof_bag",    "Waterproof bag",              0.25, 1.0, "storage",  0,    0.0, False),
    ("zip_bags",          "Plastic zip bags",            0.1,  0.2, "storage",  0,    0.0, False),
    ("garbage_bags",      "Garbage bags",                0.1,  0.3, "storage",  0,    0.0, False),
    # signalling
    ("whistle",           "Emergency whistle",           0.05, 0.1, "signal",   0,    0.0, False),
    ("whistle_reflective","Whistle with reflective tag", 0.08, 0.1, "signal",   0,    0.0, False),
    ("signal_mirror",     "Signal mirror",               0.1,  0.2, "signal",   0,    0.0, False),
    ("small_radio",       "Small radio",                 0.4,  1.0, "signal",   0,    0.0, False),
    ("thermo_hygro",      "Thermo-hygrometer",           0.2,  0.6, "signal",   0,    0.0, False),
    ("drone",             "Lightweight drone",           1.1,  4.0, "signal",   0,    0.0, False),
    # safety / first aid
    ("small_medkit",      "Small medical kit",           0.5,  2.0, "medical",  0,    0.0, False),
    ("adv_medkit",        "Advanced medical kit",        0.9,  3.0, "medical",  0,    0.0, False),
    ("bandages",          "Bandages and gauze",          0.25, 0.7, "medical",  0,    0.0, False),
    ("cold_compress",     "Cold compress packs (2)",     0.2,  0.5, "medical",  0,    0.0, False),
    ("sunscreen",         "Sunscreen",                   0.2,  0.5, "medical",  0,    0.0, False),
    ("mosquito_repel",    "Mosquito repellent",          0.25, 0.6, "medical",  0,    0.0, False),
    ("painkillers",       "Painkillers (10)",            0.15, 0.4, "medical",  0,    0.0, False),
    ("allergy_meds",      "Allergy medication",          0.1,  0.3, "medical",  0,    0.0, False),
    ("antibiotic_cream",  "Antibiotic cream",            0.1,  0.3, "medical",  0,    0.0, False),
    ("heat_pack",         "Emergency heat pack",         0.15, 0.6, "medical",  0,    0.0, False),
    ("hand_warmers",      "Hand warmers (10)",           0.25, 0.6, "medical",  0,    0.0, False),
    ("disinfectant",      "Disinfectant wipes",          0.2,  0.6, "medical",  0,    0.0, False),
    ("hygiene_kit",       "Hygiene kit",                 0.4,  1.5, "medical",  0,    0.0, False),
    ("soap",              "Biodegradable soap",          0.2,  0.5, "medical",  0,    0.0, False),
    ("toothbrush",        "Toothbrush and toothpaste",   0.15, 0.3, "medical",  0,    0.0, False),
    ("towel",             "Quick-dry towel",             0.25, 0.7, "medical",  0,    0.0, False),
    # defence
    ("bear_spray",        "Bear spray",                  0.4,  1.0, "defence",  0,    0.0, False),
    ("pepper_spray",      "Pepper spray",                0.15, 0.4, "defence",  0,    0.0, False),
    # morale
    ("notebook",          "Notebook and pencil",         0.1,  0.5, "morale",   0,    0.0, False),
    ("playing_cards",     "Small book or playing cards", 0.3,  1.0, "morale",   0,    0.0, False),
    ("statue",            "Mysterious small statue",     0.2,  0.5, "morale",   0,    0.0, False),
]

# ----------------------------------------------------------------------------
# EVENTS — 187 events, parsed and categorised from Events PDF
# Fields: id, name, category, base_hp, mit_logic, mit_set, mit_hp, raw_prob
# mit_set is a list of item ids; semantics governed by mit_logic.
# raw_prob is per-day Bernoulli probability (Scheme A); sum ≈ 1.65.
# ----------------------------------------------------------------------------

# Helper to abbreviate event tuples
def E(id, name, cat, hp, logic, mset, mhp, p):
    return (id, name, cat, hp, logic, mset, mhp, p)

EVENTS = [
    # ---- weather neutral
    E("clear_weather",      "Clear weather",      "weather_neutral",   0, "NONE", [], 0, 0.010),
    E("cloudy_sky",         "Cloudy sky",         "weather_neutral",   0, "NONE", [], 0, 0.010),
    E("foggy_morning",      "Foggy morning",      "weather_neutral",   0, "ANY",  ["compass_map","gps"], 0, 0.010),
    E("misty_dawn",         "Misty dawn",         "weather_neutral",   0, "ANY",  ["compass_map","gps"], 0, 0.006),
    E("fog_covers_sun",     "Fog covers sun",     "weather_neutral",   0, "NONE", [], 0, 0.008),
    E("fine_dry_air",       "Fine dry air",       "weather_neutral",   0, "NONE", [], 0, 0.006),
    E("light_breeze",       "Light breeze",       "weather_neutral",   0, "NONE", [], 0, 0.006),
    E("dew_on_gear",        "Dew on gear",        "weather_neutral",   0, "ANY",  ["waterproof_bag"], 0, 0.006),
    # ---- weather wet
    E("light_rain",         "Light rain",         "weather_wet",      -1, "ANY",  ["rain_poncho"], 0, 0.010),
    E("short_shower",       "Short shower",       "weather_wet",      -1, "ANY",  ["rain_poncho","waterproof_jacket"], 0, 0.010),
    E("heavy_rain",         "Heavy rain",         "weather_wet",      -2, "ANY",  ["rain_tarp","tent"], 0, 0.010),
    E("torrential_rain",    "Torrential rain",    "weather_wet",      -3, "ALL",  ["rain_tarp","waterproof_bag"], 0, 0.006),
    E("chilly_drizzle",     "Chilly drizzle",     "weather_wet",      -1, "ANY",  ["rain_poncho"], 0, 0.008),
    E("cold_drizzle",       "Cold drizzle",       "weather_wet",      -1, "ANY",  ["rain_poncho"], 0, 0.006),
    E("rain_at_night",      "Rain at night",      "weather_wet",      -1, "ANY",  ["tent"], 0, 0.006),
    E("thunderstorm",       "Thunderstorm",       "weather_wet",      -2, "ANY",  ["waterproof_bag","rain_tarp"], 0, 0.008),
    E("hail_storm",         "Hail storm",         "weather_wet",      -3, "ANY",  ["waterproof_jacket","rain_tarp"], 0, 0.008),
    E("hail_at_noon",       "Hail at noon",       "weather_wet",      -2, "ANY",  ["waterproof_jacket"], 0, 0.006),
    E("high_humidity",      "High humidity",      "weather_wet",      -1, "ANY",  ["thermal_socks","extra_socks"], 0, 0.008),
    E("humid_cold",         "Humid cold",         "weather_wet",      -1, "ANY",  ["thermal_socks"], 0, 0.008),
    # ---- weather cold
    E("cold_morning",       "Cold morning",       "weather_cold",     -1, "ANY",  ["fleece_jacket"], 0, 0.010),
    E("cold_wave",          "Cold wave",          "weather_cold",     -3, "ANY",  ["sleeping_bag","down_jacket","winter_coat","thermal_blanket","bivy_bag"], 0, 0.010),
    E("frost_night",        "Frost at night",     "weather_cold",     -2, "ANY",  ["sleeping_bag"], 0, 0.008),
    E("sudden_cold_drop",   "Sudden cold drop",   "weather_cold",     -2, "ANY",  ["down_jacket"], 0, 0.008),
    E("snow_flurries",      "Snow flurries",      "weather_cold",     -2, "ANY",  ["thermal_blanket","down_jacket"], 0, 0.008),
    E("snowstorm",          "Snowstorm",          "weather_cold",     -3, "ALL",  ["tent","sleeping_bag"], 0, 0.008),
    E("freezing_wind",      "Freezing wind",      "weather_cold",     -2, "ALL",  ["gloves","wool_hat"], 0, 0.008),
    E("cold_night",         "Cold night",         "weather_cold",     -2, "ANY",  ["sleeping_bag","heat_pack"], 0, 0.008),
    E("black_ice_slip",     "Black ice slip",     "weather_cold",     -2, "ANY",  ["hiking_boots"], 0, 0.008),
    E("icy_ground",         "Icy ground",         "weather_cold",     -1, "ANY",  ["trekking_pole","hiking_boots"], 0, 0.008),
    E("night_frost",        "Night frost",        "weather_cold",     -1, "ANY",  ["heat_pack"], 0, 0.006),
    E("chill_wind",         "Chill wind",         "weather_cold",     -1, "ANY",  ["fleece_jacket"], 0, 0.006),
    E("bright_cold_day",    "Bright cold day",    "weather_cold",     -1, "ALL",  ["sunglasses","fleece_jacket"], 0, 0.006),
    E("frozen_ground",      "Frozen ground cracks","weather_cold",    -1, "ANY",  ["hiking_boots"], 0, 0.006),
    # ---- weather hot
    E("hot_dry_sun",        "Hot dry sun",        "weather_hot",      -1, "ANY",  ["sun_hat","sunscreen"], 0, 0.010),
    E("uv_burn",            "UV burn",            "weather_hot",      -1, "ANY",  ["sunscreen"], 0, 0.008),
    E("blazing_sun",        "Blazing sun",        "weather_hot",      -2, "ANY",  ["sun_hat"], 0, 0.008),
    E("strong_uv",          "Strong UV",          "weather_hot",      -1, "ANY",  ["sun_hat"], 0, 0.006),
    E("blinding_sun",       "Blinding sunshine",  "weather_hot",      -1, "ANY",  ["sunglasses"], 0, 0.006),
    E("cloudbreak_heat",    "Cloudbreak heat",    "weather_hot",      -1, "ANY",  ["sunscreen"], 0, 0.008),
    E("heat_surge",         "Heat surge",         "weather_hot",      -1, "ANY",  ["sun_hat"], 0, 0.008),
    E("dry_hot_wind",       "Dry hot wind",       "weather_hot",      -1, "ANY",  ["water_2L","water_5L"], 0, 0.008),
    # ---- weather wind
    E("windy_day",          "Windy day",          "weather_wind",     -1, "ANY",  ["waterproof_jacket"], 0, 0.010),
    E("strong_wind",        "Strong wind",        "weather_wind",     -2, "ANY",  ["tent","rain_tarp"], 0, 0.010),
    E("windstorm",          "Windstorm",          "weather_wind",     -3, "ALL",  ["tent","tent_repair_kit"], 0, 0.010),
    E("dust_storm",         "Dust storm",         "weather_wind",     -2, "ANY",  ["sunglasses","scarf"], 0, 0.008),
    E("floating_ash",       "Floating ash",       "weather_wind",     -1, "ANY",  ["scarf"], 0, 0.006),
    # ---- bonus_morale (positive events)
    E("fine_afternoon",     "Fine afternoon",     "bonus_morale",     +1, "NONE", [], 0, 0.006),
    E("calm_warm_night",    "Calm warm night",    "bonus_morale",     +1, "NONE", [], 0, 0.006),
    E("hot_tea",            "Hot tea",            "bonus_morale",     +1, "ALL",  ["stove_fuel","cooking_pot"], 0, 0.005),
    E("tea_leaves_found",   "Tea leaves found",   "bonus_morale",     +1, "ANY",  ["cooking_pot"], 0, 0.005),
    E("wild_herb_tea",      "Wild herb tea",      "bonus_morale",     +1, "ANY",  ["cooking_pot"], 0, 0.005),
    E("nightingale_sings",  "Nightingale sings",  "bonus_morale",     +1, "NONE", [], 0, 0.008),
    # ---- medical_illness
    E("stove_smoke",        "Stove smoke",        "medical_illness",  -1, "ANY",  ["rain_tarp"], 0, 0.008),
    E("cold_sore",          "Cold sore",          "medical_illness",  -1, "ANY",  ["small_medkit"], 0, 0.008),
    E("cough_all_night",    "Cough all night",    "medical_illness",  -1, "ANY",  ["sleeping_bag"], 0, 0.008),
    E("frozen_breath",      "Frozen breath",      "medical_illness",  -1, "ANY",  ["heat_pack"], 0, 0.008),
    E("cold_lungs",         "Cold lungs",         "medical_illness",  -2, "ANY",  ["scarf"], 0, 0.008),
    E("heat_rash",          "Heat rash",          "medical_illness",  -1, "ANY",  ["sunscreen"], 0, 0.008),
    E("severe_fever",       "Severe fever",       "medical_illness",  -3, "ANY",  ["adv_medkit"], 0, 0.008),
    E("altitude_sickness",  "Altitude sickness",  "medical_illness",  -2, "ANY",  ["sleeping_bag"], 0, 0.007),
    E("cold_sweat",         "Cold sweat",         "medical_illness",  -1, "ANY",  ["heat_pack"], 0, 0.007),
    E("heat_headache",      "Heat headache",      "medical_illness",  -1, "ANY",  ["water_2L","water_5L"], 0, 0.007),
    E("minor_concussion",   "Minor concussion",   "medical_illness",  -3, "ANY",  ["small_medkit","adv_medkit"], 0, 0.007),
    E("mild_fever",         "Mild fever",         "medical_illness",  -2, "ANY",  ["small_medkit"], 0, 0.010),
    E("stomach_pain",       "Stomach pain",       "medical_illness",  -2, "ANY",  ["water_purif_tabs"], 0, 0.010),
    E("food_poisoning",     "Food poisoning",     "medical_illness",  -3, "ANY",  ["small_medkit","adv_medkit"], -1, 0.010),
    E("toothache",          "Toothache",          "medical_illness",  -1, "ANY",  ["painkillers"], 0, 0.010),
    E("nosebleed",          "Nosebleed",          "medical_illness",  -1, "ANY",  ["water_2L","water_5L"], 0, 0.010),
    # ---- medical_injury
    E("severe_blister1",    "Severe blister",     "medical_injury",   -1, "ANY",  ["bandages"], 0, 0.008),
    E("severe_blister2",    "Severe blister (deep)","medical_injury", -2, "ANY",  ["small_medkit"], 0, 0.008),
    E("minor_infection",    "Minor infection",    "medical_injury",   -1, "ANY",  ["antibiotic_cream"], 0, 0.008),
    E("severe_infection",   "Severe infection",   "medical_injury",   -3, "ANY",  ["adv_medkit"], 0, 0.008),
    E("infected_wound",     "Infected wound",     "medical_injury",   -3, "ANY",  ["antibiotic_cream","adv_medkit"], 0, 0.010),
    E("frozen_fingers",     "Frozen fingers",     "medical_injury",   -2, "ANY",  ["gloves","hand_warmers","heat_pack"], 0, 0.008),
    E("frozen_toes",        "Frozen toes",        "medical_injury",   -2, "ANY",  ["thermal_socks"], 0, 0.008),
    E("minor_burn",         "Minor burn",         "medical_injury",   -1, "ANY",  ["cold_compress"], 0, 0.008),
    E("thorn_scratch",      "Thorn scratch",      "medical_injury",   -1, "ANY",  ["bandages"], 0, 0.007),
    E("small_cut",          "Small cut",          "medical_injury",   -1, "ANY",  ["bandages"], 0, 0.010),
    E("blister_foot",       "Blister on foot",    "medical_injury",   -1, "ANY",  ["bandages"], 0, 0.010),
    E("sprained_ankle",     "Sprained ankle",     "medical_injury",   -2, "ANY",  ["painkillers"], 0, 0.010),
    E("small_burn",         "Small burn",         "medical_injury",   -1, "ANY",  ["cold_compress"], 0, 0.010),
    E("knife_slip",         "Knife slip",         "medical_injury",   -1, "ANY",  ["bandages"], 0, 0.010),
    E("allergic_rash",      "Allergic rash",      "medical_injury",   -1, "ANY",  ["allergy_meds"], 0, 0.010),
    E("gas_inhalation",     "Gas inhalation",     "medical_injury",   -2, "ANY",  ["rain_tarp"], 0, 0.008),
    E("cold_hands",         "Cold hands",         "medical_injury",   -1, "ANY",  ["gloves"], 0, 0.010),
    E("cold_feet",          "Cold feet",          "medical_injury",   -1, "ANY",  ["thermal_socks"], 0, 0.010),
    E("frozen_nose",        "Frozen nose",        "medical_injury",   -1, "ANY",  ["scarf"], 0, 0.010),
    E("sunburn",            "Sunburn",            "medical_injury",   -1, "ANY",  ["sunscreen"], 0, 0.010),
    E("eye_burn",           "Eye burn",           "medical_injury",   -1, "ANY",  ["sunglasses"], 0, 0.010),
    E("sore_back",          "Sore back",          "medical_injury",   -1, "ANY",  ["seat_pad","ground_tarp"], 0, 0.010),
    E("shoulder_pain",      "Shoulder pain",      "medical_injury",   -1, "NONE", [], 0, 0.010),
    E("muscle_cramp",       "Muscle cramp",       "medical_injury",   -2, "ALL",  ["water_2L","electrolyte"], 0, 0.007),
    E("hypothermia_warn",   "Hypothermia warning","medical_injury",   -3, "ANY",  ["sleeping_bag","heat_pack","thermal_blanket","bivy_bag"], -1, 0.010),
    E("heat_exhaustion",    "Heat exhaustion",    "medical_injury",   -3, "ANY",  ["water_2L","water_5L"], -1, 0.010),
    E("severe_dehydration", "Severe dehydration", "medical_injury",   -4, "ALL",  ["water_5L","electrolyte"], -2, 0.010),
    # ---- medical_sting (insect / bite related)
    E("mosquito_fever",     "Mosquito fever",     "medical_sting",    -2, "ANY",  ["mosquito_repel"], 0, 0.008),
    E("bee_sting",          "Bee sting",          "medical_sting",    -1, "ANY",  ["allergy_meds"], 0, 0.008),
    E("spider_bite",        "Spider bite",        "medical_sting",    -2, "ANY",  ["small_medkit"], 0, 0.008),
    E("scorpion_sting",     "Scorpion sting",     "medical_sting",    -2, "ANY",  ["adv_medkit"], 0, 0.007),
    E("snake_bite",         "Snake bite",         "medical_sting",    -3, "ANY",  ["adv_medkit"], 0, 0.007),
    E("insect_swarm",       "Insect swarm",       "insect",           -2, "ANY",  ["mosquito_repel"], 0, 0.010),
    E("bee_swarm",          "Bee swarm",          "insect",           -2, "ANY",  ["mosquito_repel"], -1, 0.008),
    E("beehive_disc",       "Beehive discovered", "insect",           -1, "ANY",  ["mosquito_repel"], 0, 0.005),
    # ---- navigation
    E("lost_at_night",      "Lost at night",      "navigation",       -1, "ANY",  ["compass_map","gps","headlamp"], 0, 0.010),
    E("path_disappears",    "Path disappears",    "navigation",       -1, "ANY",  ["compass_map"], 0, 0.010),
    E("wrong_turn",         "Wrong turn",         "navigation",       -1, "ANY",  ["compass_map"], 0, 0.010),
    E("deep_forest",        "Deep forest",        "navigation",       -1, "ANY",  ["gps"], 0, 0.010),
    E("night_wandering",    "Night wandering",    "navigation",       -1, "ANY",  ["headlamp"], 0, 0.010),
    E("headlamp_dead",      "Headlamp battery dead","navigation",     -1, "ANY",  ["spare_batteries"], 0, 0.010),
    E("far_echo",           "Far echo",           "navigation",        0, "ANY",  ["whistle","whistle_reflective"], 0, 0.010),
    E("map_soaked",         "Map soaked",         "navigation",        0, "ANY",  ["waterproof_bag"], 0, 0.010),
    E("compass_drop",       "Compass drop",       "navigation",        0, "ANY",  ["duct_tape"], 0, 0.010),
    E("gps_glitch",         "GPS glitch",         "navigation",       -1, "ANY",  ["compass_map"], 0, 0.010),
    E("compass_demag",      "Compass demagnetized","navigation",      -2, "ANY",  ["gps"], 0, 0.010),
    E("map_torn",           "Map torn",           "navigation",       -1, "ANY",  ["duct_tape"], 0, 0.010),
    # ---- slip / fall
    E("slippery_trail",     "Slippery trail",     "slip_fall",        -1, "ANY",  ["trekking_pole","hiking_boots"], 0, 0.010),
    E("loose_rocks",        "Loose rocks",        "slip_fall",        -1, "ANY",  ["hiking_boots"], 0, 0.010),
    E("fallen_log",         "Fallen log",         "slip_fall",         0, "ANY",  ["multi_tool","saw"], 0, 0.010),
    E("narrow_pass",        "Narrow pass",        "slip_fall",         0, "ANY",  ["rope_tool_kit","climbing_rope"], 0, 0.010),
    E("cliff_edge",         "Cliff edge",         "slip_fall",        -2, "ANY",  ["rope_tool_kit","climbing_rope"], -1, 0.010),
    E("deep_stream",        "Deep stream",        "slip_fall",        -1, "ANY",  ["rope_tool_kit","trekking_pole"], 0, 0.010),
    # ---- equipment
    E("tent_peg_lost",      "Tent peg lost",      "equipment",         0, "ANY",  ["duct_tape"], 0, 0.010),
    E("tent_pole_break",    "Tent pole break",    "equipment",        -1, "ANY",  ["tent_repair_kit","duct_tape"], 0, 0.010),
    E("backpack_strap",     "Backpack strap tear","equipment",        -1, "ANY",  ["duct_tape"], 0, 0.010),
    E("boot_lace_snap",     "Boot lace snap",     "equipment",         0, "ANY",  ["duct_tape"], 0, 0.010),
    E("storage_crack",      "Storage box crack",  "equipment",         0, "ANY",  ["duct_tape"], 0, 0.010),
    E("cooking_pot_dent",   "Cooking pot dent",   "equipment",         0, "ANY",  ["pry_bar"], 0, 0.010),
    E("spade_handle",       "Spade loose handle", "equipment",         0, "ANY",  ["duct_tape"], 0, 0.010),
    E("saw_blade_dull",     "Saw blade dull",     "equipment",         0, "ANY",  ["tent_repair_kit"], 0, 0.010),
    E("knife_rust",         "Knife rust",         "equipment",         0, "ANY",  ["disinfectant"], 0, 0.010),
    E("radio_static",       "Radio static",       "equipment",         0, "NONE", [], 0, 0.010),
    E("water_filter_clog",  "Water filter clog",  "equipment",        -1, "ANY",  ["water_purif_tabs","filter_bottle"], 0, 0.010),
    E("fuel_spill",         "Fuel spill",         "equipment",        -1, "ANY",  ["waterproof_box"], 0, 0.010),
    E("fuel_can_leak",      "Fuel can leak",      "equipment",        -1, "ANY",  ["duct_tape"], 0, 0.010),
    E("matches_wet",        "Matches wet",        "equipment",        -1, "ANY",  ["waterproof_bag"], 0, 0.010),
    E("lighter_jam",        "Lighter jam",        "equipment",         0, "ANY",  ["matches"], 0, 0.010),
    E("tarp_tear",          "Tarp tear",          "equipment",        -1, "ANY",  ["duct_tape"], 0, 0.010),
    E("seat_punct",         "Seat pad puncture",  "equipment",         0, "ANY",  ["duct_tape"], 0, 0.010),
    E("power_bank_dead",    "Power bank dead",    "equipment",         0, "ANY",  ["solar_panel"], 0, 0.010),
    E("radio_batt_empty",   "Radio battery empty","equipment",         0, "ANY",  ["spare_batteries"], 0, 0.010),
    E("drone_lost",         "Drone lost",         "equipment",        -1, "NONE", [], 0, 0.010),
    E("drone_camera",       "Drone camera crack", "equipment",         0, "ANY",  ["duct_tape"], 0, 0.010),
    E("loose_screws",       "Loose screws",       "equipment",         0, "ANY",  ["tent_repair_kit"], 0, 0.010),
    E("boot_sole_peel",     "Boot sole peel",     "equipment",        -1, "ANY",  ["duct_tape"], 0, 0.010),
    E("knife_in_water",     "Knife falls in water","equipment",       -1, "ANY",  ["waterproof_bag"], 0, 0.010),
    E("stove_clogged",      "Stove clogged",      "equipment",        -1, "ANY",  ["tent_repair_kit"], 0, 0.010),
    E("mirror_scratch",     "Mirror scratched",   "equipment",         0, "NONE", [], 0, 0.010),
    E("signal_mirror_drop", "Signal mirror drop", "equipment",         0, "NONE", [], 0, 0.010),
    E("whistle_lost",       "Whistle lost",       "equipment",         0, "NONE", [], 0, 0.010),
    E("cup_dent",           "Cup dent",           "equipment",         0, "NONE", [], 0, 0.010),
    E("shovel_bend",        "Shovel bend",        "equipment",         0, "ANY",  ["pry_bar"], 0, 0.010),
    E("saw_tooth_broke",    "Saw tooth broke",    "equipment",         0, "ANY",  ["tent_repair_kit"], 0, 0.010),
    E("broken_water_bag",   "Broken water bag",   "equipment",        -1, "ANY",  ["duct_tape"], 0, 0.005),
    E("fuel_soaked",        "Fuel soaked",        "equipment",         0, "ANY",  ["waterproof_box"], 0, 0.005),
    E("lost_spoon",         "Lost spoon",         "equipment",         0, "NONE", [], 0, 0.005),
    E("water_container_torn","Water container torn","equipment",      -1, "ANY",  ["duct_tape"], 0, 0.005),
    E("lost_battery",       "Lost battery",       "equipment",         0, "ANY",  ["waterproof_box"], 0, 0.010),
    # ---- food spoilage
    E("mushrooms",          "Mushrooms",          "food_spoilage",    -1, "ANY",  ["stove_fuel","cooking_pot"], 0, 0.010),
    E("food_frozen",        "Food frozen",        "food_spoilage",    -1, "ANY",  ["cooking_pot","insulated_food"], 0, 0.010),
    E("fish_bones_cut",     "Fish bones cut",     "food_spoilage",    -1, "ANY",  ["small_medkit"], 0, 0.010),
    E("wet_food_mold",      "Wet food mold",      "food_spoilage",    -1, "ANY",  ["insulated_food","waterproof_bag"], 0, 0.010),
    E("foraging_failure",   "Foraging failure",   "food_spoilage",    -1, "ANY",  ["energy_bars","dry_food"], 0, 0.010),
    E("berries_sour",       "Berries turned sour","food_spoilage",    -1, "ANY",  ["small_medkit"], 0, 0.005),
    E("carried_too_much_w", "Carried too much water","food_spoilage", -1, "ANY",  ["seat_pad"], 0, 0.005),
    E("stale_crackers",     "Stale crackers",     "food_spoilage",     0, "NONE", [], 0, 0.005),
    E("poisonous_berries",  "Poisonous berries",  "food_spoilage",    -2, "ANY",  ["small_medkit","adv_medkit"], 0, 0.005),
    E("only_nuts_eaten",    "Only nuts eaten",    "food_spoilage",    -1, "NONE", [], 0, 0.005),
    # ---- water collection (water-gain events; HP often 0, gain depends on items)
    E("stored_water_frozen","Stored water frozen","water_collection", -1, "ALL",  ["stove_fuel","cooking_pot"], 0, 0.010),
    E("melted_snow",        "Melted snow",        "water_collection", -1, "ANY",  ["water_purif_tabs","filter_bottle","stove_fuel"], 0, 0.005),
    E("water_too_muddy",    "Water too muddy",    "water_collection", -1, "ANY",  ["filter_bottle"], 0, 0.005),
    E("dry_throat",         "Dry throat",         "water_collection", -1, "ANY",  ["water_2L","water_5L"], 0, 0.005),
    E("dry_lips",           "Dry lips",           "water_collection",  0, "ANY",  ["water_2L","water_5L"], 0, 0.010),
    # ---- wildlife calm (non-attack)
    E("partridge_scare",    "Partridge scare",    "wildlife_calm",    -1, "ANY",  ["trekking_pole"], 0, 0.008),
    E("goat_appears",       "Goat appears",       "wildlife_calm",     0, "ANY",  ["drone"], 0, 0.008),
    E("lynx_passing",       "Lynx passing",       "wildlife_calm",     0, "ANY",  ["bear_spray"], 0, 0.008),
    E("pine_cone_fall",     "Pine cone fall",     "wildlife_calm",    -1, "ANY",  ["wool_hat"], 0, 0.008),
    E("wild_boar_distant",  "Wild boar distant",  "wildlife_calm",     0, "ANY",  ["bear_spray"], 0, 0.008),
    E("ants_invade",        "Ants invade bag",    "wildlife_calm",     0, "ANY",  ["waterproof_bag"], 0, 0.008),
    E("fox_sniff_camp",     "Fox sniff camp",     "wildlife_calm",     0, "ANY",  ["whistle"], 0, 0.008),
    E("hawks_overhead",     "Hawks overhead",     "wildlife_calm",     0, "NONE", [], 0, 0.008),
    E("deer_passing",       "Deer passing",       "wildlife_calm",     0, "NONE", [], 0, 0.008),
    E("dog_barking",        "Dog barking",        "wildlife_calm",     0, "ANY",  ["whistle"], 0, 0.008),
    E("bird_droppings",     "Bird droppings",     "wildlife_calm",     0, "ANY",  ["rain_poncho"], 0, 0.008),
    # ---- wildlife attack
    E("bear_nearby",        "Bear nearby",        "wildlife_attack",  -3, "ANY",  ["bear_spray"], -1, 0.008),
    E("mice_chew_rope",     "Mice chew rope",     "wildlife_attack",  -1, "ANY",  ["tent_repair_kit"], 0, 0.008),
    E("snake_under_tarp",   "Snake under tarp",   "wildlife_attack",  -2, "ANY",  ["hiking_boots"], 0, 0.008),
]

# ----------------------------------------------------------------------------
# LOCATIONS — 10 cards, formalised as per-category HP modifiers
# Positive modifier = extra HP loss (worse for player)
# Negative modifier = reduced HP loss (better for player)
# Water multiplier applies to water_collection events that generate water
# ----------------------------------------------------------------------------

LOCATIONS = {
    "lakeside": {
        "display_name": "Lakeside",
        "hp_modifiers": {
            "medical_injury": -1,    # dehydration penalties reduced
        },
        "water_gain_mult": {
            "water_collection": 1.5,
            "weather_wet": 1.5,
        },
        "notes": "Cold exposure unchanged. Water events produce 1.5x more water.",
    },
    "glacier_ridge": {
        "display_name": "Glacier Ridge",
        "hp_modifiers": {
            "weather_cold": -1,      # extra 1 HP damage from cold
            "slip_fall": -1,         # extra 1 HP from slips
        },
        "water_gain_mult": {
            "water_collection": 0.0, # no stove = no water (handled separately)
        },
        "requires_stove_for_water": True,
        "notes": "Cold-weather events cause an extra 1 HP damage. Water events need stove.",
    },
    "deep_forest": {
        "display_name": "Deep Forest",
        "hp_modifiers": {
            "weather_wet": -1,
            "insect": -1,
        },
        "food_gain_bonus": 100,  # food/berry events give +100 kcal
        "notes": "Food/berry events give +100 kcal. Wet-cold and insect events deal extra 1 HP.",
    },
    "valley_floor": {
        "display_name": "Valley Floor",
        "hp_modifiers": {
            "weather_cold": 1,
            "weather_hot": 1,
            "weather_wet": 1,
            "weather_wind": 1,
            "navigation": -1,        # navigation events 1 HP worse (less risk of being lost reduced)
        },
        "water_gain_mult": {
            "water_collection": 1.2,
            "weather_wet": 1.2,
        },
        "notes": "All weather HP reduced by 1. Water events x1.2. Navigation events 1 HP worse.",
    },
    "high_plateau": {
        "display_name": "High Plateau",
        "hp_modifiers": {
            "weather_hot": -1,       # sun/UV worse
            "weather_wind": -1,      # wind worse
            "navigation": 1,         # better visibility -> 1 HP better
        },
        "notes": "Sun/UV and wind events worse by 1 HP. Navigation events better by 1 HP.",
    },
    "scree_slope": {
        "display_name": "Scree Slope",
        "hp_modifiers": {
            "slip_fall": -1,
            "equipment": -1,
        },
        "notes": "Slip/fall and equipment damage events deal extra 1 HP.",
    },
    "cave_mouth": {
        "display_name": "Cave Mouth",
        "hp_modifiers": {
            "weather_cold": 1,
            "food_spoilage": -1,
            "navigation": -1,        # only at night, simplified
        },
        "notes": "Cold night events reduced by 1. Food spoilage and night navigation extra 1 HP.",
    },
    "wind_pass": {
        "display_name": "Wind Pass",
        "hp_modifiers": {
            "weather_wind": -2,
            "weather_wet": -1,
        },
        "notes": "Wind events extra 2 HP. Rain/snow storms extra 1 HP.",
    },
    "boggy_hollow": {
        "display_name": "Boggy Hollow",
        "hp_modifiers": {
            "insect": -1,
            "water_collection": -1,
        },
        "water_purif_required": True,
        "notes": "Water easy but dirty. Insect events extra 1 HP. Without purification water events extra 1 HP.",
    },
    "old_trail": {
        "display_name": "Old Trail",
        "hp_modifiers": {
            "navigation": 2,         # very unlikely to get lost
        },
        "set_to_zero_categories": ["wildlife_calm"],
        "notes": "Navigation events reduced by 2 HP. Wildlife (non-attack) become HP 0.",
    },
}

# ----------------------------------------------------------------------------
# TRAITS — 20 cards
# Drawn AFTER item selection. Not in MILP planning scope.
# Some have one-shot effects (first time X) tracked via 'oneshot_trigger'
# ----------------------------------------------------------------------------

TRAITS = {
    "injured_at_start":   {"name": "Injured at Start",
                           "hp_init_delta": -3,
                           "notes": "Begin with HP -3."},
    "leaky_backpack":     {"name": "Leaky Backpack",
                           "trigger_category": "water_collection",
                           "extra_water_loss_per_event": 1.0,
                           "negated_by_items": ["waterproof_bag"],
                           "notes": "Each water leak event loses extra 1 L unless waterproof bag carried."},
    "lucky_ration":       {"name": "Lucky Ration",
                           "food_init_delta": 600,
                           "notes": "Start with +600 kcal dry food."},
    "fragile_shoelaces":  {"name": "Fragile Shoelaces",
                           "oneshot_trigger": "boot_lace_snap",
                           "oneshot_hp_delta": -1,
                           "negated_by_items": ["duct_tape"],
                           "notes": "First boot lace snap causes HP -1 unless duct tape carried."},
    "cold_sensitive":     {"name": "Cold Sensitive",
                           "hp_modifiers": {"weather_cold": -1, "medical_injury": 0},
                           "negated_by_items": ["down_jacket"],
                           "negation_amount": 1,
                           "notes": "Cold-related events extra 1 HP loss; down jacket cancels 1."},
    "heat_resistant":     {"name": "Heat Resistant",
                           "hp_modifiers": {"weather_hot": 1},
                           "notes": "Hot weather and sun events 1 HP better."},
    "climber":            {"name": "Climber",
                           "hp_modifiers": {"slip_fall": 1},
                           "notes": "Slip or fall events 1 HP better."},
    "allergy_prone":      {"name": "Allergy Prone",
                           "hp_modifiers": {"medical_sting": -1, "insect": -1},
                           "negated_by_items": ["allergy_meds"],
                           "notes": "Bee sting and insect events extra 1 HP unless allergy medicine."},
    "old_batteries":      {"name": "Old Batteries",
                           "oneshot_trigger": "headlamp_dead",
                           "oneshot_hp_delta": -1,
                           "negated_by_items": ["spare_batteries"],
                           "notes": "First headlamp dead causes HP -1 if no spares."},
    "hot_drink_lover":    {"name": "Hot Drink Lover",
                           "trigger_events": ["hot_tea","tea_leaves_found","wild_herb_tea"],
                           "extra_hp_delta": 1,
                           "requires_items": ["stove_fuel","cooking_pot"],
                           "notes": "Hot drink events give +1 extra HP with stove + pot."},
    "clean_freak":        {"name": "Clean Freak",
                           "oneshot_trigger": "berries_sour",
                           "oneshot_hp_delta": -1,
                           "negated_by_items": ["disinfectant"],
                           "notes": "First scavenged food event extra -1 HP without disinfectant."},
    "water_hoarder":      {"name": "Water Hoarder",
                           "condition": "water_carried > 5",
                           "daily_hp_delta": -1,
                           "notes": "If carrying >5L water, suffer HP -1 per day."},
    "light_pack_expert":  {"name": "Light Pack Expert",
                           "condition": "total_weight <= 15",
                           "daily_hp_delta": 1,
                           "notes": "If total weight <=15 kg, recover HP +1 each night."},
    "repair_expert":      {"name": "Repair Expert",
                           "hp_modifiers": {"equipment": 1},
                           "requires_items": ["tent_repair_kit"],
                           "notes": "Equipment damage events 1 HP better with repair kit."},
    "animal_friend":      {"name": "Animal Friend",
                           "set_to_zero_categories": ["wildlife_calm"],
                           "notes": "Non-attack wildlife always HP 0."},
    "night_walker":       {"name": "Night Walker",
                           "hp_modifiers": {"navigation": 1},
                           "requires_items": ["headlamp"],
                           "notes": "Night/darkness events 1 HP better with headlamp."},
    "coffee_bonus":       {"name": "Coffee Bonus",
                           "oneshot_trigger_category": "medical_illness",
                           "oneshot_set_to_zero": True,
                           "requires_items": ["coffee_press","stove_fuel"],
                           "notes": "First fatigue/headache event becomes HP 0 with coffee press + stove."},
    "picky_eater":        {"name": "Picky Eater",
                           "hp_modifiers": {"food_spoilage": -1},
                           "notes": "Raw/uncooked food events always extra -1 HP."},
    "backup_hammock":     {"name": "Backup Hammock",
                           "condition": "no_tent_or_tarp",
                           "hp_modifiers": {"weather_wet": 1},
                           "notes": "If no tent/tarp on rainy nights, exposure reduced by 1 HP."},
    "old_rope":           {"name": "Old Rope",
                           "oneshot_trigger_category": "slip_fall",
                           "oneshot_hp_delta": -1,
                           "negated_by_items": ["rope_tool_kit","climbing_rope"],
                           "notes": "First cliff/river crossing event extra -1 HP without rope/tool kit."},
}

# ----------------------------------------------------------------------------
# PARAMETERS — Calibration values
# ----------------------------------------------------------------------------

PARAMETERS = {
    "horizon_days": 50,
    "hp_initial": 20,
    "water_initial_L": 6.0,
    "food_initial_kcal": 6000,

    "weight_cap_kg": 20.0,
    "volume_cap_L": 80.0,

    # daily baseline consumption
    "baseline_water_L_per_day": 0.5,
    "baseline_food_kcal_per_day": 500,

    # carrying penalty
    "carrying_threshold_kg": 15.0,
    "carrying_penalty_hp_per_kg_per_day": 0.1,

    # end-game scoring (Option C: capped)
    "endgame_water_L_per_hp": 1.0,
    "endgame_food_kcal_per_hp": 1000,
    "endgame_water_hp_cap": 5,
    "endgame_food_hp_cap": 10,

    # elimination
    "dehydration_days_max": 3,
    "starvation_days_max": 10,
    "starvation_kcal_threshold": 500,

    # event sampling scheme
    "event_sampling_scheme": "A_plus",  # A=Bernoulli only; A_plus = A + scheduled calendar
    "expected_events_per_day_target": 1.59,

    # water gain per water_collection event (base, before location multipliers)
    "water_gain_base_L": 1.0,
    "food_gain_base_kcal": 300,

    # calendar for Scheme A+
    # rest days override Scheme A: no random events, no baseline consumption, +1 HP
    # fortune days override Scheme A: one scheduled bonus event from the pool
    "calendar": {
        "rest_days": [10, 20, 30, 40, 50],
        "fortune_days": {
            "7":  ["foraging_success", "wild_herb_garden", "treasure_found"],
            "17": ["foraging_success", "clear_lake"],
            "25": ["treasure_found", "wild_herb_garden", "shelter_cave"],
            "33": ["successful_haunt", "shelter_cave", "treasure_found"],
            "43": ["foraging_success", "successful_haunt", "clear_lake"]
        }
    }
}

# ----------------------------------------------------------------------------
# OUTPUT
# ----------------------------------------------------------------------------

def main():
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # items.csv
    with open("items.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id","name","weight_kg","volume_L","category","kcal","litres","is_wearable"])
        for row in ITEMS:
            w.writerow(row)

    # events.csv
    with open("events.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id","name","category","base_hp","mit_logic","mit_set","mit_hp","raw_prob"])
        for ev in EVENTS:
            id, name, cat, hp, logic, mset, mhp, p = ev
            w.writerow([id, name, cat, hp, logic, "|".join(mset), mhp, p])

    # locations.json
    with open("locations.json", "w") as f:
        json.dump(LOCATIONS, f, indent=2)

    # traits.json
    with open("traits.json", "w") as f:
        json.dump(TRAITS, f, indent=2)

    # parameters.json (yaml not installed by default; using json for portability)
    with open("parameters.json", "w") as f:
        json.dump(PARAMETERS, f, indent=2)

    # quick summary
    sum_p = sum(e[7] for e in EVENTS)
    print(f"Items     : {len(ITEMS)}")
    print(f"Events    : {len(EVENTS)}")
    print(f"Locations : {len(LOCATIONS)}")
    print(f"Traits    : {len(TRAITS)}")
    print(f"Sum of raw_prob across events: {sum_p:.4f}")
    print(f"Expected events per day (Scheme A): {sum_p:.3f}")
    print()
    by_cat = {}
    for ev in EVENTS:
        by_cat[ev[2]] = by_cat.get(ev[2], 0) + ev[7]
    print("Per-category expected events per day:")
    for cat, p in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {cat:24s}  {p:.4f}")

if __name__ == "__main__":
    main()
