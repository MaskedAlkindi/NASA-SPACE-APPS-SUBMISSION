"""Generate docs/ai/model_cards/<id>.md and docs/ai/PERFORMANCE.md from manifests + report.json files.

    python -m ai.documentation.generate_cards

Numbers come straight from the evaluation reports, so the documentation cannot drift from the results.
"""
from __future__ import annotations

import json
from pathlib import Path

from ai.registry.registry import MemoryStateStore, ModelRegistry

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "ai"
EVID = {"earth_research": "Earth-based research data (not astronauts)", "simulation": "Simulated data only",
        "rule_based": "Transparent rules on published reference values", "spaceflight": "Spaceflight data"}


def _metrics(mid: str, r: dict | None) -> list[str]:
    if not r:
        return ["No evaluation report."]
    if mid == "illness_rhr":
        L = [f"Data: {r['participants_with_daily_data']} participants, {r['illness_events_with_data']} labelled illness events "
             f"({', '.join(f'{k}: {v}' for k, v in r['events_by_kind'].items())}).",
             f"Protocol: {r['protocol']['split']}. Event window {r['protocol']['event_window_days']} days around symptom onset; "
             f"healthy days are >= {r['protocol']['healthy_day_gap_days']} days from any reported illness.", "",
             "| Detector | Threshold | Consecutive days | Events | Sensitivity | Day specificity | False-alert episodes / 30 healthy days | Median alert vs onset (days) | % detected before onset |",
             "|---|---|---|---|---|---|---|---|---|"]
        rows = [("selected on tuning half", r["selected"]), ("**held-out half (reported)**", r["held_out_half"])]
        rows += [("all participants", x) for x in r["all_participants_grid"]]
        for name, x in rows:
            if x:
                thr = x["threshold"] if not isinstance(x["threshold"], float) else round(x["threshold"], 3)
                L.append(f"| {x['detector']} ({name}) | {thr} | {x['consecutive_days']} | {x['events_evaluable']} | {x['sensitivity']} | "
                         f"{x['specificity_day']} | {x['false_alert_episodes_per_30_healthy_days']} | {x['median_days_alert_vs_onset']} | {x['pct_detected_before_onset']} |")
        return L
    if mid == "fatigue_pmdata":
        L = [f"Leave-one-subject-out over {r['subjects']} participants. Label direction check (Spearman with readiness): {r['label_direction_check_spearman_vs_readiness']}.", "",
             "| Target | Feature set / model | Days | Positives | AUC pooled | AUC within person (median) | Balanced acc. @0.5 | Brier |", "|---|---|---|---|---|---|---|---|"]
        for tgt, res in r["results"].items():
            for k, v in res.items():
                L.append(f"| {tgt} | {k} | {v.get('n_days', '')} | {v.get('positives', '')} | {v.get('auc_pooled')} | {v.get('auc_within_person_median', '')} | "
                         f"{v.get('balanced_accuracy@0.5', '')} | {v.get('brier', '')} |")
        L.append("")
        L.append("Deployed (wearable-only): " + "; ".join(f"{k}: {v['kind']}, AUC {v['loso']['auc_pooled']}" for k, v in r["deployed"].items()))
        return L
    if mid == "glucose_metabolic":
        ir, pp, h = r["insulin_resistance_from_cgm"], r["postprandial_rise"], r["homa_ir"]
        return [f"Participants: {r['participants']} ({', '.join(f'{k}: {v}' for k, v in r['groups_from_hba1c'].items())}, from HbA1c).",
                f"HOMA-IR ({h['formula']}): median {h['median']} (IQR {h['iqr']}); by group {h['by_group_median']}. {h['cutoff_note']}",
                f"Insulin-resistance flag from CGM metrics (HOMA-IR >= {h['cutoff_used']}, {ir['positives']}/{ir['n']} positive): "
                f"leave-one-subject-out AUC **{ir['auc']}** (bootstrap 95% CI {ir['auc_95ci_bootstrap']}). Spearman with HOMA-IR: {ir['spearman_cgm_feature_vs_homa_ir']}.",
                f"Post-meal glucose rise ({pp['meals']} meals, {pp['subjects']} people, leave-one-subject-out): MAE **{pp['mae_mg_dl_model']} mg/dL** vs "
                f"{pp['mae_mg_dl_carbs_only_linear']} (carbs-only linear) and {pp['mae_mg_dl_predict_mean']} (predict mean); Spearman {pp['spearman_pred_vs_actual']}."]
    if mid == "sleep_hrv":
        a, s, n = r["hr_from_rr_vs_actigraph"], r["sleep_efficiency_recomputed"], r["night_hrv"]
        return [f"{r['evaluation_type']}.",
                f"HR from our RR processing vs ActiGraph HR: {a['people']} people, {a['minutes']} minutes, median MAE {a['median_mae_bpm']} bpm, "
                f"bias {a['median_bias_bpm']} bpm, r {a['median_r']}.",
                f"Sleep efficiency recomputed as TST / time in bed: max difference {s['max_abs_diff_pct_points']} percentage points ({s['people']} people).",
                f"Night RMSSD median {n['rmssd_ms_median']} ms (IQR {n['rmssd_ms_iqr']}); artefact filter kept {n['median_kept_pct']}% of beats.",
                f"Exploratory correlations (uncorrected): {r['exploratory_correlations']}"]
    if mid == "orthostatic":
        return [f"{r['evaluation_type']}. {r['valid']}/{r['recordings']} recordings processed.",
                f"Agreement with the study's published sit-to-stand change (sign-aligned): {r['agreement_with_published_sit2stand_change']}",
                f"Consensus criteria met: {r['criteria_met']}. Median changes: {r['median_changes']}.",
                f"Association with self-reported orthostatic symptoms (exploratory): {r['association_with_self_reported_symptoms']}"]
    if mid.startswith("legacy"):
        return [f"Simulated evaluation (see docs/AI_MODELS.md): {json.dumps(r.get('model') or r.get('metrics') or {}, default=str)[:600]}",
                "Real-data check for legacy_anomaly: see illness_rhr report rows `legacy_iforest`."]
    return [json.dumps(r, default=str)[:800]]


