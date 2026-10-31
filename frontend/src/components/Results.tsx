"use client";

import { useEffect, useState } from "react";
import { getSummary } from "@/lib/api";
import type { ClaimOutcome, CoverCheck, FamilyProfile, MixSummary, Policy, PolicyKind, Recommendation } from "@/lib/types";
import { conditionLabel, cover, rupees } from "@/lib/format";
import { Avatar } from "./Avatar";
import { AlertIcon, CheckIcon, DocIcon, XIcon } from "./icons";

const KIND_LABEL: Record<PolicyKind, string> = {
  floater: "Family floater",
  individual: "Individual",
  senior: "Senior plan",
  super_topup: "Super top-up",
};

const years = (months: number) => (months % 12 === 0 ? `${months / 12} ${months === 12 ? "year" : "years"}` : `${months} months`);

type Props = {
  rec: Recommendation;
  family: FamilyProfile;
  onOpenPolicy: (id: string) => void;
  onEditFamily: () => void;
};

export function Results({ rec, family, onOpenPolicy, onEditFamily }: Props) {
  const indexOf = (id: string) => Math.max(0, family.members.findIndex((m) => m.id === id));
  const nameOf = (id: string) => family.members.find((m) => m.id === id)?.name ?? id;

  return (
    <section className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-6" aria-labelledby="results-title">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="results-title" className="text-lg font-semibold text-navy">Your family&apos;s mix</h2>
        </div>
        <button type="button" onClick={onEditFamily} className="text-sm font-medium text-sky hover:underline">
          Edit family
        </button>
      </header>

      {rec.coverCheck && rec.coverCheck.code !== "cover_met" && <CoverShort check={rec.coverCheck} />}
      <SummaryBox recId={rec.id} />
      <Compare rec={rec} family={family} />
      <CoverMap rec={rec} family={family} indexOf={indexOf} />
      <ClaimCheck rec={rec} nameOf={nameOf} indexOf={indexOf} />

      {rec.mixCatches.length > 0 && (
        <div>
          <h3 className="mb-3 font-semibold text-ink">Catches in this mix</h3>
          <ul className="divide-y divide-line rounded-2xl border border-line bg-white">
            {rec.mixCatches.map((c) => (
              <li key={c.text} className="flex items-start gap-3 px-4 py-3 text-sm text-ink">
                <AlertIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber" />
                <span className="flex-1">{c.text}</span>
                <span className="flex shrink-0 -space-x-2">
                  {c.memberIds.map((id) => <Avatar key={id} name={nameOf(id)} index={indexOf(id)} size="sm" />)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h3 className="mb-3 font-semibold text-ink">The {rec.mix.policies.length} policies and their catches</h3>
        <ul className="grid gap-3 md:grid-cols-2">
          {rec.mix.policies.map((p, i) => (
            <PolicyCard key={`${p.id}-${i}`} policy={p} nameOf={nameOf} indexOf={indexOf} onOpen={() => onOpenPolicy(p.id)} />
          ))}
        </ul>
      </div>
    </section>
  );
}

/** Why this mix and what to watch, in a few lines. Sarvam writes it from the solver's facts. */
/** The budget kept cover below what the family asked for. Says by how much and what budget would reach it. */
function CoverShort({ check }: { check: CoverCheck }) {
  return (
    <div role="status" className="flex items-start gap-3 rounded-2xl border border-amber bg-amber-soft p-4 text-sm text-ink">
      <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-amber" />
      <div className="space-y-1">
        <div className="font-semibold">
          {cover(check.totalCover)} of cover, short of the {cover(check.target)} you asked for
        </div>
        <p>{check.text}</p>
        {check.budgetNeeded != null && (
          <p className="text-muted">To try another budget, tap Edit family and tell me the new amount.</p>
        )}
      </div>
    </div>
  );
}

function SummaryBox({ recId }: { recId: string }) {
  const [result, setResult] = useState<{ id: string; summary: MixSummary | null } | null>(null);

  useEffect(() => {
    let live = true;
    getSummary(recId)
      .then((summary) => live && setResult({ id: recId, summary }))
      .catch(() => live && setResult({ id: recId, summary: null }));
    return () => {
      live = false;
    };
  }, [recId]);

  const loading = result?.id !== recId;
  const summary = loading ? null : result.summary;
  // The rest of the screen says the same things, so a failed summary just leaves the box out
  if (!loading && !summary) return null;

  return (
    <div className="rounded-2xl bg-navy p-4 text-white shadow-sm" aria-live="polite" aria-busy={loading}>
      <div className="text-xs font-semibold uppercase tracking-wide text-sky">Why this mix</div>
      {summary ? (
        <p className="mt-1 text-sm leading-relaxed">{summary.why}</p>
      ) : (
        <div className="mt-2 space-y-2" aria-label="Writing a short summary">
          <div className="h-3 w-full animate-pulse rounded bg-white/15" />
          <div className="h-3 w-4/5 animate-pulse rounded bg-white/15" />
        </div>
      )}
      {summary && summary.watch.length > 0 && (
        <>
          <div className="mt-3 text-xs font-semibold uppercase tracking-wide text-amber">What to watch</div>
          <ul className="mt-1 space-y-1">
            {summary.watch.map((w) => (
              <li key={w} className="flex items-start gap-1.5 text-sm">
                <AlertIcon className="mt-0.5 h-4 w-4 shrink-0 text-amber" />
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {summary && (
        <p className="mt-3 text-[11px] text-white/60">
          {summary.source === "llm" ? "Written by AI from the solver's results." : "From the solver's results."}
        </p>
      )}
    </div>
  );
}

/** When each member's existing conditions get covered, from the base plan that covers them. */
function conditionWaits(policies: Policy[], family: FamilyProfile): string[] {
  return family.members
    .filter((m) => m.conditions.length)
    .map((m) => {
      const base = policies.find((p) => p.kind !== "super_topup" && p.memberIds.includes(m.id));
      if (!base) return null;
      return `${m.name}'s ${m.conditions.map(conditionLabel).join(" and ")} covered after ${years(base.waitsMonths.preExisting)}`;
    })
    .filter((x): x is string => Boolean(x));
}

function Compare({ rec, family }: { rec: Recommendation; family: FamilyProfile }) {
  const { usual, mix } = rec;
  const times = usual ? mix.totalCover / usual.totalCover : 0;
  const usualPolicy = usual?.policies[0];
  const mixCopays = mix.policies.filter((p) => p.copayPercent > 0);
  const facts = rec.vsUsual.filter((f) => f.code !== "member_cover");

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {usual ? (
        <div className="rounded-2xl border border-line bg-white p-4">
          <div className="text-sm font-medium text-muted">{usual.label}</div>
          <div className="mt-1 text-2xl font-bold text-ink">{rupees(usual.premium)}<span className="text-sm font-normal text-muted"> a year</span></div>
          <div className="mt-0.5 text-sm text-ink">{cover(usual.totalCover)} total cover</div>
          <ul className="mt-3 space-y-1 text-sm text-muted">
            {usualPolicy && <li>· One {usualPolicy.product} floater for all {usualPolicy.memberIds.length}</li>}
            {conditionWaits(usual.policies, family).map((w) => <li key={w}>· {w}</li>)}
          </ul>
        </div>
      ) : (
        <div className="rounded-2xl border border-line bg-white p-4">
          <div className="text-sm font-medium text-muted">Usual pick</div>
          <div className="mt-1 text-lg font-semibold text-ink">No single floater fits</div>
          <p className="mt-1 text-sm text-muted">
            No family floater takes all {family.members.length} of you, so there is no one-policy price to compare with.
          </p>
        </div>
      )}
      <div className="relative rounded-2xl border-2 border-sky bg-white p-4 shadow-sm">
        <span className="absolute -top-3 left-4 rounded-full bg-sky px-2.5 py-0.5 text-xs font-semibold text-navy">Recommended</span>
        <div className="text-sm font-medium text-navy">{mix.label}</div>
        <div className="mt-1 text-2xl font-bold text-navy">{rupees(mix.premium)}<span className="text-sm font-normal text-muted"> a year</span></div>
        <div className="mt-0.5 text-sm text-ink">{cover(mix.totalCover)} total cover</div>
        <div className="mt-3 flex flex-wrap gap-1.5 text-xs">
          {rec.saving != null && rec.saving > 0 && <span className="rounded-full bg-emerald-50 px-2 py-0.5 font-medium text-emerald-700">{rupees(rec.saving)} less a year</span>}
          {rec.coverCheck?.code === "cover_met" && (
            <span className="rounded-full bg-sky-soft px-2 py-0.5 font-medium text-navy">You asked for {cover(rec.coverCheck.target)}</span>
          )}
          {times > 1 && <span className="rounded-full bg-sky-soft px-2 py-0.5 font-medium text-navy">{Number(times.toFixed(1))}x the cover</span>}
          <span className="rounded-full bg-canvas px-2 py-0.5 text-ink">{mix.policies.length} policies</span>
          {!facts.some((f) => f.code === "condition_wait") && conditionWaits(mix.policies, family).map((w) => (
            <span key={w} className="rounded-full bg-canvas px-2 py-0.5 text-ink">{w}</span>
          ))}
          {mixCopays.map((p) => (
            <span key={p.id} className="rounded-full bg-amber-soft px-2 py-0.5 text-ink">
              {p.copayPercent}% co-pay on {p.product}
            </span>
          ))}
        </div>
      </div>
      {facts.length > 0 && (
        <ul className="space-y-1 rounded-2xl bg-sky-soft/60 px-4 py-3 text-sm text-ink sm:col-span-2">
          {facts.map((f) => (
            <li key={f.text} className="flex items-start gap-1.5">
              <CheckIcon className="mt-0.5 h-4 w-4 text-sky" />
              {f.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Each member's cover as layers: base plan, then a top-up above its deductible. The total comes from the solver. */
function CoverMap({ rec, family, indexOf }: { rec: Recommendation; family: FamilyProfile; indexOf: (id: string) => number }) {
  const rows = family.members
    .map((m) => {
      const policies = rec.mix.policies.filter((p) => p.memberIds.includes(m.id));
      const usual = rec.usual?.policies.find((p) => p.memberIds.includes(m.id));
      return {
        m,
        base: policies.filter((p) => p.kind !== "super_topup"),
        topUps: policies.filter((p) => p.kind === "super_topup"),
        total: rec.memberCover[m.id] ?? 0,
        usual,
      };
    })
    .filter((r) => r.total > 0);
  if (rows.length === 0) return null;
  const scale = Math.max(...rows.map((r) => r.total), ...rows.map((r) => r.usual?.sumInsured ?? 0));
  const pct = (n: number) => `${(n / scale) * 100}%`;

  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-semibold text-ink">How much each person can claim in one year</h3>
        <div className="flex gap-3 text-xs text-muted">
          <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-navy" />Base plan</span>
          <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-sky" />Super top-up</span>
          {rec.usual && <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm border border-dashed border-muted" />Usual pick, shared</span>}
        </div>
      </div>
      <p className="mb-4 text-xs text-muted">Shared plans split this limit with the others on the same plan.</p>
      <ul className="space-y-3">
        {rows.map(({ m, base, topUps, total, usual }) => (
          <li key={m.id} className="grid grid-cols-[2.5rem_1fr_4.5rem] items-center gap-3">
            <Avatar name={m.name} index={indexOf(m.id)} />
            <div className="space-y-1">
              <div className="flex h-5 overflow-hidden rounded-md bg-canvas" role="img" aria-label={`${m.name}: up to ${cover(total)}`}>
                {base.map((p) => (
                  <span key={p.id} className="h-full bg-navy" style={{ width: pct(p.sumInsured) }} title={`${p.product} ${cover(p.sumInsured)}`} />
                ))}
                {topUps.map((p) => (
                  <span key={p.id} className="h-full border-l-2 border-white bg-sky" style={{ width: pct(p.sumInsured) }}
                    title={`${p.product} ${cover(p.sumInsured)} after ${cover(p.deductible)}`} />
                ))}
              </div>
              {usual && <div className="h-1.5 rounded-full border border-dashed border-muted/60" style={{ width: pct(usual.sumInsured) }} />}
            </div>
            <span className="text-right text-sm font-semibold tabular-nums text-ink">{cover(total)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ClaimCheck({ rec, nameOf, indexOf }: {
  rec: Recommendation;
  nameOf: (id: string) => string;
  indexOf: (id: string) => number;
}) {
  const [scenarioId, setScenarioId] = useState(rec.claimScenarios[0]?.id);
  const scenario = rec.claimScenarios.find((s) => s.id === scenarioId);
  const yearsAvailable = scenario?.byYear.map((y) => y.year) ?? [];
  const [year, setYear] = useState(2);
  if (!scenario) return null;
  const row = scenario.byYear.find((y) => y.year === year) ?? scenario.byYear[0];
  const minYear = Math.min(...yearsAvailable);
  const maxYear = Math.max(...yearsAvailable);

  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <h3 className="font-semibold text-ink">Claim check</h3>
      <p className="text-xs text-muted">Pick a hospital bill and a year. See who pays.</p>

      {rec.claimScenarios.length > 1 && (
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
      )}
      {rec.claimScenarios.length === 1 && (
        <p className="mt-3 text-sm font-medium text-ink">{nameOf(scenario.memberId)}: {scenario.label}, {cover(scenario.amount)}</p>
      )}

      {maxYear > minYear && (
        <div className="mt-4 flex items-center gap-3">
          <label htmlFor="claim-year" className="shrink-0 text-sm font-medium text-ink">Policy year {row.year}</label>
          <input id="claim-year" type="range" min={minYear} max={maxYear} value={row.year}
            onChange={(e) => setYear(Number(e.target.value))} className="flex-1 accent-sky" />
        </div>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Outcome label="Usual pick" o={row.usual} year={row.year} />
        <Outcome label="Parivaar Cover mix" o={row.mix} year={row.year} />
      </div>
    </div>
  );
}

function Outcome({ label, o, year }: { label: string; o: ClaimOutcome; year: number }) {
  const full = o.covered && o.outOfPocket === 0;
  const status = full ? "Fully covered" : o.covered ? "Partly covered" : "Not covered";
  const tone = full ? "border-emerald-300 bg-emerald-50/60" : o.covered ? "border-amber bg-amber-soft/60" : "border-rose-300 bg-rose-50";
  const ink = full ? "text-emerald-700" : o.covered ? "text-ink" : "text-rose-700";
  return (
    <div className={`rounded-xl border-2 p-3 transition-colors ${tone}`}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-muted">{label}</span>
        <span className={`inline-flex items-center gap-1 text-sm font-semibold ${ink}`}>
          {full ? <CheckIcon className="h-4 w-4" /> : o.covered ? <AlertIcon className="h-4 w-4" /> : <XIcon className="h-4 w-4" />}
          {status}
        </span>
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-2 text-sm">
        <div><dt className="text-xs text-muted">Insurance pays</dt><dd className="font-bold text-ink">{rupees(o.payable)}</dd></div>
        <div><dt className="text-xs text-muted">You pay</dt><dd className="font-bold text-ink">{rupees(o.outOfPocket)}</dd></div>
      </dl>
      {!o.covered && o.coveredFromYear > year && o.notes.length === 0 && (
        <p className="mt-2 text-xs font-medium text-ink">Covered from year {o.coveredFromYear}.</p>
      )}
      {o.notes.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-ink">
          {o.notes.map((n) => <li key={n}>{n}</li>)}
        </ul>
      )}
    </div>
  );
}

function PolicyCard({ policy, nameOf, indexOf, onOpen }: {
  policy: Policy;
  nameOf: (id: string) => string;
  indexOf: (id: string) => number;
  onOpen: () => void;
}) {
  return (
    <li className="flex flex-col rounded-2xl border border-line bg-white p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${policy.kind === "super_topup" ? "bg-sky-soft text-navy" : "bg-navy-soft text-navy"}`}>
            {KIND_LABEL[policy.kind]}
          </span>
          <div className="mt-1.5 font-semibold text-ink">{cover(policy.sumInsured)} {policy.product}</div>
          <div className="text-xs text-muted">
            {policy.insurer}
            {policy.deductible ? ` · starts after ${cover(policy.deductible)}` : ""}
          </div>
        </div>
        <div className="text-right">
          <div className="font-bold text-navy">{rupees(policy.premium)}</div>
          <div className="text-[11px] text-muted">a year</div>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2">
        <span className="flex -space-x-2">
          {policy.memberIds.map((id) => <Avatar key={id} name={nameOf(id)} index={indexOf(id)} size="sm" />)}
        </span>
        <span className="text-xs text-muted">{policy.memberIds.map(nameOf).join(", ")}</span>
      </div>

      {policy.reasons.length > 0 && (
        <div className="mt-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted">Why this pick</div>
          <ul className="mt-1 space-y-1">
            {policy.reasons.map((r) => (
              <li key={r} className="flex items-start gap-1.5 text-sm text-ink">
                <CheckIcon className="mt-0.5 h-4 w-4 text-sky" />
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {policy.catches.length > 0 && (
        <div className="mt-3 text-xs font-semibold uppercase tracking-wide text-muted">Catches</div>
      )}
      {policy.catches.length > 0 && (
        <ul className="mt-1 space-y-1">
          {policy.catches.map((c) => (
            <li key={c} className="flex items-start gap-1.5 text-sm text-ink">
              <AlertIcon className="mt-0.5 h-4 w-4 text-amber" />
              <span>{c}</span>
            </li>
          ))}
        </ul>
      )}
      {policy.nextBest && (
        <details className="group mt-3 rounded-lg bg-canvas px-3 py-2 text-sm">
          <summary className="cursor-pointer list-none text-xs font-medium text-navy marker:hidden">
            <span className="group-open:hidden">Show the next best option</span>
            <span className="hidden group-open:inline">Next best option</span>
          </summary>
          <p className="mt-1.5 text-ink">{policy.nextBest}</p>
        </details>
      )}
      <div className="mt-auto pt-3">
        <button type="button" onClick={onOpen}
          className="inline-flex items-center gap-1 rounded-full bg-navy-soft px-2.5 py-1 text-xs text-navy hover:bg-sky-soft">
          <DocIcon className="h-3.5 w-3.5" /> Fine print
        </button>
      </div>
    </li>
  );
}
