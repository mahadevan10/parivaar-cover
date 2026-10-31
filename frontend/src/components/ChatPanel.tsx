"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "@/lib/types";
import { languageName } from "@/lib/format";
import { Composer, type SendMeta } from "./Composer";
import { useSpeaker } from "@/lib/useSpeaker";
import { DocIcon, MicIcon, ShieldIcon, SpeakerIcon, SpeakerOffIcon } from "./icons";

type Props = {
  messages: ChatMessage[];
  loading: boolean;
  quickReplies: string[];
  policyNames: Record<string, string>;
  placeholder: string;
  onSend: (text: string, meta: SendMeta) => void;
  onOpenPolicy: (id: string) => void;
  talkMode: boolean;
  onTalkModeChange: (on: boolean) => void;
};

export function ChatPanel({
  messages, loading, quickReplies, policyNames, placeholder, onSend, onOpenPolicy, talkMode, onTalkModeChange,
}: Props) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, loading]);

  // Voice replies. A reply is read aloud when the user spoke, or always in talk mode.
  // In talk mode the mic opens again once the reply has been read.
  const speaker = useSpeaker();
  const { speak } = speaker;
  const [muted, setMuted] = useState(false);
  const [listenToken, setListenToken] = useState(0);
  const prefs = useRef({ talkMode, muted });
  useEffect(() => {
    prefs.current = { talkMode, muted };
  }, [talkMode, muted]);
  const spoken = useRef(new Set(messages.map((m) => m.id)));

  useEffect(() => {
    // Every reply since the user's last message, read as one.
    const fresh: ChatMessage[] = [];
    for (let i = messages.length - 1; i >= 0 && messages[i].role === "assistant"; i--) {
      if (!spoken.current.has(messages[i].id)) fresh.unshift(messages[i]);
    }
    if (fresh.length === 0) return;
    fresh.forEach((m) => spoken.current.add(m.id));
    const user = messages.findLast((m) => m.role === "user");
    const { talkMode: talking, muted: silent } = prefs.current;
    if (!talking && user?.via !== "voice") return;
    const listenAgain = () => {
      if (prefs.current.talkMode) setListenToken((t) => t + 1);
    };
    if (silent) {
      queueMicrotask(listenAgain);
      return;
    }
    void speak(fresh.map((m) => m.text).join(" "), user?.language).then((r) => r === "done" && listenAgain());
  }, [messages, speak]);

  const setTalk = (on: boolean) => {
    onTalkModeChange(on);
    if (on) setListenToken((t) => t + 1);
    else speaker.stop();
  };

  const toggleMuted = () => {
    setMuted(!muted);
    if (!muted && speaker.speaking) {
      speaker.stop();
      if (talkMode) setListenToken((t) => t + 1);
    }
  };

  // Outside talk mode, a small bar to stop or mute a reply being read.
  const toolbar = speaker.speaking && !talkMode && (
    <div className="mb-2 flex items-center gap-2">
      <button
        type="button"
        onClick={speaker.stop}
        className="pop-in flex items-center gap-1.5 rounded-full bg-navy-soft px-2.5 py-1 text-xs text-navy hover:bg-sky-soft"
      >
        <SpeakerIcon className="h-3.5 w-3.5 animate-pulse text-sky" />
        Reading aloud. Tap to stop.
      </button>
      <button
        type="button"
        onClick={toggleMuted}
        aria-label="Mute replies"
        title="Mute replies"
        className="ml-auto rounded-full p-1.5 text-muted hover:bg-canvas hover:text-navy"
      >
        <SpeakerOffIcon className="h-4 w-4" />
      </button>
    </div>
  );

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto px-3 py-4 sm:px-4" role="log" aria-live="polite" aria-label="Conversation">
        {messages.map((m) => (
          <Bubble key={m.id} message={m} policyNames={policyNames} onOpenPolicy={onOpenPolicy} />
        ))}
        {loading && (
          <div className="flex items-center gap-2 pl-10 text-muted" aria-label="Assistant is typing">
            {[0, 1, 2].map((i) => (
              <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-sky" style={{ animationDelay: `${i * 120}ms` }} />
            ))}
          </div>
        )}
        <div ref={end} />
      </div>

      {quickReplies.length > 0 && !loading && (
        <div className="flex gap-2 overflow-x-auto px-3 pb-2 sm:px-4">
          {quickReplies.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => onSend(q, { via: "text" })}
              className="pop-in shrink-0 rounded-full border border-sky/60 bg-white px-3 py-1.5 text-sm text-navy hover:bg-sky-soft"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      <Composer
        onSend={onSend}
        disabled={loading}
        placeholder={placeholder}
        handsFree={talkMode}
        listenToken={listenToken}
        onMicStart={speaker.stop}
        toolbar={toolbar}
        speaking={speaker.speaking}
        muted={muted}
        onToggleMute={toggleMuted}
        onTalkMode={setTalk}
      />
    </div>
  );
}

function Bubble({ message, policyNames, onOpenPolicy }: {
  message: ChatMessage;
  policyNames: Record<string, string>;
  onOpenPolicy: (id: string) => void;
}) {
  if (message.role === "user") {
    const lang = languageName(message.language);
    return (
      <div className="pop-in flex flex-col items-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-navy px-3.5 py-2 text-[15px] leading-6 text-white">
          {message.text}
        </div>
        {message.via === "voice" && (
          <span className="mt-1 flex items-center gap-1 text-[11px] text-muted">
            <MicIcon className="h-3 w-3" /> Voice{lang ? `, ${lang}` : ""}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="pop-in flex items-start gap-2">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-navy text-sky" aria-hidden="true">
        <ShieldIcon className="h-4 w-4" />
      </span>
      <div className="max-w-[85%]">
        <div className="rounded-2xl rounded-tl-md border border-line bg-white px-3.5 py-2 text-[15px] leading-6 text-ink shadow-sm">
          {message.text}
        </div>
        {message.citations && message.citations.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {message.citations.map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => onOpenPolicy(id)}
                className="inline-flex items-center gap-1 rounded-full bg-navy-soft px-2.5 py-1 text-xs text-navy hover:bg-sky-soft"
              >
                <DocIcon className="h-3.5 w-3.5" />
                {policyNames[id] ? `${policyNames[id]}: fine print` : "Fine print"}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
