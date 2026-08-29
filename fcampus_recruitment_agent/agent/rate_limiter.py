# -*- coding: utf-8 -*-
"""
速率限制器：防止用户滥用 API，节省 token
支持：每分钟调用次数限制、每日调用上限、基于会话ID/IP限流
后端：Redis（分布式）或 内存（单机）
"""
import time
from typing import Optional
from .cache_manager import CacheManager


class RateLimiter:
    def __init__(self, cache: CacheManager,
                 max_per_minute: int = 10,
                 max_per_day: int = 100):
        """
        Args:
            cache: CacheManager 实例（Redis 或内存）
            max_per_minute: 每分钟最大调用次数
            max_per_day: 每天最大调用次数
        """
        self.cache = cache
        self.max_per_minute = max_per_minute
        self.max_per_day = max_per_day

    def check(self, user_id: str) -> dict:
        """
        检查用户是否可以调用，返回状态信息
        Returns: {"allowed": bool, "reason": str, "minute_used": int, "day_used": int}
        """
        now = time.time()
        minute_key = f"ratelimit:{user_id}:minute:{int(now // 60)}"
        day_key = f"ratelimit:{user_id}:day:{time.strftime('%Y%m%d')}"

        # 读取当前计数
        minute_count = self.cache.get("ratelimit", minute_key) or 0
        day_count = self.cache.get("ratelimit", day_key) or 0

        result = {
            "allowed": True,
            "reason": "",
            "minute_used": minute_count,
            "day_used": day_count,
            "minute_limit": self.max_per_minute,
            "day_limit": self.max_per_day,
        }

        # 检查分钟限制
        if minute_count >= self.max_per_minute:
            result["allowed"] = False
            result["reason"] = f"调用过于频繁，请稍后再试（每分钟限{self.max_per_minute}次）"
            return result

        # 检查每日限制
        if day_count >= self.max_per_day:
            result["allowed"] = False
            result["reason"] = f"今日调用次数已达上限（每天限{self.max_per_day}次）"
            return result

        # 计数+1
        self.cache.set("ratelimit", minute_key, minute_count + 1, ttl=120)
        self.cache.set("ratelimit", day_key, day_count + 1, ttl=86400)

        result["minute_used"] = minute_count + 1
        result["day_used"] = day_count + 1
        return result

    def get_usage(self, user_id: str) -> dict:
        """查询用户当前使用量（不计数）"""
        now = time.time()
        minute_key = f"ratelimit:{user_id}:minute:{int(now // 60)}"
        day_key = f"ratelimit:{user_id}:day:{time.strftime('%Y%m%d')}"
        return {
            "minute_used": self.cache.get("ratelimit", minute_key) or 0,
            "day_used": self.cache.get("ratelimit", day_key) or 0,
            "minute_limit": self.max_per_minute,
            "day_limit": self.max_per_day,
        }

    def reset(self, user_id: str):
        """重置用户限制（管理员用）"""
        now = time.time()
        minute_key = f"ratelimit:{user_id}:minute:{int(now // 60)}"
        day_key = f"ratelimit:{user_id}:day:{time.strftime('%Y%m%d')}"
        self.cache.delete("ratelimit", minute_key)
        self.cache.delete("ratelimit", day_key)
