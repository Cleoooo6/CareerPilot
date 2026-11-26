def test_industry_trends_empty_state_is_honest(client):
    payload = client.get("/api/market/industry-trends").json()["data"]
    assert payload["items"] == []
    assert len(payload["industry_catalog"]) == 16
    assert len(payload["insufficient_industries"]) == 16
    assert payload["months"] == 12
    assert payload["warnings"] == []


def test_personal_trends_without_profile_does_not_invent_match(client):
    payload = client.get(
        "/api/market/industry-trends/personal",
        headers={"X-User-Id": "trends-no-profile"},
    ).json()["data"]
    assert payload["profile_sufficient"] is False
    assert payload["items"] == []
    assert "目标岗位" in payload["profile_missing"]
    assert "不会凭空推断" in payload["insufficient_reason"]