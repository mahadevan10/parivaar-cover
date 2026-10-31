# API contract (proposal from frontend)

Status: **proposal, not yet agreed with backend.** Once agreed, move it to `shared/` and keep `src/lib/types.ts` in sync.

The frontend calls the backend at `NEXT_PUBLIC_API_BASE_URL`. With it unset, the UI uses its built-in mock, which follows this same contract. JSON keys are camelCase. Money is whole rupees as numbers.

## POST /chat

The LLM talks to the user and pulls family details out of what they say. It does not pick policies or quote prices.

Request:

```json
{
  "sessionId": "uuid",
  "message": "My father Mohan is 64 and diabetic",
  "family": { "...FamilyProfile, as the user currently sees and edits it" },
  "history": [{ "role": "assistant", "text": "..." }, { "role": "user", "text": "..." }],
  "recommendationId": "only after /recommend, so questions get answered from that result"
}
```

Response:

```json
{
  "reply": "Noted: Mohan, 64, diabetes. Does anyone else have a health condition?",
  "family": { "...updated FamilyProfile" },
  "missing": ["City", "Yearly budget"],
  "quickReplies": ["No one else"],
  "readyToOptimise": false,
  "citations": ["c-ped-senior"]
}
```

- The user can edit the family board directly, so always treat the `family` in the request as the latest truth and return a full updated copy.
- Keep each member's `id` stable across turns. The board animates by id.
- `citations` are clause ids from the current recommendation. The UI turns them into tappable chips.

### FamilyProfile

```json
{
  "members": [
    { "id": "mohan", "name": "Mohan", "relation": "father", "age": 64, "conditions": ["diabetes"], "heardFrom": "my father Mohan is 64 and diabetic" }
  ],
  "city": "Pune",
  "budget": 110000,
  "officeCover": { "amount": 500000, "memberIds": ["rahul"] },
  "healthChecked": true,
  "officeChecked": true
}
```

`heardFrom` is the phrase the details came from. The board shows it so the user can spot a mishearing.

## POST /recommend

Request: `{ "sessionId": "uuid", "family": FamilyProfile }`

Response: `Recommendation`. See `src/lib/mock/demo.ts` for a full example with the deck's demo family.

```json
{
  "id": "rec-123",
  "illustrative": true,
  "usual": PlanOption,
  "mix": PlanOption,
  "clauses": { "c-ped-senior": { "id", "title", "text", "source" } },
  "claimScenarios": [ClaimScenario]
}
```

- `PlanOption`: `label`, `premium`, `totalCover`, `highlights[]`, `policies[]`.
- `Policy`: `id`, `planName`, `insurer`, `kind` (`floater` | `individual` | `senior` | `super_top_up`), `memberIds[]`, `sumInsured`, `deductible?`, `premium`, `why`, `catches[]`, `clauseIds[]`.
- `ClaimScenario`: `id`, `memberId`, `label`, `amount`, `byYear[]` where each entry is `{ year, usual: ClaimOutcome, mix: ClaimOutcome }`. The UI has a year slider, so send years 1 to 4.
- `ClaimOutcome`: `covered`, `paidBy[{ policyId, amount }]`, `outOfPocket`, `reason`, `clauseId?`.

The claim simulator lives in the backend. The UI only displays its results.

## Needs CORS

Allow `http://localhost:3000` during development.
