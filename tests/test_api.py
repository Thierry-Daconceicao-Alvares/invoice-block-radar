from fastapi.testclient import TestClient

from api.main import OrderLine, app

OrderLineFields = set(OrderLine.model_fields) - {"example_id"}

client = TestClient(app)


def test_health():
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["open_blocks"] > 0


def test_queue_filters_by_cause_and_counts_every_cause():
    body = client.get("/api/queue", params={"cause": "likely_mismatch", "limit": 5}).json()
    assert len(body["items"]) == 5
    assert {item["cause"] for item in body["items"]} == {"likely_mismatch"}
    assert set(body["by_cause"]) == {"likely_mismatch", "routine_check", "waiting_for_goods"}


def test_a_case_comes_with_a_checked_note():
    first = client.get("/api/queue", params={"limit": 1}).json()["items"][0]
    body = client.get(f"/api/cases/{first['case_id']}").json()
    assert body["checks"] == []
    assert body["note"]["summary"]
    assert body["note_source"] in {"template", "recorded ministral-14b-latest", "mistral"}


def test_a_recorded_note_is_replayed():
    recorded = next(i for i in client.get("/api/queue", params={"limit": 200}).json()["items"] if i["has_recorded_note"])
    assert client.get(f"/api/cases/{recorded['case_id']}").json()["note_source"].startswith("recorded")


def test_unknown_case_is_a_404():
    assert client.get("/api/cases/nope").status_code == 404


def test_forecast_scores_an_example_line():
    example = client.get("/api/forecast/options").json()["examples"][0]
    line = {k: v for k, v in example.items() if k in OrderLineFields}
    body = client.post("/api/forecast", json=line).json()
    assert 0 <= body["risk"] <= 1
    assert len(body["reasons"]) == 5
    assert body["band"] in {"low", "medium", "high"}


def test_queue_can_show_only_notes_written_by_the_model():
    body = client.get("/api/queue", params={"recorded": True, "limit": 200}).json()
    assert body["total"] == 30
    assert all(item["has_recorded_note"] for item in body["items"])


def test_an_example_line_is_scored_with_the_history_of_its_own_day():
    example = client.get("/api/forecast/options").json()["examples"][0]
    line = {k: v for k, v in example.items() if k in OrderLineFields}
    body = client.post("/api/forecast", json=line | {"example_id": example["case_id"]}).json()
    assert body["history_as_of"] == example["po_created_at"][:10]
    assert body["history"]["vendor"]["paid_before"] == (example["vendor_paid_before"] or 0)
    edited = client.post("/api/forecast", json=line | {"example_id": example["case_id"], "vendor": "vendorID_0000"}).json()
    assert edited["history_as_of"] == "2018-10-15"
