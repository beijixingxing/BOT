from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from database.models import KnowledgeBase
from typing import List, Optional
import jieba


class KnowledgeService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, title: str, content: str, keywords: str = None, category: str = None) -> KnowledgeBase:
        kb = KnowledgeBase(
            title=title,
            content=content,
            keywords=keywords,
            category=category
        )
        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)
        return kb
    
    async def get_by_id(self, kb_id: int) -> Optional[KnowledgeBase]:
        result = await self.db.execute(
            select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        )
        return result.scalar_one_or_none()
    
    async def update(self, kb_id: int, **kwargs) -> Optional[KnowledgeBase]:
        kb = await self.get_by_id(kb_id)
        if not kb:
            return None
        
        for key, value in kwargs.items():
            if value is not None and hasattr(kb, key):
                setattr(kb, key, value)
        
        await self.db.commit()
        await self.db.refresh(kb)
        return kb
    
    async def delete(self, kb_id: int) -> bool:
        kb = await self.get_by_id(kb_id)
        if not kb:
            return False
        
        await self.db.delete(kb)
        await self.db.commit()
        return True
    
    async def search(self, query: str, limit: int = 5) -> List[KnowledgeBase]:
        keywords = list(jieba.cut(query))
        keywords = [k.strip() for k in keywords if len(k.strip()) > 1]
        
        if not keywords:
            return []
        
        conditions = []
        for kw in keywords:
            conditions.append(KnowledgeBase.keywords.contains(kw))
            conditions.append(KnowledgeBase.title.contains(kw))
            conditions.append(KnowledgeBase.content.contains(kw))
        
        result = await self.db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.is_active == True)
            .where(or_(*conditions))
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_all(self, skip: int = 0, limit: int = 100, active_only: bool = False):
        query = select(KnowledgeBase)
        if active_only:
            query = query.where(KnowledgeBase.is_active == True)
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
