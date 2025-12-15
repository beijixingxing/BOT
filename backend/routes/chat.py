from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from backend.schemas import ChatRequest, ChatResponse
from backend.services import ChatService
import json

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    service = ChatService(db, bot_id=request.bot_id)
    result = await service.chat(
        discord_id=request.discord_id,
        username=request.username,
        channel_id=request.channel_id,
        message=request.message,
        context_messages=[m.model_dump() for m in request.context_messages],
        pinned_messages=request.pinned_messages,
        reply_content=request.reply_content,
        image_urls=request.image_urls
    )
    return ChatResponse(**result)


@router.post("/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    service = ChatService(db, bot_id=request.bot_id)
    
    async def generate():
        async for chunk in service.chat_stream(
            discord_id=request.discord_id,
            username=request.username,
            channel_id=request.channel_id,
            message=request.message,
            context_messages=[m.model_dump() for m in request.context_messages],
            pinned_messages=request.pinned_messages,
            reply_content=request.reply_content,
            image_urls=request.image_urls
        ):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
