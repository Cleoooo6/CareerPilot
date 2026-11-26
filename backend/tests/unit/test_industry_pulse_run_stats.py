from app.services.industry_pulse_service import _run_out


def test_legacy_run_stats_are_not_trusted():
    run = {
        "id": "legacy",
        "status": "succeeded",
        "articles_fetched": 20,
        "articles_inserted": 5,
        "articles_duplicates": 15,
        "sources_total": 34,
        "sources_ok": 1,
        "sources_failed": 0,
        "details": [
            {
                "source": "chinanews-scroll",
                "entries": 20,
                "inserted": 5,
                "duplicates": 15,
            }
        ],
    }
    out = _run_out(run)
    assert out["stats_legacy"] is True
    assert out["articles_skipped_limit"] is None
    assert out["sources_skipped"] == 33
    assert out["articles_duplicates"] == 15


def test_new_run_reports_exact_skips_and_pending_sources():
    run = {
        "id": "fresh",
        "status": "succeeded",
        "articles_fetched": 20,
        "articles_inserted": 5,
        "articles_duplicates": 0,
        "details": [
            {
                "source": "chinanews-scroll",
                "status": "ok",
                "entries": 20,
                "processed": 5,
                "inserted": 5,
                "duplicates": 0,
                "skipped_limit": 15,
            },
            {
                "source": "chinanews-china",
                "status": "skipped",
                "entries": 0,
                "processed": 0,
                "inserted": 0,
                "duplicates": 0,
                "skipped_limit": 0,
            },
        ],
    }
    out = _run_out(run)
    assert out["stats_legacy"] is False
    assert out["articles_skipped_limit"] == 15
    assert out["sources_skipped"] == 1
    assert out["articles_duplicates"] == 0


def test_run_without_details_is_not_marked_legacy():
    out = _run_out({"id": "empty", "details": [], "articles_duplicates": 0})
    assert out["stats_legacy"] is False
    assert out["articles_skipped_limit"] == 0
    assert out["sources_skipped"] == 0