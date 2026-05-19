"""
app.py — Survival Knapsack Game (Streamlit)

Run:  streamlit run app.py

Requirements: streamlit, (optional) pulp
All data files (parameters.json, events.csv, items.csv, etc.) must be
in the same directory.
"""

import streamlit as st
import random
import json
from pathlib import Path
from collections import defaultdict
from gamedata import load_all, mitigates, inventory_summary, feasible
from simulator import _compute_hp_delta
from calendar_gen import generate_calendar

DATA_DIR = str(Path(__file__).parent)

# ── Category display names (no mechanical detail) ──────────────────────────
CAT_NARRATIVE = {
    "weather_cold":    "🥶  Cold weather strikes.",
    "weather_hot":     "🔥  Scorching heat bears down.",
    "weather_wet":     "🌧️  Rain and dampness set in.",
    "weather_wind":    "💨  Strong winds batter the camp.",
    "weather_neutral": "🌤️  Mild weather — nothing dramatic.",
    "medical_injury":  "🩹  Someone in the group is hurt.",
    "medical_illness": "🤒  Illness threatens the team.",
    "medical_sting":   "🐝  A sting or bite causes trouble.",
    "insect":          "🪲  Insects swarm the area.",
    "navigation":      "🧭  The group struggles with direction.",
    "slip_fall":       "⛰️  Treacherous footing ahead.",
    "equipment":       "🔧  Gear trouble — something breaks.",
    "food_spoilage":   "🍄  Food-related problem.",
    "water_collection":"💧  Water situation changes.",
    "wildlife_calm":   "🦌  Wildlife nearby.",
    "wildlife_attack": "🐻  Dangerous animal encounter!",
    "bonus_morale":    "☀️  A moment of calm and recovery.",
}


# ═══════════════════════════════════════════════════════════════════════════
#  Session State Initialisation
# ═══════════════════════════════════════════════════════════════════════════

def init():
    if "phase" not in st.session_state:
        st.session_state.phase = "setup"
        st.session_state.data = load_all(DATA_DIR)
        st.session_state.teams = []
        st.session_state.seed = 42
        st.session_state.current_day = 0
        st.session_state.calendar = []
        st.session_state.daily_events_cache = {}
        st.session_state.team_states = {}


# ═══════════════════════════════════════════════════════════════════════════
#  Phase 1: Setup
# ═══════════════════════════════════════════════════════════════════════════

def render_setup():
    st.title("🎒 Running Wild — Survival Knapsack Game")
    st.markdown("### Instructor Setup")

    seed = st.number_input("Game seed", min_value=0, max_value=99999,
                           value=st.session_state.seed, step=1)
    st.session_state.seed = int(seed)

    n_teams = st.number_input("Number of teams", min_value=1, max_value=20,
                              value=max(len(st.session_state.teams), 4), step=1)

    loc_ids = list(st.session_state.data.locations.keys())
    loc_names = {k: v.display_name for k, v in st.session_state.data.locations.items()}

    # build team rows
    teams = []
    for i in range(int(n_teams)):
        cols = st.columns([2, 3])
        default_name = st.session_state.teams[i]["name"] if i < len(st.session_state.teams) else f"Team {i+1}"
        default_loc = st.session_state.teams[i]["location_id"] if i < len(st.session_state.teams) else loc_ids[i % len(loc_ids)]
        with cols[0]:
            name = st.text_input(f"Name", value=default_name, key=f"tname_{i}", label_visibility="collapsed",
                                 placeholder=f"Team {i+1}")
        with cols[1]:
            loc = st.selectbox(f"Location", loc_ids, index=loc_ids.index(default_loc),
                               format_func=lambda x: loc_names[x], key=f"tloc_{i}",
                               label_visibility="collapsed")
        teams.append({"name": name, "location_id": loc, "inventory": set(), "trait_id": None})

    if st.button("✅  Confirm teams → Item selection", type="primary"):
        st.session_state.teams = teams
        st.session_state.phase = "item_selection"
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
#  Phase 2: Item Selection
# ═══════════════════════════════════════════════════════════════════════════

