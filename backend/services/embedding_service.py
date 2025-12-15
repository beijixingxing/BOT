from openai import AsyncOpenAI
from typing import List, Optional
import numpy as np
from config import get_settings

settings = get_settings()


class EmbeddingService:
    """向量化服务，使用硅基流动或其他OpenAI兼容的embedding API"""
    
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = base_url or settings.embedding_base_url or settings.llm_base_url
        self.api_key = api_key or settings.embedding_api_key or settings.llm_api_key
        self.model = model or settings.embedding_model or "BAAI/bge-m3"
        self._client = None
    
    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
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
