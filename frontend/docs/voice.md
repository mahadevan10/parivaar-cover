# Voice input (Sarvam AI)

## Flow

1. User taps the mic. `useRecorder` records with `MediaRecorder` (WebM/Opus on Chrome, MP4 on Safari) and draws a live waveform.
2. Recording stops on tap, or by itself at 28 seconds. Sarvam's REST endpoint only takes clips under 30 seconds.
3. The browser posts the clip to our route `POST /api/stt`. The route adds the key and forwards it to Sarvam.
4. The transcript lands in the message box, with the detected language and every number found highlighted in amber. The user checks it, edits if needed, then sends. We never auto-send, because a misheard age or amount would go straight into the solver.

## Sarvam call

- `POST https://api.sarvam.ai/speech-to-text`, header `api-subscription-key`.
- Multipart fields we send: `file`, `language_code=unknown` (auto-detect), `keyterms` (JSON array of insurance terms and demo names, improves spelling), plus `model` and `mode` only if set in env.
- API defaults: model `saaras:v4`, mode `transcribe`. Other modes: `translate` (to English), `codemix`, `translit`, `verbatim`.
- Response used: `transcript`, `language_code`.
- Errors: 403 bad key, 429 quota, 422 bad input. The route turns these into short user messages and logs the detail.

## Env

`SARVAM_API_KEY` (required), `SARVAM_STT_MODEL`, `SARVAM_STT_MODE`, `SARVAM_STT_LANGUAGE` (optional). Put them in `frontend/.env.local`.

## Ideas if time allows

- Read answers aloud with Sarvam Bulbul text to speech.
- Streaming speech-to-text over WebSocket for live captions.
