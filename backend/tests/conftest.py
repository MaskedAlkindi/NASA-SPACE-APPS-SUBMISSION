import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
_tmp = tempfile.mkdtemp(prefix="hmt-test-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
    "NASA_ONLINE": "false",                 # tests never hit the network; bundled snapshot is used
    "NASA_CACHE_DIR": f"{_tmp}/nasa_cache",
    "SEED_DAYS": "35",
    "OPENAI_API_KEY": "",
    "ASSISTANT_PROVIDER": "auto",
    "OLLAMA_BASE_URL": "http://127.0.0.1:9",   # unreachable: unit tests never call a real local model
    "SECRET_KEY": "test-secret",
    "DEMO_PASSCODE": "test-pass",
    "LOKY_MAX_CPU_COUNT": "2",
    "HMT_LLM_DATA": f"{_tmp}/llm",              # LLM corpus/datasets/runs go to a temp folder in tests
    "HMT_AI_IMPORT_DIR": f"{_tmp}/imported_models",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _login(client, user):
    r = client.post("/api/v1/auth/login", json={"username": user, "passcode": "test-pass"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="session")
def mc(client):
    return _login(client, "mission-control")


@pytest.fixture(scope="session")
def orion(client):
    return _login(client, "hajid")
