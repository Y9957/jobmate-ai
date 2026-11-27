import pymupdf
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import ExtractedText, ResumeCreate, ResumeOut, ResumeSummary
from app.db import get_session
from app.models import Resume
from app.pipeline.privacy import mask_pii

router = APIRouter(prefix="/api/resumes", tags=["resumes"])

MAX_PDF_BYTES = 5 * 1024 * 1024


@router.post("/extract", response_model=ExtractedText)
async def extract_pdf(file: UploadFile) -> ExtractedText:
    """Extract text from a text-based PDF. Nothing is stored; the user reviews and saves the text."""
    data = await file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "PDF는 5MB 이하만 올릴 수 있습니다")
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            text = "\n".join(page.get_text("text", sort=True) for page in doc).strip()
            pages = doc.page_count
    except (pymupdf.FileDataError, RuntimeError, ValueError) as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "PDF를 읽을 수 없습니다") from e
    if len(text) < 20:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "텍스트를 찾지 못했습니다. 스캔한 이미지 PDF는 지원하지 않습니다 — 텍스트를 직접 붙여넣어 주세요",
        )
    _, found = mask_pii(text)
    return ExtractedText(text=text, pages=pages, pii_found=found)


@router.post("", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
def create_resume(body: ResumeCreate, session: Session = Depends(get_session)) -> Resume:
    masked, _ = mask_pii(body.text)
    resume = Resume(label=body.label, masked_text=masked, is_sample=body.is_sample)
    session.add(resume)
    session.commit()
    session.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeSummary])
def list_resumes(session: Session = Depends(get_session)) -> list[Resume]:
    return list(session.scalars(select(Resume).order_by(Resume.created_at.desc())))


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(resume_id: int, session: Session = Depends(get_session)) -> Resume:
    resume = session.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "이력서를 찾을 수 없습니다")
    return resume


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: int, session: Session = Depends(get_session)) -> None:
    resume = session.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "이력서를 찾을 수 없습니다")
    session.delete(resume)
    session.commit()
