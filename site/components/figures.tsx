import flight from "@/data/flight.json";

type Pt = { t: number; x: number; y: number; z: number; rx: number; ry: number; m: string; vis: boolean };
// every other sample: halves the inline SVG with no visible change at this scale
const pts = (flight.points as Pt[]).filter((_, i) => i % 2 === 0);

export function Figure({ n, caption, children, className = "" }: { n: number; caption: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <figure id={`fig-${n}`}>
      <div className={`frame ${className}`}>{children}</div>
      <figcaption>
        <span className="n">Fig. {n}</span>
        {caption}
      </figcaption>
    </figure>
  );
}

/* Fig: the four rates. Tick density is log-scaled so 500 Hz and 2.5 Hz fit one ruler. */
const LAYERS = [
  { hz: "500", name: "Geometric flight controller", who: "code", gap: 5, note: "Attitude, thrust-priority motor mixing, slew-limited commands. flight.Pilot" },
  { hz: "50", name: "Guidance and safety reflex", who: "code", gap: 14, note: "Always owns safety. Overrides any judgment when something is close. run.Guidance" },
  { hz: "15", name: "Camera to symbolic scene", who: "code", gap: 30, note: "Depth and segmentation buffers become five range sectors, an obstruction height and a target bearing. flight.Eye" },
  { hz: "2.5", name: "Tactical judgment", who: "jev", gap: 84, note: "Jev reads the scene as JSON and answers three typed questions. Advisory only. tactics.py" },
];

export function RateStack() {
  return (
    <div className="stack" role="list">
      {LAYERS.map((l) => (
        <div className="row" role="listitem" key={l.hz}>
          <div className="hz">
            {l.hz}
            <small>Hz</small>
          </div>
          <div className="what">
            <b>{l.name}</b>
            <span>{l.note}</span>
            <div className={`ticks ${l.who === "jev" ? "is-jev" : "is-code"}`} style={{ "--gap": `${l.gap}px` } as React.CSSProperties} aria-hidden="true" />
          </div>
        </div>
      ))}
    </div>
  );
}

const LOOP = [
  { who: "code", k: "sense · 15 Hz", b: "Onboard camera", p: "64×48 depth and segmentation. No ground truth, no map, no GPS." },
  { who: "code", k: "perceive · numpy", b: "Symbolic scene", p: "Sector ranges, top-edge height, target bearing and range." },
  { who: "jev", k: "judge · ~2.5 Hz", b: "Jev", p: "Choice, Score and Noul in one call. 0.11 s median." },
  { who: "code", k: "veto · 50 Hz", b: "Guidance + reflex", p: "Accepts, refuses or overrides the proposal." },
  { who: "code", k: "fly · 500 Hz", b: "Controller", p: "Quaternion attitude error, four rotor commands." },
];

export function LoopDiagram() {
  return (
    <div className="loop" role="list">
      {LOOP.map((n) => (
        <div className={`node ${n.who}`} role="listitem" key={n.b}>
          <span className="k">{n.k}</span>
          <b>{n.b}</b>
          <p>{n.p}</p>
        </div>
      ))}
    </div>
  );
}

/* Fig: real trajectory from the recorded tape of the 65 s run. */
const W = 1000, L = 34, R = 12;
const sx = (x: number) => L + (x / 82) * (W - L - R);
const TOP = { y0: 34, h: 150 }; // y from +6.5 (top) to -6.5
const sy = (y: number) => TOP.y0 + ((6.5 - y) / 13) * TOP.h;
const SIDE = { y0: 222, h: 96 }; // z from 0 to 4
const sz = (z: number) => SIDE.y0 + SIDE.h - (Math.min(z, 4) / 4) * SIDE.h;
const path = (f: (p: Pt) => [number, number]) => pts.map((p, i) => `${i ? "L" : "M"}${f(p)[0].toFixed(1)} ${f(p)[1].toFixed(1)}`).join("");

function runs(pred: (p: Pt) => boolean) {
  const out: Pt[][] = [];
  let cur: Pt[] = [];
  for (const p of pts) {
    if (pred(p)) cur.push(p);
    else if (cur.length) { out.push(cur); cur = []; }
  }
  if (cur.length) out.push(cur);
  return out;
}

const PILLARS = [[7, 1.8], [10, -1.8], [13, 1.8], [50, 1.5], [51, -1.6], [54, 0.2], [57, -2.2], [58, 2.0]];
const STATIONS = [
  { x: 10, label: "1 slalom" }, { x: 19, label: "2 beam" }, { x: 28.5, label: "3 turnstiles" },
  { x: 38, label: "4 gate" }, { x: 44, label: "beam" }, { x: 54, label: "5 cluster" },
];