def render_item_selection():
    data = st.session_state.data
    params = data.parameters
    st.title("🎒 Item Selection")

    team_idx = st.selectbox("Select team to edit",
                            range(len(st.session_state.teams)),
                            format_func=lambda i: st.session_state.teams[i]["name"])
    team = st.session_state.teams[team_idx]

    # group items by category
    items_by_cat = defaultdict(list)
    for it in data.items.values():
        items_by_cat[it.category].append(it)

    cat_display = {
        "shelter": "🏕️ Shelter", "clothing": "🧥 Clothing", "nav_light": "🔦 Navigation & Light",
        "tools": "🔧 Tools", "fire_cook": "🔥 Fire & Cooking", "food": "🍖 Food",
        "water": "💧 Water", "storage": "📦 Storage", "signal": "📡 Signalling",
        "medical": "🩹 Medical & Hygiene", "defence": "🐻 Defence", "morale": "📖 Morale",
    }

    current_inv = team["inventory"].copy()

    for cat_id, cat_label in cat_display.items():
        if cat_id not in items_by_cat:
            continue
        with st.expander(cat_label, expanded=False):
            for it in sorted(items_by_cat[cat_id], key=lambda x: x.name):
                checked = it.id in current_inv
                extra = ""
                if it.kcal > 0:
                    extra = f" — {it.kcal} kcal"
                if it.litres > 0:
                    extra = f" — {it.litres} L"
                label = f"{it.name}  ({it.weight_kg}kg, {it.volume_L}L){extra}"
                if st.checkbox(label, value=checked, key=f"item_{team_idx}_{it.id}"):
                    current_inv.add(it.id)
                else:
                    current_inv.discard(it.id)

    team["inventory"] = current_inv
    st.session_state.teams[team_idx] = team

    # budget display
    summ = inventory_summary(current_inv, data.items)
    w_pct = summ["weight_kg"] / params["weight_cap_kg"]
    v_pct = summ["volume_L"] / params["volume_cap_L"]
    over = w_pct > 1.0 or v_pct > 1.0

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("Items", summ["n_items"])
    col2.metric("Weight", f"{summ['weight_kg']} / {params['weight_cap_kg']} kg",
                delta=f"{'⚠️ OVER' if w_pct > 1 else ''}")
    col3.metric("Volume", f"{summ['volume_L']} / {params['volume_cap_L']} L",
                delta=f"{'⚠️ OVER' if v_pct > 1 else ''}")

    col4, col5 = st.columns(2)
    col4.metric("Food carried", f"{summ['kcal']} kcal")
    col5.metric("Water carried", f"{summ['litres']} L")

    st.progress(min(w_pct, 1.0), text=f"Weight: {w_pct:.0%}")
    st.progress(min(v_pct, 1.0), text=f"Volume: {v_pct:.0%}")

    if over:
        st.error("Over budget! Remove items before submitting.")

    # check all teams submitted
    st.markdown("---")
    st.markdown("### Team readiness")
    all_ready = True
    for i, t in enumerate(st.session_state.teams):
        n = len(t["inventory"])
        s = inventory_summary(t["inventory"], data.items)
        ok, _ = feasible(t["inventory"], data)
        status = "✅" if (n > 0 and ok) else "❌"
        if not (n > 0 and ok):
            all_ready = False
        st.write(f"{status}  **{t['name']}** — {n} items, {s['weight_kg']}kg")

    if all_ready and st.button("🚀  All teams ready → Start game!", type="primary"):
        _start_game()
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
#  Game start — pre-compute simulations
# ═══════════════════════════════════════════════════════════════════════════

def _start_game():
    data = st.session_state.data
    params = data.parameters
    seed = st.session_state.seed
    horizon = params["horizon_days"]
    calendar = generate_calendar(seed, horizon, DATA_DIR)
    st.session_state.calendar = calendar

    # assign traits (drawn AFTER item submission)
    trait_ids = list(data.traits.keys())
    trait_rng = random.Random(seed + 9999)
    for i, team in enumerate(st.session_state.teams):
        team["trait_id"] = trait_rng.choice(trait_ids)

    # pre-generate daily events (shared across all teams, from seed)
    rng = random.Random(seed)
    scheduled = json.load(open(Path(DATA_DIR) / "scheduled_events.json"))
    daily_events = []

    for day_idx in range(horizon):
        cal = calendar[day_idx]
        if cal["type"] == "rest":
            daily_events.append({"type": "rest", "events": [], "fortune": None})
        elif cal["type"] == "fortune":
            daily_events.append({"type": "fortune", "events": [], "fortune": cal["scheduled"]})
        else:
            # Scheme A: per-event Bernoulli
            fired = []
            for ev in data.events.values():
                if rng.random() < ev.raw_prob:
                    fired.append(ev.id)
            daily_events.append({"type": "normal", "events": fired, "fortune": None})

    st.session_state.daily_events_cache = daily_events

    # initialise per-team state
    for i, team in enumerate(st.session_state.teams):
        trait = data.traits.get(team["trait_id"])
        hp = float(params["hp_initial"])
        food = int(params["food_initial_kcal"])
        water = float(params["water_initial_L"])
        if trait:
            hp += trait.raw.get("hp_init_delta", 0)
            food += trait.raw.get("food_init_delta", 0)
        total_w = sum(data.items[j].weight_kg for j in team["inventory"] if j in data.items)

        st.session_state.team_states[i] = {
            "hp": hp, "water": water, "food": food,
            "alive": True, "death_day": None, "death_cause": None,
            "c_water": 0, "c_food": 0,
            "total_weight": total_w,
            "hp_history": [hp], "water_history": [water], "food_history": [food],
        }

    st.session_state.current_day = 0
    st.session_state.phase = "playing"


