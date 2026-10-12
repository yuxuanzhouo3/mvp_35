"""Minimal RESP client for the commands this cache uses.

The package is named redis, so it speaks the protocol itself instead of
importing the redis-py distribution.
"""

from __future__ import annotations

import socket
import threading
from urllib.parse import unquote, urlparse

from redis.errors import CacheError
from redis.keys import INCR_LUA, RELEASE_LUA


def encode(parts: list[str]) -> bytes:
    chunks = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        raw = part.encode()
        chunks.append(f"${len(raw)}\r\n".encode())
        chunks.append(raw)
        chunks.append(b"\r\n")
    return b"".join(chunks)


class RedisKv:
    def __init__(self, url: str):
        parsed = urlparse(url)
        if parsed.scheme != "redis":
            raise CacheError("REDIS_URL", "只支持 redis://")
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 6379
        self._sock = socket.create_connection((host, port), timeout=2)
        self._buf = b""
        self._lock = threading.Lock()
        password = unquote(parsed.password) if parsed.password else ""
        username = unquote(parsed.username) if parsed.username else ""
        if password and username:
            self._call("AUTH", username, password)
        elif password:
            self._call("AUTH", password)
        database = int((parsed.path or "/0").strip("/") or "0")
        if database:
            self._call("SELECT", str(database))

    def close(self) -> None:
        self._sock.close()

    def get(self, key: str) -> str | None:
        value = self._call("GET", key)
        if value is None:
            return None
        return _text(value)

    def set(self, key: str, value: str, ttl: int) -> None:
        self._call("SET", key, value, "EX", str(ttl))

    def delete(self, key: str) -> None:
        self._call("DEL", key)

    def incr(self, key: str, ttl: int) -> int:
        return int(self._call("EVAL", INCR_LUA, "1", key, str(ttl)))

    def set_nx(self, key: str, value: str, ttl: int) -> bool:
        return self._call("SET", key, value, "EX", str(ttl), "NX") is not None

    def compare_delete(self, key: str, value: str) -> bool:
        return int(self._call("EVAL", RELEASE_LUA, "1", key, value)) == 1

    def sadd(self, key: str, member: str, ttl: int) -> None:
        self._call("SADD", key, member)
        self._call("EXPIRE", key, str(ttl))

    def srem(self, key: str, member: str) -> None:
        self._call("SREM", key, member)

    def smembers(self, key: str) -> set[str]:
        raw = self._call("SMEMBERS", key) or []
        return {_text(item) for item in raw}

    def pttl(self, key: str) -> int:
        ttl = int(self._call("TTL", key))
        return max(ttl, 0)

    def _call(self, *parts: str):
        with self._lock:
            self._sock.sendall(encode(list(parts)))
            return self._read()

    def _read(self):
        line = self._line()
        kind, rest = line[:1], line[1:]
        if kind == b"+":
            return rest.decode()
        if kind == b"-":
            raise CacheError("REDIS", rest.decode())
        if kind == b":":
            return int(rest)
        if kind == b"$":
            size = int(rest)
            if size < 0:
                return None
            data = self._exact(size)
            self._exact(2)
            return data
        if kind == b"*":
            size = int(rest)
            if size < 0:
                return None
            return [self._read() for _ in range(size)]
        raise CacheError("REDIS", "无法解析响应")

    def _line(self) -> bytes:
        while b"\r\n" not in self._buf:
            self._fill()
        line, self._buf = self._buf.split(b"\r\n", 1)
        return line

    def _exact(self, size: int) -> bytes:
        while len(self._buf) < size:
            self._fill()
        data, self._buf = self._buf[:size], self._buf[size:]
        return data

    def _fill(self) -> None:
        chunk = self._sock.recv(4096)
        if not chunk:
            raise CacheError("REDIS", "连接已断开")
        self._buf += chunk


def _text(value) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return str(value)
