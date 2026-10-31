"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, FamilyProfile, Policy, Recommendation, Stage } from "@/lib/types";
import { getRecommendation, NoFitError, sendChat } from "@/lib/api";
import { missingList, VERIFIED } from "@/lib/family";
import { cover, rupees } from "@/lib/format";
import { Avatar } from "./Avatar";
import { ChatPanel } from "./ChatPanel";
import type { SendMeta } from "./Composer";
import { FamilyBoard } from "./FamilyBoard";
import { FinePrintSheet } from "./FinePrintSheet";
import { JourneySteps } from "./JourneySteps";
import { Optimising } from "./Optimising";
import { Results } from "./Results";
import { ShieldIcon } from "./icons";

const EMPTY_FAMILY: FamilyProfile = { members: [], healthChecked: false, officeChecked: false };

const WELCOME: ChatMessage = {
  id: "welcome",
  role: "assistant",
  text: "Namaste. I'll help you cover your whole family with the right mix of health policies. Who should the plan cover? Tap the mic and speak in any language, or type.",
};

// Only the verify button on the board (or a retry) starts the search.
const START_SEARCH = /^(i have verified all my information|find my mix|try again)[.!]?$/i;

/** The backend adds this when intake is done. The app says it in its own words instead. */
const BACKEND_READY_LINE = /I have everything I need to find your options\.?/i;

function readyMessage(language: string | undefined, endedTalk: boolean): string {
  const wide = typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches;
  if (language === "hi-IN") {
    const where = wide ? "दाईं ओर अपनी जानकारी देख लें" : "Family board खोलकर अपनी जानकारी देख लें";
    return `मेरे पास आपकी सारी जानकारी है। ${endedTalk ? "मैंने talk mode बंद कर दिया है। " : ""}${where}, फिर "${VERIFIED}" दबाएं।`;
  }
  const where = wide ? "Please check the details on the right" : "Please open the Family board tab and check the details";
  return `I have all your information. ${endedTalk ? "I've turned off talk mode so you can check it. " : ""}${where}, then tap "${VERIFIED}".`;
}

let counter = 0;
const nextId = () => `m${++counter}`;

/** Keys of what changed, so the board can flash those cards. */
function diffFamily(a: FamilyProfile, b: FamilyProfile): Set<string> {
  const out = new Set<string>();
  for (const m of b.members) {
    const prev = a.members.find((x) => x.id === m.id);
    if (!prev || JSON.stringify(prev) !== JSON.stringify(m)) out.add(m.id);
  }
  if (a.city !== b.city) out.add("city");
  if (a.budget !== b.budget) out.add("budget");
  if (a.coverTarget !== b.coverTarget || a.coverChecked !== b.coverChecked) out.add("cover");
  if (a.officeChecked !== b.officeChecked || a.officeCover?.amount !== b.officeCover?.amount) out.add("office");
  return out;
}

