"use client";

import { useEffect, useRef, useState } from "react";
import { transcribe } from "@/lib/api";
import { languageName } from "@/lib/format";
import { SARVAM_LANGUAGES } from "@/lib/sarvam";
import { MAX_SECONDS, useRecorder } from "@/lib/useRecorder";
import { MicIcon, SendIcon, SpinnerIcon, StopIcon, WaveIcon, XIcon } from "./icons";
import { TalkPanel, type TalkState } from "./TalkPanel";

export type SendMeta = { via: "voice" | "text"; language?: string };

type VoiceDraft = { language?: string; numbers: string[] };

const NUMBER_RE = /(?:₹\s*)?\d[\d,.]*\s*(?:lakhs?|lacs?|k\b|thousand|crores?|years?|yrs|saal)?/gi;

export function Composer({
  onSend, disabled, placeholder, handsFree = false, listenToken = 0, onMicStart, toolbar,
  speaking = false, muted = false, onToggleMute, onTalkMode,
}: {
  onSend: (text: string, meta: SendMeta) => void;
  disabled: boolean;
  placeholder: string;
  /** Talk mode: stop on a pause, send without review. */
  handsFree?: boolean;
  /** Each new value opens the mic, e.g. after a spoken reply ends. */
  listenToken?: number;
  /** Called when the user starts speaking, so a reply being read aloud stops. */
  onMicStart?: () => void;
  /** Voice controls shown above the input. */
  toolbar?: React.ReactNode;
  /** A reply is being read aloud. */
  speaking?: boolean;
  muted?: boolean;
  onToggleMute?: () => void;
  /** Turn talk mode on or off. */
  onTalkMode?: (on: boolean) => void;
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [voice, setVoice] = useState<VoiceDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  // The first Indian language Sarvam detects is kept for the rest of the session.
  // English is not kept, since people often switch from English to their own language.
  const sessionLanguage = useRef<string | undefined>(undefined);

  const onClip = async (clip: Blob) => {
    setBusy(true);
    setError(null);
    try {
      const { transcript, languageCode } = await transcribe(clip, sessionLanguage.current);
      if (!transcript) {
        setError("I didn't hear anything. Try again a little closer to the mic.");
        return;
      }
      if (!sessionLanguage.current && languageCode && languageCode !== "en-IN" && SARVAM_LANGUAGES.has(languageCode)) {
        sessionLanguage.current = languageCode;
      }
      if (handsFree) {
        onSend(text.trim() ? `${text.trim()} ${transcript}` : transcript, { via: "voice", language: languageCode });
        setText("");
        setVoice(null);
        return;
      }
      setText((prev) => (prev ? `${prev} ${transcript}` : transcript));
      setVoice({ language: languageCode, numbers: [...new Set(transcript.match(NUMBER_RE)?.map((n) => n.trim()) ?? [])] });
      requestAnimationFrame(() => inputRef.current?.focus());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Voice failed. Please type instead.");
    } finally {
      setBusy(false);
    }
  };

  const rec = useRecorder({
    onClip,
    onNoSpeech: () => setError("I didn't hear anything. Tap the mic when you're ready."),
    autoStop: handsFree,
    onBargeIn: () => onMicStart?.(),
  });

  const listen = () => {
    onMicStart?.();
    void rec.start();
  };

  // Talk mode reopens the mic when asked, unless it's already busy.
  const startRef = useRef(rec.start);
  useEffect(() => {
    startRef.current = rec.start;
  }, [rec.start]);
  useEffect(() => {
    if (listenToken > 0) void startRef.current();
  }, [listenToken]);

  // Barge in: in talk mode the mic watches while a reply is read, so the user can cut in.
  const { recording, armed, cancel } = rec;
  useEffect(() => {
    if (handsFree && speaking && !recording && !busy) void startRef.current({ armed: true });
    // The reply ended without a barge in: record the next turn now.
    else if (handsFree && !speaking && armed) void startRef.current();
  }, [handsFree, speaking, recording, busy, armed]);
  useEffect(() => {
    if (!handsFree && armed) cancel();
  }, [handsFree, armed, cancel]);

  // Grow the textarea with its content.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  const send = () => {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t, voice ? { via: "voice", language: voice.language } : { via: "text" });
    setText("");
    setVoice(null);
    setError(null);
  };

  const shownError = error ?? rec.error;
  const talkState: TalkState = rec.recording ? "listening" : busy || disabled ? "thinking" : speaking ? "speaking" : "idle";
  const tapTalk = () => {
    if (rec.recording) rec.stop();
    else if (talkState !== "thinking") listen();
  };
  const lang = languageName(voice?.language);

  return (
    <div className="border-t border-line bg-white p-3">
      {toolbar}
      {voice && !rec.recording && (
        <div className="pop-in mb-2 rounded-xl bg-sky-soft px-3 py-2 text-xs text-ink">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium">
              <MicIcon className="mr-1 inline h-3.5 w-3.5 text-sky" />
              {lang ? `Heard in ${lang}.` : "Heard you."} Check it, edit if needed, then send.
            </span>
            <button type="button" aria-label="Discard voice text" onClick={() => { setText(""); setVoice(null); }}
              className="rounded-full p-0.5 text-muted hover:bg-white">
              <XIcon className="h-3.5 w-3.5" />
            </button>
          </div>
          {voice.numbers.length > 0 && (
            <div className="mt-1.5 flex flex-wrap items-center gap-1">
              <span className="text-muted">Numbers I heard:</span>
              {voice.numbers.map((n) => (
                <span key={n} className="rounded-md bg-amber px-1.5 py-0.5 font-semibold text-navy">{n}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {shownError && (
        <p role="alert" className="mb-2 rounded-lg bg-rose-50 px-3 py-1.5 text-xs text-rose-700">{shownError}</p>
      )}

      {handsFree ? (
        <TalkPanel
          state={talkState}
          levels={rec.levels}
          muted={muted}
          onTap={tapTalk}
          onToggleMute={() => onToggleMute?.()}
          onEnd={() => {
            rec.cancel();
            onTalkMode?.(false);
          }}
        />
      ) : (
      <>
      <div className="flex items-end gap-2">
        {rec.recording ? (
          <Recording levels={rec.levels} seconds={rec.seconds} handsFree={handsFree} onCancel={rec.cancel} />
        ) : (
          <textarea
            ref={inputRef}
            rows={1}
            value={text}
            disabled={busy}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                send();
              }
            }}
            placeholder={busy ? "Turning your voice into text..." : placeholder}
            aria-label="Message"
            className="min-h-11 flex-1 resize-none rounded-2xl border border-line bg-canvas px-4 py-2.5 text-[15px] leading-6 placeholder:text-muted/70 focus:border-sky focus:bg-white focus:outline-none"
          />
        )}

        <MicButton
          recording={rec.recording}
          busy={busy}
          onStart={listen}
          onStop={rec.stop}
        />

        {!rec.recording && !text.trim() && onTalkMode && (
          <button
            type="button"
            onClick={() => onTalkMode(true)}
            disabled={disabled || busy}
            aria-label="Start talk mode"
            title="Talk mode: a hands-free voice conversation"
            className="flex h-11 w-11 items-center justify-center rounded-full bg-navy text-white transition hover:bg-navy/90 disabled:bg-navy/25"
          >
            <WaveIcon />
          </button>
        )}

        {!rec.recording && (text.trim() || !onTalkMode) && (
          <button
            type="button"
            onClick={send}
            disabled={!text.trim() || disabled || busy}
            aria-label="Send"
            className="flex h-11 w-11 items-center justify-center rounded-full bg-navy text-white transition hover:bg-navy/90 disabled:bg-navy/25"
          >
            <SendIcon />
          </button>
        )}
      </div>
      <p className="mt-1.5 px-1 text-[11px] text-muted">
        Speak in Hindi, English or any Indian language. Tap the wave icon for a hands-free talk.
      </p>
      </>
      )}
    </div>
  );
}

function MicButton({ recording, busy, onStart, onStop }: {
  recording: boolean;
  busy: boolean;
  onStart: () => void;
  onStop: () => void;
}) {
  if (busy) {
    return (
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-sky-soft text-sky" aria-live="polite" aria-label="Transcribing">
        <SpinnerIcon />
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={recording ? onStop : onStart}
      aria-label={recording ? "Stop and transcribe" : "Speak"}
      aria-pressed={recording}
      className={`relative flex h-11 w-11 items-center justify-center rounded-full transition ${
        recording ? "bg-rose-500 text-white" : "bg-sky text-navy hover:brightness-95"
      }`}
    >
      {recording && <span className="pulse-ring absolute inset-0 rounded-full bg-rose-500" aria-hidden="true" />}
      <span className="relative">{recording ? <StopIcon /> : <MicIcon />}</span>
    </button>
  );
}

function Recording({ levels, seconds, handsFree, onCancel }: {
  levels: number[];
  seconds: number;
  handsFree: boolean;
  onCancel: () => void;
}) {
  const left = Math.max(0, Math.ceil(MAX_SECONDS - seconds));
  return (
    <div className="flex min-h-11 flex-1 items-center gap-3 rounded-2xl border border-rose-200 bg-rose-50 px-3" aria-live="polite">
      <button type="button" onClick={onCancel} aria-label="Cancel recording" className="rounded-full p-1 text-rose-600 hover:bg-white">
        <XIcon className="h-4 w-4" />
      </button>
      <div className="flex h-8 flex-1 items-center gap-[3px]" aria-hidden="true">
        {levels.map((l, i) => (
          <span key={i} className="w-full max-w-1 rounded-full bg-rose-500/80" style={{ height: `${Math.max(8, l * 100)}%` }} />
        ))}
      </div>
      <span className={`w-10 text-right text-xs tabular-nums ${left <= 5 ? "font-semibold text-rose-600" : "text-rose-700/80"}`}>
        0:{String(Math.floor(seconds)).padStart(2, "0")}
      </span>
      <span className="sr-only">{handsFree ? "Listening. I'll send when you pause." : "Listening. Tap stop when you finish."}</span>
    </div>
  );
}
