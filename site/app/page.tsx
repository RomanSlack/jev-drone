import Image from "next/image";
import { REPO_URL, X_POST_URL } from "@/lib";
import { Toc } from "@/components/toc";
import { Figure, RateStack, LoopDiagram, CourseMap, AttitudeCurve, ResultsChart, ReactionBudget, SceneIO } from "@/components/figures";

const SECTIONS = [
  { id: "abstract", label: "Abstract" },
  { id: "architecture", label: "Architecture" },
  { id: "questions", label: "Three questions" },
  { id: "course", label: "The course" },
  { id: "results", label: "Results" },
  { id: "state", label: "State design" },
  { id: "lessons", label: "Simulator lessons" },
  { id: "tunnel", label: "Tunnel experiment" },
  { id: "run", label: "Run it" },
  { id: "faq", label: "FAQ" },
];

const GitHubMark = () => (
  <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
    <path d="M8 0a8 8 0 0 0-2.53 15.59c.4.07.55-.17.55-.38v-1.33c-2.23.48-2.7-1.07-2.7-1.07-.36-.93-.89-1.17-.89-1.17-.73-.5.05-.49.05-.49.8.06 1.23.83 1.23.83.72 1.22 1.88.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.6 7.6 0 0 1 4 0c1.53-1.03 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.28.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48v2.19c0 .21.15.46.55.38A8 8 0 0 0 8 0Z" />
  </svg>
);

const XMark = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
  </svg>
);

const STATIONS = [
  { img: "slalom", name: "1. Slalom", text: "Ordinary steering around three pillars." },
  { img: "beam", name: "2. Low beam", text: "Spans the whole corridor. There is no gap at any width, so it must be flown over." },
  { img: "turnstiles", name: "3. Turnstiles", text: "Arms sweep across the lane. Moving, so they must be timed." },
  { img: "gate", name: "4. Sliding gate", text: "A 3.2 m gap that slides sideways. Too tall to climb, so it must be threaded." },
  { img: "cluster", name: "5. Cluster", text: "Dense pillars. The rover disappears behind them." },
];

const JUDGMENTS = [
  ["Low barrier, all 5 sectors blocked, top edge 0.45 m", "climb", 0.93, "risk 1.42"],
  ["Tall pillar ahead, right wide open", "gap_right", 0.72, "risk 1.53"],
  ["Tall pillar ahead, left wide open", "gap_left", 0.4, "risk 1.58"],
  ["Target gone 7 s, scene wide open", "reacquire", 0.96, "lost 0.85"],
  ["Boxed in, close on all sides, tall", "brake", 0.84, "risk 1.89"],
  ["All clear, target dead ahead", "hold_course", 0.82, "risk 0.46"],
  ["Brief occlusion 0.6 s, path clear", "(muddy)", 0.24, "lost 0.12"],
] as const;

const LESSONS = [
  ["znear and zfar are fractions of the scene extent, not metres", "In a 40 m arena, znear=0.05 blinded the drone inside 1.93 m, so the safety reflex never once fired."],
  ["Image-right is -y for a camera looking down +x", "The target bearing sign was inverted and the yaw loop became positive feedback. The drone turned away from what it was chasing."],
  ["The camera sees its own airframe", "The drone detected its own body as an obstacle at 3.94 m until own-body geoms were masked out."],
  ["Clipping negative motor commands destroys thrust and torque together", "Thrust-priority mixing plus a slew-limited velocity command took peak tilt from 84° (unrecoverable tumble) to a 40° transient."],
  ["A quadrotor cannot thrust downward, and the controller has to know", "On a hard descent the desired thrust axis points at the floor and the controller faithfully commands inverted flight. Clamping desired vertical acceleration positive was worth more than every gain-tuning attempt combined."],
  ["Lateral control needs a position loop, not a velocity command", "A held lateral velocity has no notion of where to stop. Dead-reckon laterally and correct only on plausible wall readings: 0.07 m median error against ground truth."],
  ["A lost target needs a world-frame estimate, not a bearing", "Convert bearing, range and own pose into a world position, carry it forward with the observed velocity, and fly there. Good to 0.14 m and 0.12 m/s, differentiated over about 1 s."],
  ["A reflex must brake for what is in your path, not what is beside you", "Walls 1.2 m to either side triggered a permanent brake, so the gate was not hard, it was forbidden. Splitting out the middle sectors fixed it."],
  ["Separate the tracking field of view from the threat cone", "A wide lens helps you see the target but ruins threat assessment: things 60° off the nose were never in the way."],
  ["Latch one setpoint per camera frame", "Re-applying a heading correction at 50 Hz off a 15 Hz camera applies the same error three times and spins the aircraft."],
  ["Sim time is not wall-clock time", "The sim ran at 10x real time, so 152 of 182 judgment requests hit a full queue and the model influenced nothing. Pace the sim to real time or you are not testing anything."],
];