def main():
    reg = ModelRegistry(state=MemoryStateStore())
    (OUT / "model_cards").mkdir(parents=True, exist_ok=True)
    perf = ["# Model performance report", "", "Generated from `ai/models/*/report.json` by `python -m ai.documentation.generate_cards`.",
            "All results are from **Earth-based** or **simulated** data. **No model has been validated on astronauts.**", ""]
    for mid in reg.entries:
        d = reg.describe(mid)
        plugin_report = None
        try:
            plugin_report = reg.plugin(mid).report()
        except Exception:   # noqa: BLE001
            pass
        r = plugin_report or d.get("report")
        ds = "\n".join(f"- **{x['name']}** - {x['source']}  \n  Licence: {x['license']}. Population: {x['population']}. "
                       f"Citation: {x.get('citation', '')}" for x in d["datasets"])
        card = [f"# Model card: {d['name']}", "",
                f"| | |\n|---|---|\n| ID / version | `{d['id']}` v{d['version']} |\n| Category | {d['category']} |\n| Status | {d['status']} |\n"
                f"| Enabled by default | {d['enabled']} |\n| Evidence level | {EVID[d['evidence_level']]} |\n| Validated on astronaut data | **{'yes' if d['validated_on_astronauts'] else 'no'}** |\n"
                f"| Execution | {', '.join(d['execution']['environments'])}; provider {d['execution']['provider']}; timeout {d['execution']['timeout_s']} s |", "",
                f"**What it does.** {d['description']}", "", f"**Intended use.** {d['intended_use']}", "", f"**Not intended for.** {d['not_intended_for']}", "",
                "## Dataset(s)", ds, "", "## Inputs",
                "| Metric | Unit | Required | Min days | Max staleness (days) |", "|---|---|---|---|---|",
                *[f"| {i['metric']} | {i['unit']} | {i['required']} | {i['min_days']} | {i['max_staleness_days']} |" for i in d["inputs"]], "",
                "## Outputs", *[f"- `{k}`: {v}" for k, v in d["outputs"].items()], "",
                "## Training / evaluation method and actual metrics", *_metrics(mid, r), "",
                "## Alerting", f"Emits alerts: {d['alerting']['emit_alerts']}; concern at severity >= {d['alerting']['min_severity']}; "
                f"cooldown {d['alerting']['cooldown_hours']} h; thresholds {d['thresholds']}.", "",
                "## Limitations", *[f"- {x}" for x in ((r or {}).get("limitations") or ["See model code and report."])], ""]
        (OUT / "model_cards" / f"{mid}.md").write_text("\n".join(card), encoding="utf-8")
        perf += [f"## {d['name']} (`{mid}`)", f"Evidence: {EVID[d['evidence_level']]}. Validated on astronauts: no.", "", *_metrics(mid, r), ""]
    (OUT / "PERFORMANCE.md").write_text("\n".join(perf), encoding="utf-8")
    print("cards:", len(reg.entries))


if __name__ == "__main__":
    main()
