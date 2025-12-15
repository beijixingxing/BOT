from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User
from typing import Optional


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_or_create_user(self, discord_id: str, username: str = None, display_name: str = None) -> User:
        result = await self.db.execute(
            select(User).where(User.discord_id == discord_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                discord_id=discord_id,
                username=username,
                display_name=display_name
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
        elif username or display_name:
            if username:
                user.username = username
            if display_name:
                user.display_name = display_name
            await self.db.commit()
            await self.db.refresh(user)
        
        return user
    
    async def get_user_by_discord_id(self, discord_id: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.discord_id == discord_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all_users(self, skip: int = 0, limit: int = 100):
        result = await self.db.execute(
            select(User).offset(skip).limit(limit)
        )
        return result.scalars().all()
