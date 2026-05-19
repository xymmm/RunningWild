"""
app.py - Running Wild: Survival Knapsack Game (Multi-user Streamlit)

Students and instructor open the same URL.
Students: join with game code, select items, submit.
Instructor: create game, monitor submissions, run simulation.

Run:  streamlit run app.py
"""

import streamlit as st
import random
import json
import time
from pathlib import Path
from collections import defaultdict
from gamedata import load_all, mitigates, inventory_summary, feasible
from simulator import _compute_hp_delta
from calendar_gen import generate_calendar
from shared_state import create_game, get_game, update_game, submit_team

DATA_DIR = str(Path(__file__).parent)

CAT_NARRATIVE = {
    "weather_cold": "🥶 Cold weather strikes.",
    "weather_hot": "🔥 Scorching heat bears down.",
    "weather_wet": "🌧️ Rain and dampness set in.",
    "weather_wind": "💨 Strong winds batter the camp.",
    "weather_neutral": "🌤️ Mild weather.",
    "medical_injury": "🩹 Someone in the group is hurt.",
    "medical_illness": "🤒 Illness threatens the team.",
    "medical_sting": "🐝 A sting or bite causes trouble.",
    "insect": "🪲 Insects swarm the area.",
    "navigation": "🧭 The group struggles with direction.",
    "slip_fall": "⛰️ Treacherous footing ahead.",
    "equipment": "🔧 Gear trouble.",
    "food_spoilage": "🍄 Food-related problem.",
    "water_collection": "💧 Water situation changes.",
    "wildlife_calm": "🦌 Wildlife nearby.",
    "wildlife_attack": "🐻 Dangerous animal encounter!",
    "bonus_morale": "☀️ A moment of calm and recovery.",
}


def init():
    if "role" not in st.session_state:
        st.session_state.role = None
        st.session_state.game_code = None
        st.session_state.team_name = None
        st.session_state.data = load_all(DATA_DIR)
        st.session_state.submitted = False
        st.session_state.inst_phase = "create"
        st.session_state.current_day = 0
        st.session_state.daily_events_cache = []
        st.session_state.team_states = {}
        st.session_state.calendar = []
        st.session_state.team_list = []


# ---- Landing ----

def render_landing():
    st.title("🎒 Running Wild")
    st.markdown("### Survival Knapsack Game")
    st.markdown("---")
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### 👨‍🎓 Student")
        st.caption("Join a game and select your backpack.")
        if st.button("Join Game", type="primary", use_container_width=True):
            st.session_state.role = "student"
            st.rerun()
    with col2:
        st.markdown("#### 👩‍🏫 Instructor")
        st.caption("Create and run a game session.")
        if st.button("Create / Manage Game", type="primary", use_container_width=True):
            st.session_state.role = "instructor"
            st.rerun()


# ---- Student Flow ----

def render_student():
    st.title("🎒 Running Wild — Student")
    if not st.session_state.game_code:
        _student_join()
    elif not st.session_state.submitted:
        _student_items()
    else:
        _student_waiting()


def _student_join():
    st.markdown("### Join a Game")
    code = st.text_input("Game code (from your instructor)", max_chars=6, placeholder="e.g. 4521")
    name = st.text_input("Your team name", max_chars=30, placeholder="e.g. Team Alpha")
    if code and name:
        game = get_game(code)
        if game is None:
            st.error("Game not found. Check the code.")
        elif game["phase"] != "lobby":
            st.error("This game has already started.")
        elif name in game["teams"]:
            st.warning(f"Team '{name}' already exists.")
        elif st.button("✅ Join", type="primary"):
            st.session_state.game_code = code
            st.session_state.team_name = name
            st.rerun()


