"""Sarvam chat calls that return JSON."""
import functools
import json
import os
from pathlib import Path

from sarvamai import SarvamAI

# Load SARVAM_API_KEY from the repo-root .env without extra dependencies
env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))

# The conversations model answers in about a second. sarvam-105b reasons first and takes 20s or more.
MODEL = "sarvam-105b-conversations"
_client = None


def client():
    global _client
    if _client is None:
        _client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
    return _client


def ask_json(system, messages):
    """Sends a system prompt and chat turns, and returns the reply parsed as a JSON object."""
    response = client().chat.completions(
        model=MODEL,
        temperature=0,
        max_tokens=4000,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}] + messages,
    )
    text = response.choices[0].message.content
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Some replies wrap the JSON in prose or a code fence
        return json.loads(text[text.index("{"):text.rindex("}") + 1])


@functools.lru_cache(maxsize=512)
def to_english(text):
    """English for an Indian-language message, with numbers as digits. English text comes back as it is.

    Used to check the LLM's values against what the user said. On any error the original text is returned.
    """
    if text.isascii():
        return text
    try:
        response = client().text.translate(input=text[:1000], source_language_code="auto", target_language_code="en-IN",
                                           model="mayura:v1", numerals_format="international")
        return response.translated_text or text
    except Exception:
        return text


@functools.lru_cache(maxsize=512)
def from_english(text, language):
    """The text in an Indian language, like hi-IN, with numbers as digits. On any error the English comes back."""
    if len(text) > 1000:
        return text
    try:
        response = client().text.translate(input=text, source_language_code="en-IN", target_language_code=language,
                                           model="mayura:v1", numerals_format="international")
        return response.translated_text or text
    except Exception:
        return text
