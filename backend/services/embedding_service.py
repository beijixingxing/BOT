from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import SystemConfig
from typing import List, Optional
import numpy as np


class EmbeddingService:
    """向量化服务，使用硅基流动或其他OpenAI兼容的embedding API"""
    
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model or "BAAI/bge-m3"
        self._client = None
    
    @classmethod
    async def from_db(cls, db: AsyncSession) -> "EmbeddingService":
        """从数据库加载配置创建实例"""
        async def get_config(key: str) -> Optional[str]:
            result = await db.execute(
                select(SystemConfig).where(SystemConfig.key == key)
            )
            config = result.scalar_one_or_none()
            return config.value if config else None
        
        base_url = await get_config("embedding_base_url")
        api_key = await get_config("embedding_api_key")
        model = await get_config("embedding_model")
        
        # 如果embedding没配置，回退到LLM配置
        if not base_url:
            base_url = await get_config("llm_base_url")
        if not api_key:
            api_key = await get_config("llm_api_key")
        
        return cls(base_url=base_url, api_key=api_key, model=model)
    
    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            if not self.base_url or not self.api_key:
                raise ValueError("Embedding API未配置，请在API设置中配置向量化服务")
            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key
            )
        return self._client
    
    async def embed(self, text: str) -> List[float]:
        """将单个文本转换为向量"""
        response = await self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量将文本转换为向量"""
        if not texts:
            return []
        
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts
        )
        return [item.embedding for item in response.data]
    
    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    @staticmethod
    def find_most_similar(
        query_embedding: List[float],
        embeddings: List[List[float]],
        top_k: int = 3,
        threshold: float = 0.5
    ) -> List[tuple]:
        """找出最相似的向量，返回 [(index, score), ...]"""
        if not embeddings:
            return []
        
        scores = []
        for i, emb in enumerate(embeddings):
            score = EmbeddingService.cosine_similarity(query_embedding, emb)
            if score >= threshold:
                scores.append((i, score))
        
        # 按相似度降序排序
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
