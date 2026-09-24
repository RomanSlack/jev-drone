"""Jev as the ONLY navigator for the tunnel chase.

There is no hand-written obstacle avoidance and no safety reflex here. If Jev
does not call the dodge, the aircraft hits the thing. That is the point: the
metric is how fast the vehicle can go before a ~0.135s judgment loop stops
being fast enough.

Pipelined: several workers each take the freshest scene, so decision RATE can
exceed 1/latency, while each individual decision is still 0.135s stale.
"""
import os, threading, time
from typesafe_sdk import TypeSafeClient, Choice, Noul, Score

MODEL = "jev-latest"

THRESHOLDS = {
    "workers": 6,          # concurrent in-flight requests
    "min_dispatch_dt": 0.045,   # ~22 decisions/s
    "stale_after_s": 0.3,  # acting on a judgment 0.8s old meant 7 m of travel
                           # on stale data, as long as the whole dodge takes
    "commit_s": 0.8,   # a lateral dodge takes about this long to execute
}

# A 6-way label re-picked every 70 ms makes bang-bang control. These are graded:
# the answer IS the steering command, and the level index maps straight to it.
STEER_LEVELS = [
    "bank hard left - the way ahead is blocked and the left sectors are far more open",
    "ease left - drifting left improves the picture",
    "hold the centre line - the path ahead is clear enough to keep chasing the car",
    "ease right - drifting right improves the picture",
    "bank hard right - the way ahead is blocked and the right sectors are far more open",
]

HEIGHT_LEVELS = [
    "dive - free_ahead_below_m is far larger than free_ahead_level_m, so there is "
    "clear air underneath the thing in the way",
    "ease down - a little lower is better",
    "hold this height",
    "ease up - a little higher is better",
    "climb - free_ahead_above_m is far larger than free_ahead_level_m, so there is "
    "clear air over the top of the thing in the way",
]

_ASK = {
    "role": "You are the sole navigator of a quadrotor chasing a car down a tunnel.",
    "mission": "Stay behind the car. Do not hit anything. There is no other collision "
               "avoidance: if you do not call the move, it crashes.",
    "reading_the_scene": "sector_range_m is free space by direction, listed left to "
                         "right. free_ahead_above/level/below_m is free space stacked "
                         "vertically straight ahead. room_left_m and room_right_m are "
                         "the tunnel walls. Bigger is more room.",
    "timing": "A move takes about a second to complete, so commit while "
              "seconds_to_blockage_ahead is still around 2, not when it is small.",
}

QUESTIONS = {
    "steer": Score(instructions=dict(_ASK, ask="How hard should it steer, and which way?"),
                   criteria=STEER_LEVELS),
    "height": Score(instructions=dict(_ASK, ask="Should it change height, and how much?"),
                    criteria=HEIGHT_LEVELS),
    "risk": Score(instructions="How close is this aircraft to hitting something?",
                  criteria=["open tunnel", "must commit to a move now", "impact unavoidable"]),
}

AIRCRAFT = {
    "type": "quadrotor, camera only, inside a 13 m wide by 7 m tall tunnel",
    "note": "Tunnel walls show up as limited range in the outermost sectors. "
            "25 m means nothing was detected. You move sideways and vertically "
            "about half as fast as you fly forward.",
    "a_move_takes_about_s": 1.0,
    "committing_late": "A move started with less than about 1.5s to contact will not "
                       "finish in time. Commit early, while it still looks calm.",
    "already_moving": "already_sliding_sideways_mps is how fast it is ALREADY moving "
                      "sideways (positive = left). If it is already sliding the way you "
                      "want, ease back toward centre or it will overshoot the gap and "
                      "hit the far wall.",
    "staying_inside": "room_left_m and room_right_m are the distances to the tunnel "
                      "walls. Below about 2 m you are about to scrape that wall, so do "
                      "not keep going that way even to avoid something else.",
}