const FAQ = [
  ["Is the language model flying the drone?", "No. Flight control runs at 500 Hz in a geometric controller, perception is numpy on depth and segmentation buffers, and a 50 Hz safety reflex overrides everything. Jev only makes the tactical choice (over it, around it, which side, is the target lost) about 2.5 times a second, and code can refuse its answer."],
  ["Does Jev see the camera image?", "No. Jev is not a vision model. It receives a small JSON description of the scene, produced by classical computer vision, and returns typed answers with probabilities."],
  ["Why does the baseline fail at the second station?", "The baseline steers toward the wider side. The low beam spans the entire corridor, so no side is wider. Going over an obstacle is not something that heuristic can express, so it stops at 17.7 m on every seed without ever crashing."],
  ["How much does a flight cost in model calls?", "The recorded 65 s run made 80 calls and used 96k tokens at 0.11 s median latency. Code decides when a judgment is worth asking for, and unchanged scenes reuse the last answer."],
  ["Can I reproduce this?", "Yes. The repository is MIT licensed. setup.sh builds the environment and fetches the Skydio X2 model from MuJoCo Menagerie. The no-Jev ablation runs for free; the Jev runs need a TypeSafe API key."],
];

export default function Page() {
  return (
    <div className="shell">
      <header className="topbar">
        <a className="wordmark" href="#main">jev<i>-</i>drone</a>
        <a className="btn btn-quiet btn-sm" href={REPO_URL}><GitHubMark />GitHub</a>
      </header>

      <main id="main">
        <div className="head">
          <h1>A judgment model in a drone&rsquo;s <em>control loop</em></h1>
          <p className="lead">
            An autonomous quadrotor flies a five-station obstacle course in MuJoCo using only its onboard camera.
            A small judgment model decides what the situation means, about 2.5 times a second. Everything
            time-critical stays in ordinary code.
          </p>
          <div className="actions">
            <a className="btn btn-primary" href={REPO_URL}><GitHubMark />View the code on GitHub</a>
            <a className="btn btn-quiet" href={X_POST_URL}><XMark />See the post on X</a>
            <a className="btn btn-quiet" href="#results">Jump to results</a>
          </div>
          <dl className="meta">
            <div><dt>Author</dt><dd>Roman Slack</dd></div>
            <div><dt>Published</dt><dd><time dateTime="2026-09-16">16 Sep 2026</time></dd></div>
            <div><dt>Stack</dt><dd>MuJoCo 3, Python, TypeSafe Jev</dd></div>
            <div><dt>License</dt><dd>MIT, open source</dd></div>
          </dl>
        </div>

        <div className="article">
          <Toc items={SECTIONS} />
          <article>
            <Figure n={1} className="dark" caption={<>The full run, unedited. Chase camera on the left; on the right, the 64×48 onboard depth image, free space by sector, and the live judgment probabilities. 47 s, up to 3.6 m/s, zero contacts.</>}>
              <video controls muted loop playsInline preload="none" poster="/figures/course-poster.jpg" width={1280} height={696} aria-label="Video of the drone clearing all five stations of the obstacle course">
                <source src="/figures/course-run.mp4" type="video/mp4" />
              </video>
            </Figure>

            <Figure n={2} className="pad" caption={<>The recorded trajectory, drawn from the flight tape rather than sketched. Orange marks where the active judgment was <code>climb</code>: both beams, and nowhere else. The gate shutters are drawn where they were at the moment of crossing.<span className="hint label">On a small screen, scroll the figure sideways.</span></>}>
                <CourseMap />
            </Figure>

            <section id="abstract" style={{ paddingTop: 0 }}>
              <div className="abstract prose">
                <span className="label">Abstract</span>
                <p>
                  We put a small judgment model (<a href="https://typesafe.ai">TypeSafe</a>&rsquo;s Jev) inside the control loop of a simulated
                  Skydio X2 quadrotor that chases a ground rover through an obstacle course with a camera as its only sensor.
                  The model is not the perception layer and it does not run at control rate. It answers three small, typed
                  questions about a symbolic scene, and a 50 Hz reflex layer keeps the veto.
                </p>
                <p>
                  The same stack with the model disabled is safe but stuck: it never crashes and never gets past the second
                  station, because flying <em>over</em> an obstacle is not something a steer-to-the-wider-side heuristic can
                  express. With Jev engaged the drone clears all 77.5 m with no collisions. The claim is deliberately
                  narrow, and the caveats are stated below.
                </p>
              </div>
            </section>

            <section id="architecture">
              <h2>Four loops, and only the slowest one is a model</h2>
              <div className="prose">
                <p>
                  Nothing about the flight is scripted. The drone is the Skydio X2 from{" "}
                  <a href="https://github.com/google-deepmind/mujoco_menagerie">MuJoCo Menagerie</a>, a real airframe with four
                  rotors. Each layer runs at the rate its job demands, and the judgment model sits at the bottom of that
                  ladder, two hundred times slower than the controller.
                </p>
              </div>
              <Figure n={3} className="pad" caption={<>The rate ladder. Tick spacing is compressed, but the ordering is the point: blue layers are ordinary code, the orange layer is Jev.</>}>
                <RateStack />
              </Figure>
              <div className="prose">
                <p>
                  Code decides <em>when</em> to ask. On an open corridor with the target in view there is nothing to decide, so
                  no call is made. Scenes are fingerprinted, so an unchanged situation reuses the last judgment.{" "}
                  <strong>Code also keeps the veto.</strong> Jev can propose <code>climb</code>, but guidance refuses it unless
                  the obstruction&rsquo;s measured top edge is actually within the aircraft&rsquo;s climb ceiling.
                </p>
              </div>
              <Figure n={4} className="pad" caption={<>One pass through the loop. Jev never touches pixels and never touches motors; it sits between a symbolic scene and a guidance layer that is free to say no.</>}>
                <LoopDiagram />
              </Figure>
            </section>

            <section id="questions">
              <h2>Three questions, three answer types</h2>
              <div className="prose">
                <p>
                  Classical computer vision turns the depth and segmentation buffers into a compact scene: five forward range
                  sectors, the height of whatever blocks the path, whether its top edge is even visible, and where the target
                  is. Jev reads that and answers three questions in one call.
                </p>
              </div>
              <div className="tablewrap">
                <table>
                  <thead><tr><th>Question</th><th>Type</th><th>What comes back</th></tr></thead>
                  <tbody>
                    <tr><td><code>maneuver</code></td><td><span className="who">Choice</span></td><td>hold_course, gap_left, gap_right, climb, brake or reacquire, each with a probability</td></tr>
                    <tr><td><code>risk</code></td><td><span className="who">Score</span></td><td>A graded value from &ldquo;clear and open&rdquo; through &ldquo;tight&rdquo; to &ldquo;about to hit something&rdquo;</td></tr>
                    <tr><td><code>target_truly_lost</code></td><td><span className="who">Noul</span></td><td>A probability: genuinely lost, or just briefly occluded?</td></tr>
                  </tbody>
                </table>
              </div>
              <Figure n={5} caption={<>A real exchange from the recorded run, 2 m short of the first beam. All five sectors are blocked, but the top edge sits 0.14 m above the drone, so the answer is inferable from the state. Jev picks <code>climb</code> at p = 0.83.</>}>
                <SceneIO />
              </Figure>

              <h3>The judgments hold up on hand-built scenes</h3>
              <div className="prose"><p>Six of seven correct, with strong probabilities.</p></div>
              <div className="tablewrap">
                <table>
                  <thead><tr><th>Scene</th><th>Choice</th><th className="num">p</th><th className="num">Other</th></tr></thead>
                  <tbody>
                    {JUDGMENTS.map(([scene, choice, p, other]) => (
                      <tr key={scene}>
                        <td>{scene}</td>
                        <td><code>{choice}</code></td>
                        <td className="num"><span className="pbar" aria-hidden="true"><i style={{ "--v": p } as React.CSSProperties} /></span>{p.toFixed(2)}</td>
                        <td className="num">{other}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="prose">
                <p>
                  The muddy case is instructive. The <strong>Choice</strong> was unconfident, but the <strong>Noul</strong>{" "}
                  answered it cleanly (<code>target_truly_lost = 0.12</code>). So search behaviour is gated on the Noul, not on
                  the Choice. Use the primitive that actually fits the question.
                </p>
              </div>
            </section>

            <section id="course">
              <h2>Five stations, each breaking a different assumption</h2>
              <Figure n={6} caption={<>Frames from the recorded run, in order. The red box is the rover the drone is chasing.</>} className="pad">
                <ol className="strip">
                  {STATIONS.map((s) => (
                    <li key={s.img}>
                      <Image src={`/figures/station-${s.img}.jpg`} alt={`Chase-camera view of the drone at the ${s.name.slice(3).toLowerCase()} station`} width={960} height={667} sizes="(min-width: 900px) 190px, (min-width: 640px) 30vw, 92vw" />
                      <b>{s.name}</b>
                      <span>{s.text}</span>
                    </li>
                  ))}
                </ol>
              </Figure>
            </section>

            <section id="results">
              <h2>The baseline is safe but stuck</h2>
              <div className="prose">
                <p>
                  The ablation is the same stack with the Jev call disabled, falling back to a greedy &ldquo;steer toward the
                  wider side&rdquo; heuristic. It stops dead at station 2 every single time. With Jev the drone clears the
                  entire course in about 47 s.
                </p>
              </div>
              <Figure n={7} className="pad" caption={<>Collisions were zero in every run on both sides. 80 model calls over 65 s, 0.11 s median latency, 96k tokens.</>}>
                <ResultsChart />
              </Figure>
              <div className="tablewrap wide">
                <table>
                  <thead><tr><th>Where</th><th className="num">x (m)</th><th className="num">t (s)</th><th className="num">z (m)</th><th>What happened</th></tr></thead>
                  <tbody>
                    <tr><td>Beam</td><td className="num">19</td><td className="num">15.7</td><td className="num">3.0</td><td>Climbed over</td></tr>
                    <tr><td>Turnstiles</td><td className="num">26</td><td className="num">20.3</td><td className="num">1.6</td><td>Timed the sweeping arms</td></tr>
                    <tr><td>Gate</td><td className="num">38</td><td className="num">31.3</td><td className="num">1.6</td><td>Threaded the sliding 3.2 m gap</td></tr>
                    <tr><td>Second beam</td><td className="num">44</td><td className="num">36.8</td><td className="num">2.8</td><td>Climbed over</td></tr>
                    <tr><td>Cluster</td><td className="num">50</td><td className="num">41.3</td><td className="num">1.6</td><td>Lost the rover in the pillars</td></tr>
                    <tr><td>Exit</td><td className="num">58</td><td className="num">46.6</td><td className="num">1.6</td><td>Re-acquired it and closed back to 3.7 m</td></tr>
                  </tbody>
                </table>
              </div>
              <div className="prose">
                <p>
                  The cluster is worth noting. The drone genuinely loses the rover there, flies to where it estimates the rover
                  has got to, and picks it back up. That recovery is the difference between a demo and a system.
                </p>
              </div>
              <div className="pair" style={{ maxWidth: "var(--wide)" }}>
                <Figure n={8} className="dark" caption="Over the low beam. The panel shows climb selected.">
                  <Image src="/figures/hud-climb.jpg" alt="Drone climbing over an orange beam, with the Jev panel showing the climb maneuver selected" width={1620} height={880} sizes="(min-width: 640px) 480px, 92vw" />
                </Figure>
                <Figure n={9} className="dark" caption="Through the sliding gate, target held in frame.">
                  <Image src="/figures/hud-gate.jpg" alt="Drone threading the gap between two cyan gate shutters while following the red rover" width={1620} height={880} sizes="(min-width: 640px) 480px, 92vw" />
                </Figure>
              </div>

              <aside className="caveat" aria-label="Caveats">
                <span className="label">Honest caveats</span>
                <p>
                  The Jev column is a single 65 s run, not a seed-matched average. On an earlier, simpler arena a matched
                  3-seed comparison showed <strong>no advantage</strong> for Jev: it crossed 0 of 3, same as baseline, and the
                  extra maneuvering cost target visibility. Run-to-run variance is large.
                </p>
                <p>
                  The claim this project supports is specific: <em>the baseline is structurally incapable of the maneuver, and
                  Jev supplies it.</em> It is not &ldquo;the model makes the drone better at everything&rdquo;.
                </p>
              </aside>

              <h3>What is, and is not, the model</h3>
              <div className="tablewrap">
                <table>
                  <thead><tr><th>Layer</th><th>Who does it</th><th className="num">Rate</th></tr></thead>
                  <tbody>
                    <tr><td>Awareness: what is out there, how far, where is the target</td><td>numpy on depth and segmentation. <span className="who">Zero Jev.</span></td><td className="num">15 Hz</td></tr>
                    <tr><td>Flight control: attitude, thrust, mixing</td><td>Geometric controller. <span className="who">Zero Jev.</span></td><td className="num">500 Hz</td></tr>
                    <tr><td>Safety reflex: do not hit that</td><td>Code, and it <span className="who">overrides</span> Jev</td><td className="num">50 Hz</td></tr>
                    <tr><td>Tactical choice: over it, around it, which side, is it lost</td><td><span className="who" style={{ color: "var(--jev-ink)" }}>100% Jev</span></td><td className="num">~3 Hz</td></tr>
                  </tbody>
                </table>
              </div>
            </section>

            <section id="state">
              <h2>The state has to contain the answer</h2>
              <div className="prose">
                <p>
                  Jev initially refused to ever pick <code>climb</code>. That was correct. The state was five horizontal range
                  sectors. It contained no vertical information at all, so &ldquo;fly over it&rdquo; was not an inferable option.
                </p>
                <p>
                  Adding the obstruction&rsquo;s top-edge height, whether that top edge is visible to the camera, and the
                  aircraft&rsquo;s own climb ceiling moved <code>climb</code> from never chosen to p = 0.93. That was a
                  state-design bug, not a model failure. It is the single most useful thing this project taught.
                </p>
              </div>
            </section>

            <section id="lessons">
              <h2>Simulator and controller lessons worth stealing</h2>
              <div className="prose">
                <p>Most of the work was the simulator and the controller, not the model. One of these deserves a figure.</p>
              </div>
              <Figure n={10} className="pad" caption={<>The geometric attitude error <code>eR = ½ vee(RdᵀR − RᵀRd)</code> has magnitude proportional to sin θ, so an upside-down aircraft sits at a stationary point with no restoring torque. A quaternion error is monotonic to 180°. Verified recovering from 179°, and the same fix extended the course run from 77 m to 88 m.</>}>
                <AttitudeCurve />
              </Figure>
              <ul className="lessons">
                {LESSONS.map(([h, p]) => (
                  <li key={h}><b>{h}</b><span>{p}</span></li>
                ))}
              </ul>
            </section>

            <section id="tunnel">
              <h2>The tunnel experiment: Jev as the only navigator</h2>
              <div className="prose">
                <p>
                  A separate, harder setup: a 620 m enclosed tunnel, 15 obstacles, chasing a car at 9 m/s, with no reflex and
                  no hand-written avoidance at all. Two graded <code>Score</code> questions (how hard to steer and which way;
                  should it change height) map straight onto the control command, so the answer <em>is</em> the steering
                  signal rather than a label to act on.
                </p>
              </div>
              <div className="tablewrap">
                <table>
                  <thead><tr><th>Measured live in a 500 Hz loop</th><th className="num">Value</th></tr></thead>
                  <tbody>
                    <tr><td>Decision latency, median</td><td className="num">0.118 s</td></tr>
                    <tr><td>Decision latency, p90</td><td className="num">0.164 s</td></tr>
                    <tr><td>Sequential ceiling</td><td className="num">7.4 Hz</td></tr>
                    <tr><td>Pipelined, 4 to 6 workers, zero errors in ~2000 calls</td><td className="num">21 decisions/s</td></tr>
                  </tbody>
                </table>
              </div>
              <Figure n={11} className="pad" caption={<>The reaction budget at 9 m/s. The model is 13% of the loop; the vehicle is 80%. Making the decisions faster cannot help, and commanding the airframe harder is what makes it tumble.</>}>
                <ReactionBudget />
              </Figure>
              <Figure n={12} className="dark" caption={<>Inside the tunnel. Here the panel shows graded steer and height scores instead of a discrete maneuver.</>}>
                <Image src="/figures/tunnel.jpg" alt="Drone chasing a red car toward a white obstacle in an enclosed tunnel, with steer and height score sliders on the Jev panel" width={1620} height={880} sizes="(min-width: 1160px) 990px, 92vw" />
              </Figure>
              <div className="prose">
                <p>
                  <strong>Status: partial.</strong> The aircraft is stable, flies full episodes and recovers from beyond 90°.
                  In the best runs it dodged with zero collisions and 94% target visibility. But it does not reliably clear the
                  whole tunnel: it tends to over-commit a dodge and end up against a wall. This is written up as a partial
                  result, not a working system.
                </p>
              </div>
            </section>

            <section id="run">
              <h2>Run it yourself</h2>
              <div className="prose">
                <p>The ablation runs without an API key. The Jev runs need one from TypeSafe.</p>
              </div>
              <Figure n={13} caption={<>A video run also writes a tape file, so visuals can be re-cut with <code>replay.py</code> without flying again or spending credits.</>}>
                <pre tabIndex={0}>{`git clone ${REPO_URL}.git && cd jev-drone
./setup.sh                      `}<span className="c"># venv + Skydio X2 model</span>{`
cp .env.example .env            `}<span className="c"># add your key</span>{`
set -a && . ./.env && set +a
export MUJOCO_GL=glfw           `}<span className="c"># or egl on a headless box</span>{`

.venv/bin/python run.py --seconds 65 --seeds 1                       `}<span className="c"># Jev engaged</span>{`
.venv/bin/python run.py --no-jev --fast --seconds 65 --seeds 0 1 2   `}<span className="c"># ablation, free</span>{`
.venv/bin/python run.py --seconds 65 --seeds 1 --video course.mp4    `}<span className="c"># telemetry video</span></pre>
              </Figure>
              <div className="prose">
                <p>
                  Every knob a human should review lives at the top of <code>tactics.py</code>: the three questions, the option
                  rubrics, and every threshold that changes how the aircraft reacts to a judgment.
                </p>
              </div>
            </section>

            <section id="faq">
              <h2>Questions people ask</h2>
              <script
                type="application/ld+json"
                dangerouslySetInnerHTML={{
                  __html: JSON.stringify({
                    "@context": "https://schema.org",
                    "@type": "FAQPage",
                    mainEntity: FAQ.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })),
                  }),
                }}
              />
              {FAQ.map(([q, a]) => (
                <details key={q}>
                  <summary>{q}</summary>
                  <p>{a}</p>
                </details>
              ))}
            </section>

            <footer className="foot">
              <h2>The code, the course and the tapes are all in the repository</h2>
              <div className="actions">
                <a className="btn btn-primary" href={REPO_URL}><GitHubMark />RomanSlack/jev-drone</a>
              </div>
              <p>
                MIT licensed. The Skydio X2 model comes from MuJoCo Menagerie under its own license. Jev is a model by{" "}
                <a href="https://typesafe.ai">TypeSafe</a>. Cite as: Roman Slack, &ldquo;jev-drone: a judgment model in a
                drone&rsquo;s control loop&rdquo;, 2026.
              </p>
            </footer>
          </article>
        </div>
      </main>
    </div>
  );
}
