from __future__ import annotations

import json
import urllib.error
import urllib.request


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
            message = data.get("message", {})
            content = (message.get("content") or "").strip()
            return content or "Sem resposta do modelo no momento."
        except urllib.error.URLError as exc:
            return (
                "Nao foi possivel conectar ao Ollama. "
                "Verifique se o servico esta ativo em http://127.0.0.1:11434. "
                f"Detalhe tecnico: {exc}"
            )
        except Exception as exc:
            return f"Falha ao consultar o Ollama: {exc}"

    def warmup(self) -> None:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "ok"}],
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        try:
            self._post_json(self.base_chat_url, payload)
        except Exception:
            # Warmup falhou; o sistema continua funcional e tentara novamente no primeiro chat.
            return