# ═══════════════════════════════════════════════════════════════════════════
#  Phase 3: Game Play
# ═══════════════════════════════════════════════════════════════════════════

def _advance_day():
    data = st.session_state.data
    params = data.parameters
    day_idx = st.session_state.current_day
    daily = st.session_state.daily_events_cache[day_idx]
    scheduled = json.load(open(Path(DATA_DIR) / "scheduled_events.json"))

    for i, team in enumerate(st.session_state.teams):
        state = st.session_state.team_states[i]
        if not state["alive"]:
            state["hp_history"].append(state["hp"])
            state["water_history"].append(state["water"])
            state["food_history"].append(state["food"])
            continue

        inv = team["inventory"]
        loc = data.locations.get(team["location_id"])
        trait = data.traits.get(team["trait_id"])
        daily_kcal = 0

        if daily["type"] == "rest":
            state["hp"] += 1

        elif daily["type"] == "fortune":
            fdata = scheduled["fortune_events"].get(daily["fortune"], {})
            skip = fdata.get("skip_consumption", False)
            if not skip:
                state["water"] = max(0, state["water"] - params["baseline_water_L_per_day"])
                consumed = min(state["food"], params["baseline_food_kcal_per_day"])
                state["food"] -= consumed
                daily_kcal += consumed
            state["hp"] += fdata.get("hp_delta", 0)
            w_gain = fdata.get("water_gain_L", 0)
            if "requires_items_pool" in fdata:
                if not any(j in inv for j in fdata["requires_items_pool"]):
                    w_gain = fdata.get("fallback_water_gain_L", 0)
            state["water"] += w_gain
            state["food"] += fdata.get("food_gain_kcal", 0)

        else:  # normal
            state["water"] = max(0, state["water"] - params["baseline_water_L_per_day"])
            consumed = min(state["food"], params["baseline_food_kcal_per_day"])
            state["food"] -= consumed
            daily_kcal += consumed

            for ev_id in daily["events"]:
                ev = data.events[ev_id]
                hp_delta = _compute_hp_delta(inv, ev, loc, trait)
                if ev.category == "bonus_morale" and ev.mit_logic != "NONE":
                    is_met = mitigates(inv, ev)
                    hp_delta = ev.base_hp if is_met else ev.mit_hp
                state["hp"] += hp_delta
                if ev.category == "water_collection":
                    w_mult = 1.0
                    if loc:
                        w_mult = loc.water_gain_mult.get("water_collection", 1.0)
                        if loc.requires_stove_for_water and "stove_fuel" not in inv:
                            w_mult = 0.0
                    state["water"] += params["water_gain_base_L"] * w_mult

        # carrying penalty
        penalty = params["carrying_penalty_hp_per_kg_per_day"] * max(0, state["total_weight"] - params["carrying_threshold_kg"])
        state["hp"] -= penalty

        # trait daily
        if trait:
            raw = trait.raw
            if raw.get("condition") == "total_weight <= 15" and state["total_weight"] <= 15:
                state["hp"] += raw.get("daily_hp_delta", 0)
            if raw.get("condition") == "water_carried > 5":
                carried_l = sum(data.items[j].litres for j in inv if j in data.items)
                if carried_l > 5:
                    state["hp"] += raw.get("daily_hp_delta", 0)

        # counters
        if state["water"] <= 0:
            state["c_water"] += 1
            state["water"] = 0
        else:
            state["c_water"] = 0

        if daily["type"] != "rest" and daily_kcal < params["starvation_kcal_threshold"]:
            state["c_food"] += 1
        else:
            state["c_food"] = 0

        # elimination
        if state["hp"] <= 0:
            state["alive"] = False
            state["death_day"] = day_idx + 1
            state["death_cause"] = "HP reached zero"
        elif state["c_water"] >= params["dehydration_days_max"]:
            state["alive"] = False
            state["death_day"] = day_idx + 1
            state["death_cause"] = "Dehydration"
        elif state["c_food"] >= params["starvation_days_max"]:
            state["alive"] = False
            state["death_day"] = day_idx + 1
            state["death_cause"] = "Starvation"

        state["hp_history"].append(round(state["hp"], 1))
        state["water_history"].append(round(state["water"], 1))
        state["food_history"].append(state["food"])

    st.session_state.current_day += 1


