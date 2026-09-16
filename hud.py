"""Telemetry overlay: makes the Jev layer visible in the video."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BG      = (11, 14, 17)
PANEL   = (17, 21, 26)
LINE    = (38, 45, 54)
TEXT    = (222, 230, 238)
DIM     = (118, 132, 146)
ACCENT  = (255, 159, 28)      # Jev
CYAN    = (46, 196, 241)      # perception
GREEN   = (64, 214, 141)
RED     = (240, 78, 72)

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
_F = {}


def font(size, bold=False):
    k = (size, bold)
    if k not in _F:
        _F[k] = ImageFont.truetype(BOLD if bold else MONO, size)
    return _F[k]


def _depth_rgb(z, zmax=25.0):
    """Pixelated false-colour depth, the way a range sensor would look."""
    t = np.clip(z / zmax, 0, 1)
    r = np.clip(1.6 - 2.2 * t, 0, 1)
    g = np.clip(1.5 - abs(2.2 * t - 1.0) * 1.4, 0, 1)
    b = np.clip(2.2 * t - 0.5, 0, 1)
    return (np.dstack([r, g, b]) * 255).astype(np.uint8)


class Hud:
    W_PANEL = 440

    def __init__(self, view_w, view_h):
        self.vw, self.vh = view_w, view_h
        self.W, self.H = view_w + self.W_PANEL, view_h
        self.smooth = {}

    def _bar(self, dr, x, y, w, h, frac, col, bg=(28, 34, 41)):
        dr.rectangle([x, y, x + w, y + h], fill=bg)
        if frac > 0:
            dr.rectangle([x, y, x + max(2, int(w * min(frac, 1.0))), y + h], fill=col)

    def _lock_on(self, img):
        """The chase camera looks AT the aircraft, so it is always dead centre.
        Ring + corner brackets so a 30 cm quadrotor reads at a glance."""
        cx, cy = self.vw // 2, (self.vh - 54) // 2
        glow = Image.new("RGBA", (self.vw, self.vh), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for rad, a in ((84, 22), (74, 38), (64, 60), (55, 95)):
            gd.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=ACCENT + (a,), width=4)
        s, g = 54, 19
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = cx + sx * s, cy + sy * s
                gd.line([x, y, x - sx * g, y], fill=ACCENT + (255,), width=3)
                gd.line([x, y, x, y - sy * g], fill=ACCENT + (255,), width=3)
        img.alpha_composite(glow)
        return img

    def draw(self, view, depth, scene, judg, tel):
        img = Image.new("RGBA", (self.W, self.H), BG + (255,))
        img.paste(Image.fromarray(view).convert("RGBA"), (0, 0))
        img = self._lock_on(img)
        dr = ImageDraw.Draw(img)
        px = self.vw
        dr.rectangle([px, 0, self.W, self.H], fill=PANEL)
        dr.line([px, 0, px, self.H], fill=LINE, width=1)
        x0, w = px + 22, self.W_PANEL - 44
        fresh = judg.get("age_s", 9) < 0.45 and judg["source"] == "jev"

        # ---- header ------------------------------------------------------
        y = 26
        dr.text((x0, y), "JEV", font=font(30, True), fill=ACCENT)
        dr.text((x0 + 62, y + 10), "SYSTEM ONE", font=font(13, True), fill=TEXT)
        dr.text((x0 + 62, y + 27), tel["model"], font=font(11), fill=DIM)
        dot = ACCENT if fresh else (70, 55, 30)
        dr.ellipse([self.W - 40, y + 12, self.W - 28, y + 24], fill=dot)
        y += 62
        dr.line([x0, y, x0 + w, y], fill=LINE)

        # ---- onboard camera ---------------------------------------------
        y += 16
        dr.text((x0, y), "ONBOARD CAMERA  64x48 DEPTH", font=font(11, True), fill=CYAN)
        y += 18
        iw = int(w * 0.78)
        dh = int(iw * depth.shape[0] / depth.shape[1])
        img.paste(Image.fromarray(_depth_rgb(depth)).resize((iw, dh), Image.NEAREST), (x0, y))
        dr.rectangle([x0, y, x0 + iw, y + dh], outline=LINE)
        t = scene["target"]
        if t["visible"]:                                   # lock reticle
            cx = x0 + iw * (0.5 - np.tan(np.deg2rad(t["bearing_deg"])) / (2 * tel["tan_h"]))
            cy = y + dh * 0.52
            dr.rectangle([cx - 13, cy - 13, cx + 13, cy + 13], outline=GREEN, width=2)
            dr.text((cx + 18, cy - 7), f"{t['range_m']:.1f}m", font=font(12, True), fill=GREEN)
        y += dh + 14

        # ---- free space --------------------------------------------------
        dr.text((x0, y), "FREE SPACE BY SECTOR", font=font(11, True), fill=CYAN)
        y += 18
        for name, rng in scene["sector_range_m"].items():
            col = RED if rng < 2.0 else (ACCENT if rng < 4.5 else CYAN)
            dr.text((x0, y), name.replace("_", " ")[:9].ljust(9), font=font(11), fill=DIM)
            self._bar(dr, x0 + 78, y + 2, w - 130, 8, rng / 12.0, col)
            dr.text((x0 + w - 44, y), f"{min(rng,99):5.1f}", font=font(11), fill=TEXT)
            y += 16
        # --- the vertical read that decides over-vs-around ------------------
        y += 6
        blocked = scene["sectors_blocked_of_5"]
        top = scene["obstruction_top_above_drone_m"]
        taller = scene["obstruction_taller_than_camera_can_see"]
        bc = RED if blocked >= 4 else (ACCENT if blocked else DIM)
        dr.text((x0, y), "blocked".ljust(9), font=font(11), fill=DIM)
        for k in range(5):
            col = bc if k < blocked else (34, 41, 49)
            dr.rectangle([x0 + 78 + k * 20, y + 2, x0 + 78 + k * 20 + 15, y + 10], fill=col)
        dr.text((x0 + w - 44, y), "%d/5" % blocked, font=font(11), fill=TEXT)
        y += 17
        if taller is True:
            vtxt, vcol = "taller than view -> go around", DIM
        elif top is not None:
            vtxt, vcol = "top edge %+.2fm -> can fly over" % top, GREEN
        else:
            vtxt, vcol = "nothing ahead", DIM
        dr.text((x0, y), vtxt, font=font(11), fill=vcol)
        y += 18
        dr.line([x0, y, x0 + w, y], fill=LINE)

        # ---- the judgment -------------------------------------------------
        y += 16
        dr.text((x0, y), "TACTICAL JUDGMENT", font=font(11, True), fill=ACCENT)
        if judg["source"] != "jev":
            dr.text((x0 + w - 62, y), "FALLBACK", font=font(11, True), fill=DIM)
        y += 22
        probs = judg.get("probabilities") or {}
        order = ["hold_course", "gap_left", "gap_right", "climb", "brake", "reacquire"]
        for k in order:
            p = probs.get(k, 0.0)
            self.smooth[k] = 0.65 * self.smooth.get(k, 0.0) + 0.35 * p   # ease the bars
            p = self.smooth[k]
            chosen = k == judg["maneuver"] and judg["source"] == "jev"
            col = ACCENT if chosen else (58, 70, 82)
            dr.text((x0, y), k.replace("_", " ").ljust(11), font=font(12, True if chosen else False),
                    fill=TEXT if chosen else DIM)
            self._bar(dr, x0 + 104, y + 3, w - 156, 9, p, col)
            dr.text((x0 + w - 40, y), f"{p*100:3.0f}%", font=font(11), fill=TEXT if chosen else DIM)
            y += 20
        y += 6

        for label, val, vmax, col in [
            ("risk", judg["risk"], 2.0, RED),
            ("confidence", judg["confidence"], 1.0, GREEN),
            ("target lost", judg["target_truly_lost"], 1.0, ACCENT),
        ]:
            dr.text((x0, y), label.ljust(11), font=font(11), fill=DIM)
            self._bar(dr, x0 + 104, y + 2, w - 156, 8, val / vmax, col)
            dr.text((x0 + w - 40, y), f"{val:.2f}", font=font(11), fill=TEXT)
            y += 18

        # ---- footer -------------------------------------------------------
        fy = self.H - 74
        dr.line([x0, fy - 12, x0 + w, fy - 12], fill=LINE)
        for i, s in enumerate([
            f"calls {tel['calls']:<4} reused {tel['skipped']}",
            f"latency {tel['lat']}  tokens {tel['tokens']}",
            f"control 500Hz   jev {tel['hz']:.0f}Hz",
        ]):
            dr.text((x0, fy + i * 16), s, font=font(11), fill=DIM)

        # ---- mission strip over the render ---------------------------------
        dr.rectangle([0, self.vh - 54, self.vw, self.vh], fill=(8, 10, 13))
        items = [("T", f"{tel['t']:5.1f}s"), ("STANDOFF", f"{tel['standoff']:4.1f}m"),
                 ("SPEED", f"{tel['speed']:4.1f}m/s"), ("NEAREST", f"{scene['nearest_obstacle_m']:4.1f}m"),
                 ("CONTACTS", f"{tel['hits']}")]
        cx = 24
        for k, v in items:
            dr.text((cx, self.vh - 42), k, font=font(10, True), fill=DIM)
            dr.text((cx, self.vh - 28), v, font=font(15, True),
                    fill=RED if (k == "CONTACTS" and tel["hits"]) else TEXT)
            cx += 150
        dr.text((self.vw - 330, self.vh - 36), tel["mode"], font=font(14, True),
                fill=ACCENT if tel["mode"].startswith("JEV") else DIM)
        if tel.get("climbing"):
            dr.text((self.vw - 330, self.vh - 52), "CLIMBING OVER BARRIER", font=font(11, True), fill=GREEN)
        return np.asarray(img.convert("RGB"))
