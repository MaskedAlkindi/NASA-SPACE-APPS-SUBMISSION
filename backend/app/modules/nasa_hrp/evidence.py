"""Quantitative facts taken from the challenge resources, and how the tool uses them.

Every fact carries an exact quote ("anchor") from its source document. The snapshot
builder refuses to write the snapshot unless each anchor is found in the downloaded
text, and records the PDF page number where it was found. Statements are short
paraphrases of the quote; the quote itself is kept for traceability.
"""
from __future__ import annotations

EVIDENCE = [
    {"id": "bone-loss-rate", "risks": ["risk-of-spaceflight-induced-bone-changes"],
     "metrics": ["exercise_minutes"],
     "statement": "Weight-bearing bones lose on average 1-1.5% of mineral density per month in spaceflight.",
     "values": {"monthly_loss_pct_low": 1.0, "monthly_loss_pct_high": 1.5},
     "source": "Fracture.pdf",
     "anchor": "averaged loss rates between 1-1.5% per month for normally weight-bearing skeletal sites"},
    {"id": "bone-loss-rate-web", "risks": ["risk-of-spaceflight-induced-bone-changes"], "metrics": [],
     "statement": "NASA HRP: bones lose on average 1% to 1.5% of mineral density per month during spaceflight.",
     "values": {}, "source": "hazard-gravity-fields",
     "anchor": "weight-bearing bones lose on average 1% to 1.5% of mineral density per month during spaceflight"},
    {"id": "core-temperature", "risks": ["risk-of-altered-immune-system-responses"],
     "metrics": ["body_temperature"],
     "statement": "Core body temperature rose by about 1 °C at rest in microgravity on the ISS, so fever cut-offs set on Earth "
                  "are unreliable; the tool compares temperature with each astronaut's own in-flight baseline.",
     "values": {"rise_c": 1.0}, "source": "Nutrition_ER_human_adaptation_2020_final.pdf",
     "anchor": "core body temperature was shown to increase by about 1"},
    {"id": "body-mass-loss", "risks": ["risk-of-inadequate-food-and-nutrition"], "metrics": ["body_mass"],
     "statement": "Across spaceflight data, body weight fell by about 2.4% per 100 days on average.",
     "values": {"loss_pct_per_100_days": 2.4}, "source": "Nutrition_ER_human_adaptation_2020_final.pdf",
     "anchor": "average loss of 2.4% of body weight per 100 days"},
    {"id": "body-mass-mir", "risks": ["risk-of-inadequate-food-and-nutrition"], "metrics": ["body_mass"],
     "statement": "Losses of more than 10% of pre-flight body mass were recorded on Mir.",
     "values": {"severe_loss_pct": 10}, "source": "Nutrition_ER_human_adaptation_2020_final.pdf",
     "anchor": "Body mass losses of more than 10% of preflight body mass were recorded on Mir"},
    {"id": "blood-volume", "risks": ["risk-of-cardiovascular-adaptations"], "metrics": [],
     "statement": "Blood volume falls by 10-15% in flight and takes about 2 weeks to stabilise.",
     "values": {"loss_pct_low": 10, "loss_pct_high": 15}, "source": "Nutrition_ER_human_adaptation_2020_final.pdf",
     "anchor": "10% to 15% reduction in blood volume that takes about 2 weeks to stabilize"},
    {"id": "urine-calcium", "risks": ["risk-of-spaceflight-induced-bone-changes", "risk-of-inadequate-food-and-nutrition"],
     "metrics": [],
     "statement": "In flight, 24-hour urine volume was about 17% lower and urinary calcium concentration 50% higher, "
                  "raising kidney-stone risk; fluid intake matters.",
     "values": {"urine_volume_pct": -17, "urinary_calcium_pct": 50}, "source": "Nutrition_ER_human_adaptation_2020_final.pdf",
     "anchor": "Twenty-four-hour urine volume is about 17% lower and urinary calcium concentration is 50% greater during flight than before flight"},
    {"id": "inflight-hr-bp", "risks": ["risk-of-cardiovascular-adaptations"],
     "metrics": ["heart_rate", "resting_heart_rate", "blood_pressure_systolic", "blood_pressure_diastolic"],
     "statement": "In-flight heart rate and systolic and diastolic blood pressure were lower than pre-flight values, "
                  "so Earth norms do not fit; the tool uses in-flight personal baselines.",
     "values": {}, "source": "Cardio_Risk_EB_2022_FINAL_4-3-2023.pdf",
     "anchor": "Inflight heart rate and systolic and diastolic blood pressure were decreased when compared to the preflight values"},
    {"id": "orthostatic", "risks": ["risk-of-cardiovascular-adaptations"],
     "metrics": ["blood_pressure_systolic", "heart_rate"],
     "statement": "Orthostatic intolerance (light-headedness on standing) is the primary cardiovascular risk when "
                  "returning to gravity.",
     "values": {}, "source": "Cardio_Risk_EB_2022_FINAL_4-3-2023.pdf",
     "anchor": "is considered the primary risk during re-exposure to acceleration"},
    {"id": "insulin-resistance", "risks": ["risk-of-cardiovascular-adaptations", "risk-of-inadequate-food-and-nutrition"],
     "metrics": ["blood_glucose"],
     "statement": "After long flights blood glucose was unchanged, but insulin was about 50% higher and HOMA-IR "
                  "about 60% higher, a sign of insulin resistance. Glucose alone can look normal.",
     "values": {"insulin_pct": 50, "homa_ir_pct": 60}, "source": "Cardio_Risk_EB_2022_FINAL_4-3-2023.pdf",
     "anchor": "blood glucose levels were not different after long -duration spaceflight but circulating insulin was increased by ~50%"},
    {"id": "radiation-dose-iss", "risks": ["risk-of-radiation-induced-cancers"], "metrics": ["radiation_dose_rate"],
     "statement": "Absorbed dose for a six-month ISS stay is about 30-120 mGy; a Mars mission is expected to be 175-450 mGy.",
     "values": {"iss_6mo_mgy_low": 30, "iss_6mo_mgy_high": 120, "mars_mgy_low": 175, "mars_mgy_high": 450},
     "source": "Cardio_Risk_EB_2022_FINAL_4-3-2023.pdf",
     "anchor": "30-120 mGy for six-month stays"},
    {"id": "vitamin-d", "risks": ["risk-of-spaceflight-induced-bone-changes"], "metrics": [],
     "statement": "NASA-STD-3001 bone-loss brief: optimal 25-OH vitamin D range is 35-90 ng/mL.",
     "values": {"low_ng_ml": 35, "high_ng_ml": 90}, "source": "ochmo-tb-030-bone-loss.pdf",
     "anchor": "The optimal/desired range for 25-OH Vitamin D is 35-90 ng/ml"},
    {"id": "sunrises", "risks": ["risk-from-inadequate-sleep-and-irregular-schedules"],
     "metrics": ["sleep_duration", "sleep_midpoint"],
     "statement": "ISS crews see 16 sunrises and sunsets a day, which can disrupt the sleep-wake cycle.",
     "values": {"sunrises_per_day": 16}, "source": "risk-from-inadequate-sleep-and-irregular-schedules",
     "anchor": "Astronauts witness 16 sunrises and sunsets per day aboard the space station"},
    {"id": "neutron-share", "risks": ["risk-of-radiation-induced-cancers"], "metrics": ["radiation_dose_rate"],
     "statement": "CSA: neutrons make up about 30% of total radiation on the ISS and need dedicated measurement.",
     "values": {"neutron_share_pct": 30}, "source": "csa-radiation",
     "anchor": "contributes to about 30% of total radiation on the ISS"},
]

