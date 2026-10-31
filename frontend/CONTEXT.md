# Frontend context log

Living notes for the chat and voice UI. Updated by `/update-context`. Newest status first.

_Last updated: 2026-10-31, on `main` (all frontend work merged, last PRs #22 and #23)._

## Status

- All frontend work is on `main`. No open frontend branches.
- Live data only. The app always calls the backend (default `http://localhost:8000`). The mock, demo data and claim-check fixture are gone.
- The repo-root `.env` now holds `SARVAM_API_KEY` on this machine. Without it `/chat` returned 502 and the app said "I can't reach the assistant".
- Board: member cards show short notes on what matters for each person (age band, conditions and their waiting periods, office cover, a missing age in amber). The "heard from" quote is gone.
- Intake end: when `/chat` first says the family is complete, the app says "I have all your information" and asks the user to check the board and tap "I have verified all my information" (Family board tab on phones, Hindi if they spoke Hindi). In talk mode it also ends talk mode. Only that button, or "Try again" after an error, starts the search.
- Talk mode: a wave button opens a voice panel (`TalkPanel.tsx`) in place of the message box. Live mic bars while listening, dots while thinking, amber waving bars while speaking (tap to interrupt), mute and end buttons. It sends on a 1.3 second pause and reopens the mic after the reply.
- Replies are read aloud with Sarvam text-to-speech via `/api/tts`, sentence by sentence: the first sentence plays while the rest are made. True WebSocket streaming was left out because it needs a relay server.
- Speech-to-text keeps the first Indian language it detects for the session.
- `/chat` requests carry `language` for spoken messages. The backend ignores it for now; the backend developer has been asked to make replies follow it. Today a Hindi message can still get an English reply. No frontend translation fallback, by choice.
- Results: navy summary box from `POST /summary` (skeleton while loading, left out if it fails), "Catches in this mix" from the solver's `mix_catches`, policy card catches from the solver. Not yet clicked through in the browser.
- Optimise screen follows the real `/recommend` call, with a "Still working" note after 6 seconds. Families with no single floater show a "No single floater fits" card.
- The dev page works at `127.0.0.1:3000` and from phones on the same Wi-Fi.
- Talk mode, sentence by sentence speech, the verify flow and the member notes pass type check and lint. They still need a full browser run.
- Seen in one `/chat` test: "मेरे माता पिता के लिए पॉलिसी चाहिए" added only "Self" and missed the parents. Reported to the backend developer.

## Decisions

| Decision | Why |
|---|---|
| Next.js 16 (App Router), TypeScript, Tailwind 4 | React, as in the deck. Server routes keep the Sarvam key off the browser without backend help. |
| Sarvam speech-to-text through `/api/stt`: auto-detect first, then the session language; insurance and Hindi family keyterms | Multilingual input. Keyterms help with "super top-up", "floater", names and family words. |
| Transcript is shown for review, never auto-sent; numbers highlighted | A misheard age or amount would feed the solver wrong data. |
| Talk mode is opt in: it auto-sends on a pause, reads replies aloud and reopens the mic | A real voice conversation for those who want it. The board still shows every number, so mistakes can be fixed. |
| Read replies in the language of the reply's script, not the user's | Sarvam needs the text and voice language to match. |
| Keep the first detected Indian language for the session; never keep English | Fixed language transcribes better on short clips. English is often only the opener. |
| Two-pane layout: chat on the left, a live canvas on the right (family board, then results) | The user sees their family build up as they talk and can fix any detail in one tap. Phones get Chat / Board tabs. |
| Member cards show short notes on what matters for that person (age band, conditions and waiting periods, office cover), not the "heard from" quote | The raw transcript added clutter, often in another script. The notes explain what the solver will weigh, with no prices. |
| Results: compare, per-person cover map, claim check with a year slider, policy cards with catches and clause chips | Matches the deck's Explain step and the Mohan claim story. |
| No mock: the app always calls the backend | The backend is live, and one code path is easier to trust in the demo. |
| Contract proposal in `docs/api-contract.md` | `shared/` needs agreement from both developers. |
| Use the backend's snake_case solver output as is; map it only in `src/lib/solver.ts` | No extra work for the backend, one place to change if the format moves. |
| `@shared/*` alias and Turbopack root kept in config, though nothing imports `shared/` since the mock went | Cheap to keep if the UI needs shared data again. |
| Show solver `reasons`, `next_best` and `vs_usual` text as is | The solver states the facts; the UI and LLM only present them, which keeps the core rule. |
| Policy citations open a "fine print" sheet built from the pick's own fields | The data has no clause text yet. Every sheet says it is from public brochures and not yet checked against the wording. |
| Strip the codec suffix from the audio type in `/api/stt` | Sarvam rejects `audio/webm;codecs=opus`, which is what Chrome records. |
| Offline message if `/chat` fails | The user can still fill the board by hand. |
| Read replies sentence by sentence, not over WebSockets | Faster start with no relay server. Sarvam WebSockets need the key in a header, which browsers can't send. |
| Send the spoken language to `/chat`; no frontend translation | The backend writes replies, so it should get the language right. |
| App's own "all details" message when intake completes; talk mode ends there | The user must check the facts the solver will use, and the button is in the other pane. |
| The search starts only from the verify button | A spoken "yes" could skip the check. |
| `usual` and `saving` on `Recommendation` are nullable; no made-up comparison when no single floater fits | The solver has nothing to compare with, and inventing a usual pick would show a fake price. |
| Optimise steps are paced by the real `/recommend` call; the solver's answer is held in `pending` until every step ticks | The old fixed timer ticked everything in 2.4 seconds, then sat still while big families took up to a minute. |
| Summary text comes from Sarvam via `/summary`, never written in the UI | Keeps the core rule: the backend checks every amount, percent and name against the solver's facts and falls back to the solver's sentences. |
| Fetch the summary separately, after the results show | The results never wait on the LLM. |
| Condition names follow `shared/README.md` (`hypertension`, `heart_disease`); the UI shows friendly labels | The solver matches conditions by name. |

## Next

1. Full browser run with the live backend: talk mode in Hindi and English, the verify message and button, member notes, summary box and mix catches, on desktop and phone widths.
2. Once the backend uses `language`, check that talk mode replies and their voice follow the user's language.
3. Rewrite the demo script for real numbers: Mohan's year 2 heart claim is partly covered (₹1,80,000 co-pay).
4. Demo polish: phone layout.

## Open questions

- The untracked `.history/` folder (editor local history) should go in the root `.gitignore`. That file is shared, so agree it with the backend developer.
- Sister and brother relations: does the solver accept them?
- Unknown health conditions: suggested the backend treats them as a general pre-existing condition. Backend's call.
- The summary is always in English. Should it follow the session language like the chat replies? Needs a backend change.
- Families of 8 can take about a minute in `/recommend` (the demo family plus people aged 40, 12 and 58 took 61 seconds; the backend runs CP-SAT at full CPU). The UI now says it is still working, but there is no timeout or cancel. Worth asking the backend for a solver time limit.

## Run

```bash
# Backend (port 8000), needs SARVAM_API_KEY in the repo-root .env for /chat
cd backend && python3 -m venv .venv && .venv/bin/pip install --no-cache-dir -r requirements.txt
.venv/bin/uvicorn app:app --reload --port 8000

# Frontend (port 3000)
cd frontend
cp .env.example .env.local   # SARVAM_API_KEY for voice; backend URL defaults to http://localhost:8000
npm install
npm run dev                  # open http://localhost:3000; 127.0.0.1 and Wi-Fi addresses also work
```
