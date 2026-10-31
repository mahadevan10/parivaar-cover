"use client";

import { useState } from "react";
import type { FamilyProfile, Policy, PolicyKind, Recommendation } from "@/lib/types";
import { cover, rupees } from "@/lib/format";
import { Avatar } from "./Avatar";
import { AlertIcon, CheckIcon, DocIcon, XIcon } from "./icons";

const KIND_LABEL: Record<PolicyKind, string> = {
  floater: "Family floater",
  individual: "Individual",
  senior: "Senior plan",
  super_top_up: "Super top-up",
};

const LAYER_COLOR: Record<PolicyKind, string> = {
  floater: "bg-navy",
  individual: "bg-navy",
  senior: "bg-navy",
  super_top_up: "bg-sky",
};

type Props = {
  rec: Recommendation;
  family: FamilyProfile;
  onOpenClause: (id: string) => void;
  onEditFamily: () => void;
};

export function Results({ rec, family, onOpenClause, onEditFamily }: Props) {
  const indexOf = (id: string) => Math.max(0, family.members.findIndex((m) => m.id === id));
  const nameOf = (id: string) => family.members.find((m) => m.id === id)?.name ?? id;

  return (
    <section className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-6" aria-labelledby="results-title">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="results-title" className="text-lg font-semibold text-navy">Your family&apos;s mix</h2>
          {rec.illustrative && (
            <p className="text-sm text-muted">
              <span className="mr-1.5 rounded bg-amber-soft px-1.5 py-0.5 text-xs font-semibold text-ink">Illustrative premiums</span>
              Prices are samples for this prototype. Real quotes come from insurers.
            </p>
          )}
        </div>
        <button type="button" onClick={onEditFamily} className="text-sm font-medium text-sky hover:underline">
          Edit family
        </button>
      </header>

      <Compare rec={rec} />
      <CoverMap rec={rec} family={family} indexOf={indexOf} />
      <ClaimCheck rec={rec} nameOf={nameOf} indexOf={indexOf} onOpenClause={onOpenClause} />

      <div>
        <h3 className="mb-3 font-semibold text-ink">The five policies, and why</h3>
        <ul className="grid gap-3 md:grid-cols-2">
          {rec.mix.policies.map((p) => (
            <PolicyCard key={p.id} policy={p} rec={rec} nameOf={nameOf} indexOf={indexOf} onOpenClause={onOpenClause} />
          ))}
        </ul>
      </div>
    </section>
  );
}

function Compare({ rec }: { rec: Recommendation }) {
  const { usual, mix } = rec;
  const save = usual.premium - mix.premium;
  const times = mix.totalCover / usual.totalCover;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="rounded-2xl border border-line bg-white p-4">
        <div className="text-sm font-medium text-muted">{usual.label}</div>
        <div className="mt-1 text-2xl font-bold text-ink">{rupees(usual.premium)}<span className="text-sm font-normal text-muted"> a year*</span></div>
        <div className="mt-0.5 text-sm text-ink">{cover(usual.totalCover)} total cover</div>
        <ul className="mt-3 space-y-1 text-sm text-muted">
          {usual.highlights.map((h) => <li key={h}>· {h}</li>)}
        </ul>
      </div>
      <div className="relative rounded-2xl border-2 border-sky bg-white p-4 shadow-sm">
        <span className="absolute -top-3 left-4 rounded-full bg-sky px-2.5 py-0.5 text-xs font-semibold text-navy">Recommended</span>
        <div className="text-sm font-medium text-navy">{mix.label}</div>
        <div className="mt-1 text-2xl font-bold text-navy">{rupees(mix.premium)}<span className="text-sm font-normal text-muted"> a year*</span></div>
        <div className="mt-0.5 text-sm text-ink">{cover(mix.totalCover)} total cover</div>
        <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
          {save > 0 && <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700">{rupees(save)} less a year</span>}
          {times > 1 && <span className="rounded-full bg-sky-soft px-2 py-0.5 font-medium text-navy">{Number(times.toFixed(1))}x the cover</span>}
          {mix.highlights.map((h) => <span key={h} className="rounded-full bg-canvas px-2 py-0.5 text-ink">{h}</span>)}
        </div>
      </div>
      <p className="text-xs text-muted sm:col-span-2">*Illustrative premiums.</p>
    </div>
  );
}

