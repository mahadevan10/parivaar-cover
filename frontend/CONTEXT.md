# Frontend context log

Living notes for the chat and voice UI. Updated by `/update-context`. Newest status first.

_Last updated: 2026-10-31, branch `fe/voice-conversation` (replies read aloud, talk mode, session language; latest `main` merged in)._

## Status

- `fe/voice-conversation` adds replies read aloud (Sarvam text-to-speech via `/api/tts`), a hands-free talk mode and a sticky session language for speech-to-text. `/api/tts` was checked with one request and returns Hindi audio. Talk mode and the pause detection still need a browser test.
- Voice input works in the browser after #10 (Chrome's `audio/webm;codecs=opus` type is stripped to the bare type).
- A Hindi voice message got an English reply when the app ran on the mock, whose replies are fixed English templates. The backend `/chat` prompt replies in the user's language.
- The mock now knows माता and पिता. It still has no sister or brother relation.
- Families with no single floater now work. When a parent is past the floaters' entry age (Mohan at 70, say), the backend sends `usual_pick: null`. The UI shows the mix with a "No single floater fits" card. Tested in the browser.
- The dev page works at `127.0.0.1:3000` and from phones on the same Wi-Fi (`allowedDevOrigins` in `next.config.ts`). The backend CORS allows the same origins (backend #11).
- `findMix` logs the real error to the console before showing the generic message.
- Frontend and backend are wired together. With `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`, `/recommend` (FastAPI, real solver, claim checks for years 1 to 4) drives the results screen. Tested in the browser.
- `/chat` on the backend uses Sarvam's LLM (`sarvam-105b-conversations`). Tested with a four-turn English intake: it built the demo family and the solver returned the deck mix. Without `SARVAM_API_KEY` the backend returns 502 and the UI says the assistant is offline.
- "Use the demo family" loads in the browser in both modes, so the demo never waits on the LLM. The board also has "Add person".
- Without `NEXT_PUBLIC_API_BASE_URL` the app runs on the mock: questions come from `src/lib/mock/chat.ts` (pattern matching, fixed question order) and results from `shared/` data.
- Mock claim checks rebuilt from the fixed `claim_check()` (backend #7): year 1 works, and Lata's knee surgery is covered from year 3 on both options.

## Decisions

| Decision | Why |
|---|---|
| Next.js 16 (App Router), TypeScript, Tailwind 4 | React, as in the deck. Server routes keep the Sarvam key off the browser without backend help. |
| Sarvam speech-to-text through `/api/stt`, `language_code=unknown`, insurance keyterms | Multilingual input with auto-detect. Keyterms help with "super top-up", "floater" and names. |
| Transcript is shown for review, never auto-sent; numbers highlighted | A misheard age or amount would feed the solver wrong data. |
| Talk mode is opt in: it auto-sends on a pause, reads replies aloud and reopens the mic | A real voice conversation for those who want it. The board still shows every number, so mistakes can be fixed. |
| Read replies in the language of the reply's script, not the user's | Sarvam needs the text and voice language to match. |
| Keep the first detected Indian language for the session; never keep English | Fixed language transcribes better on short clips. English is often only the opener. |
| Two-pane layout: chat on the left, a live canvas on the right (family board, then results) | The user sees their family build up as they talk and can fix any detail in one tap. Phones get Chat / Board tabs. |
| Every fact keeps a "heard from" quote | Shows where each detail came from, builds trust in voice input. |
| Results: compare, per-person cover map, claim check with a year slider, policy cards with catches and clause chips | Matches the deck's Explain step and the Mohan claim story. |
| Mock backend in `src/lib/mock/` following the same contract | UI is demoable before the backend is ready. |
| Contract proposal in `docs/api-contract.md` | `shared/` needs agreement from both developers. |
| Use the backend's snake_case solver output as is; map it only in `src/lib/solver.ts` | No extra work for the backend, one place to change if the format moves. |
| Import `shared/` JSON directly (`@shared/*` alias, Turbopack root set to the repo) | Demo uses real solver data and stays in sync with backend changes. |
| Show solver `reasons`, `next_best` and `vs_usual` text as is | The solver states the facts; the UI and LLM only present them, which keeps the core rule. |
| Policy citations open a "fine print" sheet built from the pick's own fields | The data has no clause text yet. Every sheet says it is from public brochures and not yet checked against the wording. |
| Strip the codec suffix from the audio type in `/api/stt` | Sarvam rejects `audio/webm;codecs=opus`, which is what Chrome records. |
| Demo family loads in the browser; offline message if `/chat` fails | The demo must not depend on the LLM being up. |
| `usual` and `saving` on `Recommendation` are nullable; no made-up comparison when no single floater fits | The solver has nothing to compare with, and inventing a usual pick would show a fake price. |
| Condition names follow `shared/README.md` (`hypertension`, `heart_disease`); the UI shows friendly labels | The solver matches conditions by name. |

## Next

1. Test `fe/voice-conversation` in the browser: replies read aloud, talk mode, pause detection in a noisy room, Hindi and Hinglish with the real backend. Then merge it.
2. Rewrite the demo script for real numbers: Mohan's year 2 heart claim is partly covered (₹1,80,000 co-pay).
3. Demo polish: phone layout, timing of the optimise animation.
4. Whenever `backend/solver.py` changes, rerun `python3 frontend/scripts/gen_claim_checks.py` so the mock matches.

## Open questions

- The untracked `.history/` folder (editor local history) should go in the root `.gitignore`. That file is shared, so agree it with the backend developer.
- Should `/chat` take the spoken language, so mixed Hindi and English input gets a Hindi reply? Needs a contract change with the backend.
- Sister and brother relations: does the solver accept them?
- Unknown health conditions: suggested the backend treats them as a general pre-existing condition. Backend's call.
- Families of 8 or more take about 18 seconds in `/recommend` (7 take about 3). The optimise screen just waits. Fine for the demo family; worth a timeout message if we show bigger families.

## Run

```bash
# Backend (port 8000), needs SARVAM_API_KEY in the repo-root .env for /chat
cd backend && python3 -m venv .venv && .venv/bin/pip install --no-cache-dir -r requirements.txt
.venv/bin/uvicorn app:app --port 8000

# Frontend (port 3000)
cd frontend
cp .env.example .env.local   # SARVAM_API_KEY for voice; NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 for the real backend
npm install
npm run dev                  # open http://localhost:3000; 127.0.0.1 and Wi-Fi addresses also work
```
