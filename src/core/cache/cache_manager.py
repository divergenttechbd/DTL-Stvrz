# src/core/cache/cache_manager.py

import functools
import pickle
from typing import Any, Callable

from src.core.cache.redis_backend import RedisBackend
from src.core.logging import logger


class CacheManager:
    """
    A decorator-based caching system that uses a Redis backend.
    It handles serialization (pickling) and async operations correctly.
    """

    def __init__(self) -> None:
        self._backend: RedisBackend | None = None

    @property
    def backend(self) -> RedisBackend:
        if self._backend is None:
            raise RuntimeError("Cache backend is not initialized. Call `Cache.init(backend)` first.")
        return self._backend

    def init(self, backend: RedisBackend) -> None:
        """Initializes the cache manager with a specific backend."""
        self._backend = backend
        logger.info("CacheManager initialized successfully.")

    async def get(self, key: str) -> Any:
        """Gets and deserializes an item from the cache."""
        try:
            raw_data = await self.backend.get(key)
            if raw_data is None:
                return None  # Standard cache miss
            return pickle.loads(raw_data)
        except pickle.UnpicklingError as e:
            logger.warning(f"Failed to unpickle cache data for key '{key}'. Data may be corrupt. Error: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get cache for key '{key}': {e}")
            return None  # Treat any error as a cache miss

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Serializes and sets an item in the cache."""
        if value is None:
            # We explicitly do not cache 'None' to prevent caching "not found" states.
            # This is a common and safe default behavior.
            return False
        try:
            serialized_value = pickle.dumps(value)
            return await self.backend.set(key, serialized_value, ttl)
        except pickle.PicklingError as e:
            logger.error(f"Failed to pickle object for key '{key}'. Cannot cache. Error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to set cache for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Deletes an item from the cache."""
        return await self.backend.delete(key)

    def cached(self, expire_time: int = 3600) -> Callable:
        """
        Decorator for caching the results of an async function.
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Create a stable cache key
                # Note: This simple key generation may fail for complex/unserializable args.
                # For production, consider a more robust key generation strategy.
                try:
                    arg_str = str(args)
                    kwarg_str = str(sorted(kwargs.items()))
                    cache_key = f"cache:{func.__module__}:{func.__name__}:{arg_str}:{kwarg_str}"
                except Exception:
                    logger.warning(f"Could not create a cache key for {func.__name__}. Calling function directly.")
                    return await func(*args, **kwargs)

                cached_result = await self.get(cache_key)

                if cached_result is not None:
                    logger.debug(f"Cache HIT for key: {cache_key}")
                    return cached_result

                logger.debug(f"Cache MISS for key: {cache_key}")

                # The decorated function must be awaitable
                result = await func(*args, **kwargs)

                await self.set(cache_key, result, expire_time)
                return result

            return wrapper

        return decorator


# Create a global instance for easy import and use throughout the application
Cache = CacheManager()
