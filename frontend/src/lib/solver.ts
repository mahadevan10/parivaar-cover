// The backend's formats (see shared/README.md) and the mapping to the UI's types.
// This is the only file that knows the solver's snake_case shapes.

import type { ClaimOutcome, ClaimScenario, CoverCheck, FamilyProfile, PlanOption, Policy, Recommendation } from "./types";

export type SolverFamily = {
  id: string;
  city?: string;
  budget?: number;
  cover_target?: number | null;
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
  /** Set by the API; the /chat endpoint looks results up by it. */
  id?: string;
  status: "ok" | "no_fit";
  family_id: string;
  budget: number;
  picks: SolverPick[];
  total_premium: number;
  total_cover: number;
  member_cover: Record<string, number>;
  /** Null when no single floater can take the whole family. */
  usual_pick: SolverPick | null;
  saving_vs_usual: number | null;
  cover_target?: number | null;
  cover_check?: {
    code: CoverCheck["code"];
    target: number;
    total_cover: number;
    shortfall?: number;
    budget_needed?: number | null;
    text: string;
  } | null;
  vs_usual?: { code: string; text: string }[];
  /** Catches from how the picks stack, most serious first. See shared/README.md. */
  mix_catches?: { code: string; text: string; members: string[] }[];
  claim_check?: { mix: SolverClaim; usual: SolverClaim };
};

/** One claim scenario run for every policy year. */
export type SolverClaimSeries = {
  id: string;
  member_id: string;
  label: string;
  amount: number;
  /** `usual` is null when the solver found no usual pick to compare with. */
  by_year: { policy_year: number; mix: SolverClaim; usual: SolverClaim | null }[];
};

/** A claim to run in /recommend. The backend checks it for policy years 1 to 4. */
export type SolverClaimRequest = {
  id: string;
  label: string;
  member_id: string;
  amount: number;
  related_condition?: string;
  treatment?: string;
};

const HEART_RISK = new Set(["diabetes", "hypertension", "heart_disease"]);

/**
 * Claims for the claim check. Without these the backend only runs condition claims and
 * one cancer claim, so a family with no conditions gets a single scenario.
 */
export function claimsFor(family: SolverFamily): SolverClaimRequest[] {
  const claims: SolverClaimRequest[] = [];
  for (const m of family.members) {
    const condition = m.conditions[0];
    if (!condition) continue;
    const heart = HEART_RISK.has(condition);
    claims.push({
      id: `${m.id}-${heart ? "heart" : "hospital"}`,
      label: heart ? "Heart procedure" : "Hospital stay",
      member_id: m.id,
      amount: 600_000,
      related_condition: condition,
      treatment: heart ? "cardiac" : undefined,
    });
  }

  const byAge = family.members.filter((m) => m.age !== undefined).sort((a, b) => b.age! - a.age!);
  const eldest = byAge[0];
  // Knee surgery is a listed illness, so it shows the 2-year wait most policies have.
  if (eldest && eldest.age! >= 45) {
    claims.push({ id: `${eldest.id}-knee`, label: "Knee surgery", member_id: eldest.id, amount: 350_000, treatment: "knee" });
  }
  const youngest = byAge[byAge.length - 1];
  if (youngest && youngest.age! < 18) {
    claims.push({ id: `${youngest.id}-dengue`, label: "Dengue hospital stay", member_id: youngest.id, amount: 150_000 });
  }

  const first = family.members[0];
  claims.push({ id: `${first.id}-cancer`, label: "Cancer treatment", member_id: first.id, amount: 3_000_000 });
  return claims;
}

const SPOUSE = new Set(["wife", "husband", "spouse"]);

export function toSolverFamily(family: FamilyProfile, id: string): SolverFamily {
  return {
    id,
    city: family.city,
    budget: family.budget,
    cover_target: family.coverTarget ?? null,
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

const NO_USUAL: ClaimOutcome = {
  covered: false,
  payable: 0,
  outOfPocket: 0,
  coveredFromYear: 0,
  notes: ["No single policy fits this family to compare with."],
};

export function toClaimScenario(s: SolverClaimSeries): ClaimScenario {
  return {
    id: s.id,
    memberId: s.member_id,
    label: s.label,
    amount: s.amount,
    byYear: s.by_year.map((y) => ({
      year: y.policy_year,
      mix: toOutcome(y.mix),
      usual: y.usual ? toOutcome(y.usual) : { ...NO_USUAL, outOfPocket: s.amount, coveredFromYear: y.policy_year },
    })),
  };
}

export function toRecommendation(out: SolverOutput, claimSeries: SolverClaimSeries[] = [], id?: string): Recommendation {
  const mix: PlanOption = {
    label: "Parivaar Cover mix",
    premium: out.total_premium,
    totalCover: out.total_cover,
    policies: out.picks.map(toPolicy),
  };
  const usual: PlanOption | null = out.usual_pick && {
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
    id: id ?? out.id ?? `${out.family_id}-${out.total_premium}`,
    usual,
    mix,
    saving: out.saving_vs_usual,
    vsUsual: out.vs_usual ?? [],
    coverCheck: out.cover_check
      ? {
          code: out.cover_check.code,
          target: out.cover_check.target,
          totalCover: out.cover_check.total_cover,
          shortfall: out.cover_check.shortfall,
          budgetNeeded: out.cover_check.budget_needed,
          text: out.cover_check.text,
        }
      : null,
    mixCatches: (out.mix_catches ?? []).map((c) => ({ code: c.code, text: c.text, memberIds: c.members })),
    memberCover: out.member_cover,
    claimScenarios: (claimSeries.length ? claimSeries : single).map(toClaimScenario),
  };
}
