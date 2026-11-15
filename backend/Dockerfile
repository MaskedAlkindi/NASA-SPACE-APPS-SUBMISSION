# Build context: repository root (see docker-compose.yml)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/backend \
    HMT_ARTIFACT_DIR=/app/ml/artifacts \
    NASA_CACHE_DIR=/data/nasa_cache \
    HMT_LLM_DATA=/data/llm \
    HMT_AI_IMPORT_DIR=/data/imported_models \
    LOKY_MAX_CPU_COUNT=2

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

# ML code + reproducible training at build time -> versioned artifacts baked into the image
COPY ml ml
RUN python -m ml.training.train_all

COPY data/nasa_snapshot data/nasa_snapshot
COPY data/challenge_snapshot data/challenge_snapshot
# Plug-in AI engine: model code, manifests, trained artifacts and evaluation reports (datasets are NOT copied)
COPY ai ai
COPY contracts contracts
COPY servers servers
COPY llm llm
COPY backend backend

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data/nasa_cache /data/llm /data/imported_models \
    && chown -R appuser /data /app/ml/artifacts /app/contracts
USER appuser
WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
