# shared/

Data and formats used by both the backend and the frontend. Change these only after both developers agree.

| File | What it holds |
|---|---|
| `policies.json` | 34 health policies from Star Health, ManipalCigna and Reliance General |
| `families.json` | Mock families. `demo-pune` is the demo family from the deck |
| `examples/demo_solver_output.json` | Solver output for the demo family, with the claim check. Build the UI against this |

## Policy data

Features follow public brochures and aggregator pages. They have not been checked against the policy wordings, so every policy has `"verified": false`. Premiums are illustrative and set so the demo family prices exactly as in the deck. The UI must say they are illustrative.

Each policy is one product at one sum insured:

| Field | Meaning |
|---|---|
| `plan_type` | `floater`, `individual`, `senior` or `super_topup` |
| `sum_insured`, `deductible` | Rupees. Deductible is 0 except for super top-ups |
| `entry_age` | Youngest and oldest age that can join |
| `premium.bands` | Yearly premium by the eldest member's age (`max_age` is inclusive) |
| `premium.members_included`, `per_extra_member` | A floater price covers this many people; each extra person adds this |
| `copay_percent` | Share of every claim the customer pays |
| `room_rent` | `capped` plus the rule in plain words |
| `waiting_periods_months` | `initial`, `specific_illness`, `pre_existing` |
| `condition_waits_months` | Waits for named conditions that differ from `pre_existing` |
| `sub_limits` | Treatments with a cap, such as `cardiac` and `cataract` |
| `catches` | Plain-language catches the explainer quotes |

## Family input

```json
{
  "id": "demo-pune",
  "city": "Pune",
  "budget": 110000,
  "members": [{"id": "mohan", "name": "Mohan", "age": 64, "relation": "father", "conditions": ["diabetes"]}],
  "office_cover": [{"members": ["rahul"], "sum_insured": 500000}]
}
```

Conditions use lowercase names: `diabetes`, `hypertension`, `asthma`, `heart_disease`.

## Solver output

See `examples/demo_solver_output.json`. Main fields: `status` (`ok` or `no_fit`), `picks` (policy, members, premium, catches), `total_premium`, `total_cover`, `member_cover`, `usual_pick`, `saving_vs_usual`, `illustrative`.
