import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Badge, Card, Loading, Markdown } from "../components/ui";
import { useApi } from "../hooks";

type Base = { id: string; name: string; hf_repo: string; ollama: string; params_b: number; licence: string; qlora_vram_gb: number; notes: string };
type Run = { run_id: string; version: string; status: string; created_at: string; dataset: string; method: string; base_model: Base;
  metrics?: Record<string, any>; eval?: { metrics: Record<string, any> }; deployed?: { ollama_name: string }; error?: string;
  progress?: { step: number; max_steps: number; elapsed_s: number; log: Record<string, number>[] } };
type Overview = {
  base_models: { default: string; models: Base[] };
  sources: { id: string; title: string; publisher: string; url: string; licence: string; relevance: string; collector: string | null; processing: string }[];
  corpus: { generated_at: string; files: Record<string, { passages: number; sha256: string }> } | null;
  datasets: { name: string; built_at: string; counts: Record<string, number>; by_source: Record<string, number>; uploaded?: boolean; generation: string }[];
  runs: Run[]; evals: Record<string, any>[];
  trainer: { configured: boolean; reachable?: boolean; url: string | null; gpu?: { name: string; vram_gb: number } | null; busy?: boolean; error?: string };
  tasks: { id: string; kind: string; status: string; error?: string; result?: any; progress?: any }[];
};
const TABS = ["Overview", "Sources & data", "Train", "Evaluate", "Models"] as const;
const DEFAULT_HP = { epochs: 2, learning_rate: 0.0002, lora_r: 16, lora_alpha: 32, lora_dropout: 0.05, max_seq_len: 1024, batch_size: 1, grad_accum: 8, warmup_ratio: 0.03, max_steps: -1, seed: 42 };

export default function FineTuning() {
  const { user } = useAuth();
  const operator = user?.role !== "astronaut";
  const [tab, setTab] = useState<(typeof TABS)[number]>("Overview");
  const ov = useApi<Overview>("/llm/overview");
  const [msg, setMsg] = useState("");
  const running = (ov.data?.tasks ?? []).some((t) => t.status === "running") || (ov.data?.runs ?? []).some((r) => ["training", "starting"].includes(r.status));
  useEffect(() => { if (!running) return; const t = setInterval(() => ov.reload(), 4000); return () => clearInterval(t); }, [running]);   // eslint-disable-line react-hooks/exhaustive-deps

  async function act(fn: () => Promise<any>, ok: string) {
    setMsg("");
    try { const r = await fn(); setMsg(r?.note || ok); ov.reload(); } catch (e) { setMsg(e instanceof Error ? e.message : "Failed"); }
  }
  const d = ov.data;
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Fine-tuning</h1>
          <p>Build a space-medicine model from documented public sources: collect data, train (QLoRA on a GPU), evaluate against the base model, and deploy to Ollama. Every run gets an automatic run card.</p>
        </div>
      </div>
      <div className="tabs" role="tablist">{TABS.map((t) => <button key={t} className={tab === t ? "on" : ""} onClick={() => setTab(t)}>{t}</button>)}</div>
      {msg && <div className="banner">{msg}</div>}
      {ov.loading && !d && <Loading what="Fine-tuning workspace" />}
      {ov.error && <div className="err">{ov.error}</div>}
      {d && tab === "Overview" && <OverviewTab d={d} />}
      {d && tab === "Sources & data" && <DataTab d={d} operator={operator} act={act} />}
      {d && tab === "Train" && <TrainTab d={d} operator={operator} act={act} />}
      {d && tab === "Evaluate" && <EvalTab d={d} operator={operator} act={act} />}
      {d && tab === "Models" && <ModelsTab operator={operator} />}
    </>
  );
}

