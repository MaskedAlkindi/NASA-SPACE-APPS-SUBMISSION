import { useMemo, useState } from "react";
import { useAuth } from "../auth";
import { useApi } from "../hooks";
import Avatar from "../components/Avatar";
import { APP_NAME, TEAM_NAME, TEAM_NUMBER } from "../config";

type Account = { username: string; display_name?: string; role: string; astronaut_id: string | null };

export default function Login() {
  const { login } = useAuth();
  const demo = useApi<{ demo_mode: boolean; accounts: Account[] }>("/auth/demo-accounts");
  const [username, setUsername] = useState("");
  const [q, setQ] = useState("");
  const [passcode, setPasscode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const accounts = demo.data?.demo_mode ? demo.data.accounts : null;
  const shown = useMemo(() => {
    const s = q.trim().toLowerCase();
    return (accounts ?? []).filter((a) => !s || a.username.includes(s) || (a.display_name ?? "").toLowerCase().includes(s));
  }, [accounts, q]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try { await login(username, passcode); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };

  return (
    <div className="login-wrap">
      <form className="login col" style={{ gap: 14 }} onSubmit={submit}>
        <div className="col" style={{ alignItems: "center", gap: 4 }}>
          <img className="login-logo" src="/logo.png" alt={`Team ${TEAM_NAME} ${TEAM_NUMBER} logo`} />
          <h1>{APP_NAME}</h1>
        </div>
        <div className="card col" style={{ gap: 10 }}>
          {accounts ? (
            <>
              <input className="input" placeholder="Search username" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search username" />
              <div className="acct-list" role="listbox" aria-label="Usernames">
                {shown.map((a) => (
                  <button type="button" key={a.username} role="option" aria-selected={username === a.username}
                    className={`acct ${username === a.username ? "on" : ""}`} onClick={() => setUsername(a.username)}>
                    {a.astronaut_id ? <Avatar id={a.astronaut_id} size={34} /> : <span className="acct-ic">{a.role === "mission_control" ? "🛰" : "⚕"}</span>}
                    <span className="mono">{a.username}</span>
                  </button>
                ))}
                {shown.length === 0 && <div className="small faint">No match</div>}
              </div>
            </>
          ) : (
            <input className="input" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
          )}
          <input className="input" type="password" placeholder="Passcode" value={passcode} onChange={(e) => setPasscode(e.target.value)} autoComplete="current-password" />
          {err && <div className="err small">{err}</div>}
          <button className="btn primary" disabled={busy || !passcode || !username}>{busy ? "Signing in…" : username ? `Sign in as ${username}` : "Pick a username"}</button>
        </div>
      </form>
    </div>
  );
}
