"""Opt-in integration test for actual local Ollama; never calls a cloud API."""

import os

import pytest

from app.core.config import get_settings
from app.services.ollama.client import OllamaClient


@pytest.mark.ollama_integration
@pytest.mark.skipif(os.getenv("CERBERUS_RUN_REAL_OLLAMA") != "1", reason="set CERBERUS_RUN_REAL_OLLAMA=1 to contact local Ollama")
def test_real_local_ollama_models_and_embedding() -> None:
    settings = get_settings()
    client = OllamaClient(settings)
    installed = client.models()
    assert any(client._model_key(model) == client._model_key(settings.ollama_chat_model) for model in installed)
    assert any(client._model_key(model) == client._model_key(settings.ollama_embed_model) for model in installed)
    vectors = client.embed(["CERBERUS-X local evidence integration check."])
    assert len(vectors) == 1
    assert len(vectors[0]) > 0
    answer, model = client.chat_json([
        {"role": "system", "content": "Return a JSON object with key answer. Do not use external services."},
        {"role": "user", "content": "Set answer to the exact string LOCAL_OLLAMA_READY."},
    ])
    assert answer.get("answer") == "LOCAL_OLLAMA_READY"
    assert model