def _student_items():
    data = st.session_state.data
    params = data.parameters
    game = get_game(st.session_state.game_code)
    if not game or game["phase"] != "lobby":
        st.error("Game is no longer accepting submissions.")
        return

    st.markdown(f"### Select your backpack — {st.session_state.team_name}")

    loc_ids = list(data.locations.keys())
    loc_names = {k: v.display_name for k, v in data.locations.items()}
    loc = st.selectbox("Your location card", loc_ids, format_func=lambda x: loc_names[x])

    items_by_cat = defaultdict(list)
    for it in data.items.values():
        items_by_cat[it.category].append(it)

    cat_labels = {
        "shelter": "🏕️ Shelter", "clothing": "🧥 Clothing",
        "nav_light": "🔦 Navigation & Light", "tools": "🔧 Tools",
        "fire_cook": "🔥 Fire & Cooking", "food": "🍖 Food",
        "water": "💧 Water", "storage": "📦 Storage",
        "signal": "📡 Signalling", "medical": "🩹 Medical & Hygiene",
        "defence": "🐻 Defence", "morale": "📖 Morale",
    }

    selected = set()
    for cat_id, label in cat_labels.items():
        if cat_id not in items_by_cat:
            continue
        with st.expander(label):
            for it in sorted(items_by_cat[cat_id], key=lambda x: x.name):
                extra = ""
                if it.kcal > 0:
                    extra = f" | {it.kcal} kcal"
                if it.litres > 0:
                    extra = f" | {it.litres} L"
                if st.checkbox(f"{it.name}  ({it.weight_kg}kg, {it.volume_L}L{extra})", key=f"s_{it.id}"):
                    selected.add(it.id)

    summ = inventory_summary(selected, data.items)
    w_pct = summ["weight_kg"] / params["weight_cap_kg"]
    v_pct = summ["volume_L"] / params["volume_cap_L"]
    over = w_pct > 1.0 or v_pct > 1.0

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Items", summ["n_items"])
    c2.metric("Weight", f"{summ['weight_kg']}/{params['weight_cap_kg']}kg")
    c3.metric("Food", f"{summ['kcal']} kcal")
    c4.metric("Water", f"{summ['litres']} L")
    st.progress(min(w_pct, 1.0), text=f"Weight: {w_pct:.0%}")
    st.progress(min(v_pct, 1.0), text=f"Volume: {v_pct:.0%}")

    if over:
        st.error("⚠️ Over budget! Remove items.")
    elif len(selected) > 0:
        if st.button("📤 Submit backpack", type="primary", use_container_width=True):
            ok = submit_team(st.session_state.game_code, st.session_state.team_name, list(selected), loc)
            if ok:
                st.session_state.submitted = True
                st.rerun()
            else:
                st.error("Submission failed.")


def _student_waiting():
    st.markdown(f"### ✅ Submitted — {st.session_state.team_name}")
    st.info("Waiting for the instructor to start the game. Watch the big screen!")
    game = get_game(st.session_state.game_code)
    if game:
        st.metric("Teams joined", len(game["teams"]))
        if game["phase"] == "playing":
            st.success("🎮 Game has started!")
        elif game["phase"] == "finished":
            st.success("🏆 Game is over!")
    time.sleep(4)
    st.rerun()


# ---- Instructor Flow ----

def render_instructor():
    phase = st.session_state.inst_phase
    if phase == "create":
        _inst_create()
    elif phase == "lobby":
        _inst_lobby()
    elif phase == "playing":
        _inst_play()
    elif phase == "finished":
        _inst_scoreboard()


def _inst_create():
    st.title("🎒 Running Wild — Instructor")
    st.markdown("### Create a new game")
    seed = st.number_input("Game seed", 0, 99999, 42)
    if st.button("🎲 Create Game", type="primary"):
        code = str(random.randint(1000, 9999))
        create_game(code, int(seed), "instructor")
        st.session_state.game_code = code
        st.session_state.inst_phase = "lobby"
        st.rerun()
    st.markdown("---")
    st.markdown("### Or rejoin existing game")
    existing = st.text_input("Game code", max_chars=6)
    if existing and st.button("Rejoin"):
        game = get_game(existing)
        if game:
            st.session_state.game_code = existing
            st.session_state.inst_phase = {"lobby": "lobby", "playing": "lobby", "finished": "finished"}.get(game["phase"], "lobby")
            st.rerun()
        else:
            st.error("Not found.")


