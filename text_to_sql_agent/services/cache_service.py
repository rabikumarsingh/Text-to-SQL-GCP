import hashlib
import json
import os

import redis.asyncio as redis


class CacheService:

    def __init__(self):
        self.client = redis.Redis(
            host=os.getenv("REDIS_HOST"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
        )

        self.default_ttl = 3600

    def build_key(
        self,
        user_id: str,
        session_id: str,
        question: str,
    ) -> str:

        normalized_question = " ".join(
            question.lower().strip().split()
        )

        raw_key = (
            f"{user_id}:"
            f"{session_id}:"
            f"{normalized_question}"
        )

        key_hash = hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()

        return f"text_to_sql:query:{key_hash}"

    async def get(
        self,
        user_id: str,
        session_id: str,
        question: str,
    ):

        key = self.build_key(
            user_id=user_id,
            session_id=session_id,
            question=question,
        )

        cached_value = await self.client.get(key)

        if cached_value is None:
            return None

        return json.loads(cached_value)

    async def set(
        self,
        user_id: str,
        session_id: str,
        question: str,
        value: dict,
        ttl: int | None = None,
    ):

        key = self.build_key(
            user_id=user_id,
            session_id=session_id,
            question=question,
        )

        await self.client.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(value),
        )

    async def delete(
        self,
        user_id: str,
        session_id: str,
        question: str,
    ):

        key = self.build_key(
            user_id=user_id,
            session_id=session_id,
            question=question,
        )

        await self.client.delete(key)

    async def close(self):
        await self.client.aclose()


cache_service = CacheService()