# How each NASA risk maps to what this tool can observe. "monitoring" is our assessment.
#   direct   - measured by the tool's sensors / check-ins
#   partial  - some related indicators, not the risk itself
#   clinical - needs an exam or lab test the tool cannot perform (shown as guidance only)
#   none     - operational risk outside personal health monitoring
RISK_MONITORING = {
    "risk-of-cardiovascular-adaptations": {"monitoring": "direct", "hazards": ["Gravity Fields", "Space Radiation"],
        "metrics": ["resting_heart_rate", "hrv_sdnn", "blood_pressure_systolic", "blood_pressure_diastolic", "oxygen_saturation"]},
    "risk-from-inadequate-sleep-and-irregular-schedules": {"monitoring": "direct", "hazards": ["Isolation and Confinement"],
        "metrics": ["sleep_duration", "sleep_midpoint", "sleep_efficiency", "fatigue_score", "workload_tlx"]},
    "risk-of-behavioral-conditions-and-psychiatric-disorders": {"monitoring": "direct", "hazards": ["Isolation and Confinement", "Distance from Earth"],
        "metrics": ["mood_score", "stress_score", "reaction_time"]},
    "risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness": {"monitoring": "direct", "hazards": ["Gravity Fields"],
        "metrics": ["exercise_minutes", "steps", "resting_heart_rate"]},
    "risk-of-spaceflight-induced-bone-changes": {"monitoring": "partial", "hazards": ["Gravity Fields"],
        "metrics": ["exercise_minutes"], "note": "Bone density needs imaging (DXA/QCT); the tool projects expected loss from NASA's published rate and tracks the exercise countermeasure."},
    "risk-of-inadequate-food-and-nutrition": {"monitoring": "partial", "hazards": ["Distance from Earth"],
        "metrics": ["body_mass", "blood_glucose"]},
    "risk-of-altered-immune-system-responses": {"monitoring": "partial", "hazards": ["Hostile/Closed Environments", "Space Radiation"],
        "metrics": ["body_temperature"], "note": "Immune markers need blood/saliva tests; body temperature against the personal baseline is an early sign of illness."},
    "risk-of-host-microorganism-interactions": {"monitoring": "partial", "hazards": ["Hostile/Closed Environments"],
        "metrics": ["body_temperature", "cabin_humidity"]},
    "risk-of-radiation-induced-cancers": {"monitoring": "partial", "hazards": ["Space Radiation"],
        "metrics": ["radiation_dose_rate"], "note": "Tracks cumulative absorbed dose against NASA's published mission ranges; cancer risk itself is long-term and not measurable in flight."},
    "risk-of-hypoxia": {"monitoring": "partial", "hazards": ["Hostile/Closed Environments"],
        "metrics": ["oxygen_saturation", "cabin_pressure"]},
    "risk-of-altered-sensorimotor-and-vestibular-function": {"monitoring": "partial", "hazards": ["Gravity Fields"],
        "metrics": ["reaction_time"], "note": "Balance and motion sickness need dedicated tests; reaction time is a rough proxy."},
    "risk-of-spaceflight-associated-neuro-ocular-syndrome-sans": {"monitoring": "clinical", "hazards": ["Gravity Fields"],
        "metrics": [], "note": "Requires eye exams (ultrasound, OCT, fundoscopy)."},
    "risk-of-decompression-sickness": {"monitoring": "none", "hazards": ["Hostile/Closed Environments"], "metrics": ["cabin_pressure"]},
    "risk-of-injury-and-compromised-performance-from-extravehicular-activity-eva": {"monitoring": "none", "hazards": ["Hostile/Closed Environments", "Gravity Fields"], "metrics": []},
    "risk-of-injury-from-dynamic-loads": {"monitoring": "none", "hazards": ["Gravity Fields"], "metrics": []},
    "risk-of-inadequate-systems-operations-support": {"monitoring": "none", "hazards": ["Distance from Earth"], "metrics": ["workload_tlx"]},
    "risk-of-inadequate-teamwork": {"monitoring": "none", "hazards": ["Isolation and Confinement"], "metrics": ["stress_score"]},
}
