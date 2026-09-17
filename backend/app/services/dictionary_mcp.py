"""
A small MCP server exposing one tool — translating a word or short phrase
between English and German — backed by the free MyMemory Translation API
(https://mymemory.translated.net/), a real external data source. This is
what grounds Level 2/3 hints in an actual translation instead of the voice
agent guessing/hallucinating vocabulary.

Connected in-process: `mcp.Client(dictionary_server)` (see
assemblyai_client.py) talks to this MCPServer instance directly rather than
over a network. This still goes through the real MCP protocol (tool
discovery via list_tools, call_tool request/response) via the official
`mcp` SDK — it's a genuine MCP client/server pair, just without a network
hop, which is the right tradeoff for a single-developer hackathon build.
Swapping to a real remote MCP server later only means changing what
`mcp.Client(...)` is constructed with (a URL instead of this object) —
nothing else in this file or its caller would need to change.
"""

import logging

import httpx
from mcp.server.mcpserver import MCPServer

logger = logging.getLogger(__name__)

_MYMEMORY_URL = "https://api.mymemory.translated.net/get"
_LANG_CODES = {"English": "en", "German": "de"}

dictionary_server = MCPServer(
    name="lingusim-dictionary",
    instructions=(
        "Translate a single word or short phrase between English and German, "
        "for grounding language-learning hints in a real translation."
    ),
)


@dictionary_server.tool()
async def translate(term: str, target_language: str) -> str:
    """
    Translate `term` into `target_language` ("English" or "German") via the
    MyMemory Translation API. Returns the translated text, or a plain
    "unavailable" string on any failure — this tool never raises, so a
    flaky translation API can never crash the live voice session.
    """
    target_code = _LANG_CODES.get(target_language)
    if target_code is None:
        return f"Unsupported target_language '{target_language}'."

    # This app only ever has two languages in play — the source is
    # whichever of the two isn't the requested target.
    source_code = "de" if target_code == "en" else "en"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                _MYMEMORY_URL,
                params={"q": term, "langpair": f"{source_code}|{target_code}"},
            )
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.warning("dictionary_translate_failed", exc_info=True, extra={"context": {"term": term}})
        return f"Translation unavailable for '{term}'."

    return _best_translation(data, term)


def _best_translation(data: dict, term: str) -> str:
    """
    MyMemory's headline `responseData.translatedText` sometimes picks a
    partial-match translation-memory entry over a better full-phrase
    machine translation that's also present in `matches[]` — prefer
    whichever match entry's source segment exactly equals the query.
    """
    term_lower = term.strip().lower()
    for match in data.get("matches", []):
        if str(match.get("segment", "")).strip().lower() == term_lower:
            translation = match.get("translation")
            if translation:
                return str(translation)

    fallback = data.get("responseData", {}).get("translatedText")
    return str(fallback) if fallback else f"Translation unavailable for '{term}'."
