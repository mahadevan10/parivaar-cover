// The backend's formats (see shared/README.md) and the mapping to the UI's types.
// This is the only file that knows the solver's snake_case shapes.

import type { ClaimOutcome, ClaimScenario, FamilyProfile, Policy, PlanOption, Recommendation } from "./types";

export type SolverFamily = {
  id: string;
  city?: string;
  budget?: number;
  members: { id: string; name: string; age?: number; relation?: string; conditions: string[] }[];
  office_cover: { members: string[]; sum_insured: number }[];
};

export type SolverPick = {
  policy_id: string;
  insurer: string;
  product: string;
  plan_type: Policy["kind"];
  members: string[];
  sum_insured: number;
  deductible: number;
  premium: number;
  copay_percent: number;
  waiting_periods_months: { initial: number; specific_illness: number; pre_existing: number };
  catches: string[];
  source?: string;
  /** Each reason has a code, the numbers behind it, and a plain sentence. See shared/README.md. */
  reasons?: { code: string; text: string }[];
};

export type SolverClaim = {
  member_id: string;
  amount: number;
  policy_year: number;
  covered: boolean;
  payable: number;
  out_of_pocket: number;
  covered_from_year: number;
  notes: string[];
};

export type SolverOutput = {
  status: "ok" | "no_fit";
  family_id: string;
  budget: number;
  illustrative: boolean;
  picks: SolverPick[];
  total_premium: number;
  total_cover: number;
  member_cover: Record<string, number>;
  usual_pick: SolverPick;
  saving_vs_usual: number;
  vs_usual?: { code: string; text: string }[];
  claim_check?: { mix: SolverClaim; usual: SolverClaim };
};

/** One claim scenario run for every policy year. */
export type SolverClaimSeries = {
  id: string;
  member_id: string;
  label: string;
  amount: number;
  by_year: { policy_year: number; mix: SolverClaim; usual: SolverClaim }[];
};

const SPOUSE = new Set(["wife", "husband", "spouse"]);

export function toSolverFamily(family: FamilyProfile, id: string): SolverFamily {
  return {
    id,
    city: family.city,
    budget: family.budget,
    members: family.members.map((m) => ({
      id: m.id,
      name: m.name,
      age: m.age,
      relation: m.relation && SPOUSE.has(m.relation) ? "spouse" : m.relation,
      conditions: m.conditions,
    })),
    office_cover: family.officeCover
      ? [{ members: family.officeCover.memberIds, sum_insured: family.officeCover.amount }]
      : [],
  };
}

export function fromSolverFamily(f: SolverFamily): FamilyProfile {
  const office = f.office_cover[0];
  return {
    members: f.members.map((m) => ({ ...m, conditions: [...m.conditions], heardFrom: undefined })),
    city: f.city,
    budget: f.budget,
    officeCover: office ? { amount: office.sum_insured, memberIds: office.members } : undefined,
    healthChecked: true,
    officeChecked: true,
  };
}

function toPolicy(p: SolverPick): Policy {
  return {
    id: p.policy_id,
    product: p.product,
    insurer: p.insurer,
    kind: p.plan_type,
    memberIds: p.members,
    sumInsured: p.sum_insured,
    deductible: p.deductible,
    premium: p.premium,
    copayPercent: p.copay_percent,
    waitsMonths: {
      initial: p.waiting_periods_months.initial,
      specificIllness: p.waiting_periods_months.specific_illness,
      preExisting: p.waiting_periods_months.pre_existing,
    },
    catches: p.catches,
    reasons: (p.reasons ?? []).filter((r) => r.code !== "next_best").map((r) => r.text),
    nextBest: p.reasons?.find((r) => r.code === "next_best")?.text,
    sourceUrl: p.source,
  };
}

function toOutcome(c: SolverClaim): ClaimOutcome {
  return {
    covered: c.covered,
    payable: c.payable,
    outOfPocket: c.out_of_pocket,
    coveredFromYear: c.covered_from_year,
    notes: c.notes,
  };
}

export function toClaimScenario(s: SolverClaimSeries): ClaimScenario {
  return {
    id: s.id,
    memberId: s.member_id,
    label: s.label,
    amount: s.amount,
    byYear: s.by_year.map((y) => ({ year: y.policy_year, mix: toOutcome(y.mix), usual: toOutcome(y.usual) })),
  };
}

export function toRecommendation(out: SolverOutput, claimSeries: SolverClaimSeries[] = []): Recommendation {
  const mix: PlanOption = {
    label: "Parivaar Cover mix",
    premium: out.total_premium,
    totalCover: out.total_cover,
    policies: out.picks.map(toPolicy),
  };
  const usual: PlanOption = {
    label: "Usual pick",
    premium: out.usual_pick.premium,
    totalCover: out.usual_pick.sum_insured,
    policies: [toPolicy(out.usual_pick)],
  };

  // A single claim check from /recommend becomes a one-year scenario.
  const single = out.claim_check
    ? [{
        id: `${out.claim_check.mix.member_id}-claim`,
        member_id: out.claim_check.mix.member_id,
        label: "Hospital bill",
        amount: out.claim_check.mix.amount,
        by_year: [{ policy_year: out.claim_check.mix.policy_year, ...out.claim_check }],
      }]
    : [];

  return {
    id: `${out.family_id}-${out.total_premium}`,
    illustrative: out.illustrative,
    usual,
    mix,
    saving: out.saving_vs_usual,
    vsUsual: out.vs_usual ?? [],
    memberCover: out.member_cover,
    claimScenarios: (claimSeries.length ? claimSeries : single).map(toClaimScenario),
  };
}

/**
 * Rename member ids in solver output, e.g. when the demo output (ids like "mohan")
 * is shown for a family the user built in chat (generated ids).
 */
export function remapMembers(out: SolverOutput, series: SolverClaimSeries[], map: (id: string) => string) {
  const pick = (p: SolverPick): SolverPick => ({ ...p, members: p.members.map(map) });
  const claim = (c: SolverClaim): SolverClaim => ({ ...c, member_id: map(c.member_id) });
  return {
    out: {
      ...out,
      picks: out.picks.map(pick),
      usual_pick: pick(out.usual_pick),
      member_cover: Object.fromEntries(Object.entries(out.member_cover).map(([k, v]) => [map(k), v])),
      claim_check: out.claim_check && { mix: claim(out.claim_check.mix), usual: claim(out.claim_check.usual) },
    },
    series: series.map((s) => ({
      ...s,
      member_id: map(s.member_id),
      by_year: s.by_year.map((y) => ({ ...y, mix: claim(y.mix), usual: claim(y.usual) })),
    })),
  };
}
