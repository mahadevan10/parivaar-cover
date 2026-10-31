"""Builds the mock claim-check fixture from the backend's own claim_check().

Run from the repo root: python3 frontend/scripts/gen_claim_checks.py
Only claim_check is used, so OR-Tools is stubbed out and needs no install.
"""
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

# solver.py imports OR-Tools at the top; claim_check doesn't use it.
ortools = types.ModuleType("ortools")
sat = types.ModuleType("ortools.sat")
python = types.ModuleType("ortools.sat.python")
python.cp_model = types.SimpleNamespace()
sys.modules.update({"ortools": ortools, "ortools.sat": sat, "ortools.sat.python": python})

from solver import claim_check, load_families  # noqa: E402

family = load_families()["demo-pune"]
output = json.loads((ROOT / "shared/examples/demo_solver_output.json").read_text())

SCENARIOS = [
    {"id": "mohan-heart", "member_id": "mohan", "label": "Heart procedure", "amount": 600_000,
     "related_condition": "diabetes", "treatment": "cardiac"},
    {"id": "rahul-cancer", "member_id": "rahul", "label": "Cancer treatment", "amount": 3_000_000},
]

result = []
for s in SCENARIOS:
    kwargs = {k: s.get(k) for k in ("related_condition", "treatment")}
    by_year = []
    for year in range(1, 5):
        mix = claim_check(family, output["picks"], s["member_id"], s["amount"], year, **kwargs)
        usual = claim_check(family, [output["usual_pick"]], s["member_id"], s["amount"], year, **kwargs)
        by_year.append({"policy_year": year, "mix": mix, "usual": usual})
    result.append({**{k: s[k] for k in ("id", "member_id", "label", "amount")}, "by_year": by_year})

out = ROOT / "frontend/src/lib/mock/claim_checks.json"
out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
print(f"Wrote {out.relative_to(ROOT)}")
