import asyncio
import io
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
from xml.etree import ElementTree

from pypdf import PdfReader

from app.core.config import get_settings
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.llm import LLMClient, LLMError, get_llm_client
from app.db.profile_repositories import profile_repository, resume_repository
from app.db.repositories import user_repository
from app.schemas.profile import (
    BasicInfo,
    CareerGoals,
    EducationItem,
    ExperienceItem,
    ProfileData,
    ProjectItem,
    SkillItem,
)
from app.services.profile_metadata import mark_resume_skills

ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",
    "",
}
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_PDF_PAGES = 20

RESUME_PARSE_SYSTEM_PROMPT = """你是 CareerPilot AI 的简历结构化解析器。
只提取简历文本中明确存在的信息，不得编造姓名、学历、经历、技能或成果。
没有出现的字段留空或返回空数组。只输出 JSON 对象，字段符合给定 Schema。
不要输出 Markdown、解释或额外字段。"""


class ResumeStorage:
    def __init__(self, base_dir: str | Path | None = None) -> None:
        settings = get_settings()
        configured = base_dir or settings.resume_storage_dir
        default = Path(tempfile.gettempdir()) / "careerpilot_resumes"
        self.base = Path(configured or default).resolve()
        self.base.mkdir(parents=True, exist_ok=True)
        try:
            self.base.chmod(0o700)
        except OSError:
            pass

    def save(self, data: bytes, suffix: str) -> str:
        name = f"{uuid4().hex}{suffix}"
        path = (self.base / name).resolve()
        if path.parent != self.base:
            raise AppError("RESUME_STORAGE_ERROR", "简历存储路径不安全", status_code=500)
        with path.open("xb") as handle:
            handle.write(data)
        return name

    def delete(self, name: str) -> None:
        if not name:
            return
        path = (self.base / Path(name).name).resolve()
        if path.parent == self.base:
            path.unlink(missing_ok=True)


