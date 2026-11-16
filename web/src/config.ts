// Product and team names shown in the website. Change them here.
export const APP_NAME = "HEALTH-01";
export const APP_TAGLINE = "Astronaut health monitoring";
export const TEAM_NAME = "Amerat";
export const TEAM_NUMBER = "01";
export const TEAM_PLACE = "Al Amerat, Oman";
export const EVENT = "NASA Space Apps Challenge 2026";

// Two looks from one code base:
//   notebook (default): hand-drawn field notebook that matches the team sketches
//   serious: clean mission-control look for formal demos (build with VITE_EDITION=serious)
export type Edition = "notebook" | "serious";
export const EDITION: Edition = (import.meta.env.VITE_EDITION as Edition) === "serious" ? "serious" : "notebook";

// Static web demo (Vercel): no backend, the API answers come from recorded JSON
// (scripts/build_static_demo.py). AI pages point to the desktop app instead.
export const STATIC_DEMO = import.meta.env.VITE_STATIC_DEMO === "1";
export const DESKTOP_APP_URL = "https://github.com/MaskedAlkindi/NASA-SPACE-APPS-SUBMISSION/releases/latest";

// Where the demo lives inside the site. The landing page is at "/".
export const APP_BASE = "/app";

// Chart palette taken from the team logo.
export const C = {
  steel: "#005c96",     // logo outline
  blue: "#1d2bdb",      // constellation line
  sky: "#6c9cff",       // visor shading
  red: "#d81b1b",       // "01"
  amber: "#b86e00",
  green: "#2e7d32",
  violet: "#6b4fbb",
  ink: "#17191f",
  grey: "#858d9c",
};
export const SERIES = [C.steel, C.red, C.blue, C.amber];
