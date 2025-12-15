from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from database.models import ChannelWhitelist
from typing import Optional, List


class ChannelService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def add_channel(
        self,
        bot_id: str,
        channel_id: str,
        guild_id: str,
        channel_name: str = None,
        added_by: str = None
    ) -> ChannelWhitelist:
        existing = await self.get_by_channel_id(bot_id, channel_id)
        if existing:
            return existing
        
        channel = ChannelWhitelist(
            bot_id=bot_id,
            channel_id=channel_id,
            guild_id=guild_id,
            channel_name=channel_name,
            added_by=added_by
        )
        self.db.add(channel)
        await self.db.commit()
        await self.db.refresh(channel)
        return channel
    
    async def remove_channel(self, bot_id: str, channel_id: str) -> bool:
        result = await self.db.execute(
            delete(ChannelWhitelist).where(
                and_(
                    ChannelWhitelist.bot_id == bot_id,
                    ChannelWhitelist.channel_id == channel_id
                )
            )
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def is_whitelisted(self, bot_id: str, channel_id: str) -> bool:
        result = await self.db.execute(
            select(ChannelWhitelist).where(
                and_(
                    ChannelWhitelist.bot_id == bot_id,
                    ChannelWhitelist.channel_id == channel_id
                )
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def get_by_channel_id(self, bot_id: str, channel_id: str) -> Optional[ChannelWhitelist]:
        result = await self.db.execute(
            select(ChannelWhitelist).where(
                and_(
                    ChannelWhitelist.bot_id == bot_id,
                    ChannelWhitelist.channel_id == channel_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, bot_id: str = None, guild_id: str = None, skip: int = 0, limit: int = 100) -> List[ChannelWhitelist]:
        query = select(ChannelWhitelist)
        if bot_id:
            query = query.where(ChannelWhitelist.bot_id == bot_id)
        if guild_id:
            query = query.where(ChannelWhitelist.guild_id == guild_id)
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_bot_channels(self, bot_id: str, guild_id: str = None) -> List[ChannelWhitelist]:
        query = select(ChannelWhitelist).where(ChannelWhitelist.bot_id == bot_id)
        if guild_id:
            query = query.where(ChannelWhitelist.guild_id == guild_id)
        result = await self.db.execute(query)
        return result.scalars().all()
