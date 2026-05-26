"""Limitador de requisicoes simples (janela deslizante de 60s).

A intencao e proteger a fonte publica: mesmo que o dashboard atualize
muitas vezes ou que um bug provoque chamadas em loop, o limitador
recusa a chamada antes de bater no servidor externo.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class RateLimitExceeded(RuntimeError):
    pass


class RateLimiter:
    def __init__(self, max_requests_per_minute: int):
        if max_requests_per_minute < 1:
            raise ValueError("max_requests_per_minute deve ser >= 1")
        self.max_requests = max_requests_per_minute
        self._window_seconds = 60.0
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        now = time.monotonic()
        with self._lock:
            while self._calls and now - self._calls[0] > self._window_seconds:
                self._calls.popleft()
            if len(self._calls) >= self.max_requests:
                raise RateLimitExceeded(
                    f"Limite de {self.max_requests} req/min atingido para scraping"
                )
            self._calls.append(now)

    def remaining(self) -> int:
        now = time.monotonic()
        with self._lock:
            while self._calls and now - self._calls[0] > self._window_seconds:
                self._calls.popleft()
            return max(0, self.max_requests - len(self._calls))
