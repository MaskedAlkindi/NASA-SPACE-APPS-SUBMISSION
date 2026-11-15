import json


def _prepare_corpus():
    """Offline collectors only (bundled NASA snapshot), then dataset + index."""
    from llm.datasets import collect
    from llm.datasets.build_sft import build
    from llm.rag.index import build as build_index
    for name in ("challenge_pages", "verified_facts"):
        sid, fn = collect.COLLECTORS[name]
        collect._write(sid, fn())
    collect.write_provenance()
    build_index()
    return build("test-set")


def test_dataset_is_extractive_and_split_by_document():
    m = _prepare_corpus()
    assert m["counts"]["train"] > 50 and "no model-generated text" in m["generation"]
    from llm.paths import DATASETS
    docs = {}
    for split in ("train", "val", "test"):
        for line in (DATASETS / "test-set" / f"{split}.jsonl").open(encoding="utf-8"):
            r = json.loads(line)
            docs.setdefault(r["doc"], set()).add(split)
            if r["kind"] == "grounded_extract":     # answer sentences come from the context passage
                ctx, ans = r["messages"][1]["content"], r["messages"][2]["content"].split("\n\nSource:")[0]
                assert ans.split(". ")[0][:60] in ctx
    assert all(len(s) == 1 for s in docs.values())      # no document in two splits


def test_llm_api_overview_rag_upload_and_runs(client, mc, orion):
    o = client.get("/api/v1/llm/overview", headers=orion).json()
    assert o["base_models"]["default"] == "qwen2.5-7b-instruct" and any(s["id"] == "europepmc_ccby" for s in o["sources"])
    hits = client.get("/api/v1/llm/rag/search?q=bone mineral density per month", headers=orion).json()["hits"]
    assert hits and hits[0]["source_id"] in ("nasa_verified_facts", "nasa_challenge_pages")

    lines = "\n".join(json.dumps({"messages": [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}]}) for i in range(12))
    assert client.post("/api/v1/llm/datasets/upload", headers=orion, json={"name": "up-1", "licence": "CC BY", "source": "test", "jsonl": lines}).status_code == 403
    up = client.post("/api/v1/llm/datasets/upload", headers=mc, json={"name": "up-1", "licence": "CC BY", "source": "test", "jsonl": lines + "\nnot json"}).json()
    assert up["uploaded"] and sum(up["counts"].values()) == 12 and len(up["rejected_lines"]) == 1
    assert client.post("/api/v1/llm/datasets/upload", headers=mc, json={"name": "test-set", "licence": "CC BY", "source": "test", "jsonl": lines}).status_code == 409

    bad = client.post("/api/v1/llm/runs", headers=mc, json={"base_model": "qwen2.5-0.5b-instruct", "dataset": "up-1", "hyperparameters": {"lora_r": 9999}})
    assert bad.status_code == 422
    r = client.post("/api/v1/llm/runs", headers=mc, json={"base_model": "qwen2.5-0.5b-instruct", "dataset": "up-1", "hyperparameters": {"epochs": 1}}).json()
    assert r["run"]["status"] == "queued" and r["job"] is None and "train_qlora" in r["note"]      # no trainer configured in tests
    got = client.get(f"/api/v1/llm/runs/{r['run']['run_id']}", headers=orion).json()
    assert got["version"].startswith("health01-qwen2.5-0.5b-instruct-v") and got["hyperparameters"]["epochs"] == 1.0
    assert client.post(f"/api/v1/llm/runs/{r['run']['run_id']}/train", headers=mc, json={}).status_code == 503
    m = client.get("/api/v1/llm/ollama/models", headers=orion).json()
    assert m["reachable"] is False and m["models"] == []      # tests point Ollama at an unreachable port
