"""In-process Redis semantics for tests and for running without a server."""

from __future__ import annotations

import threading

from redis.errors import CacheError


class MemoryKv:
    def __init__(self, clock):
        self.clock = clock
        self._data: dict[str, tuple[object, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            value = self._live(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise CacheError("WRONG_TYPE", "键类型不是字符串")
        return value

    def set(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            self._data[key] = (value, self._deadline(ttl))

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def incr(self, key: str, ttl: int) -> int:
        with self._lock:
            current = self._live(key)
            if current is None:
                self._data[key] = ("1", self._deadline(ttl))
                return 1
            if not isinstance(current, str) or not current.isdigit():
                raise CacheError("WRONG_TYPE", "键类型不是计数")
            count = int(current) + 1
            deadline = self._data[key][1]
            self._data[key] = (str(count), deadline)
            return count

    def set_nx(self, key: str, value: str, ttl: int) -> bool:
        with self._lock:
            if self._live(key) is not None:
                return False
            self._data[key] = (value, self._deadline(ttl))
            return True

    def compare_delete(self, key: str, value: str) -> bool:
        with self._lock:
            current = self._live(key)
            if current != value:
                return False
            self._data.pop(key, None)
            return True

    def sadd(self, key: str, member: str, ttl: int) -> None:
        with self._lock:
            current = self._live(key)
            if current is None:
                members: set[str] = set()
            elif not isinstance(current, set):
                raise CacheError("WRONG_TYPE", "键类型不是集合")
            else:
                members = current
            members.add(member)
            self._data[key] = (members, self._deadline(ttl))

    def srem(self, key: str, member: str) -> None:
        with self._lock:
            current = self._live(key)
            if not isinstance(current, set):
                return
            current.discard(member)
            self._data[key] = (current, self._data[key][1])

    def smembers(self, key: str) -> set[str]:
        with self._lock:
            current = self._live(key)
        if current is None:
            return set()
        if not isinstance(current, set):
            raise CacheError("WRONG_TYPE", "键类型不是集合")
        return set(current)

    def pttl(self, key: str) -> int:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return 0
            left = item[1] - self.clock()
        if left <= 0:
            return 0
        return int(left + 0.999)

    def keys(self) -> list[str]:
        with self._lock:
            return [key for key in self._data if self._live(key) is not None]

    def _live(self, key: str):
        item = self._data.get(key)
        if item is None:
            return None
        if item[1] <= self.clock():
            self._data.pop(key, None)
            return None
        return item[0]

    def _deadline(self, ttl: int) -> float:
        if ttl <= 0:
            raise CacheError("INVALID_TTL", "过期时间必须大于 0")
        return self.clock() + ttl
