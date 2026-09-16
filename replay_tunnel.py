"""Re-render a recorded tunnel run. No physics, no API calls."""
import sys, argparse
import numpy as np, mujoco, imageio.v2 as imageio
import flight
from hud import Hud

p = argparse.ArgumentParser()
p.add_argument("tape"); p.add_argument("out")
p.add_argument("--dist", type=float, default=6.0)
p.add_argument("--elev", type=float, default=-7.0)
p.add_argument("--from", dest="t0", type=float, default=None)
p.add_argument("--to", dest="t1", type=float, default=None)
a = p.parse_args()

tape = np.load(a.tape, allow_pickle=True)
m = mujoco.MjModel.from_xml_path("tunnel.xml")
d = mujoco.MjData(m)
eye = flight.Eye(m, target_body="car", ignore_below=None, floor_geom="floor_t",
                 shell=("ceil_t", "floor_t"), threat_fov=30.0, n_sectors=9,
                 walls=("wallL", "wallR"))
big = mujoco.Renderer(m, 880, 1180)
hud = Hud(1180, 880)
cam = mujoco.MjvCamera(); cam.type = mujoco.mjtCamera.mjCAMERA_FREE
cam.distance, cam.elevation, cam.azimuth = a.dist, a.elev, 0.0

w = imageio.get_writer(a.out, fps=30, quality=8, macro_block_size=1)
n = 0
for fr in tape:
    t = fr["tel"]["t"]
    if (a.t0 is not None and t < a.t0) or (a.t1 is not None and t > a.t1):
        continue
    d.qpos[:] = fr["qpos"]; d.mocap_pos[:] = fr["mocap"]
    mujoco.mj_forward(m, d)
    cam.lookat[:] = d.qpos[:3]
    m.vis.global_.fovy = 50.0
    big.update_scene(d, cam)
    tel = dict(fr["tel"]); tel["tan_h"] = eye.tan_h
    w.append_data(hud.draw(big.render(), fr["depth"].astype(np.float32),
                           fr["scene"], fr["judg"], tel))
    n += 1
w.close()
print("wrote %s  %d frames  %.1fs" % (a.out, n, n / 30.0))
