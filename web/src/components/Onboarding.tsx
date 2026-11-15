import { useEffect, useState } from "react";
import { SpaceSketch, type SketchKind } from "../landing/SpaceSketch";

// First-visit walkthrough for the website (not the desktop app). Remembered with a cookie for a year.
const COOKIE = "h01_onboarded";
const STEPS: { t: string; d: string; icon: SketchKind }[] = [
  { t: "Welcome to HEALTH-01", d: "Each crew member is compared with their own normal. Changes show up here first.", icon: "astronaut" },
  { t: "Monitoring", d: "Mission overview, each astronaut's dashboard, exercise and NASA hazards.", icon: "planet" },
  { t: "AI", d: "Health insights, the assistant and the models. Every result shows its evidence.", icon: "satellite" },
  { t: "Phones", d: "Open the app on a phone, enter this address, then assign it under Devices.", icon: "rocket" },
  { t: "Not a doctor", d: "A research prototype. The flight surgeon decides.", icon: "moon" },
];

function seen(): boolean {
  return document.cookie.split("; ").some((c) => c.startsWith(COOKIE + "="));
}

export default function Onboarding() {
  const desktop = Boolean((window as unknown as { health01?: { isDesktop?: boolean } }).health01?.isDesktop);
  const [open, setOpen] = useState(false);
  const [i, setI] = useState(0);
  useEffect(() => { if (!desktop && !seen()) setOpen(true); }, [desktop]);
  if (!open) return null;
  const done = () => {
    document.cookie = `${COOKIE}=1; max-age=${60 * 60 * 24 * 365}; path=/; SameSite=Lax`;
    setOpen(false);
  };
  const s = STEPS[i];
  return (
    <div className="ob-backdrop" role="dialog" aria-modal="true" aria-labelledby="ob-title">
      <div className="ob card">
        <SpaceSketch kind={s.icon} className="ob-icon" />
        <h2 id="ob-title">{s.t}</h2>
        <p>{s.d}</p>
        <div className="ob-dots">{STEPS.map((_, k) => <span key={k} className={k === i ? "on" : ""} />)}</div>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <button className="btn ghost" onClick={done}>Skip</button>
          <div className="row">
            {i > 0 && <button className="btn" onClick={() => setI(i - 1)}>Back</button>}
            {i < STEPS.length - 1
              ? <button className="btn primary" onClick={() => setI(i + 1)}>Next</button>
              : <button className="btn primary" onClick={done}>Start</button>}
          </div>
        </div>
      </div>
    </div>
  );
}
