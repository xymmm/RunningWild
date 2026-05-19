# 🎒 Running Wild — Survival Knapsack Game

A classroom game for teaching Mixed-Integer Linear Programming (MILP) through a wilderness survival scenario. Developed for the Prescriptive Analytics with Mathematical Programming (PAMP) course at the University of Edinburgh Business School.

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## How It Works

Student teams select a backpack loadout under weight and volume constraints, then survive 50 days of stochastic events. Items can mitigate event damage. Teams that plan well — or solve the MILP — survive longer.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit web app (classroom interface) |
| `gamedata.py` | Data loader and query API |
| `simulator.py` | Core game simulation engine |
| `calendar_gen.py` | Generates the 50-day event calendar from a seed |
| `monte_carlo.py` | Strategy comparison and calibration validation |
| `build_data.py` | Source-of-truth for all game data; regenerates CSV/JSON |

## Deployment (Streamlit Cloud)

1. Push this repo to GitHub (private recommended — see note below).
2. Go to [share.streamlit.io](https://share.streamlit.io).
3. Connect the repo and set `app.py` as the main file.

## Privacy Note

`events.csv` contains the full mitigation mapping (which items prevent which events). If the repo is **public**, students can find this data and bypass the planning exercise. Two options:

- **Private repo** (recommended): deploy via Streamlit Cloud with GitHub authentication.
- **Public repo**: accept that determined students may find the data. The printed item and event cards remain the primary planning interface.

## Author

Dr Xiyuan Ma, University of Edinburgh Business School
