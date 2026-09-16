"""Follow-and-avoid episode: Skydio X2 chases a ground rover through a pillar field.

Layering:
  500 Hz  geometric controller           (flight.Pilot)
   50 Hz  guidance + hard safety reflex  (this file -- always owns safety)
   15 Hz  onboard camera -> scene        (flight.Eye)
  ~3 Hz   Jev tactical judgment          (tactics.Tactician, advisory only)
"""
import os, sys, json, time, argparse
import numpy as np
import mujoco
import flight
from tactics import THRESHOLDS as THRESH, decision_needed

STANDOFF = 3.5
MIN_ALT = 1.15           # never command a descent below this; the floor is invisible to a
                         # downward-blind camera, so altitude has to be protected in code
CRUISE_ALT = 1.6
CHASE_FOVY = 50.0        # cinematic lens for the third-person render
CLIMB_ALT = 3.0          # beams top out at 2.1; this clears them with margin
CLIMB_HOLD_STEPS = 90    # ~1.8 s at 50 Hz guidance
REFLEX_M = 2.2           # code-owned: below this, Jev's opinion is irrelevant
TRACE = bool(os.environ.get("TRACE"))


ROVER_SPEED = 0.80
SEARCH_SPEED = 1.4       # while searching, still out-pace the rover


def rover_pose(t):
    return np.array([6.0 + ROVER_SPEED * t, 2.0 * np.sin(0.26 * t), 0.2])


def _qz(theta):
    """Quaternion for Rz(theta) applied to a capsule already lying along y."""
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    h = np.sqrt(0.5)
    # Rz(theta) (x) Rx(90deg), in w x y z
    return np.array([c * h, c * h, s * h, s * h])


def drive_course(m, d, t):
    """Move every mocap obstacle. Kept slow: mocap bodies teleport rather than
    move, so a fast sweep can materialise inside the drone and fling it."""
    d.mocap_pos[m.body("rover").mocapid[0]] = rover_pose(t)
    for i, name in enumerate(("arm0", "arm1")):
        mid = m.body(name).mocapid[0]
        d.mocap_quat[mid] = _qz(0.45 * t + i * 1.9)
    # the gap tracks the rover, so the leader always fits; the drone trails by
    # several seconds and therefore meets the gap somewhere else entirely
    c = 2.0 * np.sin(0.26 * t)
    for name, off in (("gateL", 31.2), ("gateR", -31.2)):
        mid = m.body(name).mocapid[0]
        p = d.mocap_pos[mid].copy()
        p[1] = c + off
        d.mocap_pos[mid] = p


