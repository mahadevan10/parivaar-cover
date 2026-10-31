# Frontend context log

Living notes for the chat and voice UI. Updated by `/update-context`. Newest status first.

_Last updated: 2026-10-31, branch `fe/live-only` (mock removed, ready message)._

## Status

- The app runs on live data only. The mock chat, demo data, claim-check fixture and its generator script are gone (#17 already removed "Use the demo family"). The backend must be running; the URL defaults to `http://localhost:8000`.
- When `/chat` first says the family is complete, the app adds its own message: "I have all the details I need", pointing to Find my mix on the right (or the Family board tab on phones), in Hindi if the user spoke Hindi. The backend's own ready line is dropped so it isn't said twice. The Find my mix button glows while ready. Saying or typing "go ahead", "proceed", "chalo" or "हाँ" also starts the search.
- Replies are read aloud (Sarvam text-to-speech via `/api/tts`), with a hands-free talk mode and a sticky session language for speech-to-text. Merged in #13.
- The optimise screen now follows the real request. "Testing combinations" keeps spinning until `/recommend` answers, then the last two checks tick, a "Done" line shows, and the results open. After 6 seconds a "Still working" note appears. Tested in the browser: the demo family takes 3.5 seconds end to end; a family of 8 took about 61 seconds and waited correctly.
- Fixed a duplicate React key warning when the mix holds the same product twice (big families get two Super Surplus Gold top-ups).
- Voice input works in the browser after #10 (Chrome's `audio/webm;codecs=opus` type is stripped to the bare type).
- The backend `/chat` prompt replies in the user's language.
- Families with no single floater now work. When a parent is past the floaters' entry age (Mohan at 70, say), the backend sends `usual_pick: null`. The UI shows the mix with a "No single floater fits" card. Tested in the browser.
- The dev page works at `127.0.0.1:3000` and from phones on the same Wi-Fi (`allowedDevOrigins` in `next.config.ts`). The backend CORS allows the same origins (backend #11).
- `findMix` logs the real error to the console before showing the generic message.
- Frontend and backend are wired together. `/recommend` (FastAPI, real solver, claim checks for years 1 to 4) drives the results screen. Tested in the browser.
- `/chat` on the backend uses Sarvam's LLM (`sarvam-105b-conversations`). Tested with a four-turn English intake: it built the demo family and the solver returned the deck mix. Without `SARVAM_API_KEY` the backend returns 502 and the UI says the assistant is offline.
- If `/chat` is down, the UI says the assistant is offline and the family board can still be filled by hand. The board has "Add person".

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
| No mock: the app always calls the backend | The backend is live, and one code path is easier to trust in the demo. |
| Contract proposal in `docs/api-contract.md` | `shared/` needs agreement from both developers. |
| Use the backend's snake_case solver output as is; map it only in `src/lib/solver.ts` | No extra work for the backend, one place to change if the format moves. |
| Import `shared/` JSON directly (`@shared/*` alias, Turbopack root set to the repo) | Demo uses real solver data and stays in sync with backend changes. |
| Show solver `reasons`, `next_best` and `vs_usual` text as is | The solver states the facts; the UI and LLM only present them, which keeps the core rule. |
| Policy citations open a "fine print" sheet built from the pick's own fields | The data has no clause text yet. Every sheet says it is from public brochures and not yet checked against the wording. |
| Strip the codec suffix from the audio type in `/api/stt` | Sarvam rejects `audio/webm;codecs=opus`, which is what Chrome records. |
| Offline message if `/chat` fails | The user can still fill the board by hand. |
| App's own "all details" message when intake completes | The user needs a clear next step, and the button is in the other pane. |
| `usual` and `saving` on `Recommendation` are nullable; no made-up comparison when no single floater fits | The solver has nothing to compare with, and inventing a usual pick would show a fake price. |
| Optimise steps are paced by the real `/recommend` call; the solver's answer is held in `pending` until every step ticks | The old fixed timer ticked everything in 2.4 seconds, then sat still while big families took up to a minute. |
| Condition names follow `shared/README.md` (`hypertension`, `heart_disease`); the UI shows friendly labels | The solver matches conditions by name. |

## Next

1. Tune talk mode after more browser use: pause detection in a noisy room, Hindi and Hinglish with the real backend.
2. Rewrite the demo script for real numbers: Mohan's year 2 heart claim is partly covered (₹1,80,000 co-pay).
3. Demo polish: phone layout.

## Open questions

- The untracked `.history/` folder (editor local history) should go in the root `.gitignore`. That file is shared, so agree it with the backend developer.
- Should `/chat` take the spoken language, so mixed Hindi and English input gets a Hindi reply? Needs a contract change with the backend.
- Sister and brother relations: does the solver accept them?
- Unknown health conditions: suggested the backend treats them as a general pre-existing condition. Backend's call.
- Families of 8 can take about a minute in `/recommend` (the demo family plus people aged 40, 12 and 58 took 61 seconds; the backend runs CP-SAT at full CPU). The UI now says it is still working, but there is no timeout or cancel. Worth asking the backend for a solver time limit.

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
