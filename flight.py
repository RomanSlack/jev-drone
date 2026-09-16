"""Quadrotor controller + onboard-camera perception for the Skydio X2 arena.

Nothing here talks to an LLM. This is the fast, deterministic layer: it flies the
aircraft and turns camera pixels into a small symbolic scene description.
"""
import numpy as np
import mujoco

G = 9.81
MJ_GEOM = mujoco.mjtObj.mjOBJ_GEOM


# --------------------------------------------------------------------------- #
# control
# --------------------------------------------------------------------------- #
class Pilot:
    """Cascaded velocity -> attitude -> motor-thrust controller."""

    def __init__(self, model):
        self.m = model
        self.mass = float(model.body_subtreemass[model.body("x2").id])
        self.inertia = model.body_inertia[model.body("x2").id].copy()
        self.kv = np.array([2.6, 2.6, 4.0])          # velocity -> accel
        self.kR = self.inertia * 190.0               # attitude stiffness
        self.kw = self.inertia * 26.0                # attitude damping
        self.max_tilt = np.deg2rad(28.0)
        self.max_acc = 7.5            # slew the velocity command; step changes tumble it
        self.v_cmd = np.zeros(3)
        # thrust-mixing matrix: [Fz, Mx, My, Mz] = MIX @ f
        self.mix_inv = np.linalg.inv(np.array([
            [1.0,    1.0,    1.0,    1.0],
            [-0.18,  0.18,   0.18,  -0.18],
            [0.14,   0.14,  -0.14,  -0.14],
            [-0.0201, 0.0201, -0.0201, 0.0201],
        ]))
        self.f_max = float(model.actuator_ctrlrange[0, 1])

    def __call__(self, data, v_des, yaw_des, dt=0.002):
        R = data.xmat[self.m.body("x2").id].reshape(3, 3)
        v = data.qvel[0:3]
        w = data.qvel[3:6]                            # body frame

        # A step change in the velocity command demands a step change in attitude,
        # which saturates the motors and tumbles the aircraft. Ramp it instead.
        step = self.max_acc * dt
        self.v_cmd += np.clip(np.asarray(v_des) - self.v_cmd, -step, step)
        a = self.kv * (self.v_cmd - v)
        a_h = a[:2]
        lim = np.tan(self.max_tilt) * G
        if np.linalg.norm(a_h) > lim:                 # keep the tilt command sane
            a_h = a_h / np.linalg.norm(a_h) * lim
        a_des = np.array([a_h[0], a_h[1], a[2] + G])

        b3 = a_des / np.linalg.norm(a_des)
        b1c = np.array([np.cos(yaw_des), np.sin(yaw_des), 0.0])
        b2 = np.cross(b3, b1c)
        n2 = np.linalg.norm(b2)
        b2 = b2 / n2 if n2 > 1e-6 else np.array([0.0, 1.0, 0.0])
        Rd = np.column_stack([np.cross(b2, b3), b2, b3])

        E = Rd.T @ R - R.T @ Rd
        eR = 0.5 * np.array([E[2, 1], E[0, 2], E[1, 0]])
        tau = -self.kR * eR - self.kw * w
        thrust = self.mass * float(a_des @ R[:, 2])

        # Thrust-priority mixing: if the torque demand would drive a motor negative,
        # give up torque authority rather than silently losing lift.
        thrust = float(np.clip(thrust, 0.0, 4 * self.f_max))
        f_lift = np.full(4, thrust / 4.0)
        f_tau = self.mix_inv @ np.array([0.0, tau[0], tau[1], tau[2]])
        f = f_lift + f_tau
        lo, hi = f.min(), f.max()
        scale = 1.0
        if lo < 0.0:
            scale = min(scale, thrust / 4.0 / max(1e-6, -(f_tau[np.argmin(f)])))
        if hi > self.f_max:
            scale = min(scale, (self.f_max - thrust / 4.0) / max(1e-6, f_tau[np.argmax(f)]))
        return np.clip(f_lift + np.clip(scale, 0.0, 1.0) * f_tau, 0.0, self.f_max)