class Guidance:
    """Turns a scene summary (+ an optional Jev judgment) into a velocity command.

    Rule the whole thing obeys: never translate faster sideways than the camera can
    see. The aircraft has a 91 deg forward view, so evasion is done by YAWING toward
    open space and flying into it, not by sliding blindly.
    """

    def __init__(self, eye):
        self.eye = eye
        self.last_bearing = 0.0
        self.yaw_sp = None
        self.sweep = 0.0
        self.lost_for = 0.0
        self.climb_hold = 0
        self.commit = None
        self.commit_left = 0
        self.search_yaw = None

    def _open_side(self, sec, left):
        """Bearing of the more open sector on the requested side."""
        names = ("far_left", "left") if left else ("far_right", "right")
        best = max(names, key=lambda n: sec[n])
        return self.eye.sector_bearing(best)

    def __call__(self, scene, judg, yaw, z, use_jev, fresh=False):
        if self.yaw_sp is None:
            self.yaw_sp = yaw
        sec = scene["sector_range_m"]
        tgt = scene["target"]

        if tgt["visible"]:
            self.last_bearing = np.deg2rad(tgt["bearing_deg"])
            rng = tgt["range_m"]
            self.lost_for = 0.0
            self.search_yaw = None
        else:
            rng = STANDOFF + 1.5
            self.lost_for = tgt["unseen_for_s"] or 0.0
            if self.search_yaw is None:
                self.search_yaw = self.yaw_sp

        # Every heading correction below is expressed RELATIVE to the live yaw and
        # re-derived each camera frame, so nothing can accumulate into a spin.
        yaw_rel = float(np.clip(self.last_bearing, -0.6, 0.6)) if tgt["visible"] else 0.0
        absolute_yaw = None
        fwd = float(np.clip(1.0 * (rng - STANDOFF) + 0.95, 0.0, 2.2))

        self.climb_hold = max(0, self.climb_hold - 1)
        alt_sp = CLIMB_ALT if self.climb_hold else CRUISE_ALT

        # --- reactive layer: turn away from the worst threat and slow down --------
        left_room = min(sec["far_left"], sec["left"])
        right_room = min(sec["far_right"], sec["right"])
        wr = min(sec.values())
        turn_bias, slide = 0.0, 0.0
        if wr < 4.0:
            urgency = (4.0 - wr) / 4.0
            side = 1.0 if left_room > right_room else -1.0
            room = max(left_room, right_room)
            # Strafe, keeping the nose on the target -- but only as fast as the side we
            # are strafing into is actually observed to be clear.
            slide = side * 2.6 * urgency * min(1.0, room / 4.0)
            fwd *= 1.0 - 0.7 * urgency

        # --- Jev's tactical commitment (advisory) --------------------------------
        acted = False
        if (use_jev and judg["source"] == "jev" and judg["age_s"] < THRESH["stale_after_s"]
                and (decision_needed(scene) or self.climb_hold)):
            self.commit_left = max(0, self.commit_left - 1)
            if self.commit_left == 0 or judg["risk"] >= THRESH["override_risk"]:
                if judg["maneuver"] != self.commit:
                    self.commit, self.commit_left = judg["maneuver"], THRESH["commit_steps"]
            mv = self.commit
            if not decision_needed(scene):
                mv = "hold_course"                 # the way is clear; stop maneuvering
                self.commit, self.commit_left = None, 0
            if judg["target_truly_lost"] >= THRESH["really_lost"] and mv != "climb":
                mv = "reacquire"
            acted = True

            if mv in ("gap_left", "gap_right"):
                left = mv == "gap_left"
                room = left_room if left else right_room
                slide = (1.0 if left else -1.0) * 2.6 * min(1.0, room / 4.0)
                if not tgt["visible"]:             # nothing to point at, so face the gap
                    yaw_rel = self._open_side(sec, left)
                fwd = max(fwd, 0.7)
            elif (mv == "climb" and scene["sectors_blocked_of_5"] >= 4
                  and scene["obstruction_taller_than_camera_can_see"] is False
                  and scene["obstruction_top_above_drone_m"] is not None
                  # only commit to going over it if we can actually get over it
                  and z + scene["obstruction_top_above_drone_m"] + 0.35 <= CLIMB_ALT):
                self.climb_hold = THRESH["climb_steps"]
                alt_sp = CLIMB_ALT
                fwd, slide, turn_bias = min(fwd, 0.5), 0.0, 0.0
            elif mv == "brake":
                fwd, slide = fwd * 0.15, slide * 0.3
            elif mv == "reacquire":
                if fresh:
                    self.sweep += 0.35
                    self.yaw_sp = (self.search_yaw if self.search_yaw is not None else yaw) + 0.7 * np.sin(self.sweep)
                absolute_yaw = self.yaw_sp
                fwd, slide, turn_bias = 0.3, 0.0, 0.0
            else:
                acted = False                      # hold_course changes nothing
            if judg["risk"] > THRESH["risk_slow_down"]:
                fwd *= 0.45
        elif self.lost_for > 1.2:
            # baseline search: never keep flying a bearing we can no longer see
            if fresh:
                self.sweep += 0.3
                self.yaw_sp = (self.search_yaw if self.search_yaw is not None else yaw) + 0.5 * np.sin(self.sweep)
            absolute_yaw = self.yaw_sp
            fwd, slide = SEARCH_SPEED, 0.0

        # --- hard reflex: code overrides everything, Jev included ------------------
        near, nb = scene["nearest_obstacle_m"], np.deg2rad(scene["nearest_bearing_deg"])
        reflex = near < REFLEX_M
        if reflex:
            side = 1.0 if left_room > right_room else -1.0
            slide = side * 2.6 * min(1.0, max(left_room, right_room) / 3.0)
            fwd = min(fwd, 0.25) if near > 1.3 else -0.8

        if fresh:
            self.yaw_sp = absolute_yaw if absolute_yaw is not None else yaw + yaw_rel + turn_bias
        yaw_cmd = self.yaw_sp

        # never slide sideways faster than the forward view can clear
        lat = float(np.clip(slide, -2.6, 2.6))

        vz = 1.6 * (max(alt_sp, MIN_ALT) - z)
        if z < MIN_ALT:
            vz = max(vz, 0.8)

        v_body = np.array([fwd, lat, np.clip(vz, -2.0, 2.0)])
        c, s = np.cos(yaw), np.sin(yaw)
        v_world = np.array([c * v_body[0] - s * v_body[1], s * v_body[0] + c * v_body[1], v_body[2]])
        return v_world, yaw_cmd, acted, reflex


