"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// Sarvam's REST endpoint takes clips under 30 seconds.
export const MAX_SECONDS = 28;
const BARS = 32;

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"].find((t) =>
    MediaRecorder.isTypeSupported(t),
  );
}

/** Records one voice clip and exposes live input levels for a waveform. */
export function useRecorder(onClip: (clip: Blob) => void) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [levels, setLevels] = useState<number[]>(() => Array(BARS).fill(0));
  const [error, setError] = useState<string | null>(null);

  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const audioCtx = useRef<AudioContext | null>(null);
  const frame = useRef<number>(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const cancelled = useRef(false);
  const onClipRef = useRef(onClip);
  useEffect(() => {
    onClipRef.current = onClip;
  }, [onClip]);

  const cleanup = useCallback(() => {
    cancelAnimationFrame(frame.current);
    if (timer.current) clearInterval(timer.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    audioCtx.current?.close().catch(() => {});
    stream.current = null;
    audioCtx.current = null;
    setLevels(Array(BARS).fill(0));
    setRecording(false);
  }, []);

  const stop = useCallback(() => {
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, []);

  const cancel = useCallback(() => {
    cancelled.current = true;
    stop();
  }, [stop]);

  const start = useCallback(async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("This browser can't record audio. Please type instead.");
      return;
    }
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      stream.current = s;
      const mimeType = pickMimeType();
      const rec = new MediaRecorder(s, mimeType ? { mimeType } : undefined);
      const chunks: Blob[] = [];
      cancelled.current = false;

      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      rec.onstop = () => {
        cleanup();
        const clip = new Blob(chunks, { type: rec.mimeType || mimeType || "audio/webm" });
        if (!cancelled.current && clip.size > 0) onClipRef.current(clip);
      };

      const ctx = new AudioContext();
      audioCtx.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 128;
      ctx.createMediaStreamSource(s).connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteFrequencyData(data);
        const step = Math.max(1, Math.floor(data.length / BARS));
        setLevels(Array.from({ length: BARS }, (_, i) => data[i * step] / 255));
        frame.current = requestAnimationFrame(tick);
      };
      tick();

      const startedAt = Date.now();
      setSeconds(0);
      timer.current = setInterval(() => {
        const sec = (Date.now() - startedAt) / 1000;
        setSeconds(sec);
        if (sec >= MAX_SECONDS) stop();
      }, 200);

      recorder.current = rec;
      rec.start();
      setRecording(true);
    } catch (e) {
      cleanup();
      const denied = e instanceof DOMException && e.name === "NotAllowedError";
      setError(denied ? "Microphone access is blocked. Allow it in the browser, or type instead." : "Couldn't start the microphone.");
    }
  }, [cleanup, stop]);

  useEffect(() => () => cleanup(), [cleanup]);

  return { recording, seconds, levels, error, start, stop, cancel };
}