export function App() {
  const session = useRef<string | null>(null);
  const sessionId = () => (session.current ??= crypto.randomUUID());
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [family, setFamily] = useState<FamilyProfile>(EMPTY_FAMILY);
  const [missing, setMissing] = useState<string[]>(missingList(EMPTY_FAMILY));
  const [quickReplies, setQuickReplies] = useState<string[]>([]);
  const [ready, setReady] = useState(false);
  const [stage, setStage] = useState<Stage>("talk");
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [loading, setLoading] = useState(false);
  const [openPolicy, setOpenPolicy] = useState<string | null>(null);
  const [changed, setChanged] = useState<Set<string>>(new Set());
  const [mobileView, setMobileView] = useState<"chat" | "board">("chat");
  const [talkMode, setTalkMode] = useState(false);

  const familyRef = useRef(family);
  useEffect(() => {
    familyRef.current = family;
  }, [family]);

  const applyFamily = useCallback((next: FamilyProfile) => {
    setChanged(diffFamily(familyRef.current, next));
    setFamily(next);
  }, []);

  useEffect(() => {
    if (changed.size === 0) return;
    const t = setTimeout(() => setChanged(new Set()), 1000);
    return () => clearTimeout(t);
  }, [changed]);

  const push = (m: Omit<ChatMessage, "id">) => setMessages((prev) => [...prev, { ...m, id: nextId() }]);

  // The solver's answer waits here until the optimise screen has ticked every step.
  const [pending, setPending] = useState<Recommendation | null>(null);

  const findMix = useCallback(async () => {
    setMobileView("board");
    setQuickReplies([]);
    setPending(null);
    setStage("fine_print");
    try {
      setPending(await getRecommendation(familyRef.current, sessionId()));
    } catch (e) {
      console.error("Find my mix failed", e);
      setStage("talk");
      push({
        role: "assistant",
        text: e instanceof NoFitError
          ? "No mix fits this budget. Try a higher budget, or tell me if anyone already has cover."
          : "I couldn't reach the optimiser just now. Please try again.",
      });
      setQuickReplies(["Try again"]);
    }
  }, []);

  const finePrintRead = useCallback(() => setStage("optimise"), []);

  const showResult = useCallback(() => {
    if (!pending) return;
    setRec(pending);
    setPending(null);
    setStage("explain");
    const short = pending.coverCheck && pending.coverCheck.code !== "cover_met" ? ` ${pending.coverCheck.text}` : "";
    const usualLine = pending.usual
      ? `The usual pick is one floater at ${rupees(pending.usual.premium)} for ${cover(pending.usual.totalCover)}.`
      : "No single floater can take your whole family.";
    push({
      role: "assistant",
      text: `Here is your mix. ${pending.mix.policies.length} policies for ${rupees(pending.mix.premium)} a year with ${cover(pending.mix.totalCover)} of total cover.${short} ${usualLine} Premiums are illustrative. Ask me about any pick, or try the claim check.`,
    });
    setQuickReplies(["Why not one floater?", "What is a super top-up?", "What are the catches?"]);
  }, [pending]);

  const send = useCallback(async (text: string, meta: SendMeta) => {
    if (START_SEARCH.test(text.trim()) && ready && !rec) {
      push({ role: "user", text, via: meta.via, language: meta.language });
      void findMix();
      return;
    }

    const history = messages.map(({ role, text }) => ({ role, text }));
    push({ role: "user", text, via: meta.via, language: meta.language });
    setQuickReplies([]);
    setLoading(true);
    try {
      const res = await sendChat({
        sessionId: sessionId(),
        message: text,
        family: familyRef.current,
        history,
        recommendationId: rec?.id,
        language: meta.language,
      });
      applyFamily(res.family);
      setMissing(res.missing);
      setReady(res.readyToOptimise);
      setQuickReplies(res.quickReplies);
      const nowReady = res.readyToOptimise && !ready && !rec;
      const reply = nowReady ? res.reply.replace(BACKEND_READY_LINE, "").trim() : res.reply;
      if (reply) push({ role: "assistant", text: reply, citations: res.citations });
      // Tell the user plainly that intake is done and where to go next.
      // Intake is done: end talk mode so the user can check the board and verify it.
      if (nowReady) {
        push({ role: "assistant", text: readyMessage(meta.language, talkMode) });
        setTalkMode(false);
        setQuickReplies([]);
      }
    } catch {
      push({
        role: "assistant",
        text: rec
          ? "I can't answer questions right now. The details of each pick are on the right."
          : "I can't reach the assistant right now. You can fill in the family board on the right.",
      });
    } finally {
      setLoading(false);
    }
  }, [messages, rec, ready, talkMode, applyFamily, findMix]);

  // Board edits are local. Recheck what's missing straight away.
  const editFamily = (next: FamilyProfile) => {
    setFamily(next);
    const m = missingList(next);
    setMissing(m);
    setReady(m.length === 0);
  };

  const backToFamily = () => {
    setRec(null);
    setStage("talk");
    setQuickReplies([]);
  };

  const policies: Record<string, Policy> = Object.fromEntries(
    [...(rec?.mix.policies ?? []), ...(rec?.usual?.policies ?? [])].map((p) => [p.id, p]),
  );
  const policyNames = Object.fromEntries(Object.values(policies).map((p) => [p.id, p.product]));
  const canvas =
    stage === "fine_print" || stage === "optimise" ? (
      <Optimising
        memberCount={family.members.length}
        finished={pending !== null}
        onFinePrintRead={finePrintRead}
        onComplete={showResult}
      />
    ) : rec && stage === "explain" ? (
      <Results rec={rec} family={family} onOpenPolicy={setOpenPolicy} onEditFamily={backToFamily} />
    ) : (
      <FamilyBoard
        family={family}
        missing={missing}
        ready={ready}
        changedIds={changed}
        busy={loading}
        onChange={editFamily}
        onFindMix={() => send(VERIFIED, { via: "text" })}
      />
    );

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <header className="flex shrink-0 items-center justify-between gap-3 bg-navy px-4 py-2.5 text-white">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky text-navy">
            <ShieldIcon className="h-5 w-5" />
          </span>
          <div className="leading-tight">
            <div className="font-semibold">Parivaar Cover</div>
            <div className="hidden text-[11px] text-white/60 sm:block">Health cover for the whole family</div>
          </div>
        </div>
        <JourneySteps stage={stage} />
      </header>

      {/* Phone: switch between chat and the board. */}
      <nav className="flex shrink-0 border-b border-line bg-white lg:hidden" aria-label="View">
        {(["chat", "board"] as const).map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => setMobileView(v)}
            aria-pressed={mobileView === v}
            className={`flex flex-1 items-center justify-center gap-2 py-2.5 text-sm font-medium ${
              mobileView === v ? "border-b-2 border-sky text-navy" : "text-muted"
            }`}
          >
            {v === "chat" ? "Chat" : rec ? "Your mix" : "Family board"}
            {v === "board" && family.members.length > 0 && (
              <span className="flex -space-x-1.5">
                {family.members.slice(0, 5).map((m, i) => <Avatar key={m.id} name={m.name} index={i} size="sm" className="!h-5 !w-5 !text-[9px] !ring-1" />)}
              </span>
            )}
          </button>
        ))}
      </nav>

      <main className="grid min-h-0 flex-1 lg:grid-cols-[minmax(360px,420px)_1fr]">
        <aside className={`min-h-0 min-w-0 border-r border-line bg-white ${mobileView === "chat" ? "flex" : "hidden"} flex-col lg:flex`}>
          <ChatPanel
            messages={messages}
            loading={loading}
            quickReplies={quickReplies}
            policyNames={policyNames}
            placeholder={rec ? "Ask about any pick or catch" : "Type, or tap the mic to speak"}
            onSend={send}
            onOpenPolicy={setOpenPolicy}
            talkMode={talkMode}
            onTalkModeChange={setTalkMode}
          />
        </aside>
        <div className={`min-h-0 min-w-0 overflow-y-auto ${mobileView === "board" ? "block" : "hidden"} lg:block`}>
          {canvas}
        </div>
      </main>

      <FinePrintSheet policy={openPolicy ? policies[openPolicy] ?? null : null} onClose={() => setOpenPolicy(null)} />
    </div>
  );
}
