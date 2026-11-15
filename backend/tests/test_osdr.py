from pathlib import Path

from app.modules.nasa_osdr.client import OSDRClient, OSDRUnavailable
from app.modules.nasa_osdr.module import NasaOSDRModule, compute_findings
from app.modules.nasa_osdr.parser import parse_long_csv, phase_of

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "data" / "nasa_snapshot"


def test_phase_mapping():
    assert phase_of("L-92") == "preflight" and phase_of("R+1") == "postflight" and phase_of("X") == "unknown"


def test_parse_cbc_snapshot_without_inventing_values():
    raw = (SNAP / "OSD-569" / "LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv").read_bytes()
    rows, notes = parse_long_csv(raw)
    assert rows and all(isinstance(r["value"], float) for r in rows)
    assert {r["subject_id"] for r in rows} == {"C001", "C002", "C003", "C004"}
    data_lines = raw.decode("utf-8-sig").strip().splitlines()[1:]
    assert len(rows) <= len(data_lines)


def test_parser_rejects_unknown_layout():
    rows, notes = parse_long_csv(b"foo,bar\n1,2\n")
    assert rows == [] and "unsupported layout" in notes[0]


def test_findings_are_descriptive():
    obs = [{"analyte": "X", "subject_id": f"C{i}", "timepoint": tp, "value": v, "unit": "u"}
           for i in range(4) for tp, v in (("L-3", 10.0), ("L-44", 10.0), ("R+1", 13.0))]
    f = compute_findings("OSD-1", obs, "f.csv")[0]
    assert f["mean_pct_change_R+1_vs_preflight"] == 30.0 and f["notable"] and f["n_subjects"] == 4


def test_offline_import_uses_snapshot(tmp_path):
    client = OSDRClient("https://osdr.nasa.gov", tmp_path, SNAP, online=False)
    res = NasaOSDRModule(client=client).run_import()
    accs = {d["accession"]: d for d in res["datasets"]}
    assert accs["OSD-569"]["status"] == "downloaded" and accs["OSD-575"]["status"] == "downloaded"
    assert accs["OSD-575"]["doi"] and "open" in accs["OSD-575"]["license"].lower()
    assert res["observations"] and res["origins"] == ["snapshot"]
    assert any("search" in e for e in res["errors"])  # discovery degrades gracefully offline


def test_unavailable_without_snapshot(tmp_path):
    client = OSDRClient("https://osdr.nasa.gov", tmp_path, None, online=False)
    try:
        client.study_metadata("OSD-569")
        assert False, "should raise"
    except OSDRUnavailable:
        pass
    res = NasaOSDRModule(client=client).run_import()
    assert res["datasets"] == [] and res["errors"]