/** Each member's cover as stacked layers: base plan first, then any top-up above its deductible. */
function CoverMap({ rec, family, indexOf }: { rec: Recommendation; family: FamilyProfile; indexOf: (id: string) => number }) {
  const rows = family.members
    .map((m) => {
      const policies = rec.mix.policies.filter((p) => p.memberIds.includes(m.id));
      const base = policies.filter((p) => p.kind !== "super_top_up");
      const topUps = policies.filter((p) => p.kind === "super_top_up");
      const baseAmount = base.reduce((s, p) => s + p.sumInsured, 0);
      const usual = rec.usual.policies.find((p) => p.memberIds.includes(m.id));
      return { m, base, topUps, baseAmount, max: baseAmount + topUps.reduce((s, p) => s + p.sumInsured, 0), usual };
    })
    .filter((r) => r.max > 0);
  if (rows.length === 0) return null;
  const scale = Math.max(...rows.map((r) => r.max), ...rows.map((r) => r.usual?.sumInsured ?? 0));

  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-semibold text-ink">How much each person can claim in one year</h3>
        <div className="flex gap-3 text-xs text-muted">
          <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-navy" />Base plan</span>
          <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-sky" />Super top-up</span>
          <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm border border-dashed border-muted" />Usual pick, shared</span>
        </div>
      </div>
      <p className="mb-4 text-xs text-muted">Shared plans split this limit with the others on the same plan.</p>
      <ul className="space-y-3">
        {rows.map(({ m, base, topUps, baseAmount, max, usual }) => (
          <li key={m.id} className="grid grid-cols-[2.5rem_1fr_4.5rem] items-center gap-3">
            <Avatar name={m.name} index={indexOf(m.id)} />
            <div className="space-y-1">
              <div className="flex h-5 overflow-hidden rounded-md bg-canvas" role="img" aria-label={`${m.name}: up to ${cover(max)}`}>
                {base.map((p) => (
                  <span key={p.id} className={`${LAYER_COLOR[p.kind]} h-full`} style={{ width: `${(p.sumInsured / scale) * 100}%` }} title={`${p.planName} ${cover(p.sumInsured)}`} />
                ))}
                {topUps.map((p) => (
                  <span key={p.id} className="h-full border-l-2 border-white bg-sky"
                    style={{ width: `${(p.sumInsured / scale) * 100}%`, marginLeft: p.deductible && p.deductible > baseAmount ? `${((p.deductible - baseAmount) / scale) * 100}%` : undefined }}
                    title={`${p.planName} ${cover(p.sumInsured)} after ${cover(p.deductible ?? 0)}`} />
                ))}
              </div>
              {usual && (
                <div className="h-1.5 rounded-full border border-dashed border-muted/60" style={{ width: `${(usual.sumInsured / scale) * 100}%` }} />
              )}
            </div>
            <span className="text-right text-sm font-semibold tabular-nums text-ink">{cover(max)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ClaimCheck({ rec, nameOf, indexOf, onOpenClause }: {
  rec: Recommendation;
  nameOf: (id: string) => string;
  indexOf: (id: string) => number;
  onOpenClause: (id: string) => void;
}) {
  const [scenarioId, setScenarioId] = useState(rec.claimScenarios[0]?.id);
  const scenario = rec.claimScenarios.find((s) => s.id === scenarioId);
  const [year, setYear] = useState(2);
  if (!scenario) return null;
  const row = scenario.byYear.find((y) => y.year === year) ?? scenario.byYear[0];
  const maxYear = scenario.byYear.length;
  const allPolicies = [...rec.usual.policies, ...rec.mix.policies];
  const planName = (id: string) => {
    const p = allPolicies.find((x) => x.id === id);
    return p ? `${p.planName}, ${p.memberIds.map(nameOf).join(", ")}` : id;
  };

  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <h3 className="font-semibold text-ink">Claim check</h3>
      <p className="text-xs text-muted">Pick a hospital bill and a year. See who pays.</p>

      <div className="mt-3 flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Claim scenarios">
        {rec.claimScenarios.map((s) => (
          <button
            key={s.id}
            role="tab"
            aria-selected={s.id === scenarioId}
            type="button"
            onClick={() => setScenarioId(s.id)}
            className={`flex shrink-0 items-center gap-2 rounded-full border py-1 pl-1 pr-3 text-sm transition ${
              s.id === scenarioId ? "border-navy bg-navy text-white" : "border-line bg-white text-ink hover:border-sky"
            }`}
          >
            <Avatar name={nameOf(s.memberId)} index={indexOf(s.memberId)} size="sm" />
            {nameOf(s.memberId)}: {s.label}, {cover(s.amount)}
          </button>
        ))}
      </div>

      <div className="mt-4 flex items-center gap-3">
        <label htmlFor="claim-year" className="shrink-0 text-sm font-medium text-ink">Policy year {year}</label>
        <input
          id="claim-year"
          type="range"
          min={1}
          max={maxYear}
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          className="flex-1 accent-sky"
        />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {([["Usual pick", row.usual], ["Parivaar Cover mix", row.mix]] as const).map(([label, o]) => (
          <div
            key={label}
            className={`rounded-xl border-2 p-3 transition-colors ${o.outOfPocket === 0 ? "border-emerald-300 bg-emerald-50/60" : o.covered ? "border-amber bg-amber-soft/60" : "border-rose-300 bg-rose-50"}`}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-muted">{label}</span>
              <span className={`inline-flex items-center gap-1 text-sm font-semibold ${o.outOfPocket === 0 ? "text-emerald-700" : o.covered ? "text-ink" : "text-rose-700"}`}>
                {o.outOfPocket === 0 ? <CheckIcon className="h-4 w-4" /> : o.covered ? <AlertIcon className="h-4 w-4" /> : <XIcon className="h-4 w-4" />}
                {o.outOfPocket === 0 ? "Fully covered" : o.covered ? "Partly covered" : "Not covered"}
              </span>
            </div>
            <div className="mt-2 text-sm text-ink">
              You pay <span className="font-bold">{rupees(o.outOfPocket)}</span>
            </div>
            {o.paidBy.length > 0 && (
              <ul className="mt-1 space-y-0.5 text-xs text-muted">
                {o.paidBy.map((p) => <li key={p.policyId}>{planName(p.policyId)} pays {cover(p.amount)}</li>)}
              </ul>
            )}
            <p className="mt-2 text-xs text-ink">{o.reason}</p>
            {o.clauseId && rec.clauses[o.clauseId] && (
              <button type="button" onClick={() => onOpenClause(o.clauseId!)}
                className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-navy hover:underline">
                <DocIcon className="h-3.5 w-3.5" /> {rec.clauses[o.clauseId].title}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function PolicyCard({ policy, rec, nameOf, indexOf, onOpenClause }: {
  policy: Policy;
  rec: Recommendation;
  nameOf: (id: string) => string;
  indexOf: (id: string) => number;
  onOpenClause: (id: string) => void;
}) {
  return (
    <li className="flex flex-col rounded-2xl border border-line bg-white p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${policy.kind === "super_top_up" ? "bg-sky-soft text-navy" : "bg-navy-soft text-navy"}`}>
            {KIND_LABEL[policy.kind]}
          </span>
          <div className="mt-1.5 font-semibold text-ink">{cover(policy.sumInsured)} {policy.planName.toLowerCase()}</div>
          <div className="text-xs text-muted">
            {policy.insurer}
            {policy.deductible ? ` · starts after ${cover(policy.deductible)}` : ""}
          </div>
        </div>
        <div className="text-right">
          <div className="font-bold text-navy">{rupees(policy.premium)}</div>
          <div className="text-[11px] text-muted">a year, illustrative</div>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <span className="flex -space-x-2">
          {policy.memberIds.map((id) => <Avatar key={id} name={nameOf(id)} index={indexOf(id)} size="sm" />)}
        </span>
        <span className="text-xs text-muted">{policy.memberIds.map(nameOf).join(", ")}</span>
      </div>

      <p className="mt-3 text-sm text-ink">{policy.why}</p>
      {policy.catches.length > 0 && (
        <ul className="mt-2 space-y-1">
          {policy.catches.map((c) => (
            <li key={c} className="flex items-start gap-1.5 text-sm text-ink">
              <AlertIcon className="mt-0.5 h-4 w-4 text-amber" />
              <span><span className="font-medium">Catch:</span> {c}</span>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-auto flex flex-wrap gap-1.5 pt-3">
        {policy.clauseIds.map((id) => rec.clauses[id] && (
          <button key={id} type="button" onClick={() => onOpenClause(id)}
            className="inline-flex items-center gap-1 rounded-full bg-navy-soft px-2.5 py-1 text-xs text-navy hover:bg-sky-soft">
            <DocIcon className="h-3.5 w-3.5" /> {rec.clauses[id].title}
          </button>
        ))}
      </div>
    </li>
  );
}
