from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import SystemConfig
from openai import AsyncOpenAI
from typing import List, Dict, Optional
import json
import asyncio
import random
import time


class LLMPoolService:
    """LLM模型池服务，支持多模型/多Key负载均衡、权重、分组、统计"""
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self._pool: List[Dict] = []  # [{base_url, api_key, model, name, enabled, weight, group, ...}]
        self._current_index = 0
        self._loaded = False
        self._retry_count = 3  # 报错重试次数
        self._retry_on_error = True  # 是否启用报错重试
        self._version = 0  # 配置版本号，用于缓存刷新
        self._call_logs: List[Dict] = []  # 调用日志
        self._max_logs = 100  # 最多保留日志条数
        self._groups: List[str] = []  # 分组列表
    
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
                data = json.loads(config.value)
                # 支持新旧格式
                if isinstance(data, list):
                    self._pool = data
                else:
                    self._pool = data.get("models", [])
                    self._retry_count = data.get("retry_count", 3)
                    self._retry_on_error = data.get("retry_on_error", True)
                self._loaded = True
                print(f"[LLMPool] Loaded {len(self._pool)} models, retry={self._retry_count}")
            except json.JSONDecodeError:
                self._pool = []
        
        return self._pool
    
    
    def add_model(self, base_url: str, api_key: str, model: str, name: str = None, 
                   weight: int = 1, group: str = ""):
        """添加模型到池"""
        self._pool.append({
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "name": name or model,
            "enabled": True,
            "weight": max(1, weight),  # 权重最小为1
            "group": group,
            "request_count": 0,
            "success_count": 0,
            "fail_count": 0,
            "total_response_time": 0,  # 总响应时间(ms)
            "avg_response_time": 0  # 平均响应时间(ms)
        })
        self._version += 1
    
    def remove_model(self, index: int) -> bool:
        """移除模型"""
        if 0 <= index < len(self._pool):
            self._pool.pop(index)
            if self._current_index >= len(self._pool):
                self._current_index = 0
            return True
        return False
    
    def update_model(self, index: int, base_url: str = None, api_key: str = None, 
                      model: str = None, name: str = None, weight: int = None, 
                      group: str = None) -> bool:
        """更新模型配置"""
        if 0 <= index < len(self._pool):
            if base_url is not None:
                self._pool[index]["base_url"] = base_url
            if api_key is not None:
                self._pool[index]["api_key"] = api_key
            if model is not None:
                self._pool[index]["model"] = model
            if name is not None:
                self._pool[index]["name"] = name
            if weight is not None:
                self._pool[index]["weight"] = max(1, weight)
            if group is not None:
                self._pool[index]["group"] = group
            self._version += 1
            return True
        return False
    
    def get_model(self, index: int) -> Optional[Dict]:
        """获取指定索引的模型（包含完整信息）"""
        if 0 <= index < len(self._pool):
            return self._pool[index]
        return None
    
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
        
        # 增加请求计数
        if "request_count" not in model:
            model["request_count"] = 0
        model["request_count"] += 1
        
        return model
    
    def get_next_from_list(self, models: List[Dict], group: str = None) -> Dict:
        """从指定列表中按权重选择下一个模型"""
        if not models:
            raise ValueError("模型列表为空")
        
        # 如果指定了分组，先筛选
        if group:
            models = [m for m in models if m.get("group") == group]
            if not models:
                raise ValueError(f"分组 {group} 没有可用模型")
        
        # 按权重选择模型
        model = self._weighted_choice(models)
        
        # 更新请求计数（如果是池中的模型）
        self._increment_request_count(model)
        
        return model
    
    def _weighted_choice(self, models: List[Dict]) -> Dict:
        """按权重随机选择模型"""
        total_weight = sum(m.get("weight", 1) for m in models)
        r = random.uniform(0, total_weight)
        cumulative = 0
        for model in models:
            cumulative += model.get("weight", 1)
            if r <= cumulative:
                return model
        return models[-1]  # fallback
    
    def _increment_request_count(self, model: Dict):
        """增加模型的请求计数（通过匹配base_url和model来找到池中对应的模型）"""
        for m in self._pool:
            if m.get("base_url") == model.get("base_url") and m.get("model") == model.get("model"):
                if "request_count" not in m:
                    m["request_count"] = 0
                m["request_count"] += 1
                self._needs_save = True
                break
    
    def record_call_result(self, model: Dict, success: bool, response_time_ms: float, error: str = None):
        """记录调用结果（成功率、响应时间）"""
        for m in self._pool:
            if m.get("base_url") == model.get("base_url") and m.get("model") == model.get("model"):
                # 更新成功/失败计数
                if success:
                    m["success_count"] = m.get("success_count", 0) + 1
                else:
                    m["fail_count"] = m.get("fail_count", 0) + 1
                
                # 更新响应时间统计
                m["total_response_time"] = m.get("total_response_time", 0) + response_time_ms
                total_calls = m.get("success_count", 0) + m.get("fail_count", 0)
                if total_calls > 0:
                    m["avg_response_time"] = round(m["total_response_time"] / total_calls, 2)
                
                self._needs_save = True
                break
        
        # 添加调用日志
        self._add_call_log(model, success, response_time_ms, error)
    
    def _add_call_log(self, model: Dict, success: bool, response_time_ms: float, error: str = None):
        """添加调用日志"""
        log = {
            "timestamp": time.time(),
            "model_name": model.get("name", model.get("model", "unknown")),
            "model": model.get("model", ""),
            "base_url": model.get("base_url", ""),
            "success": success,
            "response_time_ms": round(response_time_ms, 2),
            "error": error
        }
        self._call_logs.insert(0, log)
        # 保持日志数量限制
        if len(self._call_logs) > self._max_logs:
            self._call_logs = self._call_logs[:self._max_logs]
    
    def get_call_logs(self, limit: int = 50) -> List[Dict]:
        """获取调用日志"""
        return self._call_logs[:limit]
    
    def get_groups(self) -> List[str]:
        """获取所有分组"""
        groups = set()
        for m in self._pool:
            g = m.get("group", "")
            if g:
                groups.add(g)
        return sorted(list(groups))
    
    def get_models_by_group(self, group: str) -> List[Dict]:
        """按分组获取模型"""
        return [m for m in self._pool if m.get("group") == group and m.get("enabled", True)]
    
    def get_model_stats(self, index: int) -> Optional[Dict]:
        """获取模型统计信息"""
        if 0 <= index < len(self._pool):
            m = self._pool[index]
            total = m.get("success_count", 0) + m.get("fail_count", 0)
            success_rate = round(m.get("success_count", 0) / total * 100, 1) if total > 0 else 0
            return {
                "request_count": m.get("request_count", 0),
                "success_count": m.get("success_count", 0),
                "fail_count": m.get("fail_count", 0),
                "success_rate": success_rate,
                "avg_response_time": m.get("avg_response_time", 0)
            }
        return None
    
    @property
    def version(self) -> int:
        """获取配置版本号"""
        return self._version
    
    def needs_save(self) -> bool:
        """检查是否需要保存"""
        return getattr(self, '_needs_save', False)
    
    def mark_saved(self):
        """标记已保存"""
        self._needs_save = False
    
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
    
    @property
    def retry_count(self) -> int:
        return self._retry_count
    
    @retry_count.setter
    def retry_count(self, value: int):
        self._retry_count = max(1, min(10, value))  # 限制1-10次
    
    @property
    def retry_on_error(self) -> bool:
        return self._retry_on_error
    
    @retry_on_error.setter
    def retry_on_error(self, value: bool):
        self._retry_on_error = value
    
    def get_settings(self) -> Dict:
        """获取模型池设置"""
        return {
            "retry_count": self._retry_count,
            "retry_on_error": self._retry_on_error
        }
    
    def update_settings(self, retry_count: int = None, retry_on_error: bool = None):
        """更新模型池设置"""
        if retry_count is not None:
            self.retry_count = retry_count
        if retry_on_error is not None:
            self.retry_on_error = retry_on_error
    
    def reset_request_counts(self):
        """重置所有模型的请求计数"""
        for model in self._pool:
            model["request_count"] = 0
    
    def reset_all_stats(self):
        """重置所有统计数据"""
        for model in self._pool:
            model["request_count"] = 0
            model["success_count"] = 0
            model["fail_count"] = 0
            model["total_response_time"] = 0
            model["avg_response_time"] = 0
        self._call_logs = []
        self._needs_save = True
    
    async def check_and_reload(self, db: AsyncSession) -> bool:
        """检查并重新加载配置（缓存刷新）"""
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == "llm_pool_version")
        )
        version_config = result.scalar_one_or_none()
        
        if version_config:
            try:
                db_version = int(version_config.value)
                if db_version > self._version:
                    await self.load_from_db(db)
                    self._version = db_version
                    return True
            except (ValueError, TypeError):
                pass
        return False
    
    async def save_to_db(self, db: AsyncSession):
        """保存模型池配置到数据库"""
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == "llm_pool")
        )
        config = result.scalar_one_or_none()
        
        # 使用新格式保存，包含重试配置
        data = {
            "models": self._pool,
            "retry_count": self._retry_count,
            "retry_on_error": self._retry_on_error,
            "version": self._version
        }
        
        if config:
            config.value = json.dumps(data, ensure_ascii=False)
        else:
            config = SystemConfig(
                key="llm_pool",
                value=json.dumps(data, ensure_ascii=False),
                description="LLM模型池配置"
            )
            db.add(config)
        
        # 保存版本号（用于缓存刷新）
        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == "llm_pool_version")
        )
        version_config = result.scalar_one_or_none()
        if version_config:
            version_config.value = str(self._version)
        else:
            version_config = SystemConfig(
                key="llm_pool_version",
                value=str(self._version),
                description="模型池配置版本号"
            )
            db.add(version_config)
        
        await db.commit()
