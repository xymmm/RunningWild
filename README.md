# Running Wild: classroom app

Survival knapsack game for teaching MILP in Prescriptive Analytics with Mathematical Programming (PAMP), University of Edinburgh Business School.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the printed address in several browser tabs to try the instructor, big-screen and group views together.

## How a session runs

1. **Instructor** creates a room with a PIN, the number of days (default 20) and the resupply schedule. The app shows a 4-digit room code.
2. **Big screen**: open the app in a second tab, choose *Big screen*, enter the room code and PIN, and project it.
3. **Groups** open the app on their own devices, choose *I am a group*, and enter the room code and their group number.
4. Instructor draws **starting locations**: equal probability, no repeats until all 10 cards are used.
5. Instructor starts the **selection timer**. Groups set item quantities; weight and volume are checked live. When the timer ends, each group's last valid backpack is submitted automatically.
6. Instructor draws **trait cards**: equal probability, no repeats for up to 20 groups.
7. Instructor clicks **Next day**. One event is drawn by probability and applied to every group; the big screen shows the event, every group's HP, water and food, the reason for each change, and an HP chart.
8. After the last day the app converts remaining water and food into HP and names the winner. A day-by-day CSV log can be downloaded.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit interface: group, instructor and big-screen views |
| `engine.py` | All game rules: draws, mitigation, location and trait effects, water and food, elimination, final score |
| `rooms.py` | Private rooms shared by all browser sessions, with snapshots in `/tmp` |
| `calibrate.py` | Monte Carlo comparison of simple strategies under the current settings |
| `tests/test_rules.py` | 60 checks against the worked examples in the slides and the printed cards |
| `AUDIT.md` | What was corrected against the printed table, cards and slides, and why the defaults changed |
| `data/items.csv` | 118 items with weight, volume, kcal, litres, and cooking needs |
| `data/events.csv` | 196 events: tags, HP, mitigation alternatives, water needed on hand, draw weight, water and food effects |
| `data/locations.json` | 10 location cards: printed text and rules |
| `data/traits.json` | 20 trait cards: printed text (rules are in `engine.py`) |
| `data/parameters.json` | Default starting values, capacities and daily consumption |

The files in `data/` are the single source of truth and can be edited in Excel or a text editor.

## Rule conventions

These are stated in the header of `engine.py` and are the ones to describe in the teaching note:

- One event per day, drawn with probability proportional to its weight; the same event applies to every group.
- Location and trait modifiers act on unmitigated damage events only, unless a rule is marked `always`; if several rules on one card match an event, only the largest applies; a modifier never turns damage into a gain.
- Water and food gains always happen; losses happen only when the event is not mitigated.
- Daily order: event HP, event water and food, drinking and eating, daily trait effects, elimination.
- Extra copies of an item add weight, volume, water and food but do not mitigate twice.
- In `mitigation`, `|` separates alternatives and `+` joins items that must all be carried; `need_water` is the water the group must hold that day.
- Resupply days add water and food to every surviving group before the day's event; random resupply days are hidden from groups.

## Deployment on Streamlit Community Cloud

Push this folder to a **private** GitHub repository, then create an app at share.streamlit.io with `app.py` as the entry point. Open the app a few minutes before class, because free apps go to sleep when unused.
