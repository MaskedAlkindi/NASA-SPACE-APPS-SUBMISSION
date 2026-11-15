import { useSearchParams } from "react-router-dom";
import { APP_NAME } from "../config";
import { SpaceSketch } from "../landing/SpaceSketch";
import Research from "./Research";
import Risks from "./Risks";

const TABS = [["hazards", "NASA hazards & risks"], ["research", "NASA research"], ["about", "About"]] as const;

export default function Settings() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "hazards";
  return (
    <>
      <div className="page-head"><h1>Settings</h1></div>
      <div className="tabs" role="tablist">
        {TABS.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "on" : ""}
            onClick={() => setParams({ tab: id })}>{label}</button>
        ))}
      </div>
      {tab === "hazards" && <Risks />}
      {tab === "research" && <Research />}
      {tab === "about" && (
        <div className="card about">
          <img src="/logo.png" alt="Team Amerat 01 logo" />
          <div>
            <h2>{APP_NAME}</h2>
            <p className="about-team">Team <b>Amerat-01</b></p>
            <p>Made by <b>Hajid Alkindi</b></p>
            <p className="small muted">NASA Space Apps Challenge 2026 · Al Amerat, Oman</p>
            <p className="row" style={{ gap: 14, flexWrap: "wrap" }}>
              <a href="https://hajidalkindi.com" target="_blank" rel="noreferrer">HajidAlkindi.com ↗</a>
              <a href="https://www.linkedin.com/in/hajidalkindi/" target="_blank" rel="noreferrer">LinkedIn ↗</a>
              <a href="https://www.instagram.com/starlitoman/" target="_blank" rel="noreferrer">Instagram @starlitoman ↗</a>
            </p>
            <p className="small muted">@starlitoman: astronomy, every picture taken in the skies of Al Amerat. Credits: Mohmmed Alwahabi, fellow Ameratian.</p>
            <p className="small faint">Research prototype. Not a medical device.</p>
          </div>
          <SpaceSketch kind="rocket" className="about-doodle" />
        </div>
      )}
    </>
  );
}
