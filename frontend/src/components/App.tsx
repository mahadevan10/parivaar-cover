"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage, FamilyProfile, Policy, Recommendation, Stage } from "@/lib/types";
import { getRecommendation, NoFitError, sendChat, usingMock } from "@/lib/api";
import { missingList } from "@/lib/family";
import { DEMO_FAMILY } from "@/lib/mock/demo";
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
  if (a.officeChecked !== b.officeChecked || a.officeCover?.amount !== b.officeCover?.amount) out.add("office");
  return out;
}

export function App() {
  const session = useRef<string | null>(null);
  const sessionId = () => (session.current ??= crypto.randomUUID());
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [family, setFamily] = useState<FamilyProfile>(EMPTY_FAMILY);
  const [missing, setMissing] = useState<string[]>(missingList(EMPTY_FAMILY));
  const [quickReplies, setQuickReplies] = useState<string[]>(["Use the demo family"]);
  const [ready, setReady] = useState(false);
  const [stage, setStage] = useState<Stage>("talk");
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [loading, setLoading] = useState(false);
  const [openPolicy, setOpenPolicy] = useState<string | null>(null);
  const [changed, setChanged] = useState<Set<string>>(new Set());
  const [mobileView, setMobileView] = useState<"chat" | "board">("chat");

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
      setQuickReplies(["Find my mix"]);
    }
  }, []);

  const finePrintRead = useCallback(() => setStage("optimise"), []);

  const showResult = useCallback(() => {
    if (!pending) return;
    setRec(pending);
    setPending(null);
    setStage("explain");
    const usualLine = pending.usual
      ? `The usual pick is one floater at ${rupees(pending.usual.premium)} for ${cover(pending.usual.totalCover)}.`
      : "No single floater can take your whole family.";
    push({
      role: "assistant",
      text: `Here is your mix. ${pending.mix.policies.length} policies for ${rupees(pending.mix.premium)} a year with ${cover(pending.mix.totalCover)} of total cover. ${usualLine} Premiums are illustrative. Ask me about any pick, or try the claim check.`,
    });
    setQuickReplies(["Why not one floater?", "What is a super top-up?", "What are the catches?"]);
  }, [pending]);

  const send = useCallback(async (text: string, meta: SendMeta) => {
    if (/^find my mix[.!]?$/i.test(text.trim()) && ready && !rec) {
      push({ role: "user", text, via: meta.via, language: meta.language });
      void findMix();
      return;
    }

    // The demo family loads in the browser, so the demo never waits on the LLM.
    if (/demo family/i.test(text) && !rec) {
      push({ role: "user", text, via: meta.via, language: meta.language });
      applyFamily(DEMO_FAMILY);
      setMissing([]);
      setReady(true);
      push({
        role: "assistant",
        text: "I've loaded the demo family: Rahul, Sneha, Aarav, Mohan and Lata in Pune, with a budget of ₹1,10,000 a year. Check the board, then find your mix.",
      });
      setQuickReplies(["Find my mix"]);
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
      });
      applyFamily(res.family);
      setMissing(res.missing);
      setReady(res.readyToOptimise);
      setQuickReplies(res.quickReplies);
      push({ role: "assistant", text: res.reply, citations: res.citations });
    } catch {
      push({
        role: "assistant",
        text: rec
          ? "I can't answer questions right now. The details of each pick are on the right."
          : "I can't reach the assistant right now. You can fill in the family board on the right, or use the demo family.",
      });
      if (!rec) setQuickReplies(["Use the demo family"]);
    } finally {
      setLoading(false);
    }
  }, [messages, rec, ready, applyFamily, findMix]);

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
    setQuickReplies(ready ? ["Find my mix"] : []);
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
        onFindMix={() => send("Find my mix", { via: "text" })}
        onUseDemo={() => send("Use the demo family", { via: "text" })}
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
          {usingMock && <span className="ml-1 rounded-full bg-amber px-2 py-0.5 text-[10px] font-semibold text-navy">Prototype</span>}
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
