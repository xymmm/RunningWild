# Running Wild: classroom app

A survival knapsack game for teaching mixed-integer linear programming, built for Prescriptive Analytics with Mathematical Programming (PAMP) at the University of Edinburgh Business School. Groups pack a backpack under weight and volume limits, then survive a sequence of random events projected on a shared screen. This README is for instructors and anyone maintaining the package; students have their own guide in `README_students.md`.

## Requirements

Python 3.9 or later and two packages, installed with:

```bash
python3 -m pip install -r requirements.txt
```

Run every command in a system terminal (in PyCharm, the Terminal tab rather than the Python Console), from the folder that contains `app.py`.

## Running a class

Start the app:

```bash
python3 -m streamlit run app.py
```

For a real class the app must be reachable from students' devices, so deploy it on Streamlit Community Cloud (see Deployment). The flow is the same locally, where several browser tabs can play the instructor, the big screen and the groups.

1. **Create a room.** Choose *I am the instructor*, set a PIN, the number of days and the resupply schedule, and adjust anything under *Game settings*. The app shows a 4-digit room code.
2. **Project the big screen.** In a second tab choose *Big screen* and enter the room code and PIN.
3. **Groups join.** Each group opens the app, chooses *I am a group*, and enters the room code and its group number. There is no need to say in advance how many groups there are; the instructor page lists everyone who has joined, and a group joined by mistake can be removed.
4. **Draw starting locations** once every group has joined; latecomers cannot join after this. Draws have equal probability and do not repeat until all ten cards are used, so with 11 to 20 groups each location appears at most twice.
5. **Start the selection timer.** Groups set item quantities while the app checks weight and volume. Their choices are saved continuously; when the timer ends, each group's last valid backpack is submitted automatically. You can also close selection early.
6. **Draw trait cards.** Equal probability, no repeats for up to 20 groups.
7. **Play the days.** Each click of *Next day* draws one event, applies it to every group, and shows on the big screen the event, every group's HP, water and food, the reason for each change, and an HP chart. On resupply days a banner appears; the instructor page lists the resupply days in advance, groups do not see them.
8. **Finish.** After the last day the app converts leftover water and food into bonus HP, ranks the groups and names the winner. Download the day-by-day CSV from the instructor page for debriefing.

If a page is refreshed, the room survives: go back in through *Return to a room* with the code and PIN, or rejoin with the same group number.

## Default settings

All of these can be changed when creating a room.

| Setting | Default |
|---|---|
| Days | 20 |
| Starting HP, water, food | 15 HP, 6 L, 6000 kcal |
| Weight and volume limits | 15 kg, 60 L |
| Copies of one item | up to 5 |
| Daily consumption | 0.5 L water, 500 kcal food |
| Elimination | HP at or below 0; 3 days in a row without water; 10 days in a row eating under 500 kcal |
| Resupply | 3 random, unannounced days, each +2 L and +1500 kcal |
| Final bonus | min(days of water left, days of food left, 5) |

## Checking the game without the web app

```bash
python3 check_game.py                          # 15 groups, 20 days, random backpacks
python3 check_game.py --groups 20 --seed 7     # a different class
python3 check_game.py --packs sample_packs.csv # your own backpacks for chosen groups
python3 check_game.py --resupply fixed --every 5 --quiet
```

`check_game.py` runs a whole session through the same code as the app, prints each day as the big screen would show it, checks the rules automatically and ends with ALL CHECKS PASSED or a list of problems. It saves `results.csv`, `day_by_day.csv` and `backpacks.csv` in `check_output/`. In `sample_packs.csv` each row is a group number, an item id from `data/items.csv`, and a quantity.

Two further tools:

```bash
python3 -m pytest tests      # rule examples from the slides and the cards
python3 calibrate.py 20      # Monte Carlo comparison of simple strategies
```

Run both after any change to the data files.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit interface: group, instructor and big-screen views |
| `engine.py` | Every game rule: draws, protection, location and trait effects, water and food, elimination, final score |
| `rooms.py` | Private rooms shared by all browser sessions, with snapshots in the system temp folder |
| `check_game.py` | Offline run of a full session with automatic checks and CSV logs |
| `calibrate.py` | Strategy comparison by simulation |
| `tests/test_rules.py` | Worked examples from the Lecture 10 slides and the printed cards |
| `data/` | The game content, described below |
| `AUDIT.md` | Every correction and balance change, with the reasons |
| `README_students.md` | Rules and instructions for students |

## Game data

The files in `data/` are the single source of truth. They can be edited in Excel or a text editor; restart the app afterwards, because data are loaded once at start-up.

**items.csv** has one row per item: `id`, `name`, `weight_kg`, `volume_L`, `category`, `kcal`, `litres`, and `needs`, which lists items that must also be packed for the food to count (for example `cooking_pot+stove_fuel` for rice).

**events.csv** has one row per event:

| Column | Meaning |
|---|---|
| `base_hp` | HP change when the group is not protected |
| `mitigation` | Protection alternatives: `\|` separates alternatives, `+` joins items that must all be carried. `tent+sleeping_bag\|four_season_tent` means a tent and a sleeping bag, or a four-season tent |
| `need_water` | Litres the group must hold that day for protection to work |
| `mit_hp` | HP change when protected, usually 0 |
| `weight` | Relative chance of the event being drawn |
| `water_change`, `food_change` | Water or food found (always received) or lost (only when unprotected) |
| `extra_water`, `extra_food` | Extra consumption on that day |
| `boost_item`, `boost_mult` | An item that multiplies the event's gain, such as the fishing kit |
| `tags` | Categories that location and trait rules refer to, such as `cold_weather`, `navigation`, `water_gain` |

**locations.json** holds each card's on-screen text and its rules: `hp_rules` (a tag and an HP change, optionally `unless_items` and `always`), `water_gain_mult`, `water_gain_requires`, `food_gain_bonus` and `zero_tags`.

**traits.json** holds the on-screen text of each trait card; the rules themselves are in `_apply_trait` in `engine.py`.

**parameters.json** holds the defaults shown in the table above.

## Rule conventions

These are stated in the header of `engine.py` and are the ones to explain in the teaching note.

- One event per day, drawn in proportion to its weight; every group faces the same event.
- An event is protected if one alternative in `mitigation` is fully carried and the group holds the `need_water` litres. Extra copies of an item never protect twice.
- Location and trait changes apply only to unprotected damage events unless a rule is marked `always`. When several rules on one card match an event, only the largest applies, and no rule turns damage into a gain.
- Daily order: resupply, event HP, event water and food, drinking and eating, daily trait effects, elimination.
- Survivors rank above eliminated groups; among survivors, by final HP; among eliminated groups, later elimination ranks higher.

## Deployment on Streamlit Community Cloud

Push this folder to a **private** GitHub repository, because the data files reveal which items protect against which events. Create an app at share.streamlit.io with `app.py` as the entry point and share its address with students. Free apps sleep when unused, so open the app a few minutes before class. Rooms are kept in the server's memory and temporary files, so a redeployment during a class ends the running game.

## Before using it in class

The GAMS template that students complete still contains the earlier item list, event list and mitigation matrix. Regenerate it from `data/` so that students model the same game the app plays (see section 8 of `AUDIT.md`).

## Author

Dr Xiyuan Ma, University of Edinburgh Business School
