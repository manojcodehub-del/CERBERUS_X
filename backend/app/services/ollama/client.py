"""Small HTTP client for locally running Ollama; remote hosts are rejected."""

import ipaddress
import json
from urllib.parse import urlparse

import httpx

from app.core.config import Settings


class OllamaError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class OllamaClient:
    def __init__(self, settings: Settings, timeout_seconds: float = 120.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self._models_cache: list[str] | None = None
        self._assert_loopback(self.base_url)

    @staticmethod
    def _assert_loopback(base_url: str) -> None:
        parsed = urlparse(base_url)
        host = parsed.hostname
        if parsed.scheme != "http" or not host:
            raise OllamaError("invalid_ollama_url", "Ollama must use an HTTP loopback URL.")
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host.casefold() == "localhost"
        if not loopback:
            raise OllamaError("remote_ollama_blocked", "Only a local loopback Ollama service is allowed.")

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            with httpx.Client(timeout=self.timeout_seconds, trust_env=False, transport=self.transport) as client:
                response = client.request(method, f"{self.base_url}{path}", **kwargs)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise OllamaError("ollama_timeout", "The local Ollama service did not respond before the timeout.") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 405):
                raise OllamaError("ollama_endpoint_unsupported", "The installed local Ollama version does not support this endpoint.") from exc
            raise OllamaError("ollama_request_failed", f"Local Ollama returned HTTP {exc.response.status_code}.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError("ollama_unavailable", "The local Ollama service is unavailable or returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise OllamaError("ollama_invalid_response", "The local Ollama service returned an invalid response.")
        return payload

    @staticmethod
    def _model_key(name: str) -> str:
        return name if ":" in name else f"{name}:latest"

    def models(self) -> list[str]:
        if self._models_cache is not None:
            return list(self._models_cache)
        payload = self._request("GET", "/api/tags")
        self._models_cache = [str(item.get("name", "")) for item in payload.get("models", []) if item.get("name")]
        return list(self._models_cache)

    def require_model(self, configured_name: str) -> str:
        installed = self.models()
        configured_key = self._model_key(configured_name)
        actual = next((name for name in installed if self._model_key(name) == configured_key), None)
        if actual is None:
            raise OllamaError("ollama_model_missing", f"Local model '{configured_name}' is not installed; no model was downloaded.")
        return actual

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        if not texts:
            return []
        model_name = self.require_model(model or self.settings.ollama_embed_model)
        payload = self._request("POST", "/api/embed", json={"model": model_name, "input": texts, "truncate": False})
        vectors = payload.get("embeddings")
        if not isinstance(vectors, list):
            raise OllamaError("ollama_invalid_embedding", "Local Ollama did not return an embedding batch.")
        if len(vectors) != len(texts):
            raise OllamaError("ollama_invalid_embedding", "Local Ollama returned a different number of embeddings than inputs.")
        converted: list[list[float]] = []
        dimension: int | None = None
        for vector in vectors:
            if not isinstance(vector, list) or not vector:
                raise OllamaError("ollama_invalid_embedding", "Local Ollama returned an empty or malformed vector.")
            try:
                values = [float(value) for value in vector]
            except (TypeError, ValueError) as exc:
                raise OllamaError("ollama_invalid_embedding", "Local Ollama returned non-numeric vector values.") from exc
            if any(not (value == value and abs(value) != float("inf")) for value in values):
                raise OllamaError("ollama_invalid_embedding", "Local Ollama returned non-finite vector values.")
            if dimension is None:
                dimension = len(values)
            elif len(values) != dimension:
                raise OllamaError("ollama_invalid_embedding", "Local Ollama returned inconsistent embedding dimensions.")
            converted.append(values)
        return converted

    def chat_json(self, messages: list[dict[str, str]], model: str | None = None) -> tuple[dict, str]:
        model_name = self.require_model(model or self.settings.ollama_chat_model)
        payload = self._request(
            "POST",
            "/api/chat",
            json={
                "model": model_name,
                "messages": messages,
                "stream": False,
                "format": "json",
                "think": False,
                "options": {"temperature": 0, "num_ctx": 8192},
            },
        )
        content = payload.get("message", {}).get("content") if isinstance(payload.get("message"), dict) else None
        if not isinstance(content, str):
            raise OllamaError("ollama_invalid_response", "Local Ollama returned no chat response text.")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OllamaError("ollama_invalid_json", "Local Ollama returned an answer that was not valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise OllamaError("ollama_invalid_json", "Local Ollama answer must be a JSON object.")
        return parsed, str(payload.get("model") or model_name)
