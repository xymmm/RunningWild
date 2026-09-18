"""
rooms.py — private classroom rooms shared by all browser sessions.

Streamlit runs every visitor in the same Python process, so one in-memory
store (created once with st.cache_resource in app.py) is shared by the
instructor, the big screen and every group. A lock serialises changes and
each change is also written to a JSON snapshot so that a page refresh never
loses the game.
"""

import copy
import json
import random
import threading
import time
from pathlib import Path

import engine

SNAP_DIR = Path("/tmp/running_wild_rooms")
SNAP_DIR.mkdir(exist_ok=True)

PHASES = ["lobby", "locations", "selection", "selection_closed", "traits", "playing", "finished"]


class RoomStore:
    def __init__(self, data):
        self.data = data
        self.lock = threading.RLock()
        self.rooms = {}
        for f in SNAP_DIR.glob("room_*.json"):
            try:
                r = json.load(open(f))
                self.rooms[r["code"]] = r
            except Exception:
                pass

    # ------------------------------------------------------------------ utils
    def _save(self, room):
        json.dump(room, open(SNAP_DIR / f"room_{room['code']}.json", "w"))

    def get(self, code):
        with self.lock:
            r = self.rooms.get(code)
            return copy.deepcopy(r) if r else None

    def check_pin(self, code, pin):
        r = self.rooms.get(code)
        return r is not None and r["pin"] == pin

    # ----------------------------------------------------------------- create
    def create(self, pin, days, params_override=None):
        with self.lock:
            code = None
            while code is None or code in self.rooms:
                code = f"{random.randint(1000, 9999)}"
            params = dict(self.data["params"])
            params.update(params_override or {})
            room = {
                "code": code, "pin": pin, "created": time.time(),
                "seed": random.randint(1, 10**9),
                "phase": "lobby", "days": int(days), "day": 0,
                "deadline": None, "params": params,
                "groups": {}, "event_log": [],
            }
            self.rooms[code] = room
            self._save(room)
            return code

    # ------------------------------------------------------------------ lobby
    def join(self, code, group):
        with self.lock:
            r = self.rooms.get(code)
            if r is None:
                return False, "Room not found. Check the room code."
            g = str(group)
            if g in r["groups"]:
                return True, "rejoined"
            if r["phase"] != "lobby":
                return False, "This game has already started; ask the instructor."
            r["groups"][g] = {"group": g, "location": None, "trait": None,
                              "draft": {}, "last_feasible": {}, "submitted": None,
                              "submitted_by": None, "state": None}
            self._save(r)
            return True, "joined"

    def remove_group(self, code, group):
        with self.lock:
            r = self.rooms[code]
            if r["phase"] == "lobby":
                r["groups"].pop(str(group), None)
                self._save(r)

    # -------------------------------------------------------------- locations
    def draw_locations(self, code):
        with self.lock:
            r = self.rooms[code]
            rng = random.Random(f"{r['seed']}-locations")
            gids = sorted(r["groups"], key=int)
            draw = engine.draw_cards(gids, list(self.data["locations"]), rng)
            for g, loc in draw.items():
                r["groups"][g]["location"] = loc
            r["phase"] = "locations"
            self._save(r)

    # -------------------------------------------------------------- selection
    def start_selection(self, code, minutes):
        with self.lock:
            r = self.rooms[code]
            r["deadline"] = time.time() + 60 * float(minutes)
            r["phase"] = "selection"
            self._save(r)

    def save_draft(self, code, group, inv):
        with self.lock:
            r = self.rooms[code]
            g = r["groups"][str(group)]
            if r["phase"] != "selection" or g["submitted"] is not None:
                return False
            inv = {k: int(v) for k, v in inv.items() if v and int(v) > 0}
            g["draft"] = inv
            if engine.is_feasible(inv, self.data, r["params"]):
                g["last_feasible"] = inv
            self._save(r)
            return True

    def submit(self, code, group, inv):
        with self.lock:
            r = self.rooms[code]
            g = r["groups"][str(group)]
            if r["phase"] != "selection" or g["submitted"] is not None:
                return False, "Selection is closed."
            inv = {k: int(v) for k, v in inv.items() if v and int(v) > 0}
            if not engine.is_feasible(inv, self.data, r["params"]):
                return False, "Your backpack exceeds the weight or volume limit."
            g["draft"] = g["last_feasible"] = g["submitted"] = inv
            g["submitted_by"] = "group"
            self._save(r)
            return True, "submitted"

    def close_selection(self, code):
        with self.lock:
            r = self.rooms[code]
            if r["phase"] != "selection":
                return
            for g in r["groups"].values():
                if g["submitted"] is None:
                    g["submitted"] = g["last_feasible"]
                    g["submitted_by"] = "auto (time up)"
            r["phase"] = "selection_closed"
            r["deadline"] = None
            self._save(r)

    def tick(self, code):
        """Called by every auto-refreshing view: closes selection at the deadline."""
        r = self.rooms.get(code)
        if r and r["phase"] == "selection" and r["deadline"] and time.time() >= r["deadline"]:
            self.close_selection(code)

    # ----------------------------------------------------------------- traits
    def draw_traits(self, code):
        with self.lock:
            r = self.rooms[code]
            rng = random.Random(f"{r['seed']}-traits")
            gids = sorted(r["groups"], key=int)
            draw = engine.draw_cards(gids, list(self.data["traits"]), rng)
            for g, tr in draw.items():
                grp = r["groups"][g]
                grp["trait"] = tr
                grp["state"] = engine.init_team_state(grp["submitted"] or {}, grp["location"], tr,
                                                      self.data, r["params"])
            r["phase"] = "traits"
            self._save(r)

    # ------------------------------------------------------------------- days
    def next_day(self, code):
        with self.lock:
            r = self.rooms[code]
            if r["phase"] not in ("traits", "playing"):
                return
            r["phase"] = "playing"
            r["day"] += 1
            eid = engine.draw_event(self.data, r["seed"], r["day"])
            r["event_log"].append(eid)
            for g in r["groups"].values():
                team = {"inv": g["submitted"] or {}, "location": g["location"],
                        "trait": g["trait"], "state": g["state"]}
                engine.resolve_day(team, eid, r["day"], self.data, r["params"])
            alive = [g for g in r["groups"].values() if g["state"]["alive"]]
            if r["day"] >= r["days"] or not alive:
                r["phase"] = "finished"
            self._save(r)

    def finish(self, code):
        with self.lock:
            r = self.rooms[code]
            r["phase"] = "finished"
            self._save(r)

    def delete(self, code):
        with self.lock:
            self.rooms.pop(code, None)
            p = SNAP_DIR / f"room_{code}.json"
            if p.exists():
                p.unlink()
