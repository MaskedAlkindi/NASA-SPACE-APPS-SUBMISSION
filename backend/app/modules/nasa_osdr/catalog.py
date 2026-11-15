"""Which NASA OSDR datasets the tool imports.

Selection rationale: OSDR is dominated by omics studies on model organisms.
The most directly relevant *human* clinical data with small, parseable public
files are the SpaceX Inspiration4 crew lab panels (n=4, 3-day LEO flight).
They cannot train a wearable-based predictor (no HR/HRV/sleep, 4 people,
6 timepoints) so HEALTH-01 uses them as scientific context, not training data.
"""
from __future__ import annotations

OSDR_LICENSE = ("NASA OSDR public data - released under NASA's open science / open data policy without "
                "access restrictions. Cite the study accession and associated publication.")

CURATED_DATASETS = [
    {
        "accession": "OSD-569", "organism": "Homo sapiens",
        "relevance": "Human crew complete blood count (CBC) before and after spaceflight (Inspiration4).",
        "files": ["LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv"],
        "topics": ["immune", "blood", "cardiovascular"],
    },
    {
        "accession": "OSD-575", "organism": "Homo sapiens",
        "relevance": "Human crew comprehensive metabolic panel and serum cardiovascular biomarker panel (Inspiration4).",
        "files": ["LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv",
                  "LSDS-8_Multiplex_serum.cardiovascular.EvePanel_SUBMITTED.csv"],
        "topics": ["metabolic", "cardiovascular", "inflammation"],
    },
]

# Metadata-only discovery (search API). Results are listed for browsing; data files are not downloaded.
DISCOVERY_TERMS = ["Inspiration4", "astronaut", "human spaceflight", "cardiovascular microgravity",
                   "sleep spaceflight", "space radiation"]