def render_game_play():
    data = st.session_state.data
    params = data.parameters
    horizon = params["horizon_days"]
    day = st.session_state.current_day  # 0-indexed days completed

    st.title("🎒 Running Wild")

    # progress
    st.progress(day / horizon, text=f"Day {day} / {horizon}")

    # show current day's info if we've advanced
    if day > 0:
        daily = st.session_state.daily_events_cache[day - 1]
        day_num = day

        # event display
        if daily["type"] == "rest":
            st.success(f"### 🏕️  Day {day_num} — Rest Day\nNo events. No consumption. Everyone recovers +1 HP.")
        elif daily["type"] == "fortune":
            scheduled = json.load(open(Path(DATA_DIR) / "scheduled_events.json"))
            fdata = scheduled["fortune_events"].get(daily["fortune"], {})
            fname = fdata.get("name", daily["fortune"])
            notes = fdata.get("notes", "")
            st.info(f"### 🎁  Day {day_num} — Fortune: {fname}\n{notes}")
        else:
            fired = daily["events"]
            if not fired:
                st.info(f"### Day {day_num}\nNothing happened today. Quiet day.")
            else:
                st.warning(f"### ⚡  Day {day_num} — {len(fired)} event(s)")
                for ev_id in fired:
                    ev = data.events.get(ev_id)
                    if ev:
                        narrative = CAT_NARRATIVE.get(ev.category, "Something happened.")
                        st.markdown(f"**{ev.name}** — {narrative}")

        # team status table
        st.markdown("---")
        cols = st.columns(len(st.session_state.teams))
        for i, team in enumerate(st.session_state.teams):
            state = st.session_state.team_states[i]
            with cols[i]:
                if state["alive"]:
                    # HP change
                    if len(state["hp_history"]) >= 2:
                        delta = state["hp_history"][-1] - state["hp_history"][-2]
                        delta_str = f"{delta:+.1f}" if delta != 0 else "±0"
                    else:
                        delta_str = ""

                    st.metric(team["name"], f"❤️ {state['hp']:.1f}", delta_str)
                    st.caption(f"💧 {state['water']:.1f}L  |  🍖 {state['food']} kcal")

                    # HP bar
                    hp_pct = max(0, min(1, state["hp"] / params["hp_initial"]))
                    st.progress(hp_pct)
                else:
                    st.error(f"**{team['name']}**\n💀 Day {state['death_day']}\n{state['death_cause']}")

    else:
        # day 0: show initial state
        st.info("Game ready. Press **Next Day** to begin.")
        cols = st.columns(len(st.session_state.teams))
        for i, team in enumerate(st.session_state.teams):
            state = st.session_state.team_states[i]
            trait = data.traits.get(team["trait_id"])
            loc = data.locations.get(team["location_id"])
            with cols[i]:
                st.markdown(f"**{team['name']}**")
                st.write(f"📍 {loc.display_name if loc else '?'}")
                st.write(f"🃏 {trait.name if trait else '?'}")
                st.write(f"❤️ HP {state['hp']:.0f}  |  💧 {state['water']}L  |  🍖 {state['food']} kcal")
                st.write(f"🎒 {len(team['inventory'])} items, {state['total_weight']:.1f}kg")

    # controls
    st.markdown("---")
    alive_count = sum(1 for s in st.session_state.team_states.values() if s["alive"])

    if day < horizon and alive_count > 0:
        if st.button(f"▶️  Next Day (Day {day + 1})", type="primary", use_container_width=True):
            _advance_day()
            st.rerun()
    else:
        if day >= horizon:
            st.success("🏁  Game over — 50 days survived!")
        else:
            st.error("💀  All teams eliminated!")
        st.session_state.phase = "finished"
        st.rerun()

    # expandable history
    with st.expander("📊 HP History Chart"):
        import pandas as pd
        chart_data = {}
        for i, team in enumerate(st.session_state.teams):
            state = st.session_state.team_states[i]
            chart_data[team["name"]] = state["hp_history"]
        max_len = max(len(v) for v in chart_data.values())
        for k in chart_data:
            while len(chart_data[k]) < max_len:
                chart_data[k].append(chart_data[k][-1])
        df = pd.DataFrame(chart_data, index=range(max_len))
        df.index.name = "Day"
        st.line_chart(df)


