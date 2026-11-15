"""Train every model and write versioned artifacts + a metrics report.

    python -m ml.training.train_all            # from repository root
"""
from __future__ import annotations

import time

from ml.models import artifacts
from ml.training import train_anomaly, train_fatigue, train_forecast


def main() -> dict:
    t0 = time.time()
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "disclaimer": "All metrics are computed on SIMULATED data and are NOT clinical accuracy.",
        artifacts.ANOMALY_VERSION: train_anomaly.train(),
        artifacts.FATIGUE_VERSION: train_fatigue.train(),
        artifacts.FORECAST_VERSION: train_forecast.train(),
    }
    artifacts.save_json("metrics_report.json", report)
    print(f"Artifacts written to {artifacts.ARTIFACT_DIR} in {time.time() - t0:.1f}s")
    return report


if __name__ == "__main__":
    main()