def _inst_lobby():
    code = st.session_state.game_code
    st.title("🎒 Running Wild — Lobby")
    st.markdown(f"## Game code:  `{code}`")
    st.caption("Share this code with your students.")

    game = get_game(code)
    if not game:
        st.error("Game not found.")
        return

    teams = game.get("teams", {})
    data = st.session_state.data
    st.markdown(f"### Teams joined: {len(teams)}")
    for tname, tdata in teams.items():
        inv = set(tdata.get("inventory", []))
        s = inventory_summary(inv, data.items)
        loc_name = data.locations[tdata["location_id"]].display_name if tdata.get("location_id") else "?"
        st.write(f"✅ **{tname}** — 📍{loc_name} — {s['n_items']} items, {s['weight_kg']}kg")

    if len(teams) >= 1:
        if st.button("🚀 Start Game!", type="primary", use_container_width=True):
            _start_game(code)
            st.rerun()

    st.caption("Auto-refreshing every 5 seconds...")
    time.sleep(5)
    st.rerun()


def _start_game(code):
    data = st.session_state.data
    params = data.parameters
    game = get_game(code)
    seed = game["seed"]
    horizon = params["horizon_days"]

    trait_ids = list(data.traits.keys())
    trait_rng = random.Random(seed + 9999)
    teams_ordered = list(game["teams"].items())
    for tname, tdata in teams_ordered:
        tdata["trait_id"] = trait_rng.choice(trait_ids)

    calendar = generate_calendar(seed, horizon, DATA_DIR)
    st.session_state.calendar = calendar

    rng = random.Random(seed)
    daily_events = []
    for day_idx in range(horizon):
        cal = calendar[day_idx]
        if cal["type"] == "rest":
            daily_events.append({"type": "rest", "events": [], "fortune": None})
        elif cal["type"] == "fortune":
            daily_events.append({"type": "fortune", "events": [], "fortune": cal["scheduled"]})
        else:
            fired = [ev.id for ev in data.events.values() if rng.random() < ev.raw_prob]
            daily_events.append({"type": "normal", "events": fired, "fortune": None})
    st.session_state.daily_events_cache = daily_events

    team_states = {}
    team_list = []
    for tname, tdata in teams_ordered:
        inv = set(tdata.get("inventory", []))
        trait = data.traits.get(tdata["trait_id"])
        hp = float(params["hp_initial"])
        food = int(params["food_initial_kcal"])
        water = float(params["water_initial_L"])
        if trait:
            hp += trait.raw.get("hp_init_delta", 0)
            food += trait.raw.get("food_init_delta", 0)
        total_w = sum(data.items[j].weight_kg for j in inv if j in data.items)
        team_states[tname] = {
            "hp": hp, "water": water, "food": food,
            "alive": True, "death_day": None, "death_cause": None,
            "c_water": 0, "c_food": 0, "total_weight": total_w,
            "hp_history": [hp], "water_history": [water], "food_history": [food],
        }
        team_list.append({"name": tname, "inventory": inv, "location_id": tdata["location_id"], "trait_id": tdata["trait_id"]})

    st.session_state.team_states = team_states
    st.session_state.team_list = team_list
    st.session_state.current_day = 0
    st.session_state.inst_phase = "playing"
    update_game(code, lambda s: s.update({"phase": "playing"}) or s)


