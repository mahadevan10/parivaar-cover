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
| `other_catches` | Catches the other fields do not say, like an entry age limit. The solver builds the rest of a pick's `catches` from the fields above (`policy_catches` in `backend/solver.py`), so they always match the numbers |

## Family input

```json
{
  "id": "demo-pune",
  "city": "Pune",
  "budget": 110000,
  "cover_target": 10000000,
  "members": [{"id": "mohan", "name": "Mohan", "age": 64, "relation": "father", "conditions": ["diabetes"]}],
  "office_cover": [{"members": ["rahul"], "sum_insured": 500000}]
}
```

Conditions use lowercase names: `diabetes`, `hypertension`, `asthma`, `heart_disease`.

`cover_target` is optional. It is the total cover the family wants, in rupees, summed over every policy in the mix the same way as `total_cover` (office cover is not counted). The mix must reach it, but the budget comes first: when the budget cannot buy that much cover, the solver returns the mix with the most cover the budget allows and says so in `cover_check`. Leave it out, or `null`, to let the solver choose.

## Solver output

See `examples/demo_solver_output.json`. Main fields: `status` (`ok` or `no_fit`), `picks` (policy, members, premium, catches, source, reasons), `total_premium`, `total_cover`, `member_cover`, `usual_pick`, `saving_vs_usual`, `vs_usual`, `mix_catches`, `cover_target`, `cover_check`, `illustrative`.

### Reasons

The solver says why it made each pick, so the explainer only rewords facts and never invents them. Every reason has a `code`, the numbers behind it, and a plain `text` sentence.

| Code | Where | Meaning |
|---|---|---|
| `priced_on_eldest` | floater picks | The floater's premium is set by this member's age |
| `left_out` | floater picks | Why a member is not in the floater: `entry_age`, or `premium` with the price if they joined |
| `topup_on_base` | top-up picks | Cover added, the deductible, and which base plan pays below it |
| `condition_wait` | any pick | Months before a member's known condition is covered, the waits on other plans they could join, and the policy field it comes from (`clause`) |
| `next_best` | every pick, last | The solver run again without this pick: what it swaps in, `premium_change`, and per-member `changes` in cover, wait, co-pay and room rent |

`vs_usual` lists the same kind of facts against the usual single floater: the premium saving, each member's cover, and condition waits.

### Mix catches

`mix_catches` lists catches that come from how the picks stack, most serious first. Each has a `code`, `members`, `policy_ids`, the field it comes from (`clause`), the numbers behind it, and a plain `text` sentence.

| Code | Meaning |
|---|---|
| `topup_waits_longer` | A member's condition waits longer on the top-up than on the base plan, so for a while only the base plan pays (`base_months`, `topup_months`) |
| `copay_under_topup` | The base plan has a co-pay, and the top-up does not pay that share (`copay_percent`, `most_paid`) |
| `topup_on_office_cover` | Office cover counts toward the top-up's deductible, so leaving the job opens a gap below it |
| `two_insurers` | Base plan and top-up are from different insurers, so a big bill means two claims |
| `shared_cover` | Members share a top-up, and a floater too when they have one, so one big claim leaves less for the others |

### Cover check

`cover_check` is `null` when there is no `cover_target`. Otherwise it has a `code`, the numbers behind it and a plain `text` sentence.

| Code | Meaning |
|---|---|
| `cover_met` | The mix reaches the target (`target`, `total_cover`) |
| `cover_short` | The budget cannot buy the target. The mix has the most cover the budget allows. `shortfall`, `budget`, and `budget_needed`: the lowest yearly premium for a mix that reaches the target |
| `cover_out_of_reach` | No mix of the listed policies reaches the target at any price. Same fields, with `budget_needed: null` |

### Summary

`POST /summary` with `{"recommendationId": "..."}` returns `{"why": str, "watch": [str], "source": "llm" or "solver"}`. Sarvam writes it from `vs_usual`, the reasons and `mix_catches`. If Sarvam fails, or its text has an amount or percent the facts do not, the solver's own sentences come back with `source: "solver"`.
