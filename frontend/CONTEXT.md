# Frontend context log

Living notes for the chat and voice UI. Updated by `/update-context`. Newest status first.

_Last updated: 2026-10-31, branch `fe/claim-fixture`._

## Status

- Frontend and backend are wired together. With `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`, `/recommend` (FastAPI, real solver, claim checks for years 1 to 4) drives the results screen. Tested in the browser.
- `/chat` on the backend uses Sarvam's LLM (`sarvam-105b-conversations`). Not tested yet: no `SARVAM_API_KEY` on this machine. Without it the backend returns 502 and the UI says the assistant is offline.
- "Use the demo family" loads in the browser in both modes, so the demo never waits on the LLM. The board also has "Add person".
- Without `NEXT_PUBLIC_API_BASE_URL` the app runs on the mock: questions come from `src/lib/mock/chat.ts` (pattern matching, fixed question order) and results from `shared/` data.
- Mock claim checks rebuilt from the fixed `claim_check()` (backend #7): year 1 works, and Lata's knee surgery is covered from year 3 on both options.
- Voice (`/api/stt`) is wired end to end. Needs `SARVAM_API_KEY` in `frontend/.env.local` to work.

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

1. Add `SARVAM_API_KEY` to `frontend/.env.local` (voice) and the repo-root `.env` (backend chat). Test voice and chat in Hindi, English and Hinglish.
2. Rewrite the demo script for real numbers: Mohan's year 2 heart claim is partly covered (₹1,80,000 co-pay).
3. Demo polish: phone layout, timing of the optimise animation, read-aloud with Sarvam Bulbul if time allows.
4. Whenever `backend/solver.py` changes, rerun `python3 frontend/scripts/gen_claim_checks.py` so the mock matches.

## Open questions

- The backend's LLM is Sarvam (`sarvam-105b-conversations`), not Claude. The root `CLAUDE.md` AI row should record this.
- Unknown health conditions: suggested the backend treats them as a general pre-existing condition. Backend's call.

## Run

```bash
# Backend (port 8000), needs SARVAM_API_KEY in the repo-root .env for /chat
cd backend && python3 -m venv .venv && .venv/bin/pip install --no-cache-dir -r requirements.txt
.venv/bin/uvicorn app:app --port 8000

# Frontend (port 3000)
cd frontend
cp .env.example .env.local   # SARVAM_API_KEY for voice; NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 for the real backend
npm install
npm run dev
```
