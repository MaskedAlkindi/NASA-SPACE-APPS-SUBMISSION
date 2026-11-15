import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Badge, Card, Loading } from "../components/ui";
import { useApi } from "../hooks";

type Device = { device_uuid: string; platform: string; model: string; app_version: string; label: string; astronaut_id: string | null;
  callsign: string | null; status: "pending" | "assigned" | "revoked"; registered_at: string; last_seen: string | null; last_upload: string | null; uploads: number };

const ago = (iso: string | null) => {
  if (!iso) return "never";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  return s < 90 ? "just now" : s < 5400 ? `${Math.round(s / 60)} min ago` : s < 129600 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} d ago`;
};

export default function Devices() {
  const { user } = useAuth();
  const operator = user?.role !== "astronaut";
  const devices = useApi<{ devices: Device[] }>(operator ? "/devices" : null);
  const crew = useApi<{ astronauts: { id: string; callsign: string; name: string }[] }>("/astronauts");
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  async function act(uuid: string, fn: () => Promise<unknown>) {
    setBusy(uuid); setErr("");
    try { await fn(); devices.reload(); } catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } finally { setBusy(""); }
  }
  const list = devices.data?.devices ?? [];
  const pending = list.filter((d) => d.status === "pending");

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Devices</h1>
          <p>Crew phones that collect wearable data and count exercise reps. Each phone shows its device ID in the app; match it here and assign the phone to a crew member. Uploads are then credited to that person only.</p>
        </div>
      </div>
      {!operator && <div className="banner"><b>Operators only.</b> Ask mission control to assign your phone.</div>}
      {operator && (
        <>
          <div className="grid g3">
            <div className="tile"><div className="label">Waiting for assignment</div><div className="value">{pending.length}</div></div>
            <div className="tile"><div className="label">Assigned phones</div><div className="value">{list.filter((d) => d.status === "assigned").length}</div></div>
            <div className="tile"><div className="label">Server address for phones</div><div className="value mono" style={{ fontSize: 15 }}>{window.location.origin}</div>
              <div className="sub">Enter this in the phone app (use the computer's network IP, not localhost, on a real phone).</div></div>
          </div>
          {err && <div className="err">{err}</div>}
          <Card title="Phones" extra={<button className="btn ghost" onClick={() => devices.reload()}>Refresh</button>}>
            {devices.loading && !devices.data && <Loading what="Devices" />}
            {devices.data && list.length === 0 && <div className="empty">No phones yet. Open the HEALTH-01 app on a phone, enter this server's address and tap Connect.</div>}
            {list.length > 0 && (
              <div className="table-wrap">
                <table className="tbl">
                  <thead><tr><th>Device ID</th><th>Phone</th><th>Status</th><th>Assigned to</th><th>Last upload</th><th></th></tr></thead>
                  <tbody>
                    {list.map((d) => (
                      <tr key={d.device_uuid}>
                        <td><span className="mono" title={d.device_uuid}>{d.device_uuid.slice(0, 8)}</span><span className="faint mono">…{d.device_uuid.slice(-4)}</span>
                          {d.label && <div className="small muted">{d.label}</div>}</td>
                        <td>{d.platform === "ios" ? "iPhone" : d.platform === "android" ? "Android" : d.platform}<div className="small faint">{d.model} {d.app_version && `· v${d.app_version}`}</div></td>
                        <td><Badge kind={d.status === "assigned" ? "ok" : d.status === "pending" ? "caution" : "neutral"}>{d.status}</Badge>
                          <div className="small faint">seen {ago(d.last_seen)}</div></td>
                        <td>
                          {d.status === "revoked" ? <span className="faint">—</span> : (
                            <select className="input" disabled={busy === d.device_uuid} value={d.astronaut_id ?? ""}
                              onChange={(e) => act(d.device_uuid, () => api(`/devices/${d.device_uuid}`, { method: "PUT", body: { astronaut_id: e.target.value || null } }))}>
                              <option value="">— choose crew member —</option>
                              {(crew.data?.astronauts ?? []).map((a) => <option key={a.id} value={a.id}>{a.callsign} ({a.id})</option>)}
                            </select>
                          )}
                        </td>
                        <td>{ago(d.last_upload)}<div className="small faint">{d.uploads} upload{d.uploads === 1 ? "" : "s"}</div></td>
                        <td className="row">
                          <button className="btn ghost" disabled={busy === d.device_uuid} onClick={() => {
                            const label = prompt("Name for this phone", d.label || "");
                            if (label !== null) act(d.device_uuid, () => api(`/devices/${d.device_uuid}`, { method: "PUT", body: { label } }));
                          }}>Rename</button>
                          {d.status === "revoked"
                            ? <button className="btn ghost" onClick={() => act(d.device_uuid, () => api(`/devices/${d.device_uuid}/reset`, { method: "POST" }))}>Allow again</button>
                            : <button className="btn ghost danger" onClick={() => confirm("Revoke this phone? It will stop uploading.") && act(d.device_uuid, () => api(`/devices/${d.device_uuid}/revoke`, { method: "POST" }))}>Revoke</button>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
          <Card title="How pairing works">
            <ol className="small" style={{ margin: 0, paddingLeft: 18 }}>
              <li>On the phone, open HEALTH-01, type this server's address and tap <b>Connect</b>. The app shows its device ID.</li>
              <li>The phone appears above as <b>pending</b>. Check the first characters of the ID match the phone screen.</li>
              <li>Choose the crew member. The phone's screen changes to "Connected as …" and starts uploading.</li>
              <li>The phone never picks whose data it sends; the server uses this assignment. Revoke a lost phone here.</li>
            </ol>
          </Card>
        </>
      )}
    </>
  );
}