def _advance_day():
    data = st.session_state.data
    params = data.parameters
    day_idx = st.session_state.current_day
    daily = st.session_state.daily_events_cache[day_idx]
    scheduled = json.load(open(Path(DATA_DIR) / "scheduled_events.json"))

    for team in st.session_state.team_list:
        tname = team["name"]
        state = st.session_state.team_states[tname]
        if not state["alive"]:
            for k in ("hp_history", "water_history", "food_history"):
                state[k].append(state[k][-1])
            continue

        inv = team["inventory"]
        loc = data.locations.get(team["location_id"])
        trait = data.traits.get(team["trait_id"])
        daily_kcal = 0

        if daily["type"] == "rest":
            state["hp"] += 1
        elif daily["type"] == "fortune":
            fdata = scheduled["fortune_events"].get(daily["fortune"], {})
            if not fdata.get("skip_consumption", False):
                state["water"] = max(0, state["water"] - params["baseline_water_L_per_day"])
                c = min(state["food"], params["baseline_food_kcal_per_day"])
                state["food"] -= c
                daily_kcal += c
            state["hp"] += fdata.get("hp_delta", 0)
            w_gain = fdata.get("water_gain_L", 0)
            if "requires_items_pool" in fdata and not any(j in inv for j in fdata["requires_items_pool"]):
                w_gain = fdata.get("fallback_water_gain_L", 0)
            state["water"] += w_gain
            state["food"] += fdata.get("food_gain_kcal", 0)
        else:
            state["water"] = max(0, state["water"] - params["baseline_water_L_per_day"])
            c = min(state["food"], params["baseline_food_kcal_per_day"])
            state["food"] -= c
            daily_kcal += c
            for ev_id in daily["events"]:
                ev = data.events[ev_id]
                if ev.category == "bonus_morale" and ev.mit_logic != "NONE":
                    hp_delta = ev.base_hp if mitigates(inv, ev) else ev.mit_hp
                else:
                    hp_delta = _compute_hp_delta(inv, ev, loc, trait)
                state["hp"] += hp_delta
                if ev.category == "water_collection":
                    wm = loc.water_gain_mult.get("water_collection", 1.0) if loc else 1.0
                    if loc and loc.requires_stove_for_water and "stove_fuel" not in inv:
                        wm = 0.0
                    state["water"] += params["water_gain_base_L"] * wm

        state["hp"] -= params["carrying_penalty_hp_per_kg_per_day"] * max(0, state["total_weight"] - params["carrying_threshold_kg"])
        if trait:
            r = trait.raw
            if r.get("condition") == "total_weight <= 15" and state["total_weight"] <= 15:
                state["hp"] += r.get("daily_hp_delta", 0)
            if r.get("condition") == "water_carried > 5":
                cl = sum(data.items[j].litres for j in inv if j in data.items)
                if cl > 5:
                    state["hp"] += r.get("daily_hp_delta", 0)

        if state["water"] <= 0:
            state["c_water"] += 1
            state["water"] = 0
        else:
            state["c_water"] = 0
        if daily["type"] != "rest" and daily_kcal < params["starvation_kcal_threshold"]:
            state["c_food"] += 1
        else:
            state["c_food"] = 0

        if state["hp"] <= 0:
            state["alive"], state["death_day"], state["death_cause"] = False, day_idx + 1, "HP reached zero"
        elif state["c_water"] >= params["dehydration_days_max"]:
            state["alive"], state["death_day"], state["death_cause"] = False, day_idx + 1, "Dehydration"
        elif state["c_food"] >= params["starvation_days_max"]:
            state["alive"], state["death_day"], state["death_cause"] = False, day_idx + 1, "Starvation"

        state["hp_history"].append(round(state["hp"], 1))
        state["water_history"].append(round(state["water"], 1))
        state["food_history"].append(state["food"])

    st.session_state.current_day += 1


