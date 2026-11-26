from app.industry_pulse.taxonomy import (
    DB_INDUSTRY_IDS,
    INDUSTRIES,
    INDUSTRY_LABELS,
    INDUSTRY_ORDER,
    LEGACY_INDUSTRY_IDS,
    LEGACY_INDUSTRY_MAP,
    MAJORS_NOTE,
    NEW_INDUSTRY_IDS,
)

EXPECTED_IDS = (
    "digital_tech_comms",
    "finance_insurance",
    "manufacturing_industry",
    "energy_environment",
    "auto_smart_mobility",
    "transport_logistics",
    "health_life_sciences",
    "education_research",
    "agriculture_food",
    "consumer_retail_services",
    "real_estate_construction",
    "culture_media_content",
    "arts_design",
    "sports_industry",
    "tourism_hospitality_events",
    "enterprise_professional_services",
)


def test_exactly_16_stable_industry_ids():
    assert INDUSTRY_ORDER == EXPECTED_IDS
    assert len(set(INDUSTRY_ORDER)) == 16
    assert set(INDUSTRY_LABELS) == set(EXPECTED_IDS)


def test_every_industry_has_scope_and_majors():
    for item in INDUSTRIES:
        assert item.scope
        assert len(item.majors) >= 5
        assert len(set(item.majors)) == len(item.majors)
    assert "并非限定范围" in MAJORS_NOTE


def test_legacy_14_mapping_is_explicit_and_safe():
    assert set(LEGACY_INDUSTRY_MAP) == set(LEGACY_INDUSTRY_IDS)
    for old_id, new_id in LEGACY_INDUSTRY_MAP.items():
        if new_id is None:
            assert old_id in {"culture_media_tourism", "professional_services"}
        else:
            assert new_id in NEW_INDUSTRY_IDS


def test_database_check_union_covers_legacy_and_current_ids():
    assert set(DB_INDUSTRY_IDS) == set(LEGACY_INDUSTRY_IDS) | set(EXPECTED_IDS)
    assert len(DB_INDUSTRY_IDS) == 25