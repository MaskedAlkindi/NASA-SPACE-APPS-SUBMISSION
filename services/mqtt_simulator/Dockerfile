# Simulated habitat publisher. Own image so it stays out of the API container.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN pip install paho-mqtt==2.1.0 \
    && useradd --create-home --uid 10002 simuser
COPY publish.py .
USER simuser

CMD ["python", "-u", "publish.py"]