class ResumeService:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        storage: ResumeStorage | None = None,
    ) -> None:
        self.llm = llm_client or get_llm_client()
        self.storage = storage or ResumeStorage()
        self.settings = get_settings()

    async def ensure_user_id(self, external_id: str) -> UUID:
        user = await asyncio.to_thread(user_repository.ensure_user, external_id)
        return user["id"]

    async def upload(
        self,
        user_id: UUID,
        *,
        filename: str,
        content_type: str | None,
        data: bytes,
    ) -> dict[str, Any]:
        suffix = self._validate_upload(filename, content_type, data)
        stored_name = ""
        resume_id: UUID | None = None
        try:
            stored_name = await asyncio.to_thread(self.storage.save, data, suffix)
            row = await asyncio.to_thread(
                resume_repository.create,
                user_id,
                original_filename=filename,
                stored_filename=stored_name,
                file_size=len(data),
                mime_type=(content_type or "").split(";")[0].strip(),
                parse_mode=self.llm.mode,
                provider=self.llm.settings.llm_provider,
                model=self.llm.settings.llm_model,
            )
            resume_id = row["id"]
            text = await asyncio.to_thread(self._extract_text, data, suffix)
            if not text.strip():
                raise AppError("RESUME_TEXT_EMPTY", "简历中未提取到可用文本", status_code=422)
            text = text[: self.settings.resume_max_text_chars]
            draft = await self._parse_text(text)
            updated = await asyncio.to_thread(
                resume_repository.update_parsed,
                user_id,
                resume_id,
                draft.model_dump(mode="json"),
                len(text),
            )
            if updated is None:
                raise AppError("RESUME_PARSE_FAILED", "简历解析状态更新失败", status_code=500)
            return updated
        except Exception as exc:
            if resume_id is not None:
                await asyncio.to_thread(
                    resume_repository.mark_failed,
                    user_id,
                    resume_id,
                    exc.code if isinstance(exc, AppError) else type(exc).__name__,
                    exc.message if isinstance(exc, AppError) else "简历解析失败",
                )
            if stored_name:
                await asyncio.to_thread(self.storage.delete, stored_name)
            raise

    async def list_resumes(self, user_id: UUID) -> list[dict[str, Any]]:
        return await asyncio.to_thread(resume_repository.list_for_user, user_id)

    async def get_resume(self, user_id: UUID, resume_id: UUID) -> dict[str, Any]:
        row = await asyncio.to_thread(resume_repository.get, user_id, resume_id)
        if row is None:
            raise NotFoundError("简历解析记录不存在")
        return row

    async def update_draft(
        self, user_id: UUID, resume_id: UUID, data: ProfileData
    ) -> dict[str, Any]:
        row = await asyncio.to_thread(
            resume_repository.update_draft,
            user_id,
            resume_id,
            data.model_dump(mode="json"),
        )
        if row is None:
            raise ConflictError("简历解析结果已确认、已放弃或不存在")
        return row

    async def confirm(
        self,
        user_id: UUID,
        resume_id: UUID,
        *,
        sections: list[str],
        draft: ProfileData | None = None,
    ) -> dict[str, Any]:
        row = await self.get_resume(user_id, resume_id)
        if row["status"] != "pending_review":
            raise ConflictError("简历解析结果不在待审核状态")
        if draft is None:
            draft = ProfileData.model_validate(row["parsed_data"])
        marked = ProfileData.model_validate(
            mark_resume_skills(draft.model_dump(mode="json"))
        )
        existing = await asyncio.to_thread(profile_repository.get_data, user_id)
        merged = merge_profile(existing or {}, marked, sections)
        profile = await asyncio.to_thread(
            profile_repository.upsert, user_id, merged, "resume"
        )
        updated = await asyncio.to_thread(
            resume_repository.set_status, user_id, resume_id, "confirmed"
        )
        if updated is None:
            raise ConflictError("简历解析结果状态冲突")
        await asyncio.to_thread(self.storage.delete, row.get("stored_filename", ""))
        return profile

    async def discard(self, user_id: UUID, resume_id: UUID) -> dict[str, Any]:
        row = await self.get_resume(user_id, resume_id)
        if row["status"] != "pending_review":
            raise ConflictError("简历解析结果不在待审核状态")
        updated = await asyncio.to_thread(
            resume_repository.set_status, user_id, resume_id, "discarded"
        )
        if updated is None:
            raise ConflictError("简历解析结果状态冲突")
        await asyncio.to_thread(self.storage.delete, row.get("stored_filename", ""))
        return updated

    async def _parse_text(self, text: str) -> ProfileData:
        mock_payload = self._mock_draft(text) if self.llm.mode == "mock" else None
        try:
            result = await asyncio.to_thread(
                self.llm.complete_structured_with_meta,
                RESUME_PARSE_SYSTEM_PROMPT,
                f"简历文本：\n{text}",
                ProfileData,
                mock_payload=mock_payload,
            )
        except LLMError as exc:
            raise AppError(exc.code, exc.message, status_code=exc.status_code) from exc
        return result.value

    def _validate_upload(
        self, filename: str, content_type: str | None, data: bytes
    ) -> str:
        if not filename:
            raise AppError("RESUME_INVALID_FORMAT", "缺少文件名", status_code=422)
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise AppError(
                "RESUME_INVALID_FORMAT", "仅支持 PDF 或 DOCX 简历", status_code=415
            )
        if not data:
            raise AppError("RESUME_INVALID_FORMAT", "简历文件为空", status_code=422)
        if len(data) > self.settings.resume_max_bytes:
            raise AppError(
                "RESUME_TOO_LARGE",
                f"简历文件不能超过 {self.settings.resume_max_bytes // (1024 * 1024)}MB",
                status_code=413,
            )
        mime = (content_type or "").split(";")[0].strip().lower()
        if mime not in ALLOWED_MIME:
            raise AppError(
                "RESUME_INVALID_FORMAT",
                "简历 MIME 类型不受支持",
                status_code=415,
            )
        if suffix == ".pdf":
            if not data.startswith(b"%PDF-"):
                raise AppError(
                    "RESUME_INVALID_FORMAT", "PDF 文件头校验失败", status_code=422
                )
        else:
            if not zipfile.is_zipfile(io.BytesIO(data)):
                raise AppError(
                    "RESUME_INVALID_FORMAT", "DOCX 文件结构校验失败", status_code=422
                )
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise AppError(
                    "RESUME_INVALID_FORMAT", "DOCX 文件结构不完整", status_code=422
                )
        return suffix

    def _extract_text(self, data: bytes, suffix: str) -> str:
        try:
            if suffix == ".pdf":
                return _extract_pdf(data)
            return _extract_docx(data)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                "RESUME_INVALID_CONTENT", "简历文本提取失败", status_code=422
            ) from exc

    def _mock_draft(self, text: str) -> dict[str, Any]:
        def pick(pattern: str) -> str:
            match = re.search(pattern, text, flags=re.MULTILINE)
            return match.group(1).strip() if match else ""

        def split_items(value: str) -> list[str]:
            return [item.strip() for item in re.split(r"[、,，;；]", value) if item.strip()]

        name = pick(r"姓名\s*[:：]\s*([^\n]+)")
        target_role = pick(r"目标岗位\s*[:：]\s*([^\n]+)")
        education_level = pick(r"学历\s*[:：]\s*([^\n]+)")
        major = pick(r"专业\s*[:：]\s*([^\n]+)")
        location = pick(r"(?:所在地|城市)\s*[:：]\s*([^\n]+)")
        school = pick(r"学校\s*[:：]\s*([^\n]+)")
        graduation = pick(r"毕业时间\s*[:：]\s*([^\n]+)")
        skills_text = pick(r"技能\s*[:：]\s*([^\n]+)")
        project_text = pick(r"(?:项目|项目经历)\s*[:：]\s*([^\n]+)")
        experience_text = pick(r"(?:实习|工作经历)\s*[:：]\s*([^\n]+)")

        skills = [
            SkillItem(
                name=skill,
                proficiency="熟悉",
                evidence="简历解析（Mock）",
            )
            for skill in split_items(skills_text)
        ]
        education = []
        if school or education_level or major:
            education.append(
                EducationItem(
                    school=school,
                    degree=education_level,
                    major=major,
                    end_date=graduation,
                )
            )
        projects = (
            [ProjectItem(name=project_text, description=project_text)] if project_text else []
        )
        experiences = (
            [ExperienceItem(company=experience_text, description=experience_text)]
            if experience_text
            else []
        )
        return ProfileData(
            basic=BasicInfo(
                name=name,
                education_level=education_level,
                major=major,
                graduation_year=int(graduation) if graduation.isdigit() else None,
                location=location,
            ),
            goals=CareerGoals(target_role=target_role),
            skills=skills,
            education=education,
            projects=projects,
            experiences=experiences,
        ).model_dump(mode="json")


