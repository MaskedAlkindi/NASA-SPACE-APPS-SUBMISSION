def test_site_gate_stays_open(client, monkeypatch):
    monkeypatch.setenv("SITE_PASSWORD", "staydetermined")
    assert client.get("/api/v1/site/check").status_code == 204