# --------------------------------------------------------------------------- #
# perception
# --------------------------------------------------------------------------- #
class Eye:
    """Onboard forward camera -> symbolic scene summary.

    Uses the depth and segmentation buffers only; no ground-truth object poses
    leak into the summary, so the drone sees what a real camera would see.
    """

    W, H = 64, 48
    N_SECTORS = 5
    SECTOR_NAMES = ["far_left", "left", "center", "right", "far_right"]
    MAX_RANGE = 25.0
    TILT_DEG = -12.0
    IGNORE_BELOW_M = 0.5      # something we are already flying over is not a threat
    EYE_FOVY = 110.0          # wide FPV lens, independent of the cinematic chase camera
    THREAT_FOV_DEG = 40.0     # a wide lens helps us SEE the target, but only what lies
                              # within this forward cone is something we could fly into

    def __init__(self, model, target_body="rover"):
        self.m = model
        self.depth = mujoco.Renderer(model, self.H, self.W)
        self.depth.enable_depth_rendering()
        self.seg = mujoco.Renderer(model, self.H, self.W)
        self.seg.enable_segmentation_rendering()
        self.cam = mujoco.MjvCamera()
        self.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        self.cam.distance = 1.0
        self.cam.elevation = self.TILT_DEG
        # the whole rover body is the target, mast included -- not one geom of it
        self.target_ids = np.nonzero(model.geom_bodyid == model.body(target_body).id)[0]
        self.floor_id = model.geom("floor").id
        # the camera sits inside the airframe: never mistake ourselves for an obstacle
        self.self_geoms = np.nonzero(model.geom_bodyid == model.body("x2").id)[0]
        fovy = np.deg2rad(self.EYE_FOVY)
        self.tan_h = np.tan(fovy / 2) * self.W / self.H   # horizontal half-fov
        self.hfov_deg = np.rad2deg(np.arctan(self.tan_h)) * 2
        # columns spanning the threat cone; the rest of the frame is for tracking only
        ndc = np.tan(np.deg2rad(self.THREAT_FOV_DEG)) / self.tan_h
        self.t0 = int(round((1 - min(ndc, 1.0)) / 2 * (self.W - 1)))
        self.t1 = int(round((1 + min(ndc, 1.0)) / 2 * (self.W - 1))) + 1
        self._last_seen = None

    def _aim(self, pos, yaw):
        self.m.vis.global_.fovy = self.EYE_FOVY    # free cameras share one fovy; claim it
        az, el = yaw, np.deg2rad(self.TILT_DEG)
        fwd = np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])
        self.cam.azimuth = np.rad2deg(yaw)
        self.cam.lookat[:] = pos + self.cam.distance * fwd

    def look(self, data, pos, yaw, t):
        self._aim(pos, yaw)
        self.depth.update_scene(data, self.cam)
        z = np.clip(self.depth.render(), 0.0, self.MAX_RANGE)
        self.seg.update_scene(data, self.cam)
        seg = self.seg.render()[:, :, 0]

        # --- free space: ignore the floor, keep only real vertical obstructions
        obstacle = (seg != self.floor_id) & (seg >= 0)
        obstacle &= ~np.isin(seg, self.target_ids)
        obstacle &= ~np.isin(seg, self.self_geoms)
        # Height of every obstacle pixel relative to the aircraft. Anything well below
        # us is something we have already climbed over, not something we can hit.
        dz = z * np.tan(self._elevation(np.arange(self.H))[:, None])
        obstacle &= dz > -self.IGNORE_BELOW_M
        rng_full = np.where(obstacle, z, self.MAX_RANGE)
        rng = rng_full[:, self.t0:self.t1]
        cols = np.array_split(np.arange(rng.shape[1]), self.N_SECTORS)
        sectors = {n: round(float(rng[:, c].min()), 2)
                   for n, c in zip(self.SECTOR_NAMES, cols)}

        # --- vertical extent of whatever is blocking us.
        # Without this the drone cannot tell a low beam it could hop over from a
        # tall pillar it must go around: both look identical in a horizontal scan.
        # Only what lies straight ahead can be flown over; things off to the side
        # are a steering problem, not a vertical one.
        mid = (self.t1 - self.t0) // 2
        ahead = rng[:, max(0, mid - 6):mid + 6]
        near_ahead = float(ahead.min())
        # When nothing is ahead these fields are meaningless; report null rather than
        # feeding the model a confident-looking False.
        top_dz, runs_off_top = None, None
        if near_ahead < self.MAX_RANGE - 1e-3:
            cluster = ahead < near_ahead + 0.6
            runs_off_top = bool(cluster[0, :].any())   # top edge is outside the FOV
            if not runs_off_top:
                ys, xs = np.nonzero(cluster)
                dz = ahead[ys, xs] * np.tan(self._elevation(ys))
                top_dz = round(float(dz.max()), 2)

        idx = self.t0 + int(np.argmin(rng.min(axis=0)))
        nearest = float(rng.min())
        nearest_brg = self._bearing(idx)

        # --- target: purely from the segmentation mask
        mask = np.isin(seg, self.target_ids)
        px = int(mask.sum())
        if px >= 3:
            self._last_seen = t
            ys, xs = np.nonzero(mask)
            brg = self._bearing(float(xs.mean()))
            rangem = round(float(np.median(z[mask])), 2)
            target = {"visible": True, "bearing_deg": brg, "range_m": rangem,
                      "pixels": px, "unseen_for_s": 0.0}
        else:
            gap = None if self._last_seen is None else round(t - self._last_seen, 2)
            target = {"visible": False, "bearing_deg": None, "range_m": None,
                      "pixels": 0, "unseen_for_s": gap}

        blocked = sum(1 for v in sectors.values() if v < 3.0)
        # What lies in the PATH, as opposed to merely beside us. Braking for walls
        # you are flying between makes narrow gaps impossible to thread.
        path_ahead = round(min(sectors["left"], sectors["center"], sectors["right"]), 2)
        return {"sector_range_m": sectors,
                "sectors_blocked_of_5": blocked,
                "path_ahead_m": path_ahead,
                "obstruction_top_above_drone_m": top_dz,
                "obstruction_taller_than_camera_can_see": runs_off_top,
                "nearest_obstacle_m": round(nearest, 2),
                "nearest_bearing_deg": nearest_brg,
                "target": target}

    def _bearing(self, col):
        """Signed bearing in degrees, +ve = to the aircraft's left (+y body).

        Image-right is -y for a camera looking down +x with +z up, hence the negation.
        """
        ndc = 2.0 * col / (self.W - 1) - 1.0
        return round(float(np.rad2deg(-np.arctan(ndc * self.tan_h))), 1)

    def _elevation(self, rows):
        """Elevation of an image row in radians, +ve above horizontal."""
        half = (self.H - 1) / 2.0
        rel = (half - np.asarray(rows, dtype=float)) / half * np.deg2rad(self.EYE_FOVY) / 2
        return rel + np.deg2rad(self.TILT_DEG)

    def sector_bearing(self, name):
        i = self.SECTOR_NAMES.index(name)
        centre = self.t0 + (i + 0.5) * (self.t1 - self.t0) / self.N_SECTORS
        return np.deg2rad(self._bearing(centre))
