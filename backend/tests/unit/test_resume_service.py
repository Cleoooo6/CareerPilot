from app.core.config import Settings
from app.core.llm import LLMClient
from app.schemas.profile import ProfileData
from app.services.resume_service import (
    ResumeService,
    ResumeStorage,
    _extract_docx,
    _extract_pdf,
    merge_profile,
)
from tests.resume_fixtures import make_docx, make_pdf


def _service(tmp_path):
    settings = Settings(
        _env_file=None,
        llm_mode="mock",
        llm_provider="zhipu",
        llm_model="glm-4.7-flash",
        llm_base_url="https://example.invalid/v4",
        llm_api_key="test-key",
        resume_storage_dir=str(tmp_path),
    )
    return ResumeService(
        llm_client=LLMClient(settings=settings, mock_payload={}),
        storage=ResumeStorage(tmp_path),
    )


def test_docx_and_pdf_text_extraction():
    docx_text = _extract_docx(make_docx("姓名：张三\n技能：Python"))
    assert "姓名：张三" in docx_text
    assert "技能：Python" in docx_text
    assert _extract_pdf(make_pdf("Name: Zhang San")) == "Name: Zhang San"


def test_upload_validation_rejects_wrong_extension_and_spoofed_pdf(tmp_path):
    service = _service(tmp_path)
    try:
        service._validate_upload("resume.txt", "text/plain", b"hello")
    except Exception as exc:
        assert getattr(exc, "code") == "RESUME_INVALID_FORMAT"
    else:
        raise AssertionError("invalid extension accepted")

    try:
        service._validate_upload("resume.pdf", "application/pdf", b"not-pdf")
    except Exception as exc:
        assert getattr(exc, "code") == "RESUME_INVALID_FORMAT"
    else:
        raise AssertionError("spoofed PDF accepted")


def test_merge_profile_only_selected_sections_and_preserves_existing():
    existing = {
        "basic": {"name": "旧姓名", "location": "北京"},
        "goals": {"target_role": "旧目标"},
        "skills": [{"id": "1", "name": "SQL", "proficiency": "熟练", "evidence": "旧"}],
        "education": [],
        "projects": [],
        "experiences": [],
    }
    draft = ProfileData.model_validate(
        {
            "basic": {"name": "新姓名", "location": ""},
            "goals": {"target_role": "新目标"},
            "skills": [
                {"id": "2", "name": "Python", "proficiency": "熟悉", "evidence": "新"}
            ],
        }
    )
    merged = merge_profile(existing, draft, ["basic", "skills"])
    assert merged["basic"]["name"] == "新姓名"
    assert merged["basic"]["location"] == "北京"
    assert merged["goals"]["target_role"] == "旧目标"
    assert [item["name"] for item in merged["skills"]] == ["SQL", "Python"]
