"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { replyLanguage } from "./sarvam";

/** "done" when the reply finished or couldn't be read, "stopped" when something cut it off. */
export type SpeakResult = "done" | "stopped";

/**
 * Cuts a reply into pieces to read one after another. The first piece is a single
 * sentence so the voice starts quickly; later short sentences are joined.
 */
export function speechChunks(text: string): string[] {
  const sentences = text.replace(/\s+/g, " ").trim().split(/(?<=[.!?।])\s+/).filter(Boolean);
  const chunks: string[] = [];
  for (const s of sentences) {
    const last = chunks.at(-1);
    if (chunks.length > 1 && last && last.length + s.length < 180) chunks[chunks.length - 1] = `${last} ${s}`;
    else chunks.push(s);
  }
  return chunks;
}

/**
 * Reads replies aloud through /api/tts, one at a time. Every sentence is requested
 * at once and played in order, so speech starts after the first sentence is ready.
 */
export function useSpeaker() {
  const [speaking, setSpeaking] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const aborter = useRef<AbortController | null>(null);
  const run = useRef(0);

  const stop = useCallback(() => {
    run.current++;
    aborter.current?.abort();
    aborter.current = null;
    audio.current?.pause();
    audio.current = null;
    setSpeaking(false);
  }, []);

  const speak = useCallback(async (text: string, userLanguage?: string): Promise<SpeakResult> => {
    stop();
    const id = run.current;
    const abort = new AbortController();
    aborter.current = abort;
    setSpeaking(true);

    // One voice for the whole reply, so a short English phrase doesn't switch it.
    const voice = replyLanguage(text, userLanguage);
    const clips = speechChunks(text).map((chunk) =>
      fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: chunk, voice }),
        signal: abort.signal,
      })
        .then((res) => (res.ok ? res.blob() : null))
        .catch(() => null),
    );

    try {
      for (const clip of clips) {
        const blob = await clip;
        if (id !== run.current) break;
        if (!blob) continue;
        const url = URL.createObjectURL(blob);
        const a = new Audio(url);
        audio.current = a;
        await new Promise<void>((resolve) => {
          a.onended = a.onerror = a.onpause = () => resolve();
          a.play().catch(() => resolve());
        });
        URL.revokeObjectURL(url);
        if (id !== run.current) break;
      }
    } finally {
      if (id === run.current) {
        aborter.current = null;
        setSpeaking(false);
      }
    }
    return id === run.current ? "done" : "stopped";
  }, [stop]);

  useEffect(() => stop, [stop]);

  return { speaking, speak, stop };
}
