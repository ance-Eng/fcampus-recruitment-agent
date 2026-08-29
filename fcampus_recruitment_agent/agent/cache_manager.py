# -*- coding: utf-8 -*-
"""
缓存管理器：优先使用 Redis，未安装/未连接时自动降级为内存缓存
用于缓存：RAG 检索结果、LLM 响应、筛选结果、简历解析结果
"""
import hashlib
import json
import time
from typing import Optional, Any


class CacheManager:
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379,
                 redis_db: int = 0, default_ttl: int = 3600, use_redis: bool = False,
                 redis_url: str = "", redis_password: str = ""):
        self.default_ttl = default_ttl
        self._redis = None
        self._memory_cache = {}
        self._backend = "memory"

        import os
        should_use_redis = use_redis or os.environ.get("CACHE_BACKEND", "").lower() == "redis"

        if should_use_redis:
            try:
                import redis
                if redis_url:
                    # 优先使用 URL 连接（如 Upstash: redis://:password@host:port）
                    self._redis = redis.from_url(
                        redis_url,
                        socket_timeout=2,
                        socket_connect_timeout=2,
                        retry_on_timeout=False,
                    )
                else:
                    self._redis = redis.Redis(
                        host=redis_host, port=redis_port, db=redis_db,
                        password=redis_password or None,
                        socket_timeout=2, socket_connect_timeout=2,
                        retry_on_timeout=False,
                    )
                self._redis.ping()
                self._backend = "redis"
            except Exception:
                self._redis = None
                self._backend = "memory"

    @property
    def backend(self) -> str:
        return self._backend

    def _make_key(self, prefix: str, content: str) -> str:
        """生成缓存 key：prefix + md5(content)"""
        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        return f"{prefix}:{content_hash}"

    def get(self, prefix: str, content: str) -> Optional[Any]:
        """获取缓存，不存在或已过期返回 None"""
        key = self._make_key(prefix, content)

        if self._backend == "redis" and self._redis:
            try:
                data = self._redis.get(key)
                if data:
                    return json.loads(data)
            except Exception:
                pass
            return None

        # memory fallback
        if key in self._memory_cache:
            value, expire_at = self._memory_cache[key]
            if expire_at > time.time():
                return value
            else:
                del self._memory_cache[key]
        return None

    def set(self, prefix: str, content: str, value: Any, ttl: int = None) -> bool:
        """写入缓存，ttl 单位秒"""
        key = self._make_key(prefix, content)
        ttl = ttl or self.default_ttl

        if self._backend == "redis" and self._redis:
            try:
                self._redis.setex(key, ttl, json.dumps(value, ensure_ascii=False))
                return True
            except Exception:
                pass

        # memory fallback
        self._memory_cache[key] = (value, time.time() + ttl)
        # 简单清理：超过 1000 条时清掉过期的
        if len(self._memory_cache) > 1000:
            self._cleanup_expired()
        return True

    def get_or_set(self, prefix: str, content: str, producer, ttl: int = None) -> Any:
        """获取缓存，不存在则调用 producer 生成并缓存"""
        cached = self.get(prefix, content)
        if cached is not None:
            return cached
        value = producer()
        if value is not None:
            self.set(prefix, content, value, ttl)
        return value

    def delete(self, prefix: str, content: str) -> bool:
        key = self._make_key(prefix, content)
        if self._backend == "redis" and self._redis:
            try:
                self._redis.delete(key)
                return True
            except Exception:
                return False
        self._memory_cache.pop(key, None)
        return True

    def clear(self) -> int:
        """清空所有缓存（仅当前前缀相关），返回清理数量"""
        count = 0
        if self._backend == "redis" and self._redis:
            try:
                for key in self._redis.scan_iter("*"):
                    self._redis.delete(key)
                    count += 1
            except Exception:
                pass
        else:
            count = len(self._memory_cache)
            self._memory_cache.clear()
        return count

    def _cleanup_expired(self):
        now = time.time()
        expired = [k for k, (_, exp) in self._memory_cache.items() if exp <= now]
        for k in expired:
            del self._memory_cache[k]

    def stats(self) -> dict:
        """返回缓存统计信息"""
        if self._backend == "redis" and self._redis:
            try:
                return {
                    "backend": "redis",
                    "keys": self._redis.dbsize(),
                    "memory_used": self._redis.info("memory").get("used_memory_human", "unknown"),
                }
            except Exception:
                return {"backend": "redis", "keys": "unknown"}
        return {
            "backend": "memory",
            "keys": len(self._memory_cache),
        }
