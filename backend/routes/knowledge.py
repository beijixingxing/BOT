from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from backend.schemas import (
    KnowledgeBaseCreate, KnowledgeBaseUpdate, KnowledgeBaseResponse
)
from backend.services import KnowledgeService
from config import get_settings
from typing import List

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
settings = get_settings()


async def verify_admin(x_admin_secret: str = Header(None)):
    if x_admin_secret != settings.admin_password:
        raise HTTPException(status_code=403, detail="Invalid admin password")
    return True


@router.post("/", response_model=KnowledgeBaseResponse)
async def create_knowledge(
    request: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin)
):
    service = KnowledgeService(db)
    return await service.create(
        title=request.title,
        content=request.content,
        keywords=request.keywords,
        category=request.category
    )


@router.get("/", response_model=List[KnowledgeBaseResponse])
async def get_all_knowledge(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    service = KnowledgeService(db)
    return await service.get_all(skip, limit, active_only)


@router.get("/search", response_model=List[KnowledgeBaseResponse])
async def search_knowledge(
    query: str,
    limit: int = 5,
    db: AsyncSession = Depends(get_db)
):
    service = KnowledgeService(db)
    return await service.search(query, limit)


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge(
    kb_id: int,
    db: AsyncSession = Depends(get_db)
):
    service = KnowledgeService(db)
    kb = await service.get_by_id(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return kb


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge(
    kb_id: int,
    request: KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin)
):
    service = KnowledgeService(db)
    kb = await service.update(
        kb_id,
        title=request.title,
        content=request.content,
        keywords=request.keywords,
        category=request.category,
        is_active=request.is_active
    )
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return kb


@router.delete("/{kb_id}")
async def delete_knowledge(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin)
):
    service = KnowledgeService(db)
    success = await service.delete(kb_id)
    if not success:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return {"success": True}
