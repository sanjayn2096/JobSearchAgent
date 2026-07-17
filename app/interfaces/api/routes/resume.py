from __future__ import annotations

import dataclasses
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.agents.nodes.parse_resume import parse_resume_text
from app.infrastructure.resume.parser import extract_text
from app.infrastructure.storage.run_store import save_profile
from app.interfaces.api.dependencies import get_llm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["resume"])


@router.post("/resume", status_code=status.HTTP_200_OK)
async def upload_resume(file: UploadFile, llm=Depends(get_llm)) -> dict:
    """Upload a PDF or DOCX resume. Parses it and stores the profile for daily use."""
    data = await file.read()
    try:
        text = extract_text(data, file.filename or "resume")
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    if not text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Could not extract text from file")

    try:
        profile = await parse_resume_text(text, llm)
    except Exception as exc:
        logger.exception("Resume parsing failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Resume parsing failed") from exc

    save_profile(dataclasses.asdict(profile))
    return {"status": "ok", "headline": profile.headline, "skills_found": len(profile.skills)}