export function CourseMap() {
  const climbs = runs((p) => p.m === "climb");
  const g = flight.gate;
  const ink = "var(--fg)", mute = "var(--muted)", line = "var(--border)";
  return (
    <div className="scroll">
      <svg viewBox={`0 0 ${W} 372`} role="img" aria-labelledby="cm-t cm-d" fontFamily="var(--font-mono)" fontSize="10.5">
        <title id="cm-t">Recorded flight path over the obstacle course</title>
        <desc id="cm-d">Top-down and side views of the 77 metre run. The drone path weaves through the slalom, rises to 3 metres over both beams, passes through the 3.2 metre gate gap and the pillar cluster. The baseline without Jev stops at 17.7 metres, just before the first beam.</desc>

        {/* panels */}
        <rect x={L} y={TOP.y0} width={W - L - R} height={TOP.h} fill="var(--surface)" />
        <rect x={L} y={SIDE.y0} width={W - L - R} height={SIDE.h} fill="var(--surface)" />
        <text x={L} y={TOP.y0 - 22} fill={mute}>TOP-DOWN · y (m)</text>
        <text x={L} y={SIDE.y0 - 8} fill={mute}>SIDE · altitude (m)</text>

        {/* x axis */}
        {[0, 10, 20, 30, 40, 50, 60, 70, 80].map((x) => (
          <g key={x}>
            <line x1={sx(x)} x2={sx(x)} y1={SIDE.y0 + SIDE.h} y2={SIDE.y0 + SIDE.h + 5} stroke={mute} />
            <text x={sx(x)} y={SIDE.y0 + SIDE.h + 18} textAnchor="middle" fill={mute}>{x}{x === 80 ? " m" : ""}</text>
          </g>
        ))}
        {[1, 2, 3].map((z) => (
          <g key={z}>
            <line x1={L} x2={W - R} y1={sz(z)} y2={sz(z)} stroke={line} />
            <text x={L - 6} y={sz(z) + 3.5} textAnchor="end" fill={mute}>{z}</text>
          </g>
        ))}
        {[-5, 0, 5].map((y) => (
          <text key={y} x={L - 6} y={sy(y) + 3.5} textAnchor="end" fill={mute}>{y}</text>
        ))}

        {/* station labels */}
        {STATIONS.map((s) => (
          <text key={s.x} x={sx(s.x)} y={TOP.y0 - 6} textAnchor="middle" fill={ink} fontWeight="600">{s.label}</text>
        ))}

        {/* obstacles, top-down */}
        {[19, 44].map((x) => <rect key={x} x={sx(x - 0.5)} y={TOP.y0} width={sx(1) - sx(0)} height={TOP.h} fill={mute} opacity="0.45" />)}
        {[26, 31].map((x) => <line key={x} x1={sx(x)} x2={sx(x)} y1={sy(2.6)} y2={sy(-2.6)} stroke={mute} strokeWidth="3" strokeDasharray="3 3" />)}
        <rect x={sx(37.75)} y={TOP.y0} width={sx(0.5) - sx(0)} height={sy(g.left_inner_y) - TOP.y0} fill={ink} opacity="0.7" />
        <rect x={sx(37.75)} y={sy(g.right_inner_y)} width={sx(0.5) - sx(0)} height={TOP.y0 + TOP.h - sy(g.right_inner_y)} fill={ink} opacity="0.7" />
        {PILLARS.map(([x, y]) => <circle key={`${x}${y}`} cx={sx(x)} cy={sy(y)} r="4.2" fill={ink} opacity="0.7" />)}

        {/* obstacles, side */}
        {[19, 44].map((x) => <circle key={x} cx={sx(x)} cy={sz(1.6)} r={(0.5 / 4) * SIDE.h} fill={mute} opacity="0.6" />)}
        {[26, 31].map((x) => <circle key={x} cx={sx(x)} cy={sz(1.7)} r="3" fill={mute} />)}
        <rect x={sx(37.75)} y={SIDE.y0} width={sx(0.5) - sx(0)} height={SIDE.h} fill={ink} opacity="0.18" />
        {PILLARS.map(([x, y]) => <rect key={`s${x}${y}`} x={sx(x) - 2} y={SIDE.y0} width="4" height={SIDE.h} fill={ink} opacity="0.12" />)}

        {/* rover and drone */}
        <path d={path((p) => [sx(Math.min(p.rx, 82)), sy(p.ry)])} fill="none" stroke={mute} strokeWidth="1" strokeDasharray="2 3" />
        <path d={path((p) => [sx(p.x), sy(p.y)])} fill="none" stroke={ink} strokeWidth="1.6" strokeLinejoin="round" />
        <path d={path((p) => [sx(p.x), sz(p.z)])} fill="none" stroke={ink} strokeWidth="1.6" strokeLinejoin="round" />
        {climbs.map((r, i) => (
          <g key={i} fill="none" stroke="var(--jev)" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round">
            <path d={r.map((p, j) => `${j ? "L" : "M"}${sx(p.x).toFixed(1)} ${sy(p.y).toFixed(1)}`).join("")} />
            <path d={r.map((p, j) => `${j ? "L" : "M"}${sx(p.x).toFixed(1)} ${sz(p.z).toFixed(1)}`).join("")} />
          </g>
        ))}

        {/* baseline stall */}
        <line x1={sx(17.7)} x2={sx(17.7)} y1={TOP.y0} y2={SIDE.y0 + SIDE.h} stroke={ink} strokeDasharray="5 4" />
        <text x={sx(17.7) + 7} y={SIDE.y0 + SIDE.h - 8} fill={ink}>no-Jev baseline stops here: 17.7 m, 3 of 3 seeds</text>
        <text x={sx(77.35)} y={sz(1.6) - 10} textAnchor="end" fill="var(--jev-ink)" fontWeight="600">77.5 m, 0 contacts</text>

        {/* legend */}
        <g transform={`translate(${L}, 366)`} fill={mute}>
          <line x1="0" x2="22" y1="-3" y2="-3" stroke={ink} strokeWidth="1.6" /><text x="28" y="0">drone, recorded</text>
          <line x1="150" x2="172" y1="-3" y2="-3" stroke="var(--jev)" strokeWidth="3.4" strokeLinecap="round" /><text x="178" y="0">Jev judgment = climb</text>
          <line x1="336" x2="358" y1="-3" y2="-3" stroke={mute} strokeDasharray="2 3" /><text x="364" y="0">rover (target)</text>
        </g>
      </svg>
    </div>
  );
}

