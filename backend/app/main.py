"""HEALTH-01 API entry point."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_core, routes_more
from app.exercise.routes import router as exercise_router
from app.ai_engine.routes import router as ai_router
from app.devices.routes import router as devices_router
from app.devices.connections import router as servers_router
from app.llm_api.routes import router as llm_router
from app.site_gate import router as site_router
from app.mqtt.routes import router as mqtt_router
from app.nutrition.routes import router as nutrition_router
import app.mqtt.db_models  # noqa: F401  (tables)
import app.admin.db_models  # noqa: F401  (tables)
import app.nutrition.models  # noqa: F401  (tables)
from app.admin.routes import router as admin_router
from app.core.config import get_settings
from app.core.events import broadcaster
from app.database.seed import seed_history, seed_reference
from app.database.session import SessionLocal, init_db, wait_for_db
from app.intelligence import models_service
from app.modules.registry import get_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("hmt")
settings = get_settings()


def _startup_sync():
    wait_for_db()
    init_db()
    models_service.ensure_trained()
    db = SessionLocal()
    try:
        seed_reference(db)
        if settings.demo_mode:
            seed_history(db)
        from app.exercise.seed import seed_exercise_demo
        seed_exercise_demo(db)
        from app.nutrition.seed import seed_nutrition_demo
        seed_nutrition_demo(db)
        import threading
        from app.ai_engine.service import warm_up
        threading.Thread(target=warm_up, name="ai-warm-up", daemon=True).start()
        from app.mqtt import bridge as mqtt_bridge
        mqtt_bridge.start()
        from app.intelligence.research import sync_hrp_findings
        log.info("loaded %d NASA challenge-resource findings", sync_hrp_findings(db))
    finally:
        db.close()


async def _nasa_import_background():
    try:
        res = await run_in_threadpool(routes_more.run_nasa_import, False)
        log.info("NASA OSDR import: %s", {k: v for k, v in res.items() if k != "errors"})
        if res.get("errors"):
            log.warning("NASA OSDR import issues: %s", res["errors"][:5])
    except Exception:
        log.exception("NASA import failed (research module degraded, app continues)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    broadcaster.bind(asyncio.get_running_loop())
    get_registry()
    await run_in_threadpool(_startup_sync)
    task = asyncio.create_task(_nasa_import_background())
    log.info("HEALTH-01 ready (assistant provider setting: %s)", settings.assistant_provider)
    yield
    task.cancel()
    sim = get_registry().get("simulation")
    if sim:
        sim.stop()


app = FastAPI(
    title=f"{settings.app_name} API",
    description=("Modular, AI-assisted astronaut health monitoring prototype (NASA Space Apps). "
                 "Research and decision-support prototype - NOT a certified medical device. "
                 "Authenticate via POST /api/v1/auth/login and use the bearer token."),
    version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(routes_core.router)
app.include_router(routes_more.router)
app.include_router(exercise_router)
app.include_router(ai_router)
app.include_router(devices_router)
app.include_router(servers_router)
app.include_router(llm_router)
app.include_router(admin_router)
app.include_router(site_router)
app.include_router(mqtt_router)
app.include_router(nutrition_router)


@app.get("/", include_in_schema=False)
def root():
    return {"name": f"{settings.app_name} API", "docs": "/docs", "health": "/api/v1/health"}
