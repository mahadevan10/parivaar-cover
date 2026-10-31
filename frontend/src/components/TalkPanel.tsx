"use client";

import { SpeakerIcon, SpeakerOffIcon, XIcon } from "./icons";

export type TalkState = "listening" | "thinking" | "speaking" | "idle";

const LABELS: Record<TalkState, string> = {
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking. Talk or tap to cut in.",
  idle: "Tap to talk",
};

// Five bars, loudest in the middle, picked from the recorder's 32 levels.
const BANDS = [8, 3, 1, 5, 12];
const ORDER = [3, 1, 0, 2, 4];

/** Full width voice view shown in place of the message box while talk mode is on. */
export function TalkPanel({ state, levels, muted, onTap, onToggleMute, onEnd }: {
  state: TalkState;
  levels: number[];
  muted: boolean;
  onTap: () => void;
  onToggleMute: () => void;
  onEnd: () => void;
}) {
  const live = state === "listening" || state === "speaking";
  return (
    <div className="pop-in relative overflow-hidden rounded-2xl bg-navy px-3 py-3 text-white">
      <div
        aria-hidden="true"
        className={`pointer-events-none absolute inset-0 ${live ? "talk-glow" : "opacity-40"}`}
        style={{
          background: state === "speaking"
            ? "radial-gradient(60% 90% at 50% 50%, rgba(255,176,32,0.45), transparent 70%)"
            : "radial-gradient(60% 90% at 50% 50%, rgba(0,186,242,0.5), transparent 70%)",
        }}
      />
      <div className="relative flex items-center gap-2">
        <button
          type="button"
          onClick={onToggleMute}
          aria-label={muted ? "Read replies aloud" : "Mute replies"}
          title={muted ? "Read replies aloud" : "Mute replies"}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/10 hover:bg-white/20"
        >
          {muted ? <SpeakerOffIcon className="h-4 w-4" /> : <SpeakerIcon className="h-4 w-4" />}
        </button>

        <button
          type="button"
          onClick={onTap}
          disabled={state === "thinking"}
          aria-label={LABELS[state]}
          className="flex min-w-0 flex-1 flex-col items-center gap-1.5 rounded-xl py-1 focus-visible:outline-2 focus-visible:outline-sky"
        >
          <Wave state={state} levels={levels} />
          <span className="text-xs font-medium text-white/80" aria-live="polite">{LABELS[state]}</span>
        </button>

        <button
          type="button"
          onClick={onEnd}
          aria-label="End talk mode"
          title="End talk mode"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/10 hover:bg-rose-500"
        >
          <XIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function Wave({ state, levels }: { state: TalkState; levels: number[] }) {
  return (
    <div className="flex h-12 items-center justify-center gap-1.5" aria-hidden="true">
      {ORDER.map((band, i) => {
        if (state === "listening") {
          const l = Math.min(1, (levels[BANDS[band]] ?? 0) * 1.6);
          return (
            <span
              key={i}
              className="w-2.5 rounded-full bg-sky transition-[height] duration-75"
              style={{ height: `${10 + l * 38}px` }}
            />
          );
        }
        if (state === "speaking") {
          return (
            <span
              key={i}
              className="talk-wave h-10 w-2.5 rounded-full bg-amber"
              style={{ animationDelay: `${[0, 180, 360, 120, 300][i]}ms` }}
            />
          );
        }
        return (
          <span
            key={i}
            className={`h-2.5 w-2.5 rounded-full bg-white/70 ${state === "thinking" ? "animate-bounce" : ""}`}
            style={state === "thinking" ? { animationDelay: `${i * 110}ms` } : undefined}
          />
        );
      })}
    </div>
  );
}
