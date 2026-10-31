# Voice (Sarvam AI)

## Flow

1. User taps the mic. `useRecorder` records with `MediaRecorder` (WebM/Opus on Chrome, MP4 on Safari) and draws a live waveform.
2. Recording stops on tap, or by itself at 28 seconds. Sarvam's REST endpoint only takes clips under 30 seconds.
3. The browser posts the clip to our route `POST /api/stt`. The route adds the key and forwards it to Sarvam.
4. The transcript lands in the message box, with the detected language and every number found highlighted in amber. The user checks it, edits if needed, then sends. Outside talk mode we never auto-send, because a misheard age or amount would go straight into the solver.
5. The first Indian language detected is kept for the session and sent with every later clip as `language`. English is not kept, because people often start in English and switch.

## Replies read aloud

- A reply is read aloud when the user's last message was spoken, or always in talk mode. A speaker button in the chat mutes it. Tapping the mic or "Reading aloud" stops it.
- `useSpeaker` posts the reply to `POST /api/tts`, which calls Sarvam text-to-speech and returns a WAV file.
- The voice language comes from the reply's script (`replyLanguage` in `src/lib/sarvam.ts`): Devanagari is Hindi (Marathi if the user spoke Marathi), Latin is English, and so on.
- Long replies are cut at a sentence end at 1,400 characters.

## Talk mode (hands free)

- A "Talk mode" switch above the message box. Turning it on opens the mic.
- `useRecorder` with `autoStop` learns the room's noise floor, then stops after at least 250 ms of speech followed by a 1.3 second pause. If nobody speaks for 8 seconds it drops the clip and asks the user to tap the mic.
- The transcript is sent straight away. The reply is read aloud, then the mic opens again. The numbers stay visible in the chat and on the family board, where they can be fixed.
- Tuning constants are at the top of `src/lib/useRecorder.ts`. If it stops too early in a noisy room, raise `SPEECH_ABOVE_FLOOR` or `PAUSE_MS`.

## Sarvam call

- `POST https://api.sarvam.ai/speech-to-text`, header `api-subscription-key`.
- Multipart fields we send: `file`, `language_code` (the session language if known, else `unknown` for auto-detect), `keyterms` (JSON array of insurance terms, Hindi family words and demo names, improves spelling), plus `model` and `mode` only if set in env.
- API defaults: model `saaras:v4`, mode `transcribe`. Other modes: `translate` (to English), `codemix`, `translit`, `verbatim`.
- Response used: `transcript`, `language_code`.
- File type: send the bare MIME type. Chrome records `audio/webm;codecs=opus`, which Sarvam rejects with a 400, so the route strips everything after `;`.
- Errors: 400 bad file type, 403 bad key, 429 quota, 422 bad input. The route turns these into short user messages and logs the detail.

## Text-to-speech call

- `POST https://api.sarvam.ai/text-to-speech`, header `api-subscription-key`, JSON body `text`, `target_language_code`, plus `model` and `speaker` only if set in env.
- Response used: `audios[0]`, a base64 WAV.

## Env

`SARVAM_API_KEY` (required), `SARVAM_STT_MODEL`, `SARVAM_STT_MODE`, `SARVAM_STT_LANGUAGE`, `SARVAM_TTS_MODEL`, `SARVAM_TTS_SPEAKER` (optional). Put them in `frontend/.env.local`.

## Ideas if time allows

- Streaming speech-to-text over WebSocket for live captions.
- Send the spoken language to `/chat`, so mixed Hindi and English input still gets a Hindi reply. Needs a small contract change agreed with the backend.
