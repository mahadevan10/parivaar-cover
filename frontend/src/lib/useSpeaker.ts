"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** "done" when the reply finished or couldn't be read, "stopped" when something cut it off. */
export type SpeakResult = "done" | "stopped";

/** Reads replies aloud through /api/tts, one at a time. */
export function useSpeaker() {
  const [speaking, setSpeaking] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const run = useRef(0);

  const stop = useCallback(() => {
    run.current++;
    audio.current?.pause();
    audio.current = null;
    setSpeaking(false);
  }, []);

  const speak = useCallback(async (text: string, language?: string): Promise<SpeakResult> => {
    stop();
    const id = run.current;
    setSpeaking(true);
    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language }),
      });
      if (!res.ok) return "done";
      const url = URL.createObjectURL(await res.blob());
      if (id !== run.current) {
        URL.revokeObjectURL(url);
        return "stopped";
      }
      const a = new Audio(url);
      audio.current = a;
      await new Promise<void>((resolve) => {
        a.onended = a.onerror = a.onpause = () => resolve();
        a.play().catch(() => resolve());
      });
      URL.revokeObjectURL(url);
    } catch {
      // A failed reply read is not worth an error. The text is on screen.
    } finally {
      if (id === run.current) setSpeaking(false);
    }
    return id === run.current ? "done" : "stopped";
  }, [stop]);

  useEffect(() => stop, [stop]);

  return { speaking, speak, stop };
}
