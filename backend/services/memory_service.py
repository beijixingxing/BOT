from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from database.models import Memory, User, Conversation
from typing import Optional, List
from openai import AsyncOpenAI
from config import get_settings

settings = get_settings()


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key
        )
    
    async def get_user_memory(self, user_id: int) -> Optional[Memory]:
        result = await self.db.execute(
            select(Memory).where(Memory.user_id == user_id).order_by(desc(Memory.updated_at))
        )
        return result.scalar_one_or_none()
    
    async def get_memory_by_discord_id(self, discord_id: str) -> Optional[Memory]:
        result = await self.db.execute(
            select(Memory).join(User).where(User.discord_id == discord_id).order_by(desc(Memory.updated_at))
        )
        return result.scalar_one_or_none()
    
    async def save_conversation(self, user_id: int, channel_id: str, role: str, content: str):
        conv = Conversation(
            user_id=user_id,
            channel_id=channel_id,
            role=role,
            content=content
        )
        self.db.add(conv)
        await self.db.commit()
    
    async def get_recent_conversations(self, user_id: int, limit: int = 50) -> List[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.created_at))
            .limit(limit)
        )
        convs = result.scalars().all()
        return list(reversed(convs))
    
    async def summarize_user(self, user_id: int) -> Optional[Memory]:
        conversations = await self.get_recent_conversations(user_id, limit=100)
        if not conversations:
            return None
        
        conv_text = "\n".join([
            f"{c.role}: {c.content}" for c in conversations
        ])
        
        prompt = f"""根据以下对话历史，总结这位用户的特征、喜好和交流风格。请用中文回答。

对话历史：
{conv_text}

请分别总结：
1. 用户特征概述
2. 性格特点
3. 喜好偏好"""

        try:
            response = await self.client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            summary_text = response.choices[0].message.content
            
            existing_memory = await self.get_user_memory(user_id)
            if existing_memory:
                existing_memory.summary = summary_text
                await self.db.commit()
                await self.db.refresh(existing_memory)
                return existing_memory
            else:
                memory = Memory(
                    user_id=user_id,
                    summary=summary_text
                )
                self.db.add(memory)
                await self.db.commit()
                await self.db.refresh(memory)
                return memory
        except Exception as e:
            print(f"Error summarizing user: {e}")
            return None
    
    async def get_all_memories(self, skip: int = 0, limit: int = 100):
        result = await self.db.execute(
            select(Memory).join(User).offset(skip).limit(limit)
        )
        return result.scalars().all()
