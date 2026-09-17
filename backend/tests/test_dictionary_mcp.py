import httpx
import pytest

from app.services.dictionary_mcp import _best_translation, dictionary_server, translate


def test_best_translation_prefers_exact_segment_match():
    data = {
        "responseData": {"translatedText": "Ich möchte eine"},
        "matches": [
            {"segment": "I would like to order a", "translation": "Ich möchte eine"},
            {"segment": "I would like to order a coffee", "translation": "Ich möchte einen Kaffee bestellen"},
        ],
    }
    assert _best_translation(data, "I would like to order a coffee") == "Ich möchte einen Kaffee bestellen"


def test_best_translation_falls_back_to_headline_when_no_exact_match():
    data = {"responseData": {"translatedText": "gestern"}, "matches": []}
    assert _best_translation(data, "yesterday") == "gestern"


def test_best_translation_handles_empty_response():
    assert _best_translation({}, "yesterday") == "Translation unavailable for 'yesterday'."


async def test_translate_rejects_unsupported_language():
    result = await translate(term="hello", target_language="French")
    assert "Unsupported target_language" in result


async def test_translate_calls_mymemory_and_returns_translation(monkeypatch: pytest.MonkeyPatch):
    async def fake_get(self, url, params=None, **kwargs):
        assert params["langpair"] == "en|de"
        return httpx.Response(
            200,
            json={"responseData": {"translatedText": "gestern"}, "matches": []},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    result = await translate(term="yesterday", target_language="German")
    assert result == "gestern"


async def test_translate_never_raises_on_network_failure(monkeypatch: pytest.MonkeyPatch):
    async def fake_get(self, *args, **kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    result = await translate(term="yesterday", target_language="German")
    assert "unavailable" in result.lower()


async def test_dictionary_server_exposes_translate_tool():
    tools = await dictionary_server.list_tools()
    assert any(t.name == "translate" for t in tools)