# ═══════════════════════════════════════════════════════════════════════════
#  Phase 4: Scoreboard
# ═══════════════════════════════════════════════════════════════════════════

def render_scoreboard():
    data = st.session_state.data
    params = data.parameters
    st.title("🏆  Final Scoreboard")

    results = []
    for i, team in enumerate(st.session_state.teams):
        state = st.session_state.team_states[i]
        if state["alive"]:
            w_bonus = min(params["endgame_water_hp_cap"],
                          int(state["water"] / params["endgame_water_L_per_hp"]))
            f_bonus = min(params["endgame_food_hp_cap"],
                          int(state["food"] / params["endgame_food_kcal_per_hp"]))
            final_hp = state["hp"] + w_bonus + f_bonus
            results.append({
                "Team": team["name"],
                "Status": "✅ Survived",
                "Final HP": round(final_hp, 1),
                "HP (raw)": round(state["hp"], 1),
                "Water bonus": w_bonus,
                "Food bonus": f_bonus,
                "Water left": f"{state['water']:.1f}L",
                "Food left": f"{state['food']} kcal",
            })
        else:
            results.append({
                "Team": team["name"],
                "Status": f"💀 Day {state['death_day']}",
                "Final HP": -999,
                "HP (raw)": round(state["hp"], 1),
                "Water bonus": 0,
                "Food bonus": 0,
                "Water left": f"{state['water']:.1f}L",
                "Food left": f"{state['food']} kcal",
            })

    results.sort(key=lambda r: -r["Final HP"])

    # podium
    for rank, r in enumerate(results):
        if r["Final HP"] > 0:
            medal = ["🥇", "🥈", "🥉"][rank] if rank < 3 else f"#{rank+1}"
            st.markdown(f"### {medal}  {r['Team']}  —  HP {r['Final HP']}")
            st.caption(f"Raw HP: {r['HP (raw)']}  |  Water +{r['Water bonus']}  |  Food +{r['Food bonus']}  |  {r['Water left']} water, {r['Food left']} food remaining")
        else:
            st.markdown(f"### 💀  {r['Team']}  —  {r['Status']}")
            st.caption(f"Cause: {st.session_state.team_states[results.index(r)].get('death_cause','?')}")

    # HP history chart
    st.markdown("---")
    st.markdown("### HP Trajectory")
    import pandas as pd
    chart_data = {}
    for i, team in enumerate(st.session_state.teams):
        state = st.session_state.team_states[i]
        chart_data[team["name"]] = state["hp_history"]
    max_len = max(len(v) for v in chart_data.values())
    for k in chart_data:
        while len(chart_data[k]) < max_len:
            chart_data[k].append(chart_data[k][-1])
    df = pd.DataFrame(chart_data, index=range(max_len))
    df.index.name = "Day"
    st.line_chart(df)

    # restart
    st.markdown("---")
    if st.button("🔄  New Game", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="Running Wild — Survival Knapsack",
        page_icon="🎒",
        layout="wide",
    )
    init()

    # sidebar navigation
    with st.sidebar:
        st.markdown("## 🎒 Running Wild")
        phase = st.session_state.phase
        phases = ["setup", "item_selection", "playing", "finished"]
        labels = ["⚙️ Setup", "🎒 Items", "🎮 Play", "🏆 Score"]
        for p, l in zip(phases, labels):
            if p == phase:
                st.markdown(f"**→ {l}**")
            else:
                st.markdown(f"  {l}")

        st.markdown("---")
        if phase in ("item_selection", "playing"):
            st.caption(f"Seed: {st.session_state.seed}")
            st.caption(f"Teams: {len(st.session_state.teams)}")
        if phase == "playing":
            alive = sum(1 for s in st.session_state.team_states.values() if s["alive"])
            st.caption(f"Day: {st.session_state.current_day}")
            st.caption(f"Alive: {alive}/{len(st.session_state.teams)}")

    # render current phase
    if st.session_state.phase == "setup":
        render_setup()
    elif st.session_state.phase == "item_selection":
        render_item_selection()
    elif st.session_state.phase == "playing":
        render_game_play()
    elif st.session_state.phase == "finished":
        render_scoreboard()


if __name__ == "__main__":
    main()