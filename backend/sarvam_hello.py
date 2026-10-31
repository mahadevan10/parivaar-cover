"""First Sarvam chat call. Run from the repo root: backend/.venv/bin/python backend/sarvam_hello.py"""
import os
from pathlib import Path

from sarvamai import SarvamAI

# Load SARVAM_API_KEY from the repo-root .env without extra dependencies
env_file = Path(__file__).resolve().parent.parent / ".env"
for line in env_file.read_text().splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"'))

client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])

response = client.chat.completions(
    model="sarvam-105b",
    messages=[
        {"role": "system", "content": "You explain health insurance in plain, short sentences."},
        {"role": "user", "content": "In two sentences, what is a super top-up health policy?"},
    ],
)
print(response.choices[0].message.content)
