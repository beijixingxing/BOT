from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import SystemConfig
from openai import AsyncOpenAI
from typing import List, Dict, Optional
import json
import asyncio


class LLMPoolService:
    """LLM模型池服务，支持多模型/多Key轮流负载均衡"""
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self._pool: List[Dict] = []  # [{base_url, api_key, model, name, enabled}]
        self._current_index = 0
        self._loaded = False
    
    @classmethod
    async def get_instance(cls) -> "LLMPoolService":
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    async def load_from_db(self, db: AsyncSession):
        """从数据库加载模型池配置"""
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == "llm_pool")
        )
        config = result.scalar_one_or_none()
        
        if config and config.value:
            try:
                self._pool = json.loads(config.value)
                self._loaded = True
                print(f"[LLMPool] Loaded {len(self._pool)} models")
            except json.JSONDecodeError:
                self._pool = []
        
        return self._pool
    
    async def save_to_db(self, db: AsyncSession):
        """保存模型池配置到数据库"""
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == "llm_pool")
        )
        config = result.scalar_one_or_none()
        
        if config:
            config.value = json.dumps(self._pool, ensure_ascii=False)
        else:
            config = SystemConfig(
                key="llm_pool",
                value=json.dumps(self._pool, ensure_ascii=False),
                description="LLM模型池配置"
            )
            db.add(config)
        
        await db.commit()
    
    def add_model(self, base_url: str, api_key: str, model: str, name: str = None):
        """添加模型到池"""
        self._pool.append({
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "name": name or model,
            "enabled": True
        })
    
    def remove_model(self, index: int) -> bool:
        """移除模型"""
        if 0 <= index < len(self._pool):
            self._pool.pop(index)
            if self._current_index >= len(self._pool):
                self._current_index = 0
            return True
        return False
    
    def toggle_model(self, index: int, enabled: bool) -> bool:
        """启用/禁用模型"""
        if 0 <= index < len(self._pool):
            self._pool[index]["enabled"] = enabled
            return True
        return False
    
    def get_pool(self) -> List[Dict]:
        """获取模型池列表"""
        return self._pool
    
    def get_enabled_models(self) -> List[Dict]:
        """获取启用的模型列表"""
        return [m for m in self._pool if m.get("enabled", True)]
    
    def get_next(self) -> Optional[Dict]:
        """轮流获取下一个可用模型"""
        enabled = self.get_enabled_models()
        if not enabled:
            return None
        
        # 轮流选择
        self._current_index = self._current_index % len(enabled)
        model = enabled[self._current_index]
        self._current_index = (self._current_index + 1) % len(enabled)
        
        return model
    
    def get_next_from_list(self, models: List[Dict]) -> Dict:
        """从指定列表中轮流选择下一个模型"""
        if not models:
            raise ValueError("模型列表为空")
        
        self._current_index = self._current_index % len(models)
        model = models[self._current_index]
        self._current_index = (self._current_index + 1) % len(models)
        
        return model
    
    def get_client_and_model(self, config: Dict = None) -> tuple[AsyncOpenAI, str]:
        """获取客户端和模型名，如果config为空则轮流选择"""
        if config is None:
            config = self.get_next()
        
        if config is None:
            raise ValueError("No available model in pool")
        
        client = AsyncOpenAI(
            base_url=config["base_url"],
            api_key=config["api_key"]
        )
        return client, config["model"]
    
    def is_pool_enabled(self) -> bool:
        """检查是否启用了模型池（至少有一个模型）"""
        return len(self.get_enabled_models()) > 0
    
    @property
    def loaded(self) -> bool:
        return self._loaded
