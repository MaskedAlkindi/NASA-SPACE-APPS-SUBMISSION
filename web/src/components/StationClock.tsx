import { useEffect, useState } from "react";
import { api } from "../api";
import { isCrewWide, useAuth } from "../auth";

type Sim = { running?: boolean; sim_time?: string; discardable?: boolean; server_time?: string; scenario?: string };

const fmt = (d: Date) => d.toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "UTC", hour12: false });

/** Station clock in the top bar. Shows simulated time while a simulation runs, and offers to discard it afterwards. */
export default function StationClock() {
  const { user } = useAuth();
  const [now, setNow] = useState(() => new Date());
  const [sim, setSim] = useState<Sim>({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t); }, []);
  useEffect(() => {
    let alive = true;
    const poll = () => api<Sim>("/simulation/status").then((s) => alive && setSim(s)).catch(() => {});
    poll();
    const t = setInterval(poll, 2000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  async function discard() {
    setBusy(true);
    try { await api("/simulation/discard", { method: "POST" }); setSim({}); window.location.reload(); }
    finally { setBusy(false); }
  }

  const simTime = sim.sim_time ? new Date(sim.sim_time) : null;
  if (sim.running && simTime) {
    return (
      <span className="clock sim" title={`Simulation: ${sim.scenario ?? ""}`}>
        <span className="dot warn" /> SIM <b className="mono">{fmt(simTime)}</b> UTC
      </span>
    );
  }
  return (
    <span className="clock">
      {sim.discardable && simTime
        ? <><span className="dot warn" /> SIM ended <b className="mono">{fmt(simTime)}</b></>
        : <>Station time <b className="mono">{fmt(now)}</b> UTC</>}
      {sim.discardable && user && isCrewWide(user) && (
        <button className="btn danger" style={{ padding: "3px 10px" }} disabled={busy} onClick={discard}>
          {busy ? "Discarding…" : "Discard simulation"}
        </button>
      )}
    </span>
  );
}
