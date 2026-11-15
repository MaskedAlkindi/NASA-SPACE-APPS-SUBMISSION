"""Fine-tuning workspace and model management (/api/v1/llm).

Separation of concerns:
  - dataset management and RAG: llm/datasets, llm/rag (run here, CPU only)
  - fine-tuning / adapter evaluation / deployment: the trainer service on the GPU machine (HMT_LLM_TRAINER_URL)
  - inference: Ollama (OLLAMA_BASE_URL); this API only lists, pulls and deletes models there
Reading is open to signed-in users; anything that changes data, starts jobs or downloads models needs a crew-wide role.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import Principal, current_user, require_crew_wide

router = APIRouter(prefix="/api/v1/llm", tags=["llm"])
TRAINER = os.getenv("HMT_LLM_TRAINER_URL", "").rstrip("/")
TRAINER_TOKEN = os.getenv("HMT_TRAINER_TOKEN", "")
_tasks: dict[str, dict] = {}          # background CPU tasks in this process (collect, build, baseline eval, pulls)
_tasks_lock = threading.Lock()
NAME_RX = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}$")


def _ollama() -> str:
    return get_settings().ollama_base_url.rstrip("/")


def _task(kind: str, key: str, fn) -> dict:
    tid = f"{kind}:{key}"
    with _tasks_lock:
        if _tasks.get(tid, {}).get("status") == "running":
            raise HTTPException(409, f"{kind} already running")
        _tasks[tid] = {"id": tid, "kind": kind, "status": "running", "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    def run():
        try:
            res = fn()
            _tasks[tid].update(status="done", result=res)
        except Exception as e:   # noqa: BLE001 - surfaced in the UI
            _tasks[tid].update(status="failed", error=f"{type(e).__name__}: {str(e)[:500]}")
        _tasks[tid]["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    threading.Thread(target=run, daemon=True).start()
    return _tasks[tid]


def _trainer(method: str, path: str, body: dict | None = None):
    if not TRAINER:
        raise HTTPException(503, "no trainer configured: set HMT_LLM_TRAINER_URL to the GPU machine running llm.service.trainer_service")
    try:
        r = httpx.request(method, TRAINER + path, json=body, timeout=20, headers={"X-Trainer-Token": TRAINER_TOKEN})
    except httpx.HTTPError as e:
        raise HTTPException(502, f"trainer unreachable: {e}")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text)
    return r.json()


def _remote_runs() -> dict:
    """Runs the trainer machine has (they hold the real progress and metrics when it is a separate server)."""
    if not TRAINER:
        return {}
    try:
        return {r["run_id"]: r for r in _trainer("GET", "/runs")["runs"]}
    except HTTPException:
        return {}


# ---------------------------------------------------------------- overview
@router.get("/overview")
def overview(user: Principal = Depends(current_user)):
    from llm.evaluation.evaluate import compare
    from llm.models.registry import base_models, list_runs
    from llm.paths import CORPUS, DATASETS, LLM_DIR
    trainer = {"configured": bool(TRAINER), "url": TRAINER or None}
    if TRAINER:
        try:
            trainer.update(httpx.get(TRAINER + "/health", timeout=5).json(), reachable=True)
        except httpx.HTTPError as e:
            trainer.update(reachable=False, error=str(e)[:200])
    prov_p = CORPUS / "PROVENANCE.json"
    datasets = []
    for d in sorted(DATASETS.glob("*/manifest.json")):
        m = json.loads(d.read_text(encoding="utf-8"))
        datasets.append({k: m.get(k) for k in ("name", "built_at", "counts", "by_source", "licences", "generation", "uploaded")})
    return {"base_models": base_models(), "sources": json.loads((LLM_DIR / "datasets" / "sources.json").read_text(encoding="utf-8"))["sources"],
            "corpus": json.loads(prov_p.read_text(encoding="utf-8")) if prov_p.exists() else None, "datasets": datasets,
            "runs": [{k: r.get(k) for k in ("run_id", "version", "status", "created_at", "dataset", "method", "base_model", "metrics", "eval", "deployed", "error", "progress")}
                     for r in sorted({**{r["run_id"]: r for r in list_runs()}, **_remote_runs()}.values(),
                                     key=lambda r: r["run_id"], reverse=True)],
            "evals": compare(), "trainer": trainer, "tasks": list(_tasks.values())[-20:]}


@router.get("/rag/search")
def rag_search(q: str = Query(..., min_length=2, max_length=300), k: int = Query(5, le=20), user: Principal = Depends(current_user)):
    from llm.rag.index import search
    return {"hits": [{kk: h.get(kk) for kk in ("source_id", "title", "url", "page", "section", "licence", "score", "text")} for h in search(q, k)]}


# ---------------------------------------------------------------- data
class CollectIn(BaseModel):
    which: list[str] = Field(default_factory=lambda: ["challenge_pages", "challenge_pdfs", "verified_facts", "model_cards", "europepmc"])
    max_records: int = Field(400, ge=10, le=2000)


@router.post("/corpus/collect")
def collect(body: CollectIn, user: Principal = Depends(require_crew_wide)):
    from llm.datasets import collect as c
    from llm.rag.index import build as build_index
    bad = [w for w in body.which if w not in c.COLLECTORS]
    if bad:
        raise HTTPException(422, f"unknown collectors {bad}")

    def job():
        for w in body.which:
            sid, fn = c.COLLECTORS[w]
            c._write(sid, fn(body.max_records) if w == "europepmc" else fn())
        prov = c.write_provenance()
        return {"corpus": prov["files"], "rag": build_index()}
    return _task("collect", "corpus", job)


class BuildIn(BaseModel):
    name: str = Field("spacemed-v2", pattern=NAME_RX.pattern)
    seed: str = Field("health01", max_length=40)


@router.post("/datasets/build")
def build_dataset(body: BuildIn, user: Principal = Depends(require_crew_wide)):
    from llm.datasets.build_sft import build
    return _task("build", body.name, lambda: build(body.name, body.seed)["counts"])


class UploadIn(BaseModel):
    name: str = Field(..., pattern=NAME_RX.pattern)
    licence: str = Field(..., min_length=2, max_length=200)
    source: str = Field(..., min_length=2, max_length=500)       # where the data came from (URL or description)
    description: str = Field("", max_length=2000)
    jsonl: str = Field(..., max_length=20_000_000)


@router.post("/datasets/upload")
def upload_dataset(body: UploadIn, user: Principal = Depends(require_crew_wide)):
    """Chat-format JSONL: one {"messages": [{"role": "...", "content": "..."}, ...]} per line. Licence and source are required."""
    import hashlib
    import random
    from llm.datasets.prompts import SYSTEM
    from llm.paths import DATASETS
    rows, errors = [], []
    for i, line in enumerate(body.jsonl.splitlines()):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            msgs = obj["messages"]
            assert isinstance(msgs, list) and msgs and all(m["role"] in ("system", "user", "assistant") and isinstance(m["content"], str) for m in msgs)
            assert msgs[-1]["role"] == "assistant", "last message must be the assistant's answer"
            if msgs[0]["role"] != "system":
                msgs = [{"role": "system", "content": SYSTEM}] + msgs
            rows.append({"kind": "uploaded", "messages": msgs, "source": f"upload:{body.name}", "licence": body.licence, "source_ids": [f"line-{i + 1}"], "doc": f"line-{i + 1}", "tags": []})
        except Exception as e:   # noqa: BLE001
            errors.append(f"line {i + 1}: {str(e)[:120] or type(e).__name__}")
    if errors[:1] and not rows:
        raise HTTPException(422, {"errors": errors[:20]})
    if len(rows) < 10:
        raise HTTPException(422, "need at least 10 valid examples")
    out = DATASETS / body.name
    if (out / "manifest.json").exists() and not json.loads((out / "manifest.json").read_text(encoding="utf-8")).get("uploaded"):
        raise HTTPException(409, "a built dataset with this name exists; choose another name")
    out.mkdir(parents=True, exist_ok=True)
    random.Random(body.name).shuffle(rows)
    n_val = max(1, len(rows) // 10)
    splits = {"val": rows[:n_val], "test": rows[n_val:2 * n_val], "train": rows[2 * n_val:]}
    for k, v in splits.items():
        (out / f"{k}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in v), encoding="utf-8")
    manifest = {"name": body.name, "uploaded": True, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "uploaded_by": user.username, "licence": body.licence, "source": body.source, "description": body.description,
                "counts": {k: len(v) for k, v in splits.items()}, "by_source": {f"upload:{body.name}": len(rows)},
                "licences": {body.licence: len(rows)}, "rejected_lines": errors[:50], "generation": "uploaded by a user; not checked by HEALTH-01",
                "files": {f"{k}.jsonl": hashlib.sha256((out / f"{k}.jsonl").read_bytes()).hexdigest() for k in splits}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "DATASET_CARD.md").write_text(f"# Dataset card: {body.name} (uploaded)\n\n- Uploaded by {user.username} at {manifest['built_at']}\n"
                                         f"- Source: {body.source}\n- Licence: {body.licence}\n- Examples: {manifest['counts']}\n"
                                         f"- Rejected lines: {len(errors)}\n\n{body.description}\n\nNot reviewed by HEALTH-01; check content and licence before training.\n", encoding="utf-8")
    return manifest


@router.get("/datasets/{name}/card", response_class=PlainTextResponse)
def dataset_card(name: str, user: Principal = Depends(current_user)):
    from llm.paths import DATASETS
    p = DATASETS / name / "DATASET_CARD.md"
    if not NAME_RX.match(name) or not p.exists():
        raise HTTPException(404, "dataset not found")
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------- runs (training on the trainer service)
class RunIn(BaseModel):
    base_model: str
    dataset: str
    method: str = "qlora"
    hyperparameters: dict = Field(default_factory=dict)
    notes: str = ""
    start: bool = True


@router.post("/runs")
def create_run(body: RunIn, user: Principal = Depends(require_crew_wide)):
    from llm.models.registry import create_run as mk
    try:
        run = mk(body.base_model, body.dataset, body.method, body.hyperparameters, body.notes, user.username)
    except (KeyError, ValueError) as e:
        raise HTTPException(422, str(e))
    job = _trainer("POST", "/jobs", {"type": "train", "run_id": run["run_id"], "run": run}) if body.start and TRAINER else None
    return {"run": run, "job": job, "note": None if TRAINER else "Run registered. Start it on a GPU machine: python -m llm.training.train_qlora --run " + run["run_id"]}


@router.get("/runs/{run_id}")
def get_run(run_id: str, user: Principal = Depends(current_user)):
    from llm.models.registry import get_run as g
    from llm.paths import RUNS
    if TRAINER:
        try:
            return _trainer("GET", f"/runs/{run_id}")
        except HTTPException:
            pass
    try:
        r = g(run_id)
    except KeyError:
        raise HTTPException(404, "run not found")
    card = RUNS / run_id / "RUN_CARD.md"
    r["card"] = card.read_text(encoding="utf-8") if card.exists() else None
    return r


class JobIn(BaseModel):
    eval_n: int = Field(40, ge=5, le=300)
    ollama_name: str | None = Field(None, pattern=NAME_RX.pattern)
    # Ollama >= 0.20 accepts only int4/int8/nvfp4/mxfp4/mxfp8 for `ollama create --quantize`; the K-quants are for older versions
    quantize: str | None = Field("int4", pattern=r"^(int4|int8|nvfp4|mxfp4|mxfp8|q4_K_M|q5_K_M|q8_0|f16)?$")


@router.post("/runs/{run_id}/{action}")
def run_action(run_id: str, action: str, body: JobIn, user: Principal = Depends(require_crew_wide)):
    if action not in ("train", "evaluate", "deploy"):
        raise HTTPException(404, "unknown action")
    return _trainer("POST", "/jobs", {"type": action, "run_id": run_id, "run": _local_run(run_id), "eval_n": body.eval_n, "ollama_name": body.ollama_name, "quantize": body.quantize})


def _local_run(run_id: str) -> dict | None:
    from llm.models.registry import get_run as g
    try:
        return g(run_id)
    except KeyError:
        return None


@router.get("/jobs/{job_id}")
def job(job_id: str, user: Principal = Depends(current_user)):
    return _trainer("GET", f"/jobs/{job_id}")


# ---------------------------------------------------------------- evaluation of models served by Ollama (no GPU job here)
class BaselineIn(BaseModel):
    model: str = Field(..., min_length=2, max_length=120)
    dataset: str = Field("spacemed-v2", pattern=NAME_RX.pattern)
    n: int = Field(40, ge=5, le=300)


@router.post("/evals/ollama")
def eval_ollama(body: BaselineIn, user: Principal = Depends(require_crew_wide)):
    from llm.evaluation.evaluate import Ollama, evaluate
    return _task("eval", body.model, lambda: evaluate(Ollama(body.model, _ollama()), body.model, body.dataset, body.n,
                                                      meta={"backend": "ollama", "model": body.model})["metrics"])


@router.get("/evals")
def evals(user: Principal = Depends(current_user)):
    from llm.evaluation.evaluate import compare
    return {"evals": compare()}


# ---------------------------------------------------------------- Ollama model management (also used by the desktop app)
@router.get("/ollama/models")
def ollama_models(user: Principal = Depends(current_user)):
    try:
        tags = httpx.get(_ollama() + "/api/tags", timeout=8).json()
    except httpx.HTTPError as e:
        return {"reachable": False, "url": _ollama(), "error": str(e)[:200], "models": [], "pulls": [t for t in _tasks.values() if t["kind"] == "pull"]}
    return {"reachable": True, "url": _ollama(), "pulls": [t for t in _tasks.values() if t["kind"] == "pull"],
            "models": [{"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 2), "modified_at": m.get("modified_at"),
                        **{k: (m.get("details") or {}).get(k) for k in ("family", "parameter_size", "quantization_level")}} for m in tags.get("models", [])]}


class PullIn(BaseModel):
    name: str = Field(..., pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{1,100}$")


@router.post("/ollama/pull")
def ollama_pull(body: PullIn, user: Principal = Depends(require_crew_wide)):
    def pull():
        progress = {}
        with httpx.stream("POST", _ollama() + "/api/pull", json={"name": body.name, "stream": True}, timeout=None) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                ev = json.loads(line)
                if ev.get("error"):
                    raise RuntimeError(ev["error"])
                progress = {"status": ev.get("status"), "completed": ev.get("completed"), "total": ev.get("total")}
                _tasks[f"pull:{body.name}"]["progress"] = progress
        return progress
    return _task("pull", body.name, pull)


@router.delete("/ollama/models/{name:path}")
def ollama_delete(name: str, user: Principal = Depends(require_crew_wide)):
    r = httpx.request("DELETE", _ollama() + "/api/delete", json={"name": name}, timeout=30)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:300])
    return {"deleted": name}
