"""Sarvam chat calls that return JSON."""
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
