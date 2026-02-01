from fastapi import APIRouter
from backend.app.api.v1 import templates, sections, documents, jobs, audit

router = APIRouter(prefix="/api/v1")

router.include_router(templates.router, prefix="/templates", tags=["templates"])
router.include_router(sections.router, prefix="/sections", tags=["sections"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
router.include_router(audit.router, prefix="/audit", tags=["audit"])

__all__ = ["router"]
