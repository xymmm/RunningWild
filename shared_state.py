"""
shared_state.py — Thread-safe shared state for multi-user Streamlit.

All browser sessions on the same Streamlit server share a single JSON
file in /tmp.  A threading lock prevents corruption from concurrent writes.

Usage:
    from shared_state import get_game, update_game, create_game
"""

import json
import threading
import os
from pathlib import Path
from typing import Optional

_LOCK = threading.Lock()
_STATE_DIR = Path("/tmp/running_wild")
_STATE_DIR.mkdir(exist_ok=True)


def _path(code: str) -> Path:
    return _STATE_DIR / f"game_{code}.json"


def create_game(code: str, seed: int, instructor_key: str) -> dict:
    """Create a new game. Returns the initial game state."""
    state = {
        "code": code,
        "seed": seed,
        "instructor_key": instructor_key,
        "phase": "lobby",          # lobby → playing → finished
        "teams": {},               # team_name -> {inventory, location_id, trait_id, submitted}
        "current_day": 0,
        "team_results": {},        # populated when game starts
    }
    with _LOCK:
        json.dump(state, open(_path(code), "w"), indent=2)
    return state


def get_game(code: str) -> Optional[dict]:
    """Read game state. Returns None if game doesn't exist."""
    with _LOCK:
        p = _path(code)
        if not p.exists():
            return None
        return json.load(open(p))


def update_game(code: str, updater_fn):
    """
    Atomically read-modify-write the game state.

    updater_fn(state) -> state  (mutate in place or return new dict)
    """
    with _LOCK:
        p = _path(code)
        if not p.exists():
            return None
        state = json.load(open(p))
        result = updater_fn(state)
        if result is not None:
            state = result
        json.dump(state, open(p, "w"), indent=2)
        return state


def submit_team(code: str, team_name: str, inventory: list,
                location_id: str) -> bool:
    """Student submits their backpack. Returns True on success."""
    def _update(state):
        if state["phase"] != "lobby":
            return  # too late
        state["teams"][team_name] = {
            "inventory": inventory,
            "location_id": location_id,
            "trait_id": None,
            "submitted": True,
        }
    result = update_game(code, _update)
    return result is not None


def list_games() -> list:
    """List all active game codes."""
    with _LOCK:
        return [f.stem.replace("game_", "")
                for f in _STATE_DIR.glob("game_*.json")]


def delete_game(code: str):
    """Remove a game file."""
    with _LOCK:
        p = _path(code)
        if p.exists():
            p.unlink()
