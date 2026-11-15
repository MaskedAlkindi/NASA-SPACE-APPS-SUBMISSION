# Training and evaluation

All commands run from the repository root with the project virtual environment. Raw data goes to `data/external/`
(git-ignored, about 4.5 GB in total). Each dataset folder gets a `PROVENANCE.json` with source, licence, retrieval
time and SHA-256 per file. Extra packages for this step only: `pip install openpyxl wfdb` (not needed at runtime).

## 1. Download (only data whose terms permit it)

```bash
python -m ai.datasets.pmdata download
```

```bash
python -m ai.datasets.others download stanford_illness
```

```bash
python -m ai.datasets.others download cgmacros
```

```bash
python -m ai.datasets.others download mmash
```

```bash
python -m ai.datasets.others download cves
```

The Stanford illness labels come from the paper's Supplementary Data (`41551_2020_640_MOESM3_ESM.xlsx`). Download it from the
Nature Biomedical Engineering article page into `data/external/stanford_illness/`.

## 2. Train or evaluate

| Model | Command | Writes |
|---|---|---|
| fatigue_pmdata | `python -m ai.training.train_fatigue_pmdata` | `artifacts/fatigue_pmdata_v1.joblib`, `report.json` |
| illness_rhr | `python -m ai.evaluation.stanford_illness` | `report.json` (rule thresholds; caches daily resting HR) |
| glucose_metabolic | `python -m ai.training.train_glucose_cgmacros` | `artifacts/glucose_cgmacros_v1.joblib`, `report.json` |
| sleep_hrv | `python -m ai.evaluation.mmash_verification` | `report.json` |
| orthostatic | `python -m ai.evaluation.cves_orthostatic` | `report.json` |
| legacy models | `python -m ml.training.train_all` | `ml/artifacts/` (also run automatically in the Docker build) |

Then regenerate documentation:

```bash
python -m ai.documentation.generate_cards
```

## Evaluation rules used

- **No subject-level leakage:**
  - PMData and CGMacros use leave-one-subject-out evaluation.
  - Stanford tunes the threshold on one half of the participants and reports on the other half, with the selection rule fixed in advance.
  - Personal baselines only use days *before* the scored day (`causal_baseline`).
- **Baselines are always reported:** yesterday's self-report, constant, carbs-only, or the existing model, so a number can be judged.
- **Label meaning is checked, not assumed:** PMData's scales are verified by correlation with readiness (higher = better).
- **Signal processing is verified against independent references:** MMASH device HR and sleep efficiency, and the CVES published sit-to-stand changes (with sign convention checked).
- **Interpretable models first:** logistic regression is kept unless gradient boosting is more than 0.02 AUC better.

Artifacts are trained with scikit-learn 1.5.2, the same version as the Docker image. Committed artifacts are small (KB) and load in the container without retraining.