def episode(seed=0, seconds=35.0, use_jev=True, video=None, hz=None, budget=None, realtime=True):
    rng = np.random.default_rng(seed)
    m = mujoco.MjModel.from_xml_path("world.xml")
    d = mujoco.MjData(m)
    dt = m.opt.timestep
    x2 = m.body("x2").id
    x2_geoms = set(np.nonzero(m.geom_bodyid == x2)[0].tolist())

    d.qpos[:3] = [1.5 + rng.uniform(-.3, .3), rng.uniform(-.5, .5), CRUISE_ALT]
    d.qpos[3:7] = [1, 0, 0, 0]
    mujoco.mj_forward(m, d)

    pilot = flight.Pilot(m)
    eye = flight.Eye(m)
    guide = Guidance(eye)
    tac = None
    if use_jev:
        from tactics import Tactician, DEFAULT
        tac = Tactician(**{k: v for k, v in (("hz", hz), ("budget", budget)) if v})
        judg = dict(DEFAULT)
    else:
        judg = {"maneuver": "hold_course", "risk": 0.0, "confidence": 0.0,
                "target_truly_lost": 0.0, "source": "off", "age_s": 0.0, "probabilities": {}}

    writer = cam = big = None
    if video:
        import imageio.v2 as imageio
        from hud import Hud
        big = mujoco.Renderer(m, 880, 1180)
        hud = Hud(1180, 880)
        cam = mujoco.MjvCamera(); cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        cam.distance, cam.elevation = 2.9, -10.0
        writer = imageio.get_writer(video, fps=30, quality=8, macro_block_size=1)
        tape = []

    v_des, yaw_cmd = np.zeros(3), 0.0
    scene, fresh = None, False
    vis, frames, standoffs, hits, hit_steps, grounded = 0, 0, [], 0, set(), 0
    crashed_at, max_x, crossed = None, -99.0, False
    jev_steps = reflex_steps = 0
    n = int(seconds / dt)

    wall0 = time.time()
    for i in range(n):
        t = i * dt
        if realtime:
            # Sim time must track wall-clock, or an API in the loop is being judged
            # against a world running 10x too fast to be a fair test.
            lag = t - (time.time() - wall0)
            if lag > 0.0005:
                time.sleep(lag)
        drive_course(m, d, t)

        pos = d.qpos[:3].copy()
        quat = d.qpos[3:7]
        yaw = float(np.arctan2(2 * (quat[0] * quat[3] + quat[1] * quat[2]),
                               1 - 2 * (quat[2] ** 2 + quat[3] ** 2)))

        if i % 33 == 0:                                  # ~15 Hz perception
            scene = eye.look(d, pos, yaw, t)
            fresh = True
            frames += 1
            vis += scene["target"]["visible"]
            if tac and decision_needed(scene):
                tac.offer(scene, t)

        if i % 10 == 0 and scene:                        # 50 Hz guidance
            if tac:
                prev = judg.get("maneuver"), judg.get("source")
                judg = tac.read(t)
                if TRACE and (judg.get("maneuver"), judg.get("source")) != prev:
                    print("  t=%5.1f %-11s p=%.2f risk=%.2f lost=%.2f | pos=(%.1f,%.1f,%.1f) blk=%d/5 near=%.2f tall=%s vis=%s"
                          % (t, judg["maneuver"], (judg.get("probabilities") or {}).get(judg["maneuver"], 0),
                             judg["risk"], judg["target_truly_lost"], pos[0], pos[1], pos[2],
                             scene["sectors_blocked_of_5"], scene["nearest_obstacle_m"],
                             scene["obstruction_taller_than_camera_can_see"], scene["target"]["visible"]),
                          flush=True)
            v_des, yaw_cmd, acted, reflex = guide(scene, judg, yaw, pos[2], use_jev, fresh)
            fresh = False
            jev_steps += acted
            reflex_steps += reflex

        d.ctrl[:] = pilot(d, v_des, yaw_cmd, dt)
        mujoco.mj_step(m, d)

        for c in range(d.ncon):
            g1, g2 = d.contact[c].geom1, d.contact[c].geom2
            if (g1 in x2_geoms) != (g2 in x2_geoms):
                obj = g2 if g1 in x2_geoms else g1
                if obj not in hit_steps:
                    hit_steps.add(obj); hits += 1

        standoffs.append(float(np.linalg.norm(pos - rover_pose(t))))
        max_x = max(max_x, float(pos[0]))
        if pos[0] > 17.6:
            crossed = True
        if pos[2] < 0.35:
            grounded += 1
            if grounded > 750:          # 1.5 s on the deck: it is down and not coming back
                crashed_at = t
                break
        else:
            grounded = max(0, grounded - 2)

        if writer and i % 17 == 0 and scene:              # 30 fps video
            cam.lookat[:] = pos
            cam.azimuth = np.rad2deg(yaw)        # sit behind the aircraft, looking where it looks
            m.vis.global_.fovy = CHASE_FOVY
            big.update_scene(d, cam)
            eye._aim(pos, yaw); eye.depth.update_scene(d, eye.cam)
            depth = np.clip(eye.depth.render(), 0, 25.0)
            tel = {"t": t, "standoff": standoffs[-1], "speed": float(np.linalg.norm(d.qvel[:3])),
                   "hits": hits, "model": tac.model if tac else "disabled",
                   "mode": "JEV ENGAGED" if use_jev else "ABLATION: NO JEV",
                   "calls": tac.calls if tac else 0, "skipped": tac.skipped if tac else 0,
                   "tokens": tac.tokens if tac else 0, "hz": (1.0 / tac.min_dt) if tac else 0,
                   "lat": f"{np.median(tac.latency):.2f}s" if (tac and tac.latency) else "--",
                   "tan_h": eye.tan_h, "climbing": bool(guide.climb_hold)}
            writer.append_data(hud.draw(big.render(), depth, scene, judg, tel))
            tape.append({"qpos": d.qpos.copy().tolist(), "mocap": d.mocap_pos.copy().tolist(),
                         "depth": depth.astype(np.float16), "scene": scene,
                         "judg": judg, "tel": {k: v for k, v in tel.items() if k != "tan_h"}})

    if writer:
        writer.close()
        np.save(video + ".tape.npy", np.array(tape, dtype=object), allow_pickle=True)
    out = {"seed": seed, "jev": use_jev, "collisions": hits,
           "target_visible_pct": round(100 * vis / max(frames, 1), 1),
           "mean_standoff_m": round(float(np.mean(standoffs)), 2),
           "max_standoff_m": round(float(np.max(standoffs)), 2),
           "final_gap_m": round(standoffs[-1], 2),
           "distance_flown_m": round(float(np.linalg.norm(d.qpos[:3] - np.array([1.5, 0, CRUISE_ALT]))), 1),
           "steps_jev_acted_pct": round(100 * jev_steps / (n / 10), 1),
           "steps_reflex_pct": round(100 * reflex_steps / (n / 10), 1),
           "max_x_m": round(max_x, 1), "crossed_barrier": crossed, "crashed_at_s": crashed_at, "flew_s": round(len(standoffs) * dt, 1)}
    if tac:
        out["jev"] = tac.stats()
        tac.close()
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seeds", type=int, nargs="+", default=[0])
    p.add_argument("--seconds", type=float, default=35.0)
    p.add_argument("--no-jev", action="store_true")
    p.add_argument("--video", default=None)
    p.add_argument("--hz", type=float, default=None)
    p.add_argument("--budget", type=int, default=None)
    p.add_argument("--fast", action="store_true", help="run faster than real time (unfair to Jev)")
    a = p.parse_args()
    for s in a.seeds:
        r = episode(s, a.seconds, not a.no_jev, a.video, a.hz, a.budget, realtime=not a.fast)
        print(json.dumps(r))
        sys.stdout.flush()
