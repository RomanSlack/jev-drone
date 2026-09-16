"""Jev tactical layer: the drone's programmable common sense.

Everything a human should review lives at the top of this file: the questions,
the option rubrics, and the thresholds. Nothing else in the project hard-codes a
number that changes how the aircraft reacts to a judgment.

Runs off the control loop in a worker thread. The flight code never blocks on it
and never *needs* it -- it reads whatever judgment is currently cached, and the
reflex layer in run.py owns safety regardless of what comes back.
"""
import os, threading, queue, time
from typesafe_sdk import TypeSafeClient, Choice, Noul, Score

MODEL = "jev-latest"

# --- how the flight code reacts to a judgment -------------------------------
THRESHOLDS = {
    "stale_after_s": 1.5,     # ignore a judgment older than this; the world moved on
    "risk_slow_down": 1.45,   # score above which we bleed speed regardless of maneuver
    "call_hz": 3.0,           # upper bound on how often we ask
    "call_budget": 160,      # hard cap per episode, so a bug cannot run up a bill
    "consult_within_m": 4.0,  # only ask when something is actually in the way...
    "consult_lost_s": 1.0,    # ...or the target has been missing this long
    "climb_steps": 150,       # ~3s: long enough to rise AND cross, not just bob up
    "commit_steps": 55,       # ~1.4s at 50Hz: commit to a maneuver instead of chattering
    "override_risk": 1.7,     # ...unless things get this dangerous, then re-decide now
    "really_lost": 0.5,       # Noul above which we stop trusting the remembered bearing       # hard cap per episode, so a bug cannot run up a bill
}

# The drone's own capabilities. Without this the model cannot know that "climb"
# is physically available, or what counts as a small height.
AIRCRAFT = {
    "type": "quadrotor, camera-only, no map and no GPS",
    "cruise_altitude_m": 1.6,
    "can_climb_to_m": 3.0,
    "climb_takes_about_s": 1.5,
    "top_speed_mps": 3.6,
    "note": "All distances are from a forward camera. 25 m means nothing was detected.",
}

MISSION = ("Follow the ground rover and keep it in view. Do not hit anything. "
           "Losing the rover briefly is acceptable; hitting an obstacle is not.")

MANEUVERS = {
    "hold_course": (
        "Nothing meaningfully blocks the pursuit line: the path ahead is clear for "
        "several metres. Keep flying straight at the target."),
    "gap_left": (
        "Something blocks the way ahead, and the left sectors show clearly more free "
        "space than the right. Steer around it to the left."),
    "gap_right": (
        "Something blocks the way ahead, and the right sectors show clearly more free "
        "space than the left. Steer around it to the right."),
    "climb": (
        "The obstruction ahead is LOW: its top edge is visible to the camera and only a "
        "short distance above the drone (obstruction_top_above_drone_m is small and "
        "obstruction_taller_than_camera_can_see is false). This is the right answer when "
        "every sector is blocked, because that means there is no gap to steer through, "
        "but the thing is short enough to simply fly over."),
    "brake": (
        "Close to something on several sides and no option is clearly better. Bleed off "
        "speed and hold until the picture improves."),
    "reacquire": (
        "The target has been out of sight long enough that the remembered bearing is "
        "stale. Stop chasing it and sweep to find the target again."),
}

QUESTIONS = {
    "maneuver": Choice(
        instructions={
            "role": "You are the tactical decision layer of an autonomous quadrotor.",
            "mission": MISSION,
            "ask": "Which single maneuver should the drone commit to right now?",
        },
        criteria=MANEUVERS,
    ),
    "risk": Score(
        instructions="How dangerous is the drone's immediate situation?",
        criteria=["clear and open", "tight but manageable", "about to hit something"],
    ),
    "target_truly_lost": Noul(
        instructions=(
            "Has the drone genuinely lost the rover? Judge from unseen_for_s: a fraction "
            "of a second behind a pillar is a normal occlusion, several seconds of nothing "
            "in an open scene means the chase line is stale."),
        criteria={"true": "Give up the remembered bearing and sweep to search.",
                  "false": "Keep flying the last known bearing; it should reappear."},
    ),
}


def decision_needed(scene):
    """Code decides WHEN there is a judgment worth paying for. On an empty corridor
    with the target in view there is nothing to decide, so we do not ask."""
    return (scene["nearest_obstacle_m"] < THRESHOLDS["consult_within_m"]
            or scene["sectors_blocked_of_5"] >= 1
            or (scene["target"]["unseen_for_s"] or 0.0) >= THRESHOLDS["consult_lost_s"])


