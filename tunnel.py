"""Tunnel chase: how fast can the vehicle go before a ~0.135s judgment loop
stops being fast enough?

Jev is the ONLY navigator. No reflex, no hand-written obstacle avoidance. Code
flies the aircraft (attitude, thrust) and points it at the car; every decision
about getting past an obstacle is the model's.
"""
import os, sys, json, time, argparse
import numpy as np
import mujoco
import flight
import tunnel_tactics as TT

SHELL = ("ceil_t", "floor_t")
CRUISE_ALT = 3.3     # blocked by BOTH the hanging baffles and the standing blocks
DIVE_ALT = 2.55
CLIMB_ALT = 4.8
STANDOFF = 6.0
MIN_ALT = 2.35           # floor guard; the tunnel floor is not an obstacle to dodge
TRACE = bool(os.environ.get("TRACE"))


def car_pose(t, v):
    return np.array([20.0 + v * t, 1.8 * np.sin(0.22 * t), 0.55])


class Nav:
    """Jev's maneuver -> a velocity command. Nothing here avoids anything."""

    def __init__(self, v_car):
        self.v_car = v_car
        self.yaw_sp = None
        self.alt_sp = CRUISE_ALT
        self.commit_until = -1.0
        self.commit = "hold_course"
        self.last_bearing = 0.0
        self.y_est = 0.0
        self.half_est = 6.5

    def __call__(self, scene, judg, yaw, pos, t, fresh, vy=0.0, dt=0.01):
        """Body yaw stays locked to the tunnel axis so the camera always looks
        down the corridor. Turning to face the car would aim the camera at a
        wall and the free-space reading would become meaningless."""
        tgt = scene["target"]
        if tgt["visible"]:
            self.last_bearing = np.deg2rad(tgt["bearing_deg"])
            self.last_range = tgt["range_m"]
        rng = getattr(self, "last_range", STANDOFF + 3.0)
        b = self.last_bearing
        gap_along = rng * np.cos(b)          # how far ahead the car is
        off_lateral = rng * np.sin(b)        # how far to the side it is

        fwd = float(np.clip(1.1 * (gap_along - STANDOFF) + self.v_car,
                            0.0, self.v_car * 1.5))
        track = float(np.clip(1.0 * off_lateral, -0.22 * max(fwd, 3.0), 0.22 * max(fwd, 3.0)))

        # The graded score IS the steering command. No argmax, no commit window:
        # a level index maps straight onto how hard and which way to move.
        fresh_enough = (judg["source"] == "jev"
                        and judg["age_s"] < TT.THRESHOLDS["stale_after_s"])
        st = judg.get("steer", 2.0) if fresh_enough else 2.0
        ht = judg.get("height", 2.0) if fresh_enough else 2.0
        risk = judg.get("risk", 0.0) if fresh_enough else 0.0
        turn = float(np.clip((2.0 - st) / 2.0, -1.0, 1.0))     # +1 = hard left
        turn = float(np.sign(turn) * abs(turn) ** 0.7)         # sharpen mild commitments
        rise = float(np.clip((ht - 2.0) / 2.0, -1.0, 1.0))     # +1 = climb
        rise = float(np.sign(rise) * abs(rise) ** 0.5)

        # The gap is ~5.8 m wide and needs a ~3.6 m move with 3+ seconds of warning.
        # 5.4 m/s of lateral authority crosses the whole 13 m tunnel in 1.6 s and
        # buries the aircraft in the far wall before it can arrest.
        authority = 0.6 * max(fwd, 5.0)

        # LATERAL POSITION LOOP.
        # Commanding a lateral VELOCITY and holding it until the next judgment gives
        # the aircraft no notion of where to stop: it crosses the whole 13 m tunnel
        # and buries itself in the far wall. The score instead picks a target lateral
        # POSITION in the corridor, and a P-D loop flies to it and holds. Position is
        # measured, not known: it comes from the two wall distances.
        # Complementary filter on lateral position. The wall measurement vanishes
        # exactly when it matters -- an obstacle filling the view hides both walls --
        # and the naive fallback ("assume centred") had the aircraft convinced it was
        # mid-tunnel while it was pinned against the left wall at y=+5.5. So integrate
        # lateral velocity and correct it only when a wall reading is plausible.
        self.y_est += vy * dt
        rl, rr = scene.get("room_left_m"), scene.get("room_right_m")
        half = self.half_est
        if rl is not None and rr is not None and 4.0 < 0.5 * (rl + rr) < 9.0:
            self.y_est = 0.85 * self.y_est + 0.15 * (0.5 * (rr - rl))
            self.half_est = 0.9 * self.half_est + 0.1 * (0.5 * (rl + rr))
            half = self.half_est
        y_now = float(np.clip(self.y_est, -half, half))
        usable = max(half - 1.6, 1.0)             # keep off the walls

        # Blending the dodge against car-tracking by |turn| alone lets the car pull
        # the target back onto the obstacle: with the car to the left and turn=-0.57,
        # the net target was -0.8 m when clearing the slab needed -2.8 m. Once the
        # model expresses a real preference, the dodge has to win outright.
        want = float(np.clip(abs(turn) * 2.2, 0.0, 1.0))
        y_track = y_now + off_lateral             # where the car is, laterally
        y_goal = turn * usable                    # where the dodge wants to be
        y_target = (1.0 - want) * y_track + want * y_goal
        y_target = float(np.clip(y_target, -usable, usable))

        lat = 1.5 * (y_target - y_now) - 0.55 * vy
        lat = float(np.clip(lat, -authority, authority))

        self.alt_sp = float(np.clip(CRUISE_ALT + 1.55 * rise, DIVE_ALT, CLIMB_ALT))
        # You cannot slide sideways while ramming a wall: let the risk score bleed
        # off forward speed hard, so the lateral command actually has authority.
        fwd *= 1.0 - 0.7 * float(np.clip(risk - 1.1, 0.0, 1.0))
        mv = "st%+.2f y=%+.1f->%+.1f lat%+.1f" % (turn, y_now, y_target, lat)


        vz = float(np.clip(2.6 * (self.alt_sp - pos[2]), -3.0, 4.5))
        # Staying airborne is flight control, not obstacle avoidance: a hard tilt
        # during a dodge bleeds vertical thrust and the aircraft sinks. Catch it
        # early and proportionally, or the descent momentum blows straight through.
        if pos[2] < MIN_ALT + 0.5:
            vz = max(vz, 3.0 * (MIN_ALT + 0.5 - pos[2]))
        v_world = np.array([fwd, lat, vz])   # yaw is 0, so body == world
        return v_world, 0.0, mv


