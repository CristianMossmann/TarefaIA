from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request


logger = logging.getLogger(__name__)


OFFLINE_MESSAGE = (
    "O servico de IA esta temporariamente indisponivel. "
    "Tente novamente em instantes."
)


class OllamaUnavailableError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        base_chat_url: str,
        model: str,
        timeout_seconds: int,
        keep_alive: str,
    ):
        self.base_chat_url = base_chat_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.keep_alive = keep_alive

    def _post_json(self, url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)

    def chat(self, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
        }

        try:
            data = self._post_json(self.base_chat_url, payload)
        except urllib.error.URLError as exc:
            logger.warning("Falha ao conectar ao Ollama: %s", exc)
            raise OllamaUnavailableError(OFFLINE_MESSAGE) from exc
        except TimeoutError as exc:
            logger.warning("Timeout consultando Ollama: %s", exc)
            raise OllamaUnavailableError(OFFLINE_MESSAGE) from exc
        except json.JSONDecodeError as exc:
            logger.error("Resposta do Ollama nao foi JSON valido: %s", exc)
            raise OllamaUnavailableError(OFFLINE_MESSAGE) from exc

        message = data.get("message", {})
        content = (message.get("content") or "").strip()
        return content or "Sem resposta do modelo no momento."

    def warmup(self) -> None:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ok"}],
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        try:
            self._post_json(self.base_chat_url, payload)
        except Exception as exc:  # noqa: BLE001 - warmup nao pode quebrar o startup
            logger.info("Warmup do Ollama falhou (sera retentado no primeiro chat): %s", exc)
