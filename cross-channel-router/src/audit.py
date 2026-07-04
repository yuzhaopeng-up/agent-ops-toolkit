"""
src.audit — 审计日志（jsonlines 文件 + 内存 buffer）
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class AuditLogger:
    """线程安全的 jsonlines 审计日志."""

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = log_path or os.getenv(
            "ROUTER_AUDIT_LOG",
            str(Path.home() / ".agent-ops" / "audit" / "router.jsonl"),
        )
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.buffer: list[dict] = []      # 测试用

    def log(self, event: str, **fields):
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        self.buffer.append(record)
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        with self._lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line)
        return record


class IdempotencyStore:
    """内存幂等缓存（生产应换 Redis）."""

    def __init__(self, ttl_seconds: int = 600):
        self.ttl = ttl_seconds
        self._store: dict[str, float] = {}
        self._lock = threading.Lock()

    def seen(self, key: str) -> bool:
        import time
        now = time.time()
        with self._lock:
            # 清理过期
            expired = [k for k, t in self._store.items() if now - t > self.ttl]
            for k in expired:
                self._store.pop(k, None)
            if key in self._store:
                return True
            self._store[key] = now
            return False

    def reset(self):
        with self._lock:
            self._store.clear()
