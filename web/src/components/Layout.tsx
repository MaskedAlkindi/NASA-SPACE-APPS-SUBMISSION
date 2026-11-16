import { useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useChatActivity, useElapsed } from "../assistantChat";
import { useAuth } from "../auth";
import { useApi, useLive } from "../hooks";
import { Badge } from "./ui";
import Onboarding from "./Onboarding";
import StationClock from "./StationClock";
import { APP_NAME, DESKTOP_APP_URL, STATIC_DEMO, TEAM_NAME, TEAM_NUMBER } from "../config";

const I = (d: string) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>;
type NavItem = [string, string, ReactNode];
const NAV: [string, NavItem[]][] = [
  ["Admin", [
    ["/crew", "Crew", I("M9 11a4 4 0 100-8 4 4 0 000 8zM2 21v-1a6 6 0 0112 0v1M17 11a3 3 0 100-6M22 21v-1a5 5 0 00-4-4.9")],
  ]],
  ["Monitoring", [
    ["/", "Overview", I("M3 11l9-7 9 7v9a1 1 0 01-1 1h-5v-6h-6v6H4a1 1 0 01-1-1z")],
    ["/dashboard", "Astronaut", I("M3 12h4l3-8 4 16 3-8h4")],
    ["/exercise", "Exercise", I("M12 3a2 2 0 110 4 2 2 0 010-4zM8 21l2-6 2-2 2 2 2 6M9 10l3 2 3-2")],
    ["/nutrition", "Nutrition", I("M4 14h16M6 14a6 6 0 0012 0M12 4v6M9 7h6")],
  ]],
  ["AI", [
    ["/intelligence", "Insights", I("M12 3a6 6 0 016 6c0 2.5-1.5 4-2.5 5S14 16 14 18h-4c0-2-.5-3-1.5-4S6 11.5 6 9a6 6 0 016-6zM10 21h4")],
    ["/assistant", "Assistant", I("M4 5h16v11H8l-4 4z")],
    ["/ai-models", "Models", I("M4 7h16M4 12h16M4 17h10M18 15l2 2-2 2")],
    ["/fine-tuning", "Fine-tuning", I("M4 20h16M7 16V9m5 7V4m5 12v-5")],
  ]],
  ["Connect", [
    ["/devices", "Devices", I("M8 2h8a2 2 0 012 2v16a2 2 0 01-2 2H8a2 2 0 01-2-2V4a2 2 0 012-2zM11 18h2")],
    ["/habitat", "Habitat sensors", I("M4 20V10l8-6 8 6v10M9 20v-5h6v5M12 9.5h.01")],
    ["/servers", "Servers", I("M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01")],
    ["/modules", "Modules", I("M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z")],
  ]],
  ["Tools", [
    ["/simulator", "Simulator", I("M5 3l14 9-14 9z")],
  ]],
];
const SETTINGS: NavItem = ["/settings", "Settings", I("M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z")];
export const canSeeDashboard = (_role?: string) => true;
// Mission Control is the admin.
export const isAdmin = (role?: string) => role === "mission_control";

export default function Layout() {
  const activity = useChatActivity();
  const elapsed = useElapsed(activity.startedAt, activity.busy);
  const onAssistant = useLocation().pathname === "/assistant";
  const { user, switchUser } = useAuth();
  const navigate = useNavigate();
  const accounts = useApi<{ demo_mode: boolean; accounts: { username: string; display_name: string; role: string; astronaut_id: string | null }[] }>("/auth/demo-accounts");
  const [params] = useSearchParams();
  const chooseUser = async (username: string) => {
    if (!username || username === user?.username) return;
    try {
      const next = await switchUser(username);
      navigate(next.astronaut_id ? `/dashboard?a=${encodeURIComponent(next.astronaut_id)}` : "/");
    } catch { /* stay on the current user */ }
  };
  const health = useApi<any>("/health");
  const astronaut = params.get("a");
  const keepCrew = (to: string) => (astronaut && !to.includes("?") ? `${to}?a=${encodeURIComponent(astronaut)}` : to);
  const [liveCount, setLiveCount] = useState(0);
  const connected = useLive((e) => { if (e.type === "measurements") setLiveCount((c) => c + e.items.length); });
  const h = health.data;
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-logo" src="/logo.png" alt={`Team ${TEAM_NAME} ${TEAM_NUMBER} logo`} />
          <div><b>{APP_NAME}</b><small className="team">Team {TEAM_NAME} <em>{TEAM_NUMBER}</em></small></div>
        </div>
        <nav className="nav">
          {NAV.map(([group, items]) => {
            const shown = items.filter(([to]) => (to !== "/dashboard" || canSeeDashboard(user?.role)) && (to !== "/crew" || isAdmin(user?.role)));
            if (!shown.length) return null;
            return (
              <div key={group} className="nav-group">
                <span className="nav-label">{group}</span>
                {shown.map(([to, label, icon]) => (
                  <NavLink key={to} to={keepCrew(to)} end={to === "/"} title={label} className={({ isActive }) => (isActive ? "active" : "")}>
                    {icon}<span>{label}</span>
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <NavLink to={keepCrew(SETTINGS[0])} title={SETTINGS[1]} className={({ isActive }) => `nav-settings ${isActive ? "active" : ""}`}>
          {SETTINGS[2]}<span>{SETTINGS[1]}</span>
        </NavLink>
        <div className="side-foot"><a href="/">← Home</a></div>
      </aside>
      <div className="main">
        <header className="topbar">
          {STATIC_DEMO ? (
            <span className="row small">
              <Badge kind="info">web demo</Badge>
              <a href={DESKTOP_APP_URL} target="_blank" rel="noreferrer">Get the desktop app for AI</a>
            </span>
          ) : <>
          <span className="row small">
            <span className={`dot ${h?.database ? "on" : h ? "off" : ""}`} /> API {h ? h.status : "…"}
          </span>
          <span className="row small"><span className={`dot ${connected ? "on" : "warn"}`} /> Live feed {connected ? "connected" : "connecting"}{liveCount > 0 && <span className="faint">· {liveCount} readings</span>}</span>
          <span className="row small">Assistant: <Badge kind={h && h.assistant_mode !== "offline" ? "ok" : "neutral"}>{h ? (h.assistant_mode === "offline" ? "offline explainer" : h.assistant_mode === "ollama" ? "the fine tuned version" : `${h.assistant_mode} · ${h.assistant_model}`) : "…"}</Badge></span>
          </>}
          <StationClock />
          <div className="spacer" />
          {user && (
            <span className="row small">
              {accounts.data?.demo_mode ? (
                <label className="row small">view as
                  <select className="input user-switch" aria-label="Switch user" value={user.username} onChange={(e) => { void chooseUser(e.target.value); }}>
                    {accounts.data.accounts.map((a) => (
                      <option key={a.username} value={a.username}>{a.display_name || a.username}</option>
                    ))}
                  </select>
                </label>
              ) : <span className="muted">{user.display_name}</span>}
              <Badge kind="info">{user.role.replace("_", " ")}</Badge>
            </span>
          )}
        </header>
        {activity.busy && !onAssistant && (
          <NavLink to={activity.href} className="chat-banner">
            <span className="spin" aria-hidden />
            <span>{activity.local ? "The fine tuned version is answering" : "The assistant is answering"} · {elapsed}s</span>
            <span className="faint">You can change pages. The answer stays in the assistant.</span>
          </NavLink>
        )}
        <main className="content"><Outlet /></main>
        <Onboarding />
      </div>
    </div>
  );
}