def build_state(scene, speed, sideways=0.0, climbrate=0.0):
    """Ranges alone describe the present. At 15 m/s an obstacle 12 m ahead is
    0.8s away and must be dodged NOW; at 4 m/s it is three seconds of nothing.
    Time-to-contact is the quantity the decision actually turns on."""
    v = max(speed, 0.5)
    obs = dict(scene)
    obs["seconds_to_blockage_ahead"] = round(scene["free_ahead_level_m"] / v, 2)
    obs["seconds_if_we_climb"] = round(scene["free_ahead_above_m"] / v, 2)
    obs["seconds_if_we_dive"] = round(scene["free_ahead_below_m"] / v, 2)
    # Without its own motion the model cannot tell "I need to go left" from
    # "I am already going left fast enough" -- so it keeps commanding the dodge
    # and sails straight through the gap into the far wall.
    obs["already_sliding_sideways_mps"] = round(sideways, 2)   # + is to the left
    obs["already_changing_height_mps"] = round(climbrate, 2)
    return {"aircraft": AIRCRAFT, "speed_mps": round(speed, 1), "observed": obs}


DEFAULT = {"steer": 2.0, "height": 2.0, "risk": 0.0, "confidence": 0.0,
           "source": "default", "age_s": 0.0}


class FastTactician:
    def __init__(self, workers=None, budget=4000):
        key = os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY")
        self.client = TypeSafeClient(api_key=key)
        self.n = workers or THRESHOLDS["workers"]
        self.budget = budget
        self.calls = self.errors = self.tokens = 0
        self.attempts = 0
        self.last_error = None
        self.latency = []
        self.staleness = []
        self._scene = None          # (scene, sim_t, speed)
        self._seq = 0
        self._judg = dict(DEFAULT)
        self._judg_seq = -1
        self._lock = threading.Lock()
        self._last_dispatch = 0.0
        self._stop = threading.Event()
        self._threads = [threading.Thread(target=self._worker, daemon=True)
                         for _ in range(self.n)]
        for t in self._threads:
            t.start()

    def offer(self, scene, sim_t, speed, sideways=0.0, climbrate=0.0):
        with self._lock:
            self._seq += 1
            self._scene = (scene, sim_t, speed, self._seq, sideways, climbrate)

    def read(self, sim_t):
        with self._lock:
            j = dict(self._judg)
        j["age_s"] = round(sim_t - j.get("sim_t", sim_t), 3)
        return j

    def _worker(self):
        seen = -1
        while not self._stop.is_set():
            with self._lock:
                cur = self._scene
                if cur is None or cur[3] == seen or self.attempts >= self.budget:
                    cur = None
                else:
                    now = time.time()
                    if now - self._last_dispatch < THRESHOLDS["min_dispatch_dt"]:
                        cur = None
                    else:
                        self._last_dispatch = now
                        seen = cur[3]
                        # Reserve the budget before releasing the lock so concurrent
                        # workers cannot dispatch more than the configured cap.
                        self.attempts += 1
            if cur is None:
                time.sleep(0.004)
                continue
            scene, sim_t, speed, seq, sw, cr = cur
            t0 = time.time()
            try:
                r = self.client.system_one(state=build_state(scene, speed, sw, cr),
                                           model=MODEL, questions=QUESTIONS)
                a = r.answers
                j = {"steer": float(a["steer"].score),
                     "height": float(a["height"].score),
                     "steer_conf": round(a["steer"].confidence, 3),
                     "confidence": round(a["steer"].confidence, 3),
                     "risk": round(a["risk"].score, 2),
                     "source": "jev", "sim_t": sim_t}
                with self._lock:
                    self.calls += 1
                    self.tokens += r.usage.input_tokens + r.usage.output_tokens
                    self.latency.append(time.time() - t0)
                    if seq > self._judg_seq:
                        self._judg, self._judg_seq = j, seq
            except Exception as ex:
                with self._lock:
                    self.errors += 1
                    self.last_error = f"{type(ex).__name__}: {ex}"[:300]

    def close(self):
        self._stop.set()
        for t in self._threads:
            t.join(timeout=1.0)
        try:
            self.client.close()
        except Exception:
            pass

    def stats(self):
        lat = sorted(self.latency)
        return {"calls": self.calls, "attempts": self.attempts,
                "errors": self.errors, "tokens": self.tokens,
                "workers": self.n, "last_error": self.last_error,
                "median_latency_s": round(lat[len(lat) // 2], 3) if lat else None,
                "p90_latency_s": round(lat[int(len(lat) * .9)], 3) if lat else None}
