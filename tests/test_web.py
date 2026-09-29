import os
from pathlib import Path
import sys

import pytest


pytest.importorskip("django")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "marco_web.settings")

import django

django.setup()

from django.test import Client


@pytest.fixture
def client():
    return Client(enforce_csrf_checks=False)


def test_native_web_editor_renders(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Escribe con evidencia" in response.content.decode()
    assert b"hx-post" in response.content


def test_native_web_can_generate_and_save_draft(client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    response = client.post(
        "/draft/",
        {"instruction": "Redacta resultados", "provider": "Mock (offline)"},
    )

    assert response.status_code == 200
    assert "Borrador generado" in response.content.decode()

    save = client.post("/draft/save/", {"text": "Texto revisado por la persona."})
    assert save.status_code == 200
    assert "Guardado local" in save.content.decode()


def test_native_web_search_returns_empty_state(client):
    response = client.post("/evidence/search/", {"query": "sin resultados"})

    assert response.status_code == 200
    assert "Indexa documentos" in response.content.decode()


def test_native_web_settings_persist_without_rendering_secret(client):
    response = client.post(
        "/settings/",
        {
            "template": "Resultados",
            "target_words": "800",
            "provider": "OpenAI",
            "model": "gpt-test",
            "base_url": "http://localhost:1234/v1",
            "api_key": "secret-value",
        },
    )

    assert response.status_code == 200
    assert "Configuración guardada" in response.content.decode()
    assert "secret-value" not in response.content.decode()
