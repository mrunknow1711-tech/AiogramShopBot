from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
import time


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, redis, rate_limit: int = 1):
        self.redis = redis
        self.rate_limit = rate_limit
        self.throttle_manager = ThrottleManager(redis) if redis else None

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # Wenn kein Redis, skip throttling
        if not self.redis or not self.throttle_manager:
            return await handler(event, data)
        
        await self.on_process_event(event, data)
        return await handler(event, data)

    async def on_process_event(self, event: Message | CallbackQuery, data: dict):
        if not self.throttle_manager:
            return
            
        if isinstance(event, Message):
            key = f"throttle_message_{event.from_user.id}"
        else:
            key = f"throttle_callback_{event.from_user.id}"

        limit = self.rate_limit
        await self.throttle_manager.throttle(key, rate=limit, user_id=event.from_user.id)


class ThrottleManager:
    def __init__(self, redis):
        self.redis = redis
        self.bucket_keys = ['last_call', 'last_reset', 'throttle_count']

    async def throttle(self, key: str, rate: int, user_id: int):
        if not self.redis:
            return
            
        bucket_name = f"throttle:{user_id}:{key}"
        
        try:
            # Check if bucket exists
            data = await self.redis.hmget(bucket_name, self.bucket_keys)
            
            current_time = time.time()
            
            if not any(data):
                # First call - create bucket
                await self.redis.hset(bucket_name, mapping={
                    'last_call': current_time,
                    'last_reset': current_time,
                    'throttle_count': 1
                })
                await self.redis.expire(bucket_name, 60)
                return
            
            last_call = float(data[0]) if data[0] else current_time
            last_reset = float(data[1]) if data[1] else current_time
            throttle_count = int(data[2]) if data[2] else 0
            
            # Reset if more than 60 seconds passed
            if current_time - last_reset > 60:
                await self.redis.hset(bucket_name, mapping={
                    'last_call': current_time,
                    'last_reset': current_time,
                    'throttle_count': 1
                })
                await self.redis.expire(bucket_name, 60)
                return
            
            # Check throttle
            time_passed = current_time - last_call
            if time_passed < rate:
                # Too fast - but we don't raise error, just log
                return
            
            # Update
            await self.redis.hset(bucket_name, mapping={
                'last_call': current_time,
                'throttle_count': throttle_count + 1
            })
            
        except Exception as e:
            # Redis error - don't block user
            import logging
            logging.error(f"Throttling error (non-critical): {e}")
            return
