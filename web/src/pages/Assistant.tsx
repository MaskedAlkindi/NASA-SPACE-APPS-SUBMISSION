import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { sendChat, useAssistantChat, useElapsed } from "../assistantChat";
import { isCrewWide, useAuth } from "../auth";
import { AstronautPicker, useSelectedAstronaut } from "../components/AstronautPicker";
import { Badge, Card, Markdown } from "../components/ui";
import { useApi } from "../hooks";

interface Provider { id: string; label: string; local: boolean; available: boolean; detail: string; models: string[]; default_model: string | null }
const SUGGESTIONS = ["How am I doing today?", "Why is my heart rate unusual?", "Has my sleep been getting worse?",
  "What should I check next?", "Explain this health alert simply.", "What does NASA research say about this risk?"];
const CHOICE_KEY = "hmt.assistant.choice";

function modelName(provider?: string, model?: string) {
  if (!provider || provider === "offline") return "offline explainer";
  if (provider === "ollama") return "the fine tuned version";
  return model ? `${provider} · ${model}` : provider;
}

function modeLabel(meta: any) {
  return modelName(meta.mode === "offline" ? "offline" : meta.provider, meta.model);
}

export default function Assistant() {
  const { user } = useAuth();
  const { crew, selected, select, current } = useSelectedAstronaut();
  const status = useApi<any>("/assistant/status");
  const chat = useAssistantChat(user?.username ?? "", selected);
  const msgs = chat.msgs;
  const busy = chat.busy;
  const [input, setInput] = useState("");
  const [choice, setChoice] = useState<string>(() => { try { return localStorage.getItem(CHOICE_KEY) ?? "default"; } catch { return "default"; } });
  const [note, setNote] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setInput(""); }, [selected]);
  useEffect(() => { logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" }); }, [msgs, busy]);
  useEffect(() => { try { localStorage.setItem(CHOICE_KEY, choice); } catch { /* ignore */ } }, [choice]);

  const providers: Provider[] = status.data?.providers ?? [];
  // A remembered choice that is no longer available falls back to the server default.
  useEffect(() => {
    if (!status.data || choice === "default") return;
    const [pid, model] = choice.split("|");
    const p = providers.find((x) => x.id === pid);
    if (!p?.available || (model && !p.models.includes(model))) setChoice("default");
  }, [status.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const parsed = choice === "default" ? { provider: "default", model: undefined } : { provider: choice.split("|")[0], model: choice.split("|")[1] || undefined };
  const active = status.data?.active;

  const send = (text: string) => {
    if (!text.trim() || !selected || !user || busy) return;
    const local = parsed.provider === "ollama" || (parsed.provider === "default" && active?.provider === "ollama");
    setInput("");
    void sendChat(user.username, selected, text, parsed, local).then(() => status.reload());
  };

  const saveDefault = async () => {
    if (parsed.provider === "default") return;
    try {
      await api("/assistant/settings", { method: "PUT", body: { provider: parsed.provider, model: parsed.model ?? null } });
      setNote("Saved as the default for all users."); setChoice("default"); status.reload();
    } catch (e: any) { setNote(e.message); }
  };

  const st = status.data;
  const elapsed = useElapsed(chat.startedAt, busy);
  const waiting = busy && (chat.local
    ? `The fine tuned version is answering · ${elapsed}s. You can leave this page.`
    : `Answering · ${elapsed}s. You can leave this page.`);
  return (
    <>
      <div className="page-head">
        <div><h1>Health assistant{current ? ` · ${current.callsign}` : ""}</h1>
          <p>Ask about the crew's data in plain language. Answers use the recorded measurements, model results and NASA research.</p></div>
        <div className="spacer" />
        <AstronautPicker crew={crew} selected={selected} onSelect={select} />
      </div>
      <div className="grid g3">
        <Card className="span2">
          <div className="chat">
            <div className="row" style={{ marginBottom: 10 }}>
              <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                <span>Model</span>
                <select className="input" value={choice} onChange={(e) => { setChoice(e.target.value); setNote(null); }} aria-label="Assistant model">
                  <option value="default">Server default{active ? `: ${modelName(active.provider, active.model)}` : ""}</option>
                  {providers.map((p) => (
                    <optgroup key={p.id} label={`${p.id === "ollama" ? "the fine tuned version" : p.label}${p.available ? "" : ` (unavailable: ${p.detail})`}`}>
                      {p.available
                        ? p.models.map((m) => <option key={m} value={p.id === "offline" ? "offline" : `${p.id}|${m}`}>{p.id === "offline" ? "Offline explainer (no LLM)" : p.id === "ollama" ? (p.models.length > 1 ? `the fine tuned version · ${m}` : "the fine tuned version") : m}</option>)
                        : <option disabled value={`${p.id}|`}>not available</option>}
                    </optgroup>
                  ))}
                </select>
              </label>
              {isCrewWide(user) && parsed.provider !== "default" && <button className="btn ghost" onClick={saveDefault}>Save as default</button>}
              {note && <span className="small muted">{note}</span>}
            </div>
            <div className="chat-log" ref={logRef}>
              {msgs.length === 0 && (
                <div className="col" style={{ alignItems: "center", padding: "30px 10px", gap: 14 }}>
                  <div className="muted">Ask a question about {current?.callsign ?? "this astronaut"}'s health data.</div>
                  <div className="chips" style={{ justifyContent: "center" }}>{SUGGESTIONS.map((s) => <span key={s} className="chip" onClick={() => send(s)}>{s}</span>)}</div>
                </div>
              )}
              {msgs.map((m, i) => (
                <div key={i} className={`msg ${m.role}`}>
                  {m.role === "assistant" ? <Markdown text={m.content} /> : m.content}
                  {m.meta && (
                    <div className="meta">
                      <Badge kind={m.meta.mode === "offline" ? "neutral" : "ok"}>{modeLabel(m.meta)}</Badge>
                      {m.meta.fallback_reason && <span>fallback: {m.meta.fallback_reason}</span>}
                      {m.meta.usage && <span>{m.meta.usage.prompt_tokens}+{m.meta.usage.completion_tokens} tokens</span>}
                      {m.meta.context_summary && <span>context: {m.meta.context_summary.alerts} alerts · {m.meta.context_summary.research_passages} research passages · data as of {m.meta.context_summary.as_of}</span>}
                      {m.meta.citations?.map((c: any) => <a key={c.ref} href={c.source} target="_blank" rel="noreferrer" className="badge research">{c.ref}: {c.title.slice(0, 48)}{c.title.length > 48 ? "…" : ""}</a>)}
                    </div>
                  )}
                </div>
              ))}
              {busy && (
                <div className="msg assistant pending" role="status" aria-live="polite">
                  <span className="spin" aria-hidden />
                  <div>{waiting}</div>
                </div>
              )}
            </div>
            {msgs.length > 0 && <div className="chips" style={{ margin: "6px 0 10px" }}>{SUGGESTIONS.slice(0, 4).map((s) => <span key={s} className="chip" onClick={() => send(s)}>{s}</span>)}</div>}
            <form className="row" onSubmit={(e) => { e.preventDefault(); send(input); }}>
              <input className="input" style={{ flex: 1 }} value={input} maxLength={1000} placeholder="Ask about heart rate, sleep, fatigue, alerts, NASA research…" onChange={(e) => setInput(e.target.value)} />
              <button className="btn primary" disabled={busy || !input.trim()}>{busy ? "Answering…" : "Send"}</button>
            </form>
          </div>
        </Card>
        <div className="col" style={{ gap: 16 }}>
          <Card title="Providers" extra={<button className="btn ghost small" style={{ padding: "2px 10px" }} onClick={status.reload}>Refresh</button>}>
            <div className="col" style={{ gap: 8 }}>
              {providers.map((p) => (
                <div key={p.id} className="tile" style={{ padding: "8px 12px" }}>
                  <div className="row"><span className={`dot ${p.available ? "on" : "off"}`} /><b>{p.id === "ollama" ? "the fine tuned version" : p.label}</b>{p.local && <Badge kind="real">on-device</Badge>}</div>
                  <div className="small muted">{p.detail}</div>
                  {p.available && p.id !== "offline" && <div className="small faint mono">{p.id === "ollama" ? "the fine tuned version" : p.models.join(" · ")}</div>}
                </div>
              ))}
            </div>
            {st && <div className="small faint" style={{ marginTop: 8 }}>Active default: <b>{modelName(active?.provider, active?.model)}</b> (set by {active?.selected_by})</div>}
          </Card>
          <Card title="Limits">
            {st && (
              <table className="tbl"><tbody>
                <tr><td className="muted">Max output tokens</td><td className="mono">{st.max_output_tokens}</td></tr>
                <tr><td className="muted">History sent</td><td className="mono">last {st.history_limit} turns</td></tr>
                <tr><td className="muted">Rate limit</td><td className="mono">{st.rate_limit_per_minute}/min per user</td></tr>
                <tr><td className="muted">OpenAI daily budget</td><td className="mono">{st.usage_today.requests}/{st.daily_budget.requests || "∞"} req · {st.usage_today.tokens}/{st.daily_budget.tokens || "∞"} tok</td></tr>
              </tbody></table>
            )}
          </Card>
          <Card title="Safety rules">
            <ul className="small muted" style={{ paddingLeft: 18, margin: 0 }}>
              <li>Same grounded context and safety prompt for every provider; unverifiable numbers are flagged.</li>
              <li>Local Ollama models keep all health data on this machine.</li>
              <li>No diagnoses or treatment instructions; warnings or severe symptoms → contact the flight surgeon.</li>
              <li>If a provider fails or times out, the deterministic offline explainer answers instead.</li>
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
