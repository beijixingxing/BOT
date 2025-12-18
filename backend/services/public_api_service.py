from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import PublicAPIConfig, PublicAPIUser
import httpx
import secrets
import string
from typing import Optional, Dict, Any


class PublicAPIService:
    """公益站服务 - 对接NewAPI"""
    
    def __init__(self, db: AsyncSession, bot_id: str = "default"):
        self.db = db
        self.bot_id = bot_id
        self._config_cache = None
    
    async def get_config(self) -> Optional[PublicAPIConfig]:
        """获取公益站配置"""
        if self._config_cache:
            return self._config_cache
        
        result = await self.db.execute(
            select(PublicAPIConfig).where(
                PublicAPIConfig.bot_id == self.bot_id,
                PublicAPIConfig.is_active == True
            )
        )
        self._config_cache = result.scalar_one_or_none()
        return self._config_cache
    
    async def is_registered(self, discord_id: str) -> bool:
        """检查用户是否已注册"""
        result = await self.db.execute(
            select(PublicAPIUser).where(PublicAPIUser.discord_id == discord_id)
        )
        return result.scalar_one_or_none() is not None
    
    async def get_user(self, discord_id: str) -> Optional[PublicAPIUser]:
        """获取用户注册信息"""
        result = await self.db.execute(
            select(PublicAPIUser).where(PublicAPIUser.discord_id == discord_id)
        )
        return result.scalar_one_or_none()
    
    def _generate_password(self, length: int = 12) -> str:
        """生成随机密码"""
        chars = string.ascii_letters + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    def _generate_username(self, discord_id: str, discord_username: str) -> str:
        """生成NewAPI用户名"""
        # 用discord_id后6位 + 随机4位
        suffix = discord_id[-6:] + ''.join(secrets.choice(string.digits) for _ in range(4))
        # 清理用户名中的特殊字符
        clean_name = ''.join(c for c in discord_username[:10] if c.isalnum())
        if clean_name:
            return f"{clean_name}_{suffix}"
        return f"user_{suffix}"
    
    async def register_user(self, discord_id: str, discord_username: str) -> Dict[str, Any]:
        """在NewAPI注册新用户"""
        config = await self.get_config()
        if not config:
            return {"success": False, "error": "公益站未配置"}
        
        # 检查是否已注册
        if await self.is_registered(discord_id):
            user = await self.get_user(discord_id)
            return {
                "success": False, 
                "error": "您已经注册过了",
                "username": user.newapi_username,
                "api_key": user.api_key
            }
        
        # 生成用户名和密码
        username = self._generate_username(discord_id, discord_username)
        password = self._generate_password()
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 调用NewAPI创建用户接口
                resp = await client.post(
                    f"{config.newapi_url.rstrip('/')}/api/user",
                    json={
                        "username": username,
                        "password": password,
                        "display_name": discord_username,
                        "quota": config.default_quota,
                        "group": config.default_group
                    },
                    headers={
                        "Authorization": f"Bearer {config.newapi_token}",
                        "Content-Type": "application/json"
                    },
                    cookies={"session": config.newapi_token}  # 有些版本用cookie
                )
                
                print(f"[PublicAPI] Create user response: {resp.status_code} - {resp.text[:500]}")
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success", True):  # NewAPI返回格式
                        user_data = data.get("data", {})
                        newapi_user_id = user_data.get("id")
                        
                        # 获取或生成API Key
                        api_key = await self._create_api_key(config, newapi_user_id, username)
                        
                        # 保存到数据库
                        new_user = PublicAPIUser(
                            discord_id=discord_id,
                            discord_username=discord_username,
                            newapi_user_id=newapi_user_id,
                            newapi_username=username,
                            api_key=api_key
                        )
                        self.db.add(new_user)
                        await self.db.commit()
                        
                        return {
                            "success": True,
                            "username": username,
                            "password": password,
                            "api_key": api_key,
                            "quota": config.default_quota
                        }
                    else:
                        return {"success": False, "error": data.get("message", "创建失败")}
                else:
                    return {"success": False, "error": f"API请求失败: {resp.status_code}"}
                    
        except Exception as e:
            print(f"[PublicAPI] Register error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _create_api_key(self, config: PublicAPIConfig, user_id: int, username: str) -> str:
        """为用户创建API Key"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{config.newapi_url.rstrip('/')}/api/token",
                    json={
                        "name": f"discord_{username}",
                        "user_id": user_id,
                        "remain_quota": config.default_quota,
                        "unlimited_quota": False
                    },
                    headers={
                        "Authorization": f"Bearer {config.newapi_token}",
                        "Content-Type": "application/json"
                    },
                    cookies={"session": config.newapi_token}
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success", True):
                        return data.get("data", {}).get("key", "")
        except Exception as e:
            print(f"[PublicAPI] Create API key error: {e}")
        
        return ""
    
    async def get_user_usage(self, discord_id: str) -> Dict[str, Any]:
        """获取用户用量信息"""
        config = await self.get_config()
        if not config:
            return {"success": False, "error": "公益站未配置"}
        
        user = await self.get_user(discord_id)
        if not user:
            return {"success": False, "error": "您还未注册"}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 获取用户信息
                resp = await client.get(
                    f"{config.newapi_url.rstrip('/')}/api/user/{user.newapi_user_id}",
                    headers={
                        "Authorization": f"Bearer {config.newapi_token}"
                    },
                    cookies={"session": config.newapi_token}
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success", True):
                        user_data = data.get("data", {})
                        quota = user_data.get("quota", 0)
                        used_quota = user_data.get("used_quota", 0)
                        
                        # 转换为美元显示（NewAPI额度单位是1/500000美元）
                        quota_usd = quota / 500000
                        used_usd = used_quota / 500000
                        remain_usd = (quota - used_quota) / 500000
                        
                        return {
                            "success": True,
                            "username": user.newapi_username,
                            "quota": quota_usd,
                            "used": used_usd,
                            "remain": remain_usd,
                            "api_key": user.api_key
                        }
        except Exception as e:
            print(f"[PublicAPI] Get usage error: {e}")
        
        return {
            "success": True,
            "username": user.newapi_username,
            "api_key": user.api_key,
            "quota": "查询失败",
            "used": "查询失败",
            "remain": "查询失败"
        }