/* Fig: why the geometric controller cannot recover from inverted flight. */
export function AttitudeCurve() {
  const w = 520, h = 320, l = 46, b = 44, t = 38, r = 16;
  const px = (deg: number) => l + (deg / 180) * (w - l - r);
  const py = (v: number) => t + (1 - v) * (h - t - b);
  const curve = (f: (rad: number) => number) =>
    Array.from({ length: 91 }, (_, i) => i * 2).map((d, i) => `${i ? "L" : "M"}${px(d).toFixed(1)} ${py(f((d * Math.PI) / 180)).toFixed(1)}`).join("");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ maxWidth: 560, width: "100%" }} role="img" aria-labelledby="ac-t ac-d" fontFamily="var(--font-mono)" fontSize="13">
      <title id="ac-t">Restoring torque against attitude error for two error definitions</title>
      <desc id="ac-d">The rotation-matrix error grows as sine of theta, peaking at 90 degrees and returning to zero at 180. The quaternion error grows as sine of half theta and is largest at 180 degrees.</desc>
      {[0, 0.5, 1].map((v) => (
        <g key={v}>
          <line x1={l} x2={w - r} y1={py(v)} y2={py(v)} stroke="var(--border)" />
          <text x={l - 8} y={py(v) + 4} textAnchor="end" fill="var(--muted)">{v.toFixed(1)}</text>
        </g>
      ))}
      {[0, 45, 90, 135, 180].map((d) => (
        <text key={d} x={px(d)} y={h - b + 18} textAnchor="middle" fill="var(--muted)">{d}°</text>
      ))}
      <text x={(l + w - r) / 2} y={h - 4} textAnchor="middle" fill="var(--muted)">attitude error θ</text>
      <path d={curve(Math.sin)} fill="none" stroke="var(--code)" strokeWidth="2" strokeDasharray="6 4" />
      <path d={curve((x) => Math.sin(x / 2))} fill="none" stroke="var(--jev)" strokeWidth="2.6" />
      <circle cx={px(180)} cy={py(0)} r="4.5" fill="var(--bg)" stroke="var(--code)" strokeWidth="2" />
      <circle cx={px(180)} cy={py(1)} r="4.5" fill="var(--jev)" />
      <text x={px(166)} y={py(0) - 12} textAnchor="end" fill="var(--code)">sin θ: zero torque inverted</text>
      <text x={px(180)} y={py(1) - 14} textAnchor="end" fill="var(--jev-ink)" fontWeight="600">sin(θ/2): maximal at 180°</text>
    </svg>
  );
}

