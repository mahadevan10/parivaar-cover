# frontend/CLAUDE.md

Chat and voice UI for Parivaar Cover. Read the root `CLAUDE.md` first, then `CONTEXT.md` in this folder for where the work stands.

@AGENTS.md

## Rules for this folder

- Only edit files inside `frontend/`. Backend (solver, LLM calls) belongs to the other developer. Contract changes go through `docs/api-contract.md` and need their agreement before moving to `shared/`.
- The UI never picks policies or computes premiums. It shows what `/recommend` returns. There is no mock; the app needs the backend running.
- Every place that shows a premium must say it is illustrative.
- Copy follows the root product copy rules: short plain sentences, sentence case, no dashes as punctuation, no hype.
- After a meaningful change, run `/update-context` so `CONTEXT.md` stays current.

## Map

| Path | What |
|---|---|
| `src/components/App.tsx` | State and flow: talk, fine print, optimise, explain |
| `src/components/ChatPanel.tsx`, `Composer.tsx` | Chat thread, quick replies, mic and transcript check |
| `src/components/FamilyBoard.tsx` | Live family board that fills as the user talks, editable |
| `src/components/Results.tsx` | Compare, cover map, claim check, policy cards |
| `src/components/FinePrintSheet.tsx` | Fine print for one policy |
| `src/app/api/stt/route.ts` | Sarvam speech-to-text proxy (keeps the key server side) |
| `src/app/api/tts/route.ts` | Sarvam text-to-speech proxy, reads replies aloud |
| `src/lib/useRecorder.ts`, `useSpeaker.ts` | Mic recording with pause detection for talk mode; reply playback |
| `src/lib/api.ts` | Backend client (`/chat`, `/recommend`) |
| `src/lib/types.ts` | Request and response shapes (mirror of `docs/api-contract.md`) |
| `src/lib/solver.ts` | Backend formats and the mapping to UI types |
