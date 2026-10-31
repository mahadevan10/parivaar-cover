# API contract (frontend view)

Status: **the frontend now uses the backend's own formats from `shared/README.md`.** Only the HTTP wrapping below is new and needs the backend developer's agreement. Once agreed, move it to `shared/`.

All solver data stays in the backend's snake_case. `src/lib/solver.ts` is the only frontend file that maps it to UI types.

## POST /recommend

Request:

```json
{ "family": SolverFamily }
```

`SolverFamily` is the family input format from `shared/README.md` (`id`, `city`, `budget`, `cover_target`, `members[]`, `office_cover[]`). `cover_target` is the total cover the family wants, or `null` when they are not sure. Conditions use `diabetes`, `hypertension`, `asthma`, `heart_disease`. Relation for a wife or husband is sent as `spouse`. Member ids come from the frontend and must be echoed back unchanged.

Response:

```json
{
  "solution": SolverOutput,
  "claim_checks": [ClaimSeries]
}
```

- `solution` is exactly what `solve()` returns (see `shared/examples/demo_solver_output.json`). `status: "no_fit"` shows a "no mix fits this budget" message.
- `solution.cover_check` is `null` without a `cover_target`. `cover_met` adds a "You asked for" chip to the mix card. `cover_short` (the budget cannot buy that cover) and `cover_out_of_reach` show an amber banner above the summary with its `text`, which names the budget needed.
- `solution.usual_pick` and `saving_vs_usual` are `null` when no single floater can take the whole family, for example a parent past the floaters' entry age. `vs_usual` is then empty and each claim year has `usual: null`. The results screen shows "No single floater fits" in place of the usual pick.
- `claim_checks` is optional. Each entry runs `claim_check()` for policy years 1 to 4, for the mix and the usual pick:

```json
{
  "id": "mohan-heart",
  "member_id": "mohan",
  "label": "Heart procedure",
  "amount": 600000,
  "by_year": [{ "policy_year": 1, "mix": ClaimResult, "usual": ClaimResult }]
}
```

If `claim_checks` is missing, the UI falls back to `solution.claim_check` as a single year.

`solution.mix_catches` lists catches from how the picks stack (codes in `shared/README.md`), each with `members` and a plain `text`. The results screen shows them under "Catches in this mix". Each pick's `catches` is built by the solver from the policy fields.

## POST /summary

Request: `{ "recommendationId": "rec-..." }`, the id from `/recommend`.

Response:

```json
{
  "why": "This mix costs ₹1,07,000 a year, ₹11,000 less than the usual pick. ...",
  "watch": ["Mohan's diabetes is covered by Senior Citizens Red Carpet after 1 year and by the ManipalCigna top-up after 2 years."],
  "source": "llm"
}
```

Sarvam writes it from the solver's facts. `source` is `"solver"` when Sarvam failed or its text had an amount, percent or name the facts do not, and the text is then the solver's own sentences. The results screen shows it in the box at the top and leaves the box out if the call fails.

## POST /chat

The LLM talks to the user and pulls family details out of what they say. It does not pick policies or quote prices.

Request:

```json
{
  "sessionId": "uuid",
  "message": "My father Mohan is 64 and diabetic",
  "family": FamilyProfile,
  "history": [{ "role": "assistant", "text": "..." }, { "role": "user", "text": "..." }],
  "recommendationId": "set after /recommend, so follow-up questions are answered from that result",
  "language": "hi-IN"
}
```

`language` is set when the message was spoken: the language Sarvam detected. The reply should be in that language. It is missing for typed messages.

Response:

```json
{
  "reply": "Noted: Mohan, 64, diabetes. Does anyone else have a health condition?",
  "family": FamilyProfile,
  "missing": ["City", "Yearly budget"],
  "quickReplies": ["No one else"],
  "readyToOptimise": false,
  "citations": ["star-red-carpet-10l"]
}
```

`FamilyProfile` is the UI's working copy of the family (camelCase, see `src/lib/types.ts`):

```json
{
  "members": [{ "id": "mohan", "name": "Mohan", "relation": "father", "age": 64, "conditions": ["diabetes"], "heardFrom": "my father Mohan is 64 and diabetic" }],
  "city": "Pune",
  "budget": 110000,
  "officeCover": { "amount": 500000, "memberIds": ["rahul"] },
  "healthChecked": true,
  "officeChecked": true,
  "coverTarget": 10000000,
  "coverChecked": true
}
```

- The user can edit the board directly, so treat the request's `family` as the latest truth and return a full updated copy. Keep member ids stable.
- `heardFrom` is the phrase the details came from. Optional.
- `coverChecked` is true once the user gave a cover amount or picked the "Not sure" quick reply. "Cover you want" stays in `missing` until then.
- `citations` are `policy_id`s from the current solution. The UI turns them into "fine print" chips.

## CORS

Allow `http://localhost:3000` during development.
