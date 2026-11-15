"""Application settings (environment variables, see .env.example)."""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "HEALTH-01"
    environment: str = "demo"
    database_url: str = "sqlite:///./hmt.db"
    secret_key: str = ""
    token_ttl_hours: int = 24
    demo_mode: bool = True
    demo_passcode: str = "hmt-demo"
    seed_days: int = 45
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    # NASA
    nasa_cache_dir: str = str(REPO_ROOT / "data" / "nasa_cache")
    nasa_osdr_base: str = "https://osdr.nasa.gov"
    nasa_online: bool = True          # set false for fully offline demo (bundled snapshot only)
    nasa_timeout_s: float = 20.0

    # Assistant provider: auto | openai | ollama | offline
    #   auto = OpenAI if a key is set, else a local Ollama model if one is reachable, else offline explainer
    assistant_provider: str = "auto"

    # Ollama (optional, local models)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = ""             # blank = first installed chat model
    ollama_timeout_s: float = 180.0    # local CPU/GPU inference can be slow
    ollama_num_ctx: int = 8192

    # OpenAI (optional)
    openai_model_options: str = "gpt-5-mini,gpt-5-nano,gpt-4.1-mini"
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    openai_reasoning_effort: str = "low"   # sent only to reasoning models; blank to omit
    openai_max_output_tokens: int = 900
    openai_timeout_s: float = 25.0
    assistant_history_limit: int = 6
    assistant_max_passages: int = 3
    assistant_rate_limit_per_minute: int = 6
    assistant_daily_request_budget: int = 200      # all users combined; 0 = unlimited
    assistant_daily_token_budget: int = 200_000    # all users combined; 0 = unlimited

    # Simulator
    sim_tick_seconds: float = 1.5     # real seconds per simulated hour

    # Exercise module. Empty URLs keep recommendations on the rules engine and
    # camera counting in the browser. Tokens are never returned by public config.
    exercise_inference_url: str = ""
    exercise_inference_token: str = ""
    exercise_allow_remote_frames: bool = False
    exercise_recommender_url: str = ""
    exercise_recommender_token: str = ""
    exercise_pose_model_url: str = (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
    )
    exercise_pose_wasm_url: str = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.18/wasm"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.secret_key:
        # Ephemeral key: tokens are invalidated on restart. Set SECRET_KEY in .env for stability.
        s.secret_key = secrets.token_urlsafe(32)
    return s