def build_state(scene):
    """Everything the model is allowed to know, and nothing it cannot observe."""
    return {"mission": MISSION, "aircraft": AIRCRAFT, "observed": scene}


DEFAULT = {"maneuver": "hold_course", "risk": 0.0, "confidence": 0.0,
           "target_truly_lost": 0.0, "source": "default", "age_s": 0.0,
           "probabilities": {}}


class Tactician:
    """Asks Jev for a judgment at most `hz` times a second, and only when the
    scene has actually changed enough to be worth a call."""

    def __init__(self, hz=THRESHOLDS["call_hz"], budget=THRESHOLDS["call_budget"], model=MODEL):
        key = os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY")
        if not key:
            raise RuntimeError("set TYPESAFE_API_KEY (see .env.example)")
        self.client = TypeSafeClient(api_key=key)
        self.min_dt = 1.0 / hz
        self.budget = budget
        self.model = model
        self.calls = 0
        self.skipped = 0
        self.errors = 0
        self.n_offer = 0
        self.n_ratelimited = 0
        self.n_full = 0
        self.last_error = None
        self.tokens = 0
        self.latency = []
        self._q = queue.Queue(maxsize=1)
        self._latest = dict(DEFAULT)
        self._stamp = 0.0
        self._lock = threading.Lock()
        self._last_sent = float("-inf")
        self._last_key = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    @staticmethod
    def _key(scene):
        """Coarse fingerprint: only re-ask when the situation is materially new."""
        t = scene["target"]
        return (
            scene["sectors_blocked_of_5"],
            bool(scene["obstruction_taller_than_camera_can_see"]),
            tuple(min(int(v / 1.5), 6) for v in scene["sector_range_m"].values()),
            min(int(scene["nearest_obstacle_m"] / 1.5), 6),
            t["visible"],
            None if t["bearing_deg"] is None else int(t["bearing_deg"] / 15),
            (t["unseen_for_s"] or 0) > 2.0,
        )

    def offer(self, scene, now):
        """Non-blocking. Hand the latest scene over if it's worth a call."""
        self.n_offer += 1
        if self.calls >= self.budget or now - self._last_sent < self.min_dt:
            self.n_ratelimited += 1
            return
        key = self._key(scene)
        if key == self._last_key:
            self.skipped += 1
            return
        try:
            self._q.put_nowait((scene, now))
            self._last_sent, self._last_key = now, key
        except queue.Full:
            self.n_full += 1

    def read(self, now):
        with self._lock:
            out = dict(self._latest)
        out["age_s"] = round(now - self._stamp, 2)
        return out

    def _worker(self):
        while not self._stop.is_set():
            try:
                scene, now = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            t0 = time.time()
            try:
                r = self.client.system_one(state=build_state(scene), model=self.model, questions=QUESTIONS)
                a = r.answers
                judgment = {
                    "maneuver": a["maneuver"].choice,
                    "confidence": round(a["maneuver"].confidence, 3),
                    "probabilities": {k: round(v, 3) for k, v in a["maneuver"].probabilities.items()},
                    "risk": round(a["risk"].score, 2),
                    "target_truly_lost": round(a["target_truly_lost"].noul, 3),
                    "source": "jev",
                }
                self.tokens += r.usage.input_tokens + r.usage.output_tokens
                self.calls += 1
                self.latency.append(time.time() - t0)
                with self._lock:
                    self._latest, self._stamp = judgment, now
            except Exception as e:                    # degrade, never crash the flight
                self.errors += 1
                self.last_error = f"{type(e).__name__}: {e}"[:160]
                with self._lock:
                    self._latest = dict(DEFAULT, source=f"error:{type(e).__name__}")

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1.0)
        try:
            self.client.close()
        except Exception:
            pass

    def stats(self):
        lat = sorted(self.latency)
        return {"calls": self.calls, "skipped_unchanged": self.skipped, "errors": self.errors,
                "last_error": self.last_error, "tokens": self.tokens,
                "offers": self.n_offer, "rate_limited": self.n_ratelimited, "queue_full": self.n_full,
                "median_latency_s": round(lat[len(lat) // 2], 3) if lat else None,
                "p90_latency_s": round(lat[int(len(lat) * 0.9)], 3) if lat else None}