def _extract_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise AppError("RESUME_INVALID_CONTENT", "暂不支持加密 PDF", status_code=422)
    parts = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
    return "\n".join(parts)


def _extract_docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    parts = [
        node.text
        for node in root.iter()
        if node.tag.endswith("}t") and node.text and node.text.strip()
    ]
    return "\n".join(parts)


def merge_profile(
    existing: dict[str, Any], draft: ProfileData, sections: list[str]
) -> dict[str, Any]:
    current = ProfileData.model_validate(existing or {}).model_dump(mode="json")
    incoming = draft.model_dump(mode="json")
    selected = set(sections)
    if "basic" in selected:
        for key, value in incoming["basic"].items():
            if value not in (None, ""):
                current["basic"][key] = value
    if "goals" in selected:
        for key, value in incoming["goals"].items():
            if value not in (None, ""):
                current["goals"][key] = value
    if "skills" in selected:
        current["skills"] = _merge_by_key(
            current["skills"], incoming["skills"], key=lambda item: item.get("name", "").lower()
        )
    if "education" in selected:
        current["education"] = _merge_by_key(
            current["education"],
            incoming["education"],
            key=lambda item: (
                item.get("school", ""),
                item.get("degree", ""),
                item.get("major", ""),
            ),
        )
    if "projects" in selected:
        current["projects"] = _merge_by_key(
            current["projects"], incoming["projects"], key=lambda item: item.get("name", "")
        )
    if "experiences" in selected:
        current["experiences"] = _merge_by_key(
            current["experiences"],
            incoming["experiences"],
            key=lambda item: (item.get("company", ""), item.get("position", "")),
        )
    return current


def _merge_by_key(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    key,
) -> list[dict[str, Any]]:
    merged = list(existing)
    index = {key(item): position for position, item in enumerate(merged)}
    for item in incoming:
        item_key = key(item)
        if item_key in index:
            merged[index[item_key]] = item
        else:
            index[item_key] = len(merged)
            merged.append(item)
    return merged


_resume_service: ResumeService | None = None


def get_resume_service() -> ResumeService:
    global _resume_service
    if _resume_service is None:
        _resume_service = ResumeService()
    return _resume_service


def reset_resume_service() -> None:
    global _resume_service
    _resume_service = None
