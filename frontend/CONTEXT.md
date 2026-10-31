# Frontend context log

Living notes for the chat and voice UI. Updated by `/update-context`. Newest status first.

_Last updated: 2026-10-31, branch `fe/solver-adapter`._

## Status

- Chat and voice UI is on `main` (PR #2).
- The frontend now reads the backend's real data: `shared/families.json` for the demo family and `shared/examples/demo_solver_output.json` for the result. Real products (Star Health, ManipalCigna, Reliance), catches, co-pays and waits show on screen.
- Policy cards show the solver's own `reasons` ("why this pick") and its `next_best` option. The compare block shows `vs_usual` facts. Nothing is invented in the UI.
- Claim check year 1 to 4 comes from the backend's `claim_check()`, saved in `src/lib/mock/claim_checks.json` by `scripts/gen_claim_checks.py`.
- Mohan's year 2 heart claim now shows as partly covered: the mix pays ₹4,20,000 and he pays ₹1,80,000 (30% co-pay). The usual pick pays nothing until year 4.
- `/api/stt` reaches Sarvam and handles errors. Not yet tested with the real key.
- Backend has no HTTP API yet. Set `NEXT_PUBLIC_API_BASE_URL` once `/chat` and `/recommend` are up.

## Decisions

| Decision | Why |
|---|---|
| Next.js 16 (App Router), TypeScript, Tailwind 4 | React, as in the deck. Server routes keep the Sarvam key off the browser without backend help. |
| Sarvam speech-to-text through `/api/stt`, `language_code=unknown`, insurance keyterms | Multilingual input with auto-detect. Keyterms help with "super top-up", "floater" and names. |
| Transcript is shown for review, never auto-sent; numbers highlighted | A misheard age or amount would feed the solver wrong data. |
| Two-pane layout: chat on the left, a live canvas on the right (family board, then results) | The user sees their family build up as they talk and can fix any detail in one tap. Phones get Chat / Board tabs. |
| Every fact keeps a "heard from" quote | Shows where each detail came from, builds trust in voice input. |
| Results: compare, per-person cover map, claim check with a year slider, policy cards with catches and clause chips | Matches the deck's Explain step and the Mohan claim story. |
| Mock backend in `src/lib/mock/` following the same contract | UI is demoable before the backend is ready. |
| Contract proposal in `docs/api-contract.md` | `shared/` needs agreement from both developers. |
| Use the backend's snake_case solver output as is; map it only in `src/lib/solver.ts` | No extra work for the backend, one place to change if the format moves. |
| Import `shared/` JSON directly (`@shared/*` alias, Turbopack root set to the repo) | Demo uses real solver data and stays in sync with backend changes. |
| Show solver `reasons`, `next_best` and `vs_usual` text as is | The solver states the facts; the UI and LLM only present them, which keeps the core rule. |
| Policy citations open a "fine print" sheet built from the pick's own fields | The data has no clause text yet. Every sheet says it is from public brochures and not yet checked against the wording. |
| Condition names follow `shared/README.md` (`hypertension`, `heart_disease`); the UI shows friendly labels | The solver matches conditions by name. |

## Next

1. Add the real `SARVAM_API_KEY` and test voice in Hindi, English and Hinglish.
2. Agree `docs/api-contract.md` with the backend developer, then move it to `shared/`.
3. When the backend serves `/recommend` and `/chat`, set `NEXT_PUBLIC_API_BASE_URL` and test against it.
4. After backend fixes to `claim_check()`, rerun `python3 frontend/scripts/gen_claim_checks.py`.
5. Demo polish: phone layout check, demo script, optional read-aloud with Sarvam Bulbul.

## Open questions

- Backend `claim_check()`: in year 1 every claim fails, because months in force is 0 and the 1-month initial wait blocks it. The note then says "covers this only from year 1". Told to the user to pass on.
- Backend `claim_check()` does not apply the 2-year wait for listed illnesses (knee, cataract), so those pay from year 2. The knee scenario is left out until fixed.
- The backend uses Sarvam chat (`sarvam-105b`) in `backend/sarvam_hello.py`. Is that the explainer LLM instead of Claude? The root `CLAUDE.md` AI row should say which.
- Will `/chat` return `heardFrom` per member? If not, the board hides that line.

## Run

```bash
cd frontend
cp .env.example .env.local   # add SARVAM_API_KEY
npm install
npm run dev                  # http://localhost:3000
```
