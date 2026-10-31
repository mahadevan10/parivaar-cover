"use client";

import { useState } from "react";
import type { FamilyProfile, Member } from "@/lib/types";
import { conditionLabel, cover, rupees } from "@/lib/format";
import { Avatar } from "./Avatar";
import { CheckIcon, MicIcon, PlusIcon, XIcon } from "./icons";

// Names follow shared/README.md so the solver understands them.
const CONDITIONS = ["diabetes", "hypertension", "heart_disease", "asthma"];

type Props = {
  family: FamilyProfile;
  missing: string[];
  ready: boolean;
  changedIds: Set<string>;
  busy: boolean;
  onChange: (family: FamilyProfile) => void;
  onFindMix: () => void;
  onUseDemo: () => void;
};

export function FamilyBoard({ family, missing, ready, changedIds, busy, onChange, onFindMix, onUseDemo }: Props) {
  const updateMember = (id: string, patch: Partial<Member>) =>
    onChange({ ...family, members: family.members.map((m) => (m.id === id ? { ...m, ...patch } : m)) });
  const removeMember = (id: string) =>
    onChange({ ...family, members: family.members.filter((m) => m.id !== id) });

  const empty = family.members.length === 0;

  return (
    <section aria-labelledby="board-title" className="mx-auto flex w-full max-w-3xl flex-col gap-5 p-4 sm:p-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="board-title" className="text-lg font-semibold text-navy">Your family board</h2>
          <p className="text-sm text-muted">Fills in as you talk. Tap anything to fix it.</p>
        </div>
        <Readiness missing={missing} ready={ready} empty={empty} />
      </header>

      {empty ? (
        <EmptyBoard onUseDemo={onUseDemo} />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {family.members.map((m, i) => (
            <MemberCard
              key={m.id}
              member={m}
              index={i}
              flash={changedIds.has(m.id)}
              onChange={(patch) => updateMember(m.id, patch)}
              onRemove={() => removeMember(m.id)}
            />
          ))}
        </ul>
      )}

      <div className="grid grid-cols-3 gap-3">
        <Fact label="City" value={family.city} flash={changedIds.has("city")} />
        <Fact label="Yearly budget" value={family.budget ? rupees(family.budget) : undefined} flash={changedIds.has("budget")} />
        <Fact
          label="Office cover"
          value={family.officeCover ? cover(family.officeCover.amount) : family.officeChecked ? "None" : undefined}
          flash={changedIds.has("office")}
        />
      </div>

      <div className="sticky bottom-0 -mx-4 border-t border-line bg-canvas/95 px-4 py-3 backdrop-blur sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:p-0">
        <button
          type="button"
          onClick={onFindMix}
          disabled={!ready || busy}
          className="w-full rounded-xl bg-navy px-5 py-3.5 text-base font-semibold text-white shadow-sm transition hover:bg-navy/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky disabled:cursor-not-allowed disabled:bg-navy/30"
        >
          {ready ? "Find my mix" : `Find my mix (${missing.length} ${missing.length === 1 ? "detail" : "details"} to go)`}
        </button>
      </div>
    </section>
  );
}

function Readiness({ missing, ready, empty }: { missing: string[]; ready: boolean; empty: boolean }) {
  if (empty) return null;
  if (ready) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700">
        <CheckIcon className="h-4 w-4" /> Ready to find your mix
      </span>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-sm">
      <span className="text-muted">Still needed:</span>
      {missing.map((m) => (
        <span key={m} className="rounded-full border border-dashed border-amber bg-amber-soft px-2.5 py-0.5 text-ink">
          {m}
        </span>
      ))}
    </div>
  );
}

function EmptyBoard({ onUseDemo }: { onUseDemo: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-2xl border border-dashed border-line bg-white px-6 py-10 text-center">
      <div className="flex -space-x-3" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((i) => (
          <span key={i} className="h-12 w-12 rounded-full border-2 border-dashed border-navy/20 bg-navy-soft" />
        ))}
      </div>
      <div className="max-w-sm">
        <p className="font-medium text-ink">Tell me about your family, by voice or text.</p>
        <p className="mt-1 text-sm text-muted">
          Names, ages, health conditions, city and budget. Each person appears here as you mention them.
        </p>
      </div>
      <button type="button" onClick={onUseDemo} className="rounded-full border border-navy px-4 py-2 text-sm font-medium text-navy hover:bg-navy-soft">
        Use the demo family
      </button>
    </div>
  );
}

