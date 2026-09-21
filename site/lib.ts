export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://jev-drone.vercel.app").replace(/\/$/, "");
export const REPO_URL = "https://github.com/RomanSlack/jev-drone";
export const X_POST_URL = "https://x.com/RomanSlack1/status/2100335978229690683";
export const TITLE = "jev-drone: MuJoCo drone with a judgment model in the loop";
export const HEADLINE = "A judgment model in a drone's control loop";
export const DESCRIPTION =
  "Camera-only autonomous quadrotor clears a MuJoCo obstacle course. A judgment model (TypeSafe Jev) decides at 2.5 Hz; code keeps the veto. Open source.";