const RESULTS = [
  { name: "Furthest point reached", unit: "m", base: 17.7, jev: 77.5, max: 77.5, baseLabel: "17.7 m", jevLabel: "77.5 m" },
  { name: "Target kept in view", unit: "%", base: 19, jev: 82, max: 100, baseLabel: "~19%", jevLabel: "82%" },
  { name: "Time pinned in safety reflex", unit: "%", base: 68, jev: 9, max: 100, baseLabel: "65-71%", jevLabel: "9%" },
];

export function ResultsChart() {
  return (
    <>
      <div className="legend">
        <span><i className="sw jev" />Jev engaged (1 run, 65 s)</span>
        <span><i className="sw base" />Baseline, no Jev (3 seeds)</span>
      </div>
      <div className="bars">
        {RESULTS.map((m) => (
          <div className="metric" key={m.name}>
            <div className="name">{m.name}</div>
            <div className="bar"><span>Jev</span><span className="track"><span className="fill" style={{ "--v": (m.jev / m.max) * 100 } as React.CSSProperties} /></span><span className="val">{m.jevLabel}</span></div>
            <div className="bar base"><span>baseline</span><span className="track"><span className="fill" style={{ "--v": (m.base / m.max) * 100 } as React.CSSProperties} /></span><span className="val">{m.baseLabel}</span></div>
          </div>
        ))}
      </div>
    </>
  );
}

const BUDGET = [
  { k: "Perception", v: 0.03, c: "var(--code)" },
  { k: "Jev decision", v: 0.118, c: "var(--jev)" },
  { k: "Decision age", v: 0.024, c: "var(--muted)" },
  { k: "Airframe translating 2 m sideways", v: 0.7, c: "var(--fg)" },
];

export function ReactionBudget() {
  const total = BUDGET.reduce((s, b) => s + b.v, 0);
  return (
    <>
      <div className="budget" role="img" aria-label="Stacked bar: the airframe takes 0.70 of the 0.87 second reaction budget, Jev 0.118 seconds">
        {BUDGET.map((b) => <div key={b.k} style={{ width: `${(b.v / total) * 100}%`, background: b.c }} />)}
      </div>
      <div className="budget-key">
        {BUDGET.map((b) => (
          <div key={b.k}>
            <i className="sw" style={{ background: b.c }} />
            <span>{b.k}</span>
            <span className="val">{b.v.toFixed(3)} s · {Math.round((b.v / total) * 100)}%</span>
          </div>
        ))}
      </div>
    </>
  );
}

export function SceneIO() {
  const ex = flight.example;
  const probs = Object.entries(ex.judgment.probabilities).sort((a, b) => b[1] - a[1]);
  const s = ex.scene;
  return (
    <div className="io">
      <div>
        <span className="k">in · what the camera code observed, t = {ex.t} s</span>
        <pre tabIndex={0}>{`{
  "sector_range_m": { "far_left": ${s.sector_range_m.far_left}, "left": ${s.sector_range_m.left},
    "center": ${s.sector_range_m.center}, "right": ${s.sector_range_m.right}, "far_right": ${s.sector_range_m.far_right} },
  "sectors_blocked_of_5": ${s.sectors_blocked_of_5},
  "path_ahead_m": ${s.path_ahead_m},
  `}<span className="o">{`"obstruction_top_above_drone_m": ${s.obstruction_top_above_drone_m},`}</span>{`
  "obstruction_taller_than_camera_can_see": ${s.obstruction_taller_than_camera_can_see},
  "target": { "visible": ${s.target.visible}, "bearing_deg": ${s.target.bearing_deg},
    "range_m": ${s.target.range_m}, "unseen_for_s": ${s.target.unseen_for_s} }
}`}</pre>
      </div>
      <div className="out">
        <span className="k">out · typed answers with probabilities</span>
        <pre tabIndex={0}>
          <span className="c">{"# Choice: maneuver\n"}</span>
          {probs.map(([k, v]) => (
            <span key={k} className={k === ex.judgment.maneuver ? "o" : undefined}>{`${k.padEnd(12)} ${v.toFixed(2)}\n`}</span>
          ))}
          <span className="c">{"\n# Score: risk, clear -> about to hit\n"}</span>{`${ex.judgment.risk.toFixed(2)}\n`}
          <span className="c">{"\n# Noul: target_truly_lost\n"}</span>{`${ex.judgment.target_truly_lost.toFixed(2)}`}
        </pre>
      </div>
    </div>
  );
}
