# Frontend context log

Living notes for the chat and voice UI. Updated by `/update-context`. Newest status first.

_Last updated: 2026-10-31, branch `fe/chat-voice`._

## Status

- Next.js app runs on the mock backend. The full demo flow works end to end: talk (voice or text), live family board, find my mix, results with claim check.
- `/api/stt` reaches Sarvam and handles errors. Not yet tested with the real key.
- Backend not wired yet. Set `NEXT_PUBLIC_API_BASE_URL` once `/chat` and `/recommend` are up.

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

## Next

1. Add the real `SARVAM_API_KEY` and test voice in Hindi, English and Hinglish.
2. Agree the contract with the backend developer, move it to `shared/`.
3. Point `NEXT_PUBLIC_API_BASE_URL` at the backend and remove mock-only paths from the demo script.
4. Demo polish: phone layout check, demo script, optional read-aloud with Sarvam Bulbul.

## Open questions

- Does the backend return `heardFrom` per member? If not, the UI hides that line.
- Does `/recommend` include claim scenarios, or is there a separate `/claim-check`?

## Run

```bash
cd frontend
cp .env.example .env.local   # add SARVAM_API_KEY
npm install
npm run dev                  # http://localhost:3000
```