def _inst_play():
    data = st.session_state.data
    params = data.parameters
    horizon = params["horizon_days"]
    day = st.session_state.current_day

    st.title("🎒 Running Wild")
    st.progress(day / horizon, text=f"Day {day} / {horizon}")

    if day > 0:
        daily = st.session_state.daily_events_cache[day - 1]
        if daily["type"] == "rest":
            st.success(f"### 🏕️ Day {day} — Rest Day\nNo events. No consumption. +1 HP.")
        elif daily["type"] == "fortune":
            sched = json.load(open(Path(DATA_DIR) / "scheduled_events.json"))
            fd = sched["fortune_events"].get(daily["fortune"], {})
            st.info(f"### 🎁 Day {day} — {fd.get('name','?')}\n{fd.get('notes','')}")
        else:
            fired = daily["events"]
            if not fired:
                st.info(f"### Day {day} — Quiet day.")
            else:
                st.warning(f"### ⚡ Day {day} — {len(fired)} event(s)")
                for eid in fired:
                    ev = data.events.get(eid)
                    if ev:
                        st.markdown(f"**{ev.name}** — {CAT_NARRATIVE.get(ev.category, '')}")

    st.markdown("---")
    n = len(st.session_state.team_list)
    per_row = min(n, 5)
    for start in range(0, n, per_row):
        cols = st.columns(per_row)
        for j in range(per_row):
            idx = start + j
            if idx >= n:
                break
            t = st.session_state.team_list[idx]
            s = st.session_state.team_states[t["name"]]
            with cols[j]:
                if s["alive"]:
                    d = s["hp_history"][-1] - s["hp_history"][-2] if len(s["hp_history"]) >= 2 else 0
                    st.metric(t["name"], f"❤️ {s['hp']:.1f}", f"{d:+.1f}" if d else "")
                    st.caption(f"💧{s['water']:.1f}L | 🍖{s['food']}kcal")
                    st.progress(max(0, min(1, s["hp"] / params["hp_initial"])))
                else:
                    st.error(f"**{t['name']}**\n💀 Day {s['death_day']}\n{s['death_cause']}")

    st.markdown("---")
    alive = sum(1 for s in st.session_state.team_states.values() if s["alive"])
    if day < horizon and alive > 0:
        if st.button(f"▶️ Next Day (Day {day+1})", type="primary", use_container_width=True):
            _advance_day()
            st.rerun()
    else:
        st.session_state.inst_phase = "finished"
        update_game(st.session_state.game_code, lambda s: s.update({"phase": "finished"}) or s)
        st.rerun()

    with st.expander("📊 HP History"):
        import pandas as pd
        ch = {t["name"]: st.session_state.team_states[t["name"]]["hp_history"] for t in st.session_state.team_list}
        mx = max(len(v) for v in ch.values())
        for k in ch:
            ch[k] += [ch[k][-1]] * (mx - len(ch[k]))
        st.line_chart(pd.DataFrame(ch))


def _inst_scoreboard():
    data = st.session_state.data
    params = data.parameters
    st.title("🏆 Final Scoreboard")

    results = []
    for t in st.session_state.team_list:
        s = st.session_state.team_states[t["name"]]
        if s["alive"]:
            wb = min(params["endgame_water_hp_cap"], int(s["water"] / params["endgame_water_L_per_hp"]))
            fb = min(params["endgame_food_hp_cap"], int(s["food"] / params["endgame_food_kcal_per_hp"]))
            final = round(s["hp"] + wb + fb, 1)
        else:
            wb = fb = 0
            final = -999
        results.append({"name": t["name"], "final": final, "raw": round(s["hp"],1), "wb": wb, "fb": fb, "s": s})
    results.sort(key=lambda r: -r["final"])

    for rank, r in enumerate(results):
        if r["final"] > 0:
            medal = ["🥇","🥈","🥉"][rank] if rank < 3 else f"#{rank+1}"
            st.markdown(f"### {medal} {r['name']} — HP {r['final']}")
            st.caption(f"Raw {r['raw']} + 💧{r['wb']} + 🍖{r['fb']}")
        else:
            st.markdown(f"### 💀 {r['name']} — Eliminated Day {r['s']['death_day']}")

    st.markdown("---")
    import pandas as pd
    ch = {t["name"]: st.session_state.team_states[t["name"]]["hp_history"] for t in st.session_state.team_list}
    mx = max(len(v) for v in ch.values())
    for k in ch:
        ch[k] += [ch[k][-1]] * (mx - len(ch[k]))
    st.line_chart(pd.DataFrame(ch))

    if st.button("🔄 New Game", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


def main():
    st.set_page_config(page_title="Running Wild", page_icon="🎒", layout="wide")
    init()
    if not st.session_state.role:
        render_landing()
    elif st.session_state.role == "student":
        render_student()
    elif st.session_state.role == "instructor":
        render_instructor()

if __name__ == "__main__":
    main()