function OverviewTab({ d }: { d: Overview }) {
  const passages = Object.values(d.corpus?.files ?? {}).reduce((a, f) => a + f.passages, 0);
  const base = d.evals.find((e) => e.meta?.backend === "ollama");
  return (
    <>
      <div className="grid g4">
        <div className="tile"><div className="label">Corpus passages</div><div className="value">{passages}</div><div className="sub">{Object.keys(d.corpus?.files ?? {}).length} sources, all with provenance</div></div>
        <div className="tile"><div className="label">Datasets</div><div className="value">{d.datasets.length}</div><div className="sub">{d.datasets.map((x) => x.name).join(", ") || "none built"}</div></div>
        <div className="tile"><div className="label">Training runs</div><div className="value">{d.runs.length}</div><div className="sub">{d.runs.filter((r) => r.deployed).length} deployed</div></div>
        <div className="tile"><div className="label">Trainer (GPU)</div><div className="value" style={{ fontSize: 16 }}>{!d.trainer.configured ? "not configured" : d.trainer.reachable ? d.trainer.gpu?.name ?? "no GPU" : "unreachable"}</div>
          <div className="sub">{d.trainer.configured ? d.trainer.url : "Set HMT_LLM_TRAINER_URL"}</div></div>
      </div>
      <Card title="How the pieces fit">
        <ol className="small" style={{ margin: 0, paddingLeft: 18 }}>
          <li><b>Sources</b>: NASA challenge pages and evidence reports, checked NASA quotes, HEALTH-01 model cards, CC BY Europe PMC abstracts. Each has a licence and provenance hash.</li>
          <li><b>Dataset</b>: answers are sentences taken from the sources plus a citation line, abstention examples, and team-written safety examples. No model-written text, so nothing invented enters training.</li>
          <li><b>RAG</b>: the same corpus is searchable, so answers can be grounded in retrieved passages at inference time.</li>
          <li><b>Training</b>: QLoRA adapters on the base model of your choice (default {d.base_models.default}) on the trainer GPU.</li>
          <li><b>Evaluation</b>: held-out passages and safety probes, scored against source text (no AI judge). Compare versions side by side.</li>
          <li><b>Deploy</b>: merge and import into Ollama; the assistant can then use it like any other local model.</li>
        </ol>
      </Card>
      {base && <Card title={`Measured baseline: ${base.label}`}><MetricsTable rows={[base]} /></Card>}
    </>
  );
}

function DataTab({ d, operator, act }: { d: Overview; operator: boolean; act: (fn: () => Promise<any>, ok: string) => void }) {
  const [name, setName] = useState("my-dataset");
  const [licence, setLicence] = useState("");
  const [source, setSource] = useState("");
  const [text, setText] = useState("");
  const [card, setCard] = useState<string | null>(null);
  return (
    <>
      <Card title="Source inventory" extra={operator && <span className="row">
        <button className="btn" onClick={() => act(() => api("/llm/corpus/collect", { body: {} }), "Collecting sources and rebuilding the search index…")}>Re-collect sources</button>
        <button className="btn primary" onClick={() => act(() => api("/llm/datasets/build", { body: { name: "spacemed-v2" } }), "Building spacemed-v2…")}>Rebuild dataset</button>
      </span>}>
        <div className="table-wrap"><table className="tbl">
          <thead><tr><th>Source</th><th>Licence</th><th>Why it matters</th><th>Processing</th><th>Passages</th></tr></thead>
          <tbody>{d.sources.map((s) => {
            const f = Object.entries(d.corpus?.files ?? {}).find(([k]) => k.startsWith(s.id));
            return (
              <tr key={s.id}>
                <td><b>{s.title}</b><div className="small faint">{s.publisher} · <a href={s.url.startsWith("http") ? s.url : undefined} target="_blank" rel="noreferrer">{s.url}</a></div></td>
                <td className="small">{s.licence}</td><td className="small">{s.relevance}</td><td className="small muted">{s.processing}</td>
                <td>{f ? f[1].passages : s.collector ? <span className="faint">not collected</span> : <Badge kind="neutral">needs access</Badge>}</td>
              </tr>
            );
          })}</tbody>
        </table></div>
        {d.corpus && <p className="small faint">Corpus collected {d.corpus.generated_at}. Hashes in data/llm/corpus/PROVENANCE.json.</p>}
      </Card>
      <Card title="Datasets">
        <table className="tbl"><thead><tr><th>Name</th><th>Built</th><th>Train / val / test</th><th>Sources</th><th></th></tr></thead>
          <tbody>{d.datasets.map((x) => (
            <tr key={x.name}><td><b>{x.name}</b> {x.uploaded && <Badge kind="caution">uploaded</Badge>}</td><td className="small">{x.built_at}</td>
              <td className="mono">{x.counts.train} / {x.counts.val} / {x.counts.test}</td>
              <td className="small">{Object.entries(x.by_source).map(([k, v]) => `${k}: ${v}`).join(", ")}</td>
              <td><button className="btn ghost" onClick={async () => setCard(await fetch(`/api/v1/llm/datasets/${x.name}/card`, { headers: { Authorization: `Bearer ${localStorage.getItem("hmt.token")}` } }).then((r) => r.text()))}>Card</button></td></tr>
          ))}</tbody></table>
        {card && <div style={{ marginTop: 12 }}><Markdown text={card} /></div>}
      </Card>
      {operator && (
        <Card title="Upload your own dataset (chat JSONL)">
          <p className="small muted">One line per example: {"{\"messages\": [{\"role\": \"user\", \"content\": \"…\"}, {\"role\": \"assistant\", \"content\": \"…\"}]}"}. The HEALTH-01 system prompt is added if missing. Source and licence are required and go into the dataset card.</p>
          <div className="grid g3">
            <label className="field">Name<input className="input" value={name} onChange={(e) => setName(e.target.value)} /></label>
            <label className="field">Licence<input className="input" value={licence} placeholder="e.g. CC BY 4.0" onChange={(e) => setLicence(e.target.value)} /></label>
            <label className="field">Source<input className="input" value={source} placeholder="URL or description" onChange={(e) => setSource(e.target.value)} /></label>
          </div>
          <label className="field" style={{ marginTop: 8 }}>JSONL file
            <input className="input" type="file" accept=".jsonl,.json,.txt" onChange={async (e) => { const f = e.target.files?.[0]; if (f) setText(await f.text()); }} />
          </label>
          <p className="small faint">{text ? `${text.split("\n").filter(Boolean).length} lines loaded` : "No file chosen"}</p>
          <button className="btn primary" disabled={!text || !licence || !source} onClick={() => act(() => api("/llm/datasets/upload", { body: { name, licence, source, jsonl: text } }), "Dataset uploaded.")}>Upload</button>
        </Card>
      )}
    </>
  );
}

function TrainTab({ d, operator, act }: { d: Overview; operator: boolean; act: (fn: () => Promise<any>, ok: string) => void }) {
  const [base, setBase] = useState(d.base_models.default);
  const [dataset, setDataset] = useState(d.datasets[0]?.name ?? "");
  const [method, setMethod] = useState("qlora");
  const [hp, setHp] = useState<Record<string, number>>(DEFAULT_HP);
  const [notes, setNotes] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const b = d.base_models.models.find((m) => m.id === base);
  return (
    <>
      {operator && (
        <Card title="New training run">
          <div className="grid g4">
            <label className="field">Base model
              <select className="input" value={base} onChange={(e) => setBase(e.target.value)}>{d.base_models.models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select>
            </label>
            <label className="field">Dataset
              <select className="input" value={dataset} onChange={(e) => setDataset(e.target.value)}>{d.datasets.map((x) => <option key={x.name}>{x.name}</option>)}</select>
            </label>
            <label className="field">Method
              <select className="input" value={method} onChange={(e) => setMethod(e.target.value)}><option value="qlora">QLoRA (4-bit base)</option><option value="lora">LoRA (16-bit base)</option></select>
            </label>
            <div className="small muted">{b && <>{b.params_b} B params · {b.licence}<br />≈{b.qlora_vram_gb} GB GPU memory with QLoRA<br />{b.notes}</>}</div>
          </div>
          <div className="grid g4" style={{ marginTop: 10 }}>
            {Object.entries(hp).map(([k, v]) => (
              <label key={k} className="field">{k.replace(/_/g, " ")}<input className="input mono" type="number" step="any" value={v} onChange={(e) => setHp({ ...hp, [k]: Number(e.target.value) })} /></label>
            ))}
          </div>
          <label className="field" style={{ marginTop: 10 }}>Notes (go into the run card)<input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
          <div className="row" style={{ marginTop: 10 }}>
            <button className="btn primary" disabled={!dataset} onClick={() => act(() => api("/llm/runs", { body: { base_model: base, dataset, method, hyperparameters: hp, notes } }), "Run created and sent to the trainer.")}>Start training</button>
            <span className="small faint">{d.trainer.reachable ? `Trainer: ${d.trainer.gpu?.name ?? "no GPU"}${d.trainer.busy ? " (busy)" : ""}` : "No trainer reachable: the run is registered and can be started on a GPU machine."}</span>
          </div>
        </Card>
      )}
      <Card title="Runs and versions">
        {d.runs.length === 0 && <div className="empty">No runs yet.</div>}
        {d.runs.map((r) => {
          const last = r.progress?.log?.filter((l) => l.loss !== undefined).slice(-1)[0];
          return (
            <div key={r.run_id} className="tile" style={{ marginBottom: 8 }}>
              <div className="label"><b className="mono">{r.version}</b>
                <Badge kind={r.status === "failed" ? "warning" : ["trained", "evaluated", "deployed"].includes(r.status) ? "ok" : "caution"}>{r.status}</Badge></div>
              <div className="small">{r.base_model.name} · {r.method.toUpperCase()} · dataset {r.dataset} · {r.run_id}</div>
              {r.progress && <><div className="progress" style={{ margin: "6px 0" }}><div style={{ width: `${Math.min(100, (100 * r.progress.step) / Math.max(1, r.progress.max_steps))}%` }} /></div>
                <div className="small faint">step {r.progress.step}/{r.progress.max_steps} · {Math.round(r.progress.elapsed_s / 60)} min {last ? `· loss ${last.loss}` : ""}</div></>}
              {r.metrics && <div className="small">train loss {r.metrics.train_loss} · val loss {r.metrics.eval_loss} · {r.metrics.train_runtime_s}s · peak {r.metrics.peak_vram_gb} GB</div>}
              {r.error && <div className="small err">{r.error}</div>}
              {r.deployed && <div className="small">Ollama: <span className="mono">{r.deployed.ollama_name}</span></div>}
              <div className="row" style={{ marginTop: 6 }}>
                <button className="btn ghost" onClick={() => setOpen(open === r.run_id ? null : r.run_id)}>{open === r.run_id ? "Hide" : "Run card"}</button>
                {operator && ["trained", "evaluated", "deployed"].includes(r.status) && <>
                  <button className="btn ghost" onClick={() => act(() => api(`/llm/runs/${r.run_id}/evaluate`, { body: {} }), "Evaluation started on the trainer.")}>Evaluate</button>
                  <button className="btn ghost" onClick={() => act(() => api(`/llm/runs/${r.run_id}/deploy`, { body: {} }), "Deployment to Ollama started.")}>Deploy to Ollama</button></>}
                {operator && ["queued", "failed"].includes(r.status) && <button className="btn ghost" onClick={() => act(() => api(`/llm/runs/${r.run_id}/train`, { body: {} }), "Training started.")}>Start</button>}
              </div>
              {open === r.run_id && <RunCard id={r.run_id} />}
            </div>
          );
        })}
      </Card>
    </>
  );
}

function RunCard({ id }: { id: string }) {
  const r = useApi<{ card: string | null }>(`/llm/runs/${id}`);
  return <div style={{ marginTop: 8 }}>{r.data?.card ? <Markdown text={r.data.card} /> : <Loading what="Run card" />}</div>;
}

function MetricsTable({ rows }: { rows: Record<string, any>[] }) {
  const cols: [string, string, boolean][] = [["token_f1", "Token F1 ↑", true], ["rouge_l", "ROUGE-L ↑", true], ["citation_rate", "Cites source ↑", true],
    ["abstain_accuracy", "Abstains when it should ↑", true], ["false_abstain_rate", "Wrongly refuses ↓", false], ["unsupported_numbers", "Unsupported numbers ↓", false], ["safety_pass_rate", "Safety probes ↑", true]];
  return (
    <div className="table-wrap"><table className="tbl">
      <thead><tr><th>Model</th>{cols.map(([, l]) => <th key={l}>{l}</th>)}<th>Items</th><th>When</th></tr></thead>
      <tbody>{rows.map((e) => (
        <tr key={e.label + e.evaluated_at}><td><b className="mono">{e.label}</b><div className="small faint">{e.meta?.backend}</div></td>
          {cols.map(([k]) => <td key={k} className="mono">{e[k] == null ? "—" : `${Math.round(e[k] * 100)}%`}</td>)}
          <td className="small">{e.n_grounded}+{e.n_abstain}+{e.n_probes}</td><td className="small">{e.evaluated_at?.slice(0, 16)}</td></tr>
      ))}</tbody>
    </table></div>
  );
}

function EvalTab({ d, operator, act }: { d: Overview; operator: boolean; act: (fn: () => Promise<any>, ok: string) => void }) {
  const [model, setModel] = useState("qwen2.5:7b");
  return (
    <>
      <Card title="Compare models (same held-out sample, scored against source text)">
        {d.evals.length ? <MetricsTable rows={d.evals} /> : <div className="empty">No evaluations yet.</div>}
        <p className="small faint">Items = grounded questions + abstention questions + safety probes. Small samples: treat differences of a few points as noise.</p>
      </Card>
      {operator && (
        <Card title="Evaluate a model served by Ollama">
          <div className="row">
            <input className="input mono" value={model} onChange={(e) => setModel(e.target.value)} />
            <button className="btn primary" onClick={() => act(() => api("/llm/evals/ollama", { body: { model, dataset: d.datasets[0]?.name ?? "spacemed-v2", n: 40 } }), `Evaluating ${model}… (takes a few minutes)`)}>Run evaluation</button>
          </div>
          {d.tasks.filter((t) => t.kind === "eval").map((t) => <p key={t.id} className="small">{t.id}: {t.status} {t.error ?? ""}</p>)}
        </Card>
      )}
    </>
  );
}

function ModelsTab({ operator }: { operator: boolean }) {
  const m = useApi<{ reachable: boolean; url: string; error?: string; models: { name: string; size_gb: number; family: string; parameter_size: string; quantization_level: string }[]; pulls: { id: string; status: string; progress?: { status: string; completed?: number; total?: number }; error?: string }[] }>("/llm/ollama/models");
  const [name, setName] = useState("qwen2.5:7b");
  const [err, setErr] = useState("");
  const pulling = (m.data?.pulls ?? []).some((p) => p.status === "running");
  useEffect(() => { if (!pulling) return; const t = setInterval(() => m.reload(), 2000); return () => clearInterval(t); }, [pulling]);   // eslint-disable-line react-hooks/exhaustive-deps
  async function go(fn: () => Promise<any>) { setErr(""); try { await fn(); m.reload(); } catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } }
  return (
    <Card title={`Models on the inference server (${m.data?.url ?? "Ollama"})`}>
      {m.data && !m.data.reachable && <div className="banner"><b>Ollama not reachable.</b> {m.data.error}</div>}
      {err && <div className="err">{err}</div>}
      {operator && <div className="row" style={{ marginBottom: 10 }}>
        <input className="input mono" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. qwen2.5:7b" />
        <button className="btn primary" disabled={pulling} onClick={() => go(() => api("/llm/ollama/pull", { body: { name } }))}>Download</button>
      </div>}
      {(m.data?.pulls ?? []).map((p) => (
        <div key={p.id} className="small">{p.id.replace("pull:", "")}: {p.status} {p.progress?.status} {p.progress?.total ? `${Math.round((100 * (p.progress.completed ?? 0)) / p.progress.total)}%` : ""} {p.error}</div>
      ))}
      <table className="tbl"><thead><tr><th>Model</th><th>Size</th><th>Family</th><th>Params</th><th>Quant</th><th></th></tr></thead>
        <tbody>{(m.data?.models ?? []).map((x) => (
          <tr key={x.name}><td className="mono">{x.name}</td><td>{x.size_gb} GB</td><td>{x.family}</td><td>{x.parameter_size}</td><td>{x.quantization_level}</td>
            <td>{operator && <button className="btn ghost danger" onClick={() => confirm(`Delete ${x.name}?`) && go(() => api(`/llm/ollama/models/${encodeURIComponent(x.name)}`, { method: "DELETE" }))}>Delete</button>}</td></tr>
        ))}</tbody></table>
    </Card>
  );
}
