import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import Avatar from "../components/Avatar";
import { Badge, Card, DataClassBadge, Loading } from "../components/ui";
import { useApi } from "../hooks";

type Member = { id: string; callsign: string; name: string; role: string; data_class: string; login: string | null;
  measurements: number; last_data: string | null; open_alerts: number };
type Passcode = { id: number; label: string; created_by: string; created_at: string | null; last_used: string | null };

const ago = (iso: string | null) => {
  if (!iso) return "no data";
  const h = (Date.now() - new Date(iso).getTime()) / 36e5;
  return h < 1 ? "just now" : h < 48 ? `${Math.round(h)} h ago` : `${Math.round(h / 24)} d ago`;
};

/** Mission Control (admin): crew cards and extra sign-in passcodes. */
export default function Crew() {
  const crew = useApi<{ crew: Member[] }>("/admin/crew");
  const pcs = useApi<{ passcodes: Passcode[] }>("/admin/passcodes");
  return (
    <>
      <div className="page-head"><h1>Crew</h1></div>
      {!crew.data ? <Loading /> : (
        <div className="crew-grid">
          {crew.data.crew.map((m) => <CrewCard key={m.id} m={m} onSaved={crew.reload} />)}
        </div>
      )}
      <Passcodes list={pcs.data?.passcodes ?? null} reload={pcs.reload} />
    </>
  );
}

function CrewCard({ m, onSaved }: { m: Member; onSaved: () => void }) {
  const [edit, setEdit] = useState(false);
  const [name, setName] = useState(m.name);
  const [role, setRole] = useState(m.role);
  const [pass, setPass] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    setErr(null);
    try {
      await api(`/admin/crew/${m.id}`, { method: "PUT", body: { name, role, ...(pass ? { passcode: pass } : {}) } });
      setEdit(false); setPass(""); onSaved();
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <div className="card crew-card">
      <Avatar id={m.id} size={96} title={m.name} />
      {!edit ? (
        <>
          <h2>{m.name}</h2>
          <div className="small muted">{m.role}</div>
          <div className="row" style={{ gap: 6, justifyContent: "center", flexWrap: "wrap" }}>
            {m.login && <Badge kind="neutral">@{m.login}</Badge>}
            <DataClassBadge value={m.data_class} />
            {m.open_alerts > 0 && <Badge kind="caution">{m.open_alerts} alerts</Badge>}
          </div>
          <div className="small faint">{m.measurements.toLocaleString()} readings · {ago(m.last_data)}</div>
          <div className="row" style={{ gap: 6, justifyContent: "center" }}>
            <Link className="btn ghost" to={`/intelligence?a=${m.id}`}>Insights</Link>
            <button className="btn" onClick={() => setEdit(true)}>Edit</button>
          </div>
        </>
      ) : (
        <div className="col" style={{ gap: 8, width: "100%" }}>
          <label className="field">Name<input className="input" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="field">Role<input className="input" value={role} onChange={(e) => setRole(e.target.value)} /></label>
          {m.login && <label className="field">New passcode<input className="input" type="password" value={pass} placeholder="unchanged" onChange={(e) => setPass(e.target.value)} /></label>}
          {err && <div className="err small">{err}</div>}
          <div className="row" style={{ gap: 6 }}>
            <button className="btn primary" onClick={save} disabled={!!pass && pass.length < 6}>Save</button>
            <button className="btn ghost" onClick={() => { setEdit(false); setName(m.name); setRole(m.role); setPass(""); }}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}

function Passcodes({ list, reload }: { list: Passcode[] | null; reload: () => void }) {
  const [label, setLabel] = useState("");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const add = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null);
    try { await api("/admin/passcodes", { body: { label, passcode: pass } }); setLabel(""); setPass(""); reload(); }
    catch (x: any) { setErr(x.message); }
  };
  const del = async (id: number) => { await api(`/admin/passcodes/${id}`, { method: "DELETE" }); reload(); };
  return (
    <Card title="Mission Control passcodes" className="crew-pass">
      <p className="small muted" style={{ marginTop: 0 }}>Extra passcodes that sign in as <span className="mono">mission-control</span>.</p>
      <form className="row" style={{ gap: 8, flexWrap: "wrap" }} onSubmit={add}>
        <input className="input" placeholder="Label (e.g. Judges)" value={label} onChange={(e) => setLabel(e.target.value)} style={{ flex: "1 1 160px" }} />
        <input className="input" type="password" placeholder="Passcode (6+)" value={pass} onChange={(e) => setPass(e.target.value)} style={{ flex: "1 1 160px" }} />
        <button className="btn primary" disabled={!label || pass.length < 6}>Add</button>
      </form>
      {err && <div className="err small">{err}</div>}
      {list && list.length > 0 && (
        <table className="tbl" style={{ marginTop: 12 }}>
          <thead><tr><th>Label</th><th>Added</th><th>Last used</th><th /></tr></thead>
          <tbody>
            {list.map((p) => (
              <tr key={p.id}>
                <td><b>{p.label}</b> <span className="small faint">by {p.created_by}</span></td>
                <td className="small">{p.created_at ? new Date(p.created_at).toLocaleDateString() : "–"}</td>
                <td className="small">{p.last_used ? new Date(p.last_used).toLocaleString() : "never"}</td>
                <td style={{ textAlign: "right" }}><button className="btn danger" onClick={() => del(p.id)}>Remove</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}
