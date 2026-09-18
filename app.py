"""
app.py — Running Wild classroom app (Streamlit).

Three views share one server-side room:
  * Group view      : join with room code + group number, see location card,
                      choose items (quantities) before the timer ends.
  * Instructor view : create a private room, control every phase.
  * Big screen      : projected view of locations, countdown, traits,
                      daily events and every group's progress.

Run locally:  streamlit run app.py
"""

import html
import time

import pandas as pd
import streamlit as st

import engine
from rooms import RoomStore

st.set_page_config(page_title="Running Wild", page_icon="🎒", layout="wide")


@st.cache_resource
def get_store():
    return RoomStore(engine.load_data())


S = get_store()
D = S.data

# ---------------------------------------------------------------------------
# Look and feel: trail-map parchment, forest ink, ember accents
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=IBM+Plex+Sans:wght@400;600&display=swap');
html, body, [class*="css"], .stMarkdown, .stDataFrame { font-family: 'IBM Plex Sans', sans-serif; }
h1, h2, h3, .rw-title { font-family: 'Fraunces', Georgia, serif !important; color: #1F3B2D; letter-spacing: -0.01em; }
.rw-card { background: #FBF8F1; border: 1px solid #D8CDB4; border-left: 6px solid #6B7F3A;
           border-radius: 6px; padding: 1rem 1.25rem; margin: 0.5rem 0 1rem 0; }
.rw-card.ember { border-left-color: #C8553D; }
.rw-card h3 { margin: 0 0 0.35rem 0; }
.rw-big { font-family: 'Fraunces', Georgia, serif; font-size: 5.5rem; line-height: 1; color: #1F3B2D; }
.rw-mid { font-family: 'Fraunces', Georgia, serif; font-size: 2.4rem; color: #1F3B2D; }
.rw-muted { color: #5E6B61; }
.rw-chip { display: inline-block; background: #1F3B2D; color: #F4EFE4; border-radius: 4px;
           padding: 0.35rem 0.8rem; margin: 0.25rem; font-size: 1.3rem; }
.rw-dead { color: #9A3B2B; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


def esc(s):
    return html.escape(str(s))


# ---------------------------------------------------------------------------
# Shared renderers
# ---------------------------------------------------------------------------

def loc_name(lid):
    return D["locations"][lid]["name"] if lid else "—"


def trait_name(tid):
    return D["traits"][tid]["name"] if tid else "—"


def event_card_html(eid, big=False):
    ev = D["events"][eid]
    parts = []
    if ev["base_hp"] > 0:
        need = ev["mit_set"]
        if ev["mit_logic"] == "NONE" or not need:
            parts.append(f"Everyone gains <b>HP {ev['base_hp']:+d}</b>.")
        else:
            j = " + " if ev["mit_logic"] == "ALL" else " or "
            parts.append(f"Gain <b>HP {ev['base_hp']:+d}</b> if you carry "
                         f"{esc(j.join(engine.item_names(need, D)))}.")
    else:
        if ev["base_hp"] < 0:
            parts.append(f"Unprotected: <b>HP {ev['base_hp']:+d}</b>.")
        if ev["mit_logic"] != "NONE" and ev["mit_set"]:
            j = " + " if ev["mit_logic"] == "ALL" else " or "
            prot = esc(j.join(engine.item_names(ev["mit_set"], D)))
            after = f" (HP {ev['mit_hp']:+d})" if ev["mit_hp"] != 0 else ""
            parts.append(f"Protected by: {prot}{after}.")
        elif ev["base_hp"] < 0:
            parts.append("No item protects against this.")
    if ev["water_change"] > 0:
        parts.append(f"Water found: +{ev['water_change']} L.")
    if ev["water_change"] < 0:
        parts.append(f"Water lost: {ev['water_change']} L unless protected.")
    if ev["food_change"] > 0:
        parts.append(f"Food found: +{ev['food_change']} kcal.")
    if ev["food_change"] < 0:
        parts.append(f"Food lost: {ev['food_change']} kcal unless protected.")
    if ev["extra_water"] or ev["extra_food"]:
        parts.append(f"Extra consumption today: {ev['extra_water']} L water, {ev['extra_food']} kcal.")
    size = "rw-big" if big else "rw-mid"
    return (f"<div class='rw-card ember'><div class='{size}'>{esc(ev['name'])}</div>"
            f"<p style='font-size:{'1.6rem' if big else '1.05rem'}'>{' '.join(parts)}</p></div>")


def status_text(state):
    if state is None:
        return ""
    if state["alive"]:
        return "alive"
    return f"out on day {state['death_day']} ({state['death_cause']})"


def progress_table(room):
    rows = []
    for g in sorted(room["groups"].values(), key=lambda x: int(x["group"])):
        s = g["state"]
        if s is None:
            continue
        last = s["history"][-1]
        rows.append({
            "Group": int(g["group"]),
            "Location": loc_name(g["location"]),
            "Trait": trait_name(g["trait"]),
            "HP": s["hp"],
            "Today": last["dhp"] if last["day"] == room["day"] else None,
            "Water (L)": s["water"],
            "Food (kcal)": s["food"],
            "Status": status_text(s),
            "Why": last["notes"] if last["day"] == room["day"] else "",
        })
    return pd.DataFrame(rows)


def hp_chart_df(room):
    series = {}
    for g in room["groups"].values():
        if g["state"]:
            series[f"G{g['group']}"] = {h["day"]: h["hp"] for h in g["state"]["history"]}
    return pd.DataFrame(series).sort_index()


def leaderboard(room):
    rows = []
    for g in room["groups"].values():
        s = g["state"]
        if s is None:
            continue
        fs = engine.final_score(s, room["params"])
        rows.append({
            "Group": int(g["group"]),
            "Location": loc_name(g["location"]),
            "Trait": trait_name(g["trait"]),
            "HP end": s["hp"],
            "HP from water": fs["hp_water"] if fs else None,
            "HP from food": fs["hp_food"] if fs else None,
            "Final HP": fs["hp_final"] if fs else None,
            "Status": status_text(s),
            "_alive": s["alive"], "_dday": s["death_day"] or 0,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values(["_alive", "Final HP", "_dday", "HP end"], ascending=[False, False, False, False])
    df.insert(0, "Rank", range(1, len(df) + 1))
    return df.drop(columns=["_alive", "_dday"])


def pack_df(inv):
    rows = []
    for i, q in sorted(inv.items()):
        it = D["items"][i]
        rows.append({"Item": it["name"], "Qty": q, "kg": it["weight_kg"] * q, "L": it["volume_L"] * q})
    return pd.DataFrame(rows)


def countdown(room):
    if room["phase"] != "selection" or not room["deadline"]:
        return None
    return max(0, int(room["deadline"] - time.time()))


def fmt_secs(s):
    return f"{s // 60:02d}:{s % 60:02d}"


def all_history_csv(room):
    rows = []
    for g in room["groups"].values():
        if g["state"]:
            for h in g["state"]["history"]:
                rows.append({"group": g["group"], "location": g["location"], "trait": g["trait"], **h})
    return pd.DataFrame(rows).to_csv(index=False).encode()


# ---------------------------------------------------------------------------
# Landing
# ---------------------------------------------------------------------------

def landing():
    st.markdown("<h1>Running Wild</h1><p class='rw-muted'>Survival knapsack game · PAMP</p>",
                unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        st.subheader("Group")
        st.caption("Join your class room with the room code and your group number.")
        if st.button("I am a group", type="primary", width="stretch"):
            st.session_state.role = "group"
            st.rerun()
    with c2:
        st.subheader("Instructor")
        st.caption("Create a private room and run the game.")
        if st.button("I am the instructor", width="stretch"):
            st.session_state.role = "instructor"
            st.rerun()
    with c3:
        st.subheader("Big screen")
        st.caption("Projected view for the whole class.")
        if st.button("Open big screen", width="stretch"):
            st.session_state.role = "screen"
            st.rerun()


def back_button():
    if st.sidebar.button("Leave"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ---------------------------------------------------------------------------
# Group view
# ---------------------------------------------------------------------------

def group_join():
    st.markdown("<h2>Join your room</h2>", unsafe_allow_html=True)
    code = st.text_input("Room code (on the big screen)", max_chars=4)
    group = st.number_input("Your group number", min_value=1, max_value=60, step=1, value=None)
    if st.button("Join", type="primary", disabled=not (code and group)):
        ok, msg = S.join(code.strip(), int(group))
        if ok:
            st.session_state.code = code.strip()
            st.session_state.group = str(int(group))
            st.rerun()
        else:
            st.error(msg)


@st.fragment(run_every=2)
def group_watcher():
    code = st.session_state.code
    S.tick(code)
    room = S.get(code)
    if room is None:
        st.error("This room no longer exists.")
        return
    key = (room["phase"], room["day"])
    if st.session_state.get("seen") != key:
        st.session_state.seen = key
        st.rerun(scope="app")
    left = countdown(room)
    if left is not None:
        st.markdown(f"<div class='rw-mid'>⏱ {fmt_secs(left)}</div>", unsafe_allow_html=True)


def group_selection(room, g):
    params = room["params"]
    if g["submitted"] is not None:
        st.success("Backpack submitted. Waiting for the other groups.")
        st.dataframe(pack_df(g["submitted"]), hide_index=True)
        return

    ek = f"base_{room['code']}_{g['group']}"
    if ek not in st.session_state:
        base = D["items_df"][["id", "name", "category", "weight_kg", "volume_L", "kcal", "litres"]].copy()
        base["qty"] = base["id"].map(lambda i: g["draft"].get(i, 0))
        st.session_state[ek] = base.set_index("id")

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("<h3>Choose your items</h3>", unsafe_allow_html=True)
        st.caption(f"Set a quantity for each item you pack (up to {params['max_copies_per_item']} copies). "
                   "Your choice is saved as you go; when the timer ends, your last valid backpack is submitted.")
        edited = st.data_editor(
            st.session_state[ek], key=f"ed_{ek}", height=560, width="stretch",
            disabled=["name", "category", "weight_kg", "volume_L", "kcal", "litres"],
            column_config={
                "name": st.column_config.TextColumn("Item"),
                "category": st.column_config.TextColumn("Type"),
                "weight_kg": st.column_config.NumberColumn("kg", format="%.2f"),
                "volume_L": st.column_config.NumberColumn("L", format="%.1f"),
                "kcal": st.column_config.NumberColumn("Food kcal"),
                "litres": st.column_config.NumberColumn("Water L"),
                "qty": st.column_config.NumberColumn("Qty", min_value=0,
                                                     max_value=params["max_copies_per_item"], step=1),
            },
            column_order=["name", "category", "weight_kg", "volume_L", "kcal", "litres", "qty"],
        )
    inv = {i: int(q) for i, q in edited["qty"].items() if pd.notna(q) and int(q) > 0}
    if inv != g["draft"]:
        S.save_draft(room["code"], g["group"], inv)
    t = engine.pack_totals(inv, D)
    ok = engine.is_feasible(inv, D, params)
    with right:
        st.markdown(f"<h3>{esc(loc_name(g['location']))}</h3>", unsafe_allow_html=True)
        st.markdown(f"<div class='rw-card'>{esc(D['locations'][g['location']]['card'])}</div>",
                    unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.metric("Weight", f"{t['weight']} / {params['weight_cap_kg']:g} kg")
        c2.metric("Volume", f"{t['volume']} / {params['volume_cap_L']:g} L")
        st.progress(min(1.0, t["weight"] / params["weight_cap_kg"]))
        st.progress(min(1.0, t["volume"] / params["volume_cap_L"]))
        c3, c4, c5 = st.columns(3)
        c3.metric("Start HP", params["hp_initial"])
        c4.metric("Start water", f"{params['water_initial_L'] + t['litres']:g} L")
        c5.metric("Start food", f"{params['food_initial_kcal'] + t['kcal']} kcal")
        st.caption(f"Each day you drink {params['baseline_water_L_per_day']} L and eat "
                   f"{params['baseline_food_kcal_per_day']} kcal, plus any extra the day's event demands.")
        if not ok:
            st.error("Over the limit. Remove something before submitting.")
        if st.button("Submit backpack now", type="primary", disabled=not ok, width="stretch"):
            done, msg = S.submit(room["code"], g["group"], inv)
            if done:
                st.rerun()
            else:
                st.error(msg)


def group_main():
    back_button()
    room = S.get(st.session_state.code)
    if room is None:
        st.error("Room not found.")
        return
    g = room["groups"].get(st.session_state.group)
    if g is None:
        st.error("Your group was removed from this room. Join again.")
        return
    st.markdown(f"<h1>Group {esc(g['group'])}</h1><p class='rw-muted'>Room {esc(room['code'])}</p>",
                unsafe_allow_html=True)
    st.session_state.seen = (room["phase"], room["day"])
    group_watcher()
    ph = room["phase"]
    if ph == "lobby":
        st.info("You are in. Waiting for the instructor to draw starting locations.")
        return
    if ph == "locations":
        st.markdown(f"<h2>Your starting location: {esc(loc_name(g['location']))}</h2>", unsafe_allow_html=True)
        st.markdown(f"<div class='rw-card'>{esc(D['locations'][g['location']]['card'])}</div>",
                    unsafe_allow_html=True)
        st.info("Item selection opens when the instructor starts the timer.")
        return
    if ph == "selection":
        group_selection(room, g)
        return

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown(f"<h3>Location · {esc(loc_name(g['location']))}</h3>"
                    f"<div class='rw-card'>{esc(D['locations'][g['location']]['card'])}</div>",
                    unsafe_allow_html=True)
        if g["trait"]:
            st.markdown(f"<h3>Trait · {esc(trait_name(g['trait']))}</h3>"
                        f"<div class='rw-card ember'>{esc(D['traits'][g['trait']]['card'])}</div>",
                        unsafe_allow_html=True)
        else:
            st.info("Backpacks are locked. Trait cards come next.")
    with c2:
        st.markdown("<h3>Your backpack</h3>", unsafe_allow_html=True)
        if g["submitted"]:
            st.dataframe(pack_df(g["submitted"]), hide_index=True)
            st.caption(f"Submitted by: {g['submitted_by']}")
        else:
            st.warning("No valid backpack was submitted; you start with nothing packed.")
    s = g["state"]
    if s:
        st.markdown("<h3>Your journey</h3>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("HP", s["hp"])
        c2.metric("Water", f"{s['water']} L")
        c3.metric("Food", f"{s['food']} kcal")
        c4.metric("Status", "alive" if s["alive"] else "out")
        hist = pd.DataFrame(s["history"])
        hist["event"] = hist["event"].map(lambda e: D["events"][e]["name"] if e in D["events"] else e)
        st.dataframe(hist.iloc[::-1], hide_index=True, width="stretch")
    if ph == "finished":
        st.markdown("<h3>Final results</h3>", unsafe_allow_html=True)
        st.dataframe(leaderboard(room), hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Instructor view
# ---------------------------------------------------------------------------

def instructor_login():
    st.markdown("<h2>Instructor</h2>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Create a new room", "Return to a room"])
    P = D["params"]
    with t1:
        pin = st.text_input("Choose an instructor PIN", type="password", key="new_pin")
        days = st.number_input("Number of days (events)", 1, 60, P["default_days"])
        with st.expander("Game settings"):
            hp0 = st.number_input("Starting HP", 1, 100, P["hp_initial"])
            w0 = st.number_input("Starting water (L)", 0.0, 50.0, float(P["water_initial_L"]), 0.5)
            f0 = st.number_input("Starting food (kcal)", 0, 50000, P["food_initial_kcal"], 500)
            bw = st.number_input("Daily water (L)", 0.0, 5.0, float(P["baseline_water_L_per_day"]), 0.1)
            bf = st.number_input("Daily food (kcal)", 0, 3000, P["baseline_food_kcal_per_day"], 50)
            wh = st.checkbox("Use the Water Hoarder trait penalty", P["water_hoarder_enabled"])
        if st.button("Create room", type="primary", disabled=not pin):
            code = S.create(pin, days, {"hp_initial": hp0, "water_initial_L": w0, "food_initial_kcal": f0,
                                        "baseline_water_L_per_day": bw, "baseline_food_kcal_per_day": bf,
                                        "starvation_kcal_threshold": min(bf, P["starvation_kcal_threshold"]),
                                        "water_hoarder_enabled": wh})
            st.session_state.code = code
            st.session_state.inst_ok = True
            st.rerun()
    with t2:
        code = st.text_input("Room code", max_chars=4, key="old_code")
        pin = st.text_input("PIN", type="password", key="old_pin")
        if st.button("Open room"):
            if S.check_pin(code.strip(), pin):
                st.session_state.code = code.strip()
                st.session_state.inst_ok = True
                st.rerun()
            else:
                st.error("Room code or PIN is wrong.")


@st.fragment(run_every=2)
def instructor_watcher():
    code = st.session_state.code
    S.tick(code)
    room = S.get(code)
    key = (room["phase"], room["day"], len(room["groups"]))
    if st.session_state.get("seen") != key:
        st.session_state.seen = key
        st.rerun(scope="app")
    groups = sorted(room["groups"].values(), key=lambda x: int(x["group"]))
    if room["phase"] in ("lobby", "locations"):
        st.write(f"**{len(groups)} groups joined:** " + ", ".join(g["group"] for g in groups))
    if room["phase"] == "selection":
        left = countdown(room)
        n_sub = sum(g["submitted"] is not None for g in groups)
        st.markdown(f"<div class='rw-mid'>⏱ {fmt_secs(left)} · {n_sub}/{len(groups)} submitted</div>",
                    unsafe_allow_html=True)
        rows = []
        for g in groups:
            inv = g["submitted"] or g["draft"]
            t = engine.pack_totals(inv, D)
            rows.append({"Group": int(g["group"]), "Location": loc_name(g["location"]),
                         "Items": sum(inv.values()), "kg": t["weight"], "L": t["volume"],
                         "Valid": engine.is_feasible(inv, D, room["params"]),
                         "Submitted": g["submitted"] is not None})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def instructor_main():
    back_button()
    code = st.session_state.code
    room = S.get(code)
    if room is None:
        st.error("Room not found.")
        return
    ph = room["phase"]
    st.markdown(f"<h1>Room {esc(code)}</h1><p class='rw-muted'>Phase: {esc(ph)} · "
                f"Day {room['day']} of {room['days']}</p>", unsafe_allow_html=True)
    st.caption("Open this app in a second tab, choose Big screen, and enter the same room code and PIN.")
    st.session_state.seen = (room["phase"], room["day"], len(room["groups"]))
    instructor_watcher()

    if ph == "lobby":
        with st.expander("Remove a group that joined by mistake"):
            gsel = st.selectbox("Group", sorted(room["groups"], key=int)) if room["groups"] else None
            if gsel and st.button("Remove"):
                S.remove_group(code, gsel)
                st.rerun()
        if st.button("Draw starting locations", type="primary", disabled=not room["groups"]):
            S.draw_locations(code)
            st.rerun()

    elif ph == "locations":
        st.dataframe(pd.DataFrame([{"Group": int(g["group"]), "Location": loc_name(g["location"])}
                                   for g in room["groups"].values()]).sort_values("Group"),
                     hide_index=True)
        mins = st.number_input("Selection time (minutes)", 1, 120, D["params"]["default_selection_minutes"])
        if st.button("Start item selection timer", type="primary"):
            S.start_selection(code, mins)
            st.rerun()

    elif ph == "selection":
        if st.button("Close selection now (auto-submits every group)"):
            S.close_selection(code)
            st.rerun()

    elif ph == "selection_closed":
        rows = []
        for g in sorted(room["groups"].values(), key=lambda x: int(x["group"])):
            t = engine.pack_totals(g["submitted"] or {}, D)
            rows.append({"Group": int(g["group"]), "Items": sum((g["submitted"] or {}).values()),
                         "kg": t["weight"], "L": t["volume"], "Submitted by": g["submitted_by"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        if st.button("Draw trait cards", type="primary"):
            S.draw_traits(code)
            st.rerun()

    elif ph in ("traits", "playing"):
        if room["day"] > 0:
            st.markdown(event_card_html(room["event_log"][-1]), unsafe_allow_html=True)
        c1, c2 = st.columns([1, 1])
        if c1.button(f"Next day → Day {room['day'] + 1}", type="primary", width="stretch"):
            S.next_day(code)
            st.rerun()
        if room["day"] > 0 and c2.button("End the game now", width="stretch"):
            S.finish(code)
            st.rerun()
        st.dataframe(progress_table(room), hide_index=True, width="stretch")

    elif ph == "finished":
        lb = leaderboard(room)
        if not lb.empty and pd.notna(lb.iloc[0]["Final HP"]):
            st.markdown(f"<div class='rw-mid'>Winner: Group {int(lb.iloc[0]['Group'])}</div>",
                        unsafe_allow_html=True)
        st.dataframe(lb, hide_index=True, width="stretch")
        st.download_button("Download full day-by-day log (CSV)", all_history_csv(room),
                           file_name=f"running_wild_room_{code}.csv")

    with st.sidebar.expander("Danger zone"):
        if st.button("Delete this room"):
            S.delete(code)
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


# ---------------------------------------------------------------------------
# Big screen
# ---------------------------------------------------------------------------

def screen_login():
    st.markdown("<h2>Big screen</h2>", unsafe_allow_html=True)
    code = st.text_input("Room code", max_chars=4)
    pin = st.text_input("Instructor PIN", type="password")
    if st.button("Show", type="primary"):
        if S.check_pin(code.strip(), pin):
            st.session_state.code = code.strip()
            st.session_state.screen_ok = True
            st.rerun()
        else:
            st.error("Room code or PIN is wrong.")


@st.fragment(run_every=2)
def screen_main():
    code = st.session_state.code
    S.tick(code)
    room = S.get(code)
    if room is None:
        st.error("Room not found.")
        return
    ph = room["phase"]
    groups = sorted(room["groups"].values(), key=lambda x: int(x["group"]))

    if ph == "lobby":
        st.markdown(f"<p class='rw-muted' style='font-size:1.6rem'>Room code</p>"
                    f"<div class='rw-big'>{esc(code)}</div>"
                    f"<p style='font-size:1.4rem'>Open the app, choose <b>I am a group</b>, "
                    f"and enter this code with your group number.</p>", unsafe_allow_html=True)
        st.markdown("".join(f"<span class='rw-chip'>Group {esc(g['group'])}</span>" for g in groups),
                    unsafe_allow_html=True)

    elif ph == "locations":
        st.markdown("<h1>Starting locations</h1>", unsafe_allow_html=True)
        cols = st.columns(2)
        for k, g in enumerate(groups):
            loc = D["locations"][g["location"]]
            cols[k % 2].markdown(f"<div class='rw-card'><h3>Group {esc(g['group'])} · {esc(loc['name'])}</h3>"
                                 f"{esc(loc['card'])}</div>", unsafe_allow_html=True)

    elif ph == "selection":
        left = countdown(room)
        n_sub = sum(g["submitted"] is not None for g in groups)
        st.markdown(f"<h1>Pack your backpack</h1><div class='rw-big'>{fmt_secs(left)}</div>"
                    f"<p style='font-size:1.6rem'>{n_sub} of {len(groups)} groups have submitted.</p>",
                    unsafe_allow_html=True)
        st.markdown("".join(
            f"<span class='rw-chip' style='background:{'#6B7F3A' if g['submitted'] is not None else '#1F3B2D'}'>"
            f"Group {esc(g['group'])}{' ✓' if g['submitted'] is not None else ''}</span>" for g in groups),
            unsafe_allow_html=True)

    elif ph == "selection_closed":
        st.markdown("<h1>Backpacks are locked</h1><p style='font-size:1.4rem'>Trait cards are next.</p>",
                    unsafe_allow_html=True)

    elif ph == "traits" and room["day"] == 0:
        st.markdown("<h1>Trait cards</h1>", unsafe_allow_html=True)
        cols = st.columns(2)
        for k, g in enumerate(groups):
            tr = D["traits"][g["trait"]]
            cols[k % 2].markdown(f"<div class='rw-card ember'><h3>Group {esc(g['group'])} · {esc(tr['name'])}"
                                 f"</h3>{esc(tr['card'])}</div>", unsafe_allow_html=True)

    elif ph in ("traits", "playing"):
        st.markdown(f"<p class='rw-muted' style='font-size:1.5rem'>Day {room['day']} of {room['days']}</p>",
                    unsafe_allow_html=True)
        st.markdown(event_card_html(room["event_log"][-1], big=True), unsafe_allow_html=True)
        c1, c2 = st.columns([3, 2], gap="large")
        c1.dataframe(progress_table(room), hide_index=True, width="stretch", height=620)
        c2.line_chart(hp_chart_df(room), height=620)

    elif ph == "finished":
        lb = leaderboard(room)
        if not lb.empty and pd.notna(lb.iloc[0]["Final HP"]):
            st.markdown(f"<p class='rw-muted' style='font-size:1.6rem'>Winner</p>"
                        f"<div class='rw-big'>Group {int(lb.iloc[0]['Group'])}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='rw-big'>Nobody survived</div>", unsafe_allow_html=True)
        c1, c2 = st.columns([3, 2], gap="large")
        c1.dataframe(lb, hide_index=True, width="stretch")
        c2.line_chart(hp_chart_df(room), height=500)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

role = st.session_state.get("role")
if role is None:
    landing()
elif role == "group":
    if "group" not in st.session_state:
        back_button()
        group_join()
    else:
        group_main()
elif role == "instructor":
    if not st.session_state.get("inst_ok"):
        back_button()
        instructor_login()
    else:
        instructor_main()
elif role == "screen":
    if not st.session_state.get("screen_ok"):
        back_button()
        screen_login()
    else:
        back_button()
        screen_main()