function Fact({ label, value, flash }: { label: string; value?: string; flash: boolean }) {
  return (
    <div
      key={value}
      className={`rounded-xl border px-3 py-2.5 ${value ? "border-line bg-white" : "border-dashed border-line bg-white/50"} ${flash ? "flash" : ""}`}
    >
      <div className="text-xs text-muted">{label}</div>
      <div className={`truncate text-sm font-semibold ${value ? "text-ink" : "text-muted/60"}`}>{value ?? "Not yet"}</div>
    </div>
  );
}

function MemberCard({ member, index, flash, onChange, onRemove }: {
  member: Member;
  index: number;
  flash: boolean;
  onChange: (patch: Partial<Member>) => void;
  onRemove: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState("");

  const addCondition = () => {
    const typed = draft.trim().toLowerCase();
    const c = CONDITIONS.find((k) => k === typed || conditionLabel(k) === typed) ?? typed;
    if (c && !member.conditions.includes(c)) onChange({ conditions: [...member.conditions, c] });
    setDraft("");
    setAdding(false);
  };

  return (
    <li className={`pop-in group relative rounded-2xl border border-line bg-white p-4 shadow-sm ${flash ? "flash" : ""}`}>
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${member.name}`}
        className="absolute right-2 top-2 rounded-full p-1 text-muted opacity-0 transition group-hover:opacity-100 hover:bg-canvas focus-visible:opacity-100"
      >
        <XIcon className="h-4 w-4" />
      </button>

      <div className="flex items-center gap-3">
        <Avatar name={member.name} index={index} size="lg" />
        <div className="min-w-0 flex-1">
          <input
            aria-label="Name"
            value={member.name}
            onChange={(e) => onChange({ name: e.target.value })}
            className="w-full truncate rounded-md bg-transparent px-1 -mx-1 text-base font-semibold text-ink hover:bg-canvas focus:bg-canvas focus:outline-none"
          />
          <div className="flex items-center gap-2 text-sm text-muted">
            <span className="capitalize">{member.relation ?? "family"}</span>
            <span aria-hidden="true">·</span>
            <label className="flex items-center gap-1">
              <input
                aria-label={`${member.name}'s age`}
                inputMode="numeric"
                value={member.age ?? ""}
                placeholder="age?"
                onChange={(e) => {
                  const n = parseInt(e.target.value, 10);
                  onChange({ age: Number.isFinite(n) ? Math.min(n, 110) : undefined });
                }}
                className={`w-12 rounded-md px-1 text-sm font-medium hover:bg-canvas focus:bg-canvas focus:outline-none ${
                  member.age === undefined ? "border border-dashed border-amber bg-amber-soft text-ink placeholder:text-ink/50" : "bg-transparent text-ink"
                }`}
              />
              <span>yrs</span>
            </label>
          </div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {member.conditions.length === 0 && !adding && <span className="text-xs text-muted">No health conditions noted</span>}
        {member.conditions.map((c) => (
          <span key={c} className="inline-flex items-center gap-1 rounded-full bg-amber-soft px-2.5 py-0.5 text-xs font-medium text-ink">
            {conditionLabel(c)}
            <button
              type="button"
              aria-label={`Remove ${conditionLabel(c)}`}
              onClick={() => onChange({ conditions: member.conditions.filter((x) => x !== c) })}
              className="rounded-full hover:text-rose-600"
            >
              <XIcon className="h-3 w-3" />
            </button>
          </span>
        ))}
        {adding ? (
          <form onSubmit={(e) => { e.preventDefault(); addCondition(); }} className="flex items-center">
            <input
              autoFocus
              list="condition-suggestions"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onBlur={addCondition}
              placeholder="e.g. diabetes"
              className="w-28 rounded-full border border-line px-2.5 py-0.5 text-xs focus:border-sky focus:outline-none"
            />
            <datalist id="condition-suggestions">
              {CONDITIONS.map((c) => <option key={c} value={conditionLabel(c)} />)}
            </datalist>
          </form>
        ) : (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs text-sky hover:bg-sky-soft"
          >
            <PlusIcon className="h-3 w-3" /> condition
          </button>
        )}
      </div>

      {member.heardFrom && (
        <p className="mt-3 flex items-start gap-1.5 border-t border-line pt-2 text-xs text-muted">
          <MicIcon className="mt-px h-3.5 w-3.5 text-sky" />
          <span className="line-clamp-2 italic">Heard from: “{member.heardFrom}”</span>
        </p>
      )}
    </li>
  );
}