def episode(v_car=8.0, seconds=40.0, use_jev=True, workers=4, video=None, seed=0):
    m = mujoco.MjModel.from_xml_path("tunnel.xml")
    # Racing-quad build: thrust-to-weight ~8 instead of 4. Measured effect on a 2 m
    # lateral dodge is 0.78s -> 0.62s; drag caps lateral speed near 8 m/s, so this
    # is close to the physical floor for this airframe.
    m.actuator_ctrlrange[:, 1] = 13.0
    d = mujoco.MjData(m)
    dt = m.opt.timestep
    x2 = m.body("x2").id
    x2g = set(np.nonzero(m.geom_bodyid == x2)[0].tolist())

    rng0 = np.random.default_rng(seed)
    d.qpos[:3] = [20.0 - STANDOFF + rng0.uniform(-.4, .4), rng0.uniform(-.3, .3), CRUISE_ALT]
    d.qpos[3:7] = [1, 0, 0, 0]
    mujoco.mj_forward(m, d)

    pilot = flight.Pilot(m)
    pilot.max_tilt = np.deg2rad(35.0)
    pilot.max_acc = 30.0
    pilot.lat_acc = 12.0      # gentle lateral slew: hard reversals flip it past 90 deg
    pilot.kv = np.array([3.2, 3.5, 5.0])
    pilot.kq = pilot.inertia * 700.0    # heavy attitude damping for the tunnel: hard
    pilot.kw = pilot.inertia * 230.0    # lateral reversals otherwise overshoot past 90   # lateral loop is the one in the reaction path
    # Narrow cone: in a corridor the useful angular resolution is near the axis.
    # At 15 m a 5-sector fan over +/-40deg cannot resolve a 1.3 m gap edge at all.
    eye = flight.Eye(m, target_body="car", ignore_below=None,
                     floor_geom="floor_t", shell=SHELL, threat_fov=30.0, n_sectors=9,
                     walls=("wallL", "wallR"))
    nav = Nav(v_car)
    tac = TT.FastTactician(workers=workers) if use_jev else None
    judg = dict(TT.DEFAULT)

    writer = big = hud = cam = None
    if video:
        import imageio.v2 as imageio
        from hud import Hud
        big = mujoco.Renderer(m, 880, 1180)
        hud = Hud(1180, 880)
        cam = mujoco.MjvCamera(); cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        cam.distance, cam.elevation = 6.0, -7.0
        writer = imageio.get_writer(video, fps=30, quality=8, macro_block_size=1)
        tape = []

    n = int(seconds / dt)
    v_des, yaw_cmd, scene, fresh = np.zeros(3), 0.0, None, False
    hits, first_hit_x, vis, frames = 0, None, 0, 0
    max_tilt_deg, min_alt = 0.0, 99.0
    seen_geoms = set()
    mv = "hold_course"
    wall0 = time.time()

    for i in range(n):
        t = i * dt
        lag = t - (time.time() - wall0)
        if lag > 0.0005:
            time.sleep(lag)
        d.mocap_pos[m.body("car").mocapid[0]] = car_pose(t, v_car)

        pos = d.qpos[:3].copy()
        q = d.qpos[3:7]
        yaw = float(np.arctan2(2 * (q[0] * q[3] + q[1] * q[2]), 1 - 2 * (q[2] ** 2 + q[3] ** 2)))

        if i % 15 == 0:                       # 33 Hz perception
            scene = eye.look(d, pos, yaw, t)
            fresh = True
            frames += 1
            vis += scene["target"]["visible"]
            if tac:
                tac.offer(scene, t, float(np.linalg.norm(d.qvel[:3])),
                          sideways=float(d.qvel[1]), climbrate=float(d.qvel[2]))

        if i % 5 == 0 and scene:              # 100 Hz guidance
            if tac:
                judg = tac.read(t)
            v_des, yaw_cmd, mv = nav(scene, judg, yaw, pos, t, fresh, float(d.qvel[1]), 5 * dt)
            if TRACE and fresh:
                print("  t=%5.2f x=%6.1f y=%5.2f z=%4.2f %-11s risk=%.2f lvl=%4.1f up=%4.1f dn=%4.1f sec=%s"
                      % (t, pos[0], pos[1], pos[2], mv, judg.get("risk", 0),
                         scene["free_ahead_level_m"], scene["free_ahead_above_m"],
                         scene["free_ahead_below_m"],
                         [round(v, 1) for v in scene["sector_range_m"].values()]), flush=True)
            fresh = False

        d.ctrl[:] = pilot(d, v_des, yaw_cmd, dt)
        mujoco.mj_step(m, d)
        R = d.xmat[x2].reshape(3, 3)
        max_tilt_deg = max(max_tilt_deg, float(np.rad2deg(np.arccos(np.clip(R[2, 2], -1, 1)))))
        min_alt = min(min_alt, float(d.qpos[2]))

        for c in range(d.ncon):
            g1, g2 = d.contact[c].geom1, d.contact[c].geom2
            if (g1 in x2g) != (g2 in x2g):
                obj = g2 if g1 in x2g else g1
                if obj not in seen_geoms:
                    seen_geoms.add(obj)
                    hits += 1
                    if first_hit_x is None:
                        first_hit_x = float(pos[0])

        if writer and i % 17 == 0 and scene:
            cam.lookat[:] = pos
            cam.azimuth = np.rad2deg(yaw)
            m.vis.global_.fovy = 50.0
            big.update_scene(d, cam)
            eye._aim(pos, yaw); eye.depth.update_scene(d, eye.cam)
            depth = np.clip(eye.depth.render(), 0, 25.0)
            st = tac.stats() if tac else {}
            tel = {"t": t, "standoff": float(np.linalg.norm(pos - car_pose(t, v_car))),
                   "speed": float(np.linalg.norm(d.qvel[:3])), "hits": hits,
                   "model": "jev-latest" if tac else "disabled",
                   "mode": "JEV NAVIGATING  %.0f m/s" % v_car if tac else "NO JEV",
                   "calls": st.get("calls", 0), "skipped": 0, "tokens": st.get("tokens", 0),
                   "hz": (st.get("calls", 0) / max(t, 1e-6)),
                   "lat": "%.2fs" % st["median_latency_s"] if st.get("median_latency_s") else "--",
                   "tan_h": eye.tan_h, "climbing": nav.alt_sp > CRUISE_ALT + 0.15}
            writer.append_data(hud.draw(big.render(), depth, scene, judg, tel))
            tape.append({"qpos": d.qpos.copy().tolist(), "mocap": d.mocap_pos.copy().tolist(),
                         "depth": depth.astype(np.float16), "scene": scene,
                         "judg": dict(judg), "tel": {k: v for k, v in tel.items() if k != "tan_h"}})

        if pos[2] < 0.4:       # on the floor: it is down and not coming back
            break

    if writer:
        writer.close()
        np.save(video + ".tape.npy", np.array(tape, dtype=object), allow_pickle=True)
    dist = float(d.qpos[0] - (20.0 - STANDOFF))
    out = {"v_car": v_car, "jev": use_jev, "collisions": hits,
           "distance_m": round(dist, 1),
           "clean_distance_m": round((first_hit_x - (20.0 - STANDOFF)) if first_hit_x else dist, 1),
           "target_visible_pct": round(100 * vis / max(frames, 1), 1),
           "flew_s": round(i * dt, 1),
           "max_tilt_deg": round(max_tilt_deg), "min_alt_m": round(min_alt, 2)}
    if tac:
        st = tac.stats()
        out["decisions_per_s"] = round(st["calls"] / max(i * dt, 1e-6), 2)
        out["stale_m"] = round((st["median_latency_s"] or 0) * v_car, 2)
        out["jev_stats"] = st
        tac.close()
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--speeds", type=float, nargs="+", default=[8.0])
    p.add_argument("--seconds", type=float, default=40.0)
    p.add_argument("--no-jev", action="store_true")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--video", default=None)
    a = p.parse_args()
    for v in a.speeds:
        r = episode(v, a.seconds, not a.no_jev, a.workers, a.video)
        print(json.dumps(r), flush=True)
