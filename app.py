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
.rw-facts { margin: 0.5rem 0 0 1.2rem; padding: 0; }
.rw-facts li { margin: 0.15rem 0; }
.rw-pill { display: inline-block; border-radius: 4px; padding: 0.1rem 0.6rem; margin: 0.15rem 0.35rem 0.15rem 0;
           font-weight: 600; color: #FFFFFF; white-space: nowrap; }
.rw-pill.bad { background: #C8553D; }
.rw-pill.ok { background: #6B7F3A; }
.rw-pill.good { background: #3E7CB1; }
.rw-pill.out { background: #5E6B61; }
.rw-table { width: 100%; border-collapse: collapse; }
.rw-table th { text-align: left; color: #5E6B61; font-weight: 600; border-bottom: 2px solid #D8CDB4;
               padding: 0.3rem 0.6rem; }
.rw-table td { border-bottom: 1px solid #E6DECB; padding: 0.4rem 0.6rem; vertical-align: top; }
.rw-table tr.out td { color: #9A8F84; }
.rw-table .rw-num { text-align: right; white-space: nowrap; }
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


EVENT_KIND = {
    "weather_neutral": "Weather", "weather_wet": "Wet weather", "weather_cold": "Cold weather",
    "weather_hot": "Hot weather", "weather_wind": "Wind", "bonus_morale": "A good moment",
    "medical_illness": "Illness", "medical_injury": "Injury", "medical_sting": "Bite or sting",
    "insect": "Insects", "navigation": "Finding the way", "slip_fall": "Difficult ground",
    "equipment": "Equipment", "food_spoilage": "Food trouble", "water_collection": "Water",
    "wildlife_calm": "Wildlife", "wildlife_attack": "Dangerous wildlife", "food_gain": "Food found",
}


def loc_holders(room):
    """Which groups hold which location card: {location id: [group numbers]}."""
    out = {}
    for g in sorted(room["groups"].values(), key=lambda x: int(x["group"])):
        if g["location"]:
            out.setdefault(g["location"], []).append(g["group"])
    return out


def location_effects(ev, holders=None):
    """Location cards that react to this event, as short phrases for the event
    card. With `holders`, only the cards in play are listed, with their groups."""
    out = []
    for lid, loc in D["locations"].items():
        name = loc["name"]
        if holders is not None:
            if lid not in holders:
                continue
            gs = holders[lid]
            name += f" ({'Group' if len(gs) == 1 else 'Groups'} {', '.join(gs)})"
        if ev["base_hp"] != 0 and any(t in ev["tags"] for t in loc.get("zero_tags", [])):
            out.append(f"{name}: no HP change at all")
        elif ev["base_hp"] <= 0:
            best = None
            for r in loc.get("hp_rules", []):
                if r["tag"] in ev["tags"] and (best is None or abs(r["delta"]) > abs(best["delta"])):
                    best = r
            if best and not (best["delta"] > 0 and ev["base_hp"] == 0):
                txt = f"{abs(best['delta'])} HP {'more' if best['delta'] < 0 else 'less'}"
                cond = [] if best.get("always") else ["if not protected"]
                if best.get("unless_items"):
                    cond.append("unless carrying " + " or ".join(engine.item_names(best["unless_items"], D)))
                out.append(f"{name}: {txt}" + (" " + ", ".join(cond) if cond else ""))
        if ev["water_change"] > 0:
            if loc.get("water_gain_requires"):
                out.append(f"{name}: no water without "
                           + " and ".join(engine.item_names(loc["water_gain_requires"], D)))
            elif loc.get("water_gain_mult"):
                out.append(f"{name}: finds {loc['water_gain_mult']:g}x the water")
        if ev["food_change"] > 0 and loc.get("food_gain_bonus"):
            out.append(f"{name}: finds {loc['food_gain_bonus']} kcal more")
    return out


def event_card_html(eid, big=False, params=None, holders=None):
    """The day's event spelled out line by line: what it costs, what protects,
    what is found or lost, today's ration, and which location cards react."""
    ev = D["events"][eid]
    prot = esc(engine.protection_text(ev, D))
    hp, mit = ev["base_hp"], ev["mit_hp"]
    locs = location_effects(ev, holders)
    facts = []
    if hp < 0:
        facts.append(f"<b>If you are not protected:</b> you lose {-hp} HP.")
        if prot:
            after = "you lose nothing" if mit == 0 else f"you lose only {-mit} HP"
            facts.append(f"<b>You are protected if you carry:</b> {prot}. Then {after}.")
        else:
            facts.append("<b>Protection:</b> none. No item helps against this.")
    elif hp > 0:
        if prot:
            facts.append(f"<b>Bonus:</b> you gain {hp} HP, but only if you carry: {prot}.")
        else:
            facts.append(f"<b>Bonus:</b> every group gains {hp} HP.")
    else:
        facts.append("<b>HP:</b> the event itself costs no HP.")
        if prot and locs and ev["water_change"] >= 0 and ev["food_change"] >= 0:
            # a harmless event that a location card in play turns into a loss
            facts.append(f"<b>You are protected if you carry:</b> {prot}.")
    if ev["water_change"] > 0:
        facts.append(f"<b>Water found:</b> every group finds {ev['water_change']:g} L.")
    if ev["water_change"] < 0:
        facts.append(f"<b>Water lost:</b> {-ev['water_change']:g} L"
                     + (f", unless you carry: {prot}." if prot else "."))
    if ev["food_change"] > 0:
        facts.append(f"<b>Food found:</b> every group finds {ev['food_change']} kcal.")
    if ev["food_change"] < 0:
        facts.append(f"<b>Food lost:</b> {-ev['food_change']} kcal"
                     + (", unless you are protected." if prot else "."))
    if ev["boost_item"]:
        facts.append(f"<b>{esc(engine.item_names([ev['boost_item']], D)[0])}:</b> "
                     f"multiplies what you find by {ev['boost_mult']:g}.")
    if params:
        water = params["baseline_water_L_per_day"] + float(ev["extra_water"])
        food = params["baseline_food_kcal_per_day"] + int(ev["extra_food"])
        more = " This is more than a normal day." if ev["extra_water"] or ev["extra_food"] else ""
        facts.append(f"<b>Today's ration:</b> each group drinks {water:g} L and eats {food} kcal.{more}")
    if locs:
        facts.append("<b>Location cards that react today:</b> " + "; ".join(esc(x) for x in locs) + ".")
    kind = EVENT_KIND.get(ev["category"], str(ev["category"]).replace("_", " ").capitalize())
    title = "font-size:3.6rem;line-height:1.05" if big else "font-size:2.2rem"
    body = "1.3rem" if big else "1rem"
    return (f"<div class='rw-card ember'>"
            f"<div class='rw-muted' style='font-size:{body}'>{esc(kind)}</div>"
            f"<div class='rw-mid' style='{title}'>{esc(ev['name'])}</div>"
            f"<ul class='rw-facts' style='font-size:{body}'>{''.join(f'<li>{f}</li>' for f in facts)}</ul></div>")


def resupply_html(room, big=False):
    if room["day"] in room.get("resupply_days", []):
        p = room["params"]
        size = "2rem" if big else "1.1rem"
        return (f"<div class='rw-card' style='border-left-color:#3E7CB1'><span style='font-size:{size}'>"
                f"📦 Resupply day: every group receives +{p['resupply_water_L']:g} L water and "
                f"+{p['resupply_food_kcal']} kcal food.</span></div>")
    return ""


def status_text(state):
    if state is None:
        return ""
    if state["alive"]:
        return "alive"
    return f"out on day {state['death_day']} ({state['death_cause']})"


LOC_NAMES = {v["name"] for v in D["locations"].values()}
TRAIT_NAMES = {v["name"] for v in D["traits"].values()}


def card_note(note):
    """An engine note such as 'Wind Pass: -2' as a readable phrase."""
    name, sep, what = note.partition(": ")
    kind = "location card" if name in LOC_NAMES else "trait card" if name in TRAIT_NAMES else None
    if not sep or kind is None:
        return note
    if what == "becomes 0":
        return f"{name} ({kind}) cancels the HP change"
    try:
        return f"{name} ({kind}) {int(what):+d} HP"
    except ValueError:
        return f"{name} ({kind}): {what}"


def day_story(room, g):
    """What happened to one group on the current day, in full sentences.
    Returns the HP change, the explanation, the change in water and food,
    and whether the group went out today."""
    s = g["state"]
    if s is None:
        return None
    last = s["history"][-1]
    if last["day"] == 0:
        return {"dhp": None, "text": last["notes"] or "Ready to set off.", "res": "", "out": False, "today": False}
    if last["day"] != room["day"]:
        return {"dhp": None, "text": f"Out since day {s['death_day']} ({s['death_cause']}).",
                "res": "", "out": False, "today": False}
    ev = D["events"][last["event"]]
    prev = s["history"][-2]
    notes = [n for n in last["notes"].split("; ") if n]
    prot = next((n[len("protected by "):] for n in notes if n.startswith("protected by ")), None)
    dry = any(n.startswith("not enough water") for n in notes)
    nobonus = next((n[len("bonus needs "):] for n in notes if n.startswith("bonus needs ")), None)
    resupply = next((n for n in notes if n.startswith("resupply")), None)
    gone = next((n for n in notes if n.startswith("ELIMINATED")), None)
    need = engine.protection_text(ev, D)
    hp, mit = ev["base_hp"], ev["mit_hp"]

    parts = []
    if hp < 0:
        if prot:
            parts.append(f"Protected by {prot}: " + ("no HP lost" if mit == 0 else f"{mit} HP instead of {hp}"))
        elif dry:
            parts.append(f"Not protected, not enough water in hand: {hp} HP")
        elif need:
            parts.append(f"Not protected, would need {need}: {hp} HP")
        else:
            parts.append(f"Nothing protects against this: {hp} HP")
    elif hp > 0:
        parts.append(f"No bonus, would need {nobonus}" if nobonus else f"Bonus: +{hp} HP")
    elif prot:
        parts.append(f"Carries {prot}")
    handled = ("protected by ", "not enough water", "bonus needs ", "resupply", "ELIMINATED")
    parts += [card_note(n) for n in notes if not n.startswith(handled)]

    dhp = last["dhp"]
    total = "no HP change today" if dhp == 0 else f"{dhp:+d} HP today"
    if len(parts) > 1:
        text = "; ".join(parts) + f". In total {total}."
    elif parts:
        text = parts[0] + "."
    else:
        text = total.capitalize() + "."
    if gone:
        text += " " + gone.replace("ELIMINATED", "Eliminated") + "."
    res = f"Water {prev['water']:g} → {last['water']:g} L, food {prev['food']} → {last['food']} kcal"
    if resupply:
        res += f" (including {resupply})"
    return {"dhp": dhp, "text": text, "res": res, "out": bool(gone), "today": True}


def day_summary_html(room, big=False):
    """Today's outcome at a glance: which groups lost how much, which were
    spared, which went out."""
    buckets, out_today = {}, []
    for g in sorted(room["groups"].values(), key=lambda x: int(x["group"])):
        story = day_story(room, g)
        if not story or not story["today"]:
            continue
        buckets.setdefault(story["dhp"], []).append(g["group"])
        if story["out"]:
            out_today.append(g["group"])
    if not buckets:
        return ""

    def who(gs):
        return ("Group " if len(gs) == 1 else "Groups ") + ", ".join(gs)

    bits = []
    for dhp in sorted(buckets):
        cls, label = (("bad", f"Lost {-dhp} HP") if dhp < 0 else
                      ("ok", "No HP change") if dhp == 0 else ("good", f"Gained {dhp} HP"))
        bits.append(f"<span class='rw-pill {cls}'>{label}</span>{esc(who(buckets[dhp]))}")
    if out_today:
        bits.append(f"<span class='rw-pill out'>Eliminated today</span>{esc(who(out_today))}")
    size = "1.3rem" if big else "1rem"
    return f"<div style='font-size:{size};margin:0.2rem 0 0.9rem 0'>" + " &nbsp;&nbsp; ".join(bits) + "</div>"


def day_table_html(room, big=False, max_height=None):
    """Every group's HP, today's change and the reason for it. An HTML table,
    because the explanation is a sentence and must wrap rather than be cut off."""
    rows = []
    for g in sorted(room["groups"].values(), key=lambda x: int(x["group"])):
        s = g["state"]
        if s is None:
            continue
        story = day_story(room, g)
        dhp = story["dhp"]
        colour = "#9A3B2B" if (dhp or 0) < 0 else "#3E6B2A" if (dhp or 0) > 0 else "#5E6B61"
        today = "—" if dhp is None else f"{dhp:+d}" if dhp else "0"
        res = f"<br><span class='rw-muted'>{esc(story['res'])}</span>" if story["res"] else ""
        rows.append(
            f"<tr class='{'' if s['alive'] else 'out'}'>"
            f"<td><b>Group {esc(g['group'])}</b><br><span class='rw-muted'>{esc(loc_name(g['location']))}"
            f" · {esc(trait_name(g['trait']))}</span></td>"
            f"<td class='rw-num'><b>{s['hp']}</b></td>"
            f"<td class='rw-num' style='color:{colour}'><b>{today}</b></td>"
            f"<td>{esc(story['text'])}{res}</td>"
            f"<td class='rw-num'>{s['water']:g} L</td>"
            f"<td class='rw-num'>{s['food']} kcal</td></tr>")
    size = "1.05rem" if big else "0.95rem"
    box = f"max-height:{max_height}px;overflow-y:auto;" if max_height else ""
    return (f"<div style='{box}font-size:{size}'><table class='rw-table'><thead><tr>"
            f"<th>Group</th><th class='rw-num'>HP</th><th class='rw-num'>Today</th>"
            f"<th>What happened</th><th class='rw-num'>Water</th><th class='rw-num'>Food</th>"
            f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")


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
            "Water days left": fs["water_days"] if fs else None,
            "Food days left": fs["food_days"] if fs else None,
            "Bonus HP": fs["hp_bonus"] if fs else None,
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


# Column order and widths for the results table: Final HP comes right after
# the group, so it is never cut off on a narrow screen or a projector.
LEADER_ORDER = ["Rank", "Group", "Final HP", "HP end", "Bonus HP", "Water days left", "Food days left",
                "Status", "Location", "Trait"]
LEADER_CONFIG = {c: st.column_config.NumberColumn(c, width="small")
                 for c in ["Rank", "Group", "Final HP", "HP end", "Bonus HP"]}


def show_leaderboard(where, lb, **kw):
    where.dataframe(lb, hide_index=True, width="stretch",
                    column_order=LEADER_ORDER, column_config=LEADER_CONFIG, **kw)


def last_day_html(room, big=False):
    """The last day in full. The game moves to the results as soon as the last
    day is drawn, so the final screens show that day's event and outcome too."""
    if not room["event_log"]:
        return ""
    return (f"<p class='rw-muted' style='font-size:{'1.5rem' if big else '1rem'}'>"
            f"Last day · Day {room['day']} of {room['days']}</p>"
            + resupply_html(room, big=big)
            + event_card_html(room["event_log"][-1], big=big, params=room["params"], holders=loc_holders(room))
            + day_summary_html(room, big=big) + day_table_html(room, big=big))


def submitted_by_text(who):
    """'auto (time up)' is also set when the instructor closes selection early."""
    return "automatically, when selection closed" if str(who).startswith("auto") else who


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
    # The button is always enabled: a disabled button would stay grey until the
    # fields were confirmed with Enter, which looks like the app is stuck.
    if st.button("Join", type="primary"):
        if not (code and code.strip() and group):
            st.error("Enter the room code and your group number.")
        else:
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
    if st.session_state.group not in room["groups"]:
        # removed by the instructor: reload so the group is told straight away
        st.rerun(scope="app")
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
        base = D["items_df"][["id", "name", "category", "weight_kg", "volume_L", "kcal", "litres", "needs"]].copy()
        base["needs"] = base["needs"].map(
            lambda n: " + ".join(engine.item_names([x for x in str(n).split("+") if x], D)))
        base["qty"] = base["id"].map(lambda i: g["draft"].get(i, 0))
        st.session_state[ek] = base.set_index("id")

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("<h3>Choose your items</h3>", unsafe_allow_html=True)
        st.caption(f"Type a quantity in the Qty column for each item you pack (up to "
                   f"{params['max_copies_per_item']} copies). "
                   "Your choice is saved as you go; when the timer ends, your last valid backpack is submitted.")
        edited = st.data_editor(
            st.session_state[ek], key=f"ed_{ek}", height=560, width="stretch",
            disabled=["name", "category", "weight_kg", "volume_L", "kcal", "litres", "needs"],
            column_config={
                "name": st.column_config.TextColumn("Item"),
                "category": st.column_config.TextColumn("Type"),
                "weight_kg": st.column_config.NumberColumn("kg", format="%.2f"),
                "volume_L": st.column_config.NumberColumn("L", format="%.1f"),
                "kcal": st.column_config.NumberColumn("Food kcal"),
                "litres": st.column_config.NumberColumn("Water L"),
                "needs": st.column_config.TextColumn("Food only usable with"),
                "qty": st.column_config.NumberColumn("Qty", min_value=0, width="small",
                                                     max_value=params["max_copies_per_item"], step=1),
            },
            # Qty is the only editable column: keep it next to the item id so it
            # is always on screen
            column_order=["qty", "name", "weight_kg", "volume_L", "kcal", "litres", "needs", "category"],
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
        st.error("Your group was removed from this room by the instructor.")
        if st.button("Join again", type="primary"):
            del st.session_state["group"]
            st.rerun()
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
            st.caption(f"Submitted: {submitted_by_text(g['submitted_by'])}")
        else:
            st.warning("No valid backpack was submitted; you start with nothing packed.")
    s = g["state"]
    if s:
        story = day_story(room, g)
        if room["event_log"] and story:
            # today's event in full, then what it did to this group and why
            st.markdown(f"<h3>Day {room['day']} of {room['days']}</h3>" + resupply_html(room)
                        + event_card_html(room["event_log"][-1], params=room["params"],
                                          holders=loc_holders(room)),
                        unsafe_allow_html=True)
            change =(f"<br><span class='rw-muted'>{esc(story['res'])}</span>" if story["res"] else "")
            st.markdown(f"<div class='rw-card'><b>What happened to your group:</b> {esc(story['text'])}"
                        f"{change}</div>", unsafe_allow_html=True)
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
        show_leaderboard(st, leaderboard(room))


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
            wcap = st.number_input("Weight limit (kg)", 5.0, 50.0, float(P["weight_cap_kg"]), 1.0)
            vcap = st.number_input("Volume limit (L)", 10.0, 200.0, float(P["volume_cap_L"]), 5.0)
            rcap = st.number_input("Max bonus HP from leftover water and food (reserve days)", 0, 20,
                                   P["endgame_reserve_cap"])
            wh = st.checkbox("Use the Water Hoarder trait penalty", P["water_hoarder_enabled"])
        with st.expander("Resupply days", expanded=True):
            modes = {"random": "Random days (unannounced)", "fixed": "Every few days", "off": "No resupply"}
            mode = st.radio("Schedule", list(modes), format_func=modes.get,
                            index=list(modes).index(P["resupply_mode"]), horizontal=True)
            every = st.number_input("Every how many days (fixed)", 2, 20, P["resupply_every"])
            count = st.number_input("How many resupply days (random)", 1, 10, P["resupply_count"])
            rw = st.number_input("Water per resupply (L)", 0.0, 10.0, float(P["resupply_water_L"]), 0.5)
            rf = st.number_input("Food per resupply (kcal)", 0, 10000, P["resupply_food_kcal"], 250)
        # Always enabled (see the Join button): the PIN is checked on click
        if st.button("Create room", type="primary"):
            if not pin:
                st.error("Choose an instructor PIN first.")
            else:
                code = S.create(pin, days, {"hp_initial": hp0, "water_initial_L": w0, "food_initial_kcal": f0,
                                            "baseline_water_L_per_day": bw, "baseline_food_kcal_per_day": bf,
                                            "starvation_kcal_threshold": min(bf, P["starvation_kcal_threshold"]),
                                            "weight_cap_kg": wcap, "volume_cap_L": vcap,
                                            "endgame_reserve_cap": rcap,
                                            "water_hoarder_enabled": wh, "resupply_mode": mode,
                                            "resupply_every": every, "resupply_count": count,
                                            "resupply_water_L": rw, "resupply_food_kcal": rf})
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
        st.write(f"**{len(groups)} group{'' if len(groups) == 1 else 's'} joined:** "
                 + ", ".join(g["group"] for g in groups))
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
                         "kg": t["weight"], "L": t["volume"],
                         "Submitted": submitted_by_text(g["submitted_by"])})
        st.dataframe(pd.DataFrame(rows), hide_index=True)
        if st.button("Draw trait cards", type="primary"):
            S.draw_traits(code)
            st.rerun()

    elif ph in ("traits", "playing"):
        if room["day"] > 0:
            st.markdown(resupply_html(room) + event_card_html(room["event_log"][-1], params=room["params"],
                                                              holders=loc_holders(room)),
                        unsafe_allow_html=True)
        st.caption("Resupply days (hidden from groups): " +
                   (", ".join(str(d) for d in room.get("resupply_days", [])) or "none"))
        c1, c2 = st.columns([1, 1])
        if c1.button(f"Next day → Day {room['day'] + 1}", type="primary", width="stretch"):
            S.next_day(code)
            st.rerun()
        if room["day"] > 0 and c2.button("End the game now", width="stretch"):
            S.finish(code)
            st.rerun()
        st.markdown(day_summary_html(room) + day_table_html(room), unsafe_allow_html=True)

    elif ph == "finished":
        lb = leaderboard(room)
        if not lb.empty and pd.notna(lb.iloc[0]["Final HP"]):
            st.markdown(f"<div class='rw-mid'>Winner: Group {int(lb.iloc[0]['Group'])}</div>",
                        unsafe_allow_html=True)
        show_leaderboard(st, lb)
        st.download_button("Download full day-by-day log (CSV)", all_history_csv(room),
                           file_name=f"running_wild_room_{code}.csv")
        if room["event_log"]:
            st.markdown(last_day_html(room), unsafe_allow_html=True)

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
        st.markdown(resupply_html(room, big=True)
                    + event_card_html(room["event_log"][-1], big=True, params=room["params"],
                                      holders=loc_holders(room))
                    + day_summary_html(room, big=True), unsafe_allow_html=True)
        c1, c2 = st.columns([3, 2], gap="large")
        c1.markdown(day_table_html(room, big=True, max_height=640), unsafe_allow_html=True)
        c2.line_chart(hp_chart_df(room), height=620)

    elif ph == "finished":
        lb = leaderboard(room)
        if not lb.empty and pd.notna(lb.iloc[0]["Final HP"]):
            st.markdown(f"<p class='rw-muted' style='font-size:1.6rem'>Winner</p>"
                        f"<div class='rw-big'>Group {int(lb.iloc[0]['Group'])}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='rw-big'>Nobody survived</div>", unsafe_allow_html=True)
        c1, c2 = st.columns([3, 2], gap="large")
        show_leaderboard(c1, lb)
        c2.line_chart(hp_chart_df(room), height=500)
        if room["event_log"]:
            # what happened on the last day, which the class has not seen yet
            st.markdown(last_day_html(room, big=True), unsafe_allow_html=True)


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
