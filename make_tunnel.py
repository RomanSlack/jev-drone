"""Generate tunnel.xml: a long enclosed corridor with obstacles that each have
exactly one kind of answer -- go left, go right, climb over, or dive under."""
import sys

LEN, HW, CEIL = 620.0, 6.5, 7.0     # length, half-width, ceiling height
CAR_LANE = 1.35                     # everything for the drone lives above this
FIRST, SPACING = 70.0, 34.0

def obstacles():
    """(kind, x) laid out so consecutive answers differ."""
    seq = ["left", "dive", "right", "climb", "right", "dive", "left", "climb"]
    out, x, i = [], FIRST, 0
    while x < LEN - 40:
        out.append((seq[i % len(seq)], x))
        x += SPACING
        i += 1
    return out

def geom(name, size, pos, mat):
    return f'    <geom name="{name}" type="box" material="{mat}" size="{size}" pos="{pos}"/>\n'

def build():
    s = ['<mujoco model="tunnel">\n',
         '  <include file="mujoco_menagerie/skydio_x2/x2.xml"/>\n\n',
         '  <statistic extent="18" center="60 0 3"/>\n\n',
         '  <option timestep="0.002" density="1.2" viscosity="1.8e-5"/>\n',
         '  <visual>\n    <global fovy="50" offwidth="1400" offheight="900"/>\n',
         '    <headlight diffuse=".95 .95 .95" ambient=".60 .60 .62"/>\n',
         '    <map znear="0.0025" zfar="3.0"/>\n  </visual>\n\n',
         '  <asset>\n',
         '    <texture type="skybox" builtin="gradient" rgb1=".16 .18 .24" rgb2=".05 .06 .09" width="512" height="512"/>\n',
         '    <texture name="grid" type="2d" builtin="checker" rgb1=".30 .32 .36" rgb2=".38 .40 .45" width="512" height="512"/>\n',
         '    <material name="grid" texture="grid" texrepeat="150 6" reflectance="0"/>\n',
         '    <material name="wall"  rgba=".52 .55 .60 1"/>\n',
         '    <material name="side"  rgba=".95 .60 .10 1"/>\n',
         '    <material name="over"  rgba=".20 .70 .85 1"/>\n',
         '    <material name="under" rgba=".70 .35 .90 1"/>\n',
         '    <material name="car"   rgba=".95 .15 .10 1"/>\n  </asset>\n\n',
         '  <worldbody>\n',
         '    <light pos="0 0 5.5" dir="0 0 -1" directional="true" diffuse=".70 .70 .72"/>\n']
    for i in range(0, int(LEN), 22):
        s.append(f'    <light pos="{i+11} 0 {CEIL-0.6}" dir="0 0 -1" diffuse=".45 .45 .48"/>\n')
    mid, half = LEN / 2, LEN / 2
    s.append(geom("floor_t", f"{half} {HW} .1", f"{mid} 0 -.1", "grid"))
    s.append(geom("ceil_t", f"{half} {HW} .1", f"{mid} 0 {CEIL}", "wall"))
    s.append(geom("wallL", f"{half} .1 {CEIL/2}", f"{mid} {HW} {CEIL/2}", "wall"))
    s.append(geom("wallR", f"{half} .1 {CEIL/2}", f"{mid} {-HW} {CEIL/2}", "wall"))

    for n, (kind, x) in enumerate(obstacles()):
        h = (CEIL - CAR_LANE) / 2
        if kind in ("left", "right"):
            # slab hanging from one wall: blocks that side from CAR_LANE to ceiling
            w = 3.6
            y = (HW - w) if kind == "left" else -(HW - w)
            s.append(geom(f"ob{n}", f".35 {w} {(CEIL-CAR_LANE)/2}",
                          f"{x} {y} {CAR_LANE + (CEIL-CAR_LANE)/2}", "side"))
        elif kind == "dive":
            # hangs from the ceiling; must pass UNDER it
            s.append(geom(f"ob{n}", f".35 {HW} {(CEIL-3.0)/2}",
                          f"{x} 0 {3.0 + (CEIL-3.0)/2}", "under"))
        else:  # climb
            # sits above the car lane; must pass OVER it
            s.append(geom(f"ob{n}", f".35 {HW} {(3.6-CAR_LANE)/2}",
                          f"{x} 0 {CAR_LANE + (3.6-CAR_LANE)/2}", "over"))

    s.append('    <body name="car" mocap="true" pos="20 0 .55">\n')
    s.append('      <geom name="car_geom" type="box" material="car" size="1.1 .6 .55"/>\n')
    s.append('      <geom name="car_fin" type="box" material="car" size=".1 .1 .35" pos="-.6 0 .9"/>\n')
    s.append('    </body>\n  </worldbody>\n</mujoco>\n')
    return "".join(s)

if __name__ == "__main__":
    open("tunnel.xml", "w").write(build())
    obs = obstacles()
    print("tunnel %.0fm, %d obstacles, spacing %.0fm" % (LEN, len(obs), SPACING))
    from collections import Counter
    print(dict(Counter(k for k, _ in obs)))
