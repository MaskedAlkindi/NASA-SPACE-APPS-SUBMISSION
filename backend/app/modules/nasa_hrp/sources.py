"""The official challenge Resources tab, exactly as published.

Source: https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/?tab=resources
(read 2026-11-14). The tab lists five resources. None of them is a dataset; they are
information pages that link to NASA sub-pages and PDF reports, which the snapshot
builder follows one level deep.
"""
from __future__ import annotations

CHALLENGE_URL = "https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/"
RESOURCES_TAB = CHALLENGE_URL + "?tab=resources"

# Indicators named in the challenge Details tab ("Some useful health indicators are ...").
CHALLENGE_INDICATORS = {
    "blood pressure": ["blood_pressure_systolic", "blood_pressure_diastolic"],
    "heart rate": ["heart_rate", "resting_heart_rate"],
    "blood sugar": ["blood_glucose"],
    "body temperature": ["body_temperature"],
    "daily sleep hours": ["sleep_duration"],
    "mood": ["mood_score"],
}

# The five resources on the tab (titles and descriptions as published there).
RESOURCES = [
    {"id": "nasa-hrp-hazards", "agency": "NASA", "title": "5 Hazards of Human Spaceflight",
     "url": "https://www.nasa.gov/hrp/hazards/",
     "tab_description": "Basic information from NASA's human research program on the main hazards that affect humans on space missions."},
    {"id": "nasa-hrp-risks", "agency": "NASA", "title": "Risks of Human Spaceflight",
     "url": "https://www.nasa.gov/hrp/risks/",
     "tab_description": "Basic information from NASA's human research program on the main risks faced by humans on space missions."},
    {"id": "nasa-hrp-ongoing", "agency": "NASA", "title": "Ongoing HRP Research in Space",
     "url": "https://www.nasa.gov/hrp/ongoing-hrp-research/",
     "tab_description": "Articles from ongoing research on NASA's human research program."},
    {"id": "csa-radiation", "agency": "CSA", "title": "Monitoring Radiation for Astronaut Health",
     "url": "https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp",
     "tab_description": "How the CSA monitors space radiation to protect astronaut health on long-duration missions."},
    {"id": "csa-why-science", "agency": "CSA", "title": "Why Do We Conduct Science Experiments in Space?",
     "url": "https://www.asc-csa.gc.ca/eng/iss/science/why-do-we-conduct-science-experiments-in-space.asp",
     "tab_description": "Why the unique environment of space is used for experiments that advance understanding of human health."},
]

NASA_LICENSE = ("NASA content is generally not subject to copyright in the United States (NASA media usage "
                "guidelines). Cite NASA as the source.")
CSA_LICENSE = ("Government of Canada (CSA) content - Crown copyright. Linked and summarised only; "
               "the full text is not redistributed.")

# Sub-page discovery rule (one level below the NASA resources).
SUBPAGE_PATTERN = (r"https://www\.nasa\.gov/(reference/[a-z0-9\-]+|hrp/hazard-[a-z\-]+|"
                   r"hrp/(radiation|human-health-countermeasures|human-factors-and-behavioral-performance))/")
DOCUMENT_PATTERN = r"https://[^\"'\s]+\.pdf"

# NASA's own grouping on the Risks page.
RISK_CATEGORIES = {
    "Risks Involving Human Physiology": [
        "risk-of-altered-immune-system-responses", "risk-of-altered-sensorimotor-and-vestibular-function",
        "risk-of-cardiovascular-adaptations", "risk-of-decompression-sickness",
        "risk-of-host-microorganism-interactions", "risk-of-hypoxia", "risk-of-inadequate-food-and-nutrition",
        "risk-of-injury-and-compromised-performance-from-extravehicular-activity-eva",
        "risk-of-injury-from-dynamic-loads", "risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness",
        "risk-of-spaceflight-associated-neuro-ocular-syndrome-sans", "risk-of-spaceflight-induced-bone-changes"],
    "Risks Involving Behavioral Performance": [
        "risk-from-inadequate-sleep-and-irregular-schedules", "risk-of-behavioral-conditions-and-psychiatric-disorders",
        "risk-of-inadequate-systems-operations-support", "risk-of-inadequate-teamwork"],
    "Risks Involving Space Radiation": ["risk-of-radiation-induced-cancers"],
}
