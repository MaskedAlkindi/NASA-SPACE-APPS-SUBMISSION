# Bundled NASA OSDR snapshot

Files in this folder were downloaded unmodified from the public NASA Open Science
Data Repository (https://osdr.nasa.gov) on 2026-11-14 so that the BATMAN demo works
offline. They are used only when the live OSDR API and the runtime cache
(`NASA_CACHE_DIR`) are unavailable.

| Accession | File | Source URL |
|---|---|---|
| OSD-569 | LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv | https://osdr.nasa.gov/bio/repo/data/studies/OSD-569 |
| OSD-575 | LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv | https://osdr.nasa.gov/bio/repo/data/studies/OSD-575 |
| OSD-575 | LSDS-8_Multiplex_serum.cardiovascular.EvePanel_SUBMITTED.csv | https://osdr.nasa.gov/bio/repo/data/studies/OSD-575 |

`metadata.json` / `files.json` are the raw responses of
`/osdr/data/osd/meta/{n}` and `/osdr/data/osd/files/{n}`.

Data: SpaceX Inspiration4 crew (n=4), 3-day LEO mission, Sept 2021.
Associated publication DOI: 10.1038/s41586-024-07639-y (Overbey et al., Nature 2024).
Public NASA open data; cite the OSDR accession and the publication when reusing.
