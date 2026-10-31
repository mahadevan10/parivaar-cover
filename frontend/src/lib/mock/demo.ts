// Demo data that matches the deck. Used until the backend is wired in.
// Plan names, clause text and premiums are illustrative.

import type {
  ClaimOutcome,
  ClaimScenario,
  FamilyProfile,
  Recommendation,
} from "../types";

export const DEMO_FAMILY: FamilyProfile = {
  members: [
    { id: "rahul", name: "Rahul", relation: "self", age: 36, conditions: [], heardFrom: "Demo family" },
    { id: "sneha", name: "Sneha", relation: "wife", age: 33, conditions: [], heardFrom: "Demo family" },
    { id: "aarav", name: "Aarav", relation: "son", age: 6, conditions: [], heardFrom: "Demo family" },
    { id: "mohan", name: "Mohan", relation: "father", age: 64, conditions: ["diabetes"], heardFrom: "Demo family" },
    { id: "lata", name: "Lata", relation: "mother", age: 60, conditions: [], heardFrom: "Demo family" },
  ],
  city: "Pune",
  budget: 1_10_000,
  healthChecked: true,
  officeChecked: true,
};

export const DEMO_DESCRIPTION =
  "I'm Rahul, 36. My wife Sneha is 33 and our son Aarav is 6. My father Mohan is 64 and diabetic, my mother Lata is 60. We live in Pune. Budget is about 1.1 lakh a year. No office cover.";

const L = 1_00_000;

const covered = (policyId: string, amount: number, reason: string, clauseId?: string): ClaimOutcome => ({
  covered: true,
  paidBy: [{ policyId, amount }],
  outOfPocket: 0,
  reason,
  clauseId,
});

const notCovered = (amount: number, reason: string, clauseId?: string): ClaimOutcome => ({
  covered: false,
  paidBy: [],
  outOfPocket: amount,
  reason,
  clauseId,
});

const sameEveryYear = (usual: ClaimOutcome, mix: ClaimOutcome): ClaimScenario["byYear"] =>
  [1, 2, 3, 4].map((year) => ({ year, usual, mix }));

const claimScenarios: ClaimScenario[] = [
  {
    id: "mohan-heart",
    memberId: "mohan",
    label: "Heart procedure",
    amount: 6 * L,
    byYear: [1, 2, 3, 4].map((year) => ({
      year,
      usual:
        year < 4
          ? notCovered(6 * L, "Mohan's diabetes is in the 3-year waiting period, so heart care linked to it is not paid.", "c-ped-usual")
          : covered("u-floater", 6 * L, "The 3-year wait is over. The floater pays from the shared ₹25L.", "c-ped-usual"),
      mix:
        year < 2
          ? notCovered(6 * L, "Mohan's senior plan has a 1-year wait for diabetes. Year 1 is still inside it.", "c-ped-senior")
          : covered("p-senior", 6 * L, "The 1-year diabetes wait is over. Mohan's own ₹10L plan pays in full.", "c-ped-senior"),
    })),
  },
  {
    id: "rahul-cancer",
    memberId: "rahul",
    label: "Cancer treatment",
    amount: 30 * L,
    byYear: sameEveryYear(
      {
        covered: true,
        paidBy: [{ policyId: "u-floater", amount: 25 * L }],
        outOfPocket: 5 * L,
        reason: "The floater stops at ₹25L. The family pays the last ₹5L.",
        clauseId: "c-floater-usual",
      },
      {
        covered: true,
        paidBy: [
          { policyId: "p-floater", amount: 10 * L },
          { policyId: "p-topup-young", amount: 20 * L },
        ],
        outOfPocket: 0,
        reason: "The floater pays the first ₹10L. The super top-up pays the rest.",
        clauseId: "c-topup-deductible",
      },
    ),
  },
  {
    id: "aarav-dengue",
    memberId: "aarav",
    label: "Dengue, 4 days in hospital",
    amount: 80_000,
    byYear: sameEveryYear(
      covered("u-floater", 80_000, "Paid from the shared ₹25L.", "c-floater-usual"),
      covered("p-floater", 80_000, "Paid from the family floater.", "c-floater-shared"),
    ),
  },
];

export const DEMO_RECOMMENDATION: Recommendation = {
  id: "demo-pune-family",
  illustrative: true,
  usual: {
    label: "Usual pick",
    premium: 1_18_000,
    totalCover: 25 * L,
    highlights: ["One floater for all five", "Diabetes covered after 3 years"],
    policies: [
      {
        id: "u-floater",
        planName: "Family floater",
        insurer: "Insurer A",
        kind: "floater",
        memberIds: ["rahul", "sneha", "aarav", "mohan", "lata"],
        sumInsured: 25 * L,
        premium: 1_18_000,
        why: "One policy that covers everyone.",
        catches: [
          "₹25L is shared by all five, including two parents over 60.",
          "Mohan's diabetes is covered only after 3 years.",
        ],
        clauseIds: ["c-floater-usual", "c-ped-usual"],
      },
    ],
  },
  mix: {
    label: "Parivaar Cover mix",
    premium: 1_07_000,
    totalCover: 105 * L,
    highlights: ["Five policies", "Diabetes covered after 1 year", "Parents get their own cover"],
    policies: [
      {
        id: "p-floater",
        planName: "Family floater",
        insurer: "Insurer B",
        kind: "floater",
        memberIds: ["rahul", "sneha", "aarav"],
        sumInsured: 10 * L,
        premium: 21_000,
        why: "Young members are cheap to cover together. ₹10L handles most hospital stays.",
        catches: ["The ₹10L is shared by all three in a year."],
        clauseIds: ["c-floater-shared"],
      },
      {
        id: "p-topup-young",
        planName: "Super top-up",
        insurer: "Insurer C",
        kind: "super_top_up",
        memberIds: ["rahul", "sneha", "aarav"],
        sumInsured: 50 * L,
        deductible: 10 * L,
        premium: 4_500,
        why: "Adds ₹50L for big bills at a low price, because it starts after ₹10L.",
        catches: ["Pays only after ₹10L of bills in the year."],
        clauseIds: ["c-topup-deductible"],
      },
      {
        id: "p-senior",
        planName: "Senior plan",
        insurer: "Insurer D",
        kind: "senior",
        memberIds: ["mohan"],
        sumInsured: 10 * L,
        premium: 41_000,
        why: "Built for people over 60. Covers Mohan's diabetes after 1 year instead of 3.",
        catches: ["Room rent is capped at ₹10,000 a day."],
        clauseIds: ["c-ped-senior", "c-room-senior"],
      },
      {
        id: "p-lata",
        planName: "Individual plan",
        insurer: "Insurer B",
        kind: "individual",
        memberIds: ["lata"],
        sumInsured: 10 * L,
        premium: 24_500,
        why: "Lata has no health conditions, so a standard plan costs less than a senior plan.",
        catches: ["Knee and cataract surgery are covered after 2 years."],
        clauseIds: ["c-specific-wait"],
      },
      {
        id: "p-topup-parents",
        planName: "Super top-up",
        insurer: "Insurer C",
        kind: "super_top_up",
        memberIds: ["mohan", "lata"],
        sumInsured: 25 * L,
        deductible: 10 * L,
        premium: 16_000,
        why: "Gives the parents ₹25L more for a large claim, on top of their own plans.",
        catches: ["Shared by Mohan and Lata. Pays after ₹10L of bills in the year."],
        clauseIds: ["c-topup-deductible"],
      },
    ],
  },
  clauses: {
    "c-floater-usual": {
      id: "c-floater-usual",
      title: "Shared sum insured",
      text: "The sum insured of ₹25,00,000 is available for all insured persons together in a policy year.",
      source: "Insurer A, family floater wording, section 3.2 (sample)",
    },
    "c-ped-usual": {
      id: "c-ped-usual",
      title: "Waiting period for pre-existing diseases",
      text: "Expenses for a pre-existing disease and its direct complications are covered after 36 months of continuous cover.",
      source: "Insurer A, family floater wording, section 4.1 (sample)",
    },
    "c-floater-shared": {
      id: "c-floater-shared",
      title: "Shared sum insured",
      text: "The sum insured of ₹10,00,000 is available for all insured persons together in a policy year.",
      source: "Insurer B, family floater wording, section 3.1 (sample)",
    },
    "c-topup-deductible": {
      id: "c-topup-deductible",
      title: "Aggregate deductible",
      text: "The company pays admissible claims once the total of all hospital bills in the policy year goes above the deductible of ₹10,00,000.",
      source: "Insurer C, super top-up wording, section 2.4 (sample)",
    },
    "c-ped-senior": {
      id: "c-ped-senior",
      title: "Waiting period for declared diabetes",
      text: "Diabetes and hypertension declared at the start of the policy, and their complications, are covered after 12 months of continuous cover.",
      source: "Insurer D, senior plan wording, section 4.1 (sample)",
    },
    "c-room-senior": {
      id: "c-room-senior",
      title: "Room rent limit",
      text: "Room rent is payable up to ₹10,000 per day. If a costlier room is chosen, related charges are paid in the same proportion.",
      source: "Insurer D, senior plan wording, section 3.3 (sample)",
    },
    "c-specific-wait": {
      id: "c-specific-wait",
      title: "Waiting period for listed surgeries",
      text: "Joint replacement and cataract surgery are covered after 24 months of continuous cover.",
      source: "Insurer B, individual plan wording, section 4.2 (sample)",
    },
  },
  claimScenarios,
};

/** Point the demo result at the user's own member ids, matched by name, then relation. */
export function demoRecommendationFor(family: FamilyProfile): Recommendation {
  const ids = new Map<string, string>();
  const used = new Set<string>();
  for (const d of DEMO_FAMILY.members) {
    const match =
      family.members.find((m) => !used.has(m.id) && m.name.toLowerCase() === d.name.toLowerCase()) ??
      family.members.find((m) => !used.has(m.id) && m.relation === d.relation);
    if (match) {
      ids.set(d.id, match.id);
      used.add(match.id);
    }
  }
  const map = (id: string) => ids.get(id) ?? id;
  const remapOption = (o: Recommendation["usual"]) => ({
    ...o,
    policies: o.policies.map((p) => ({ ...p, memberIds: p.memberIds.map(map) })),
  });
  const r = DEMO_RECOMMENDATION;
  return {
    ...r,
    usual: remapOption(r.usual),
    mix: remapOption(r.mix),
    claimScenarios: r.claimScenarios.map((s) => ({ ...s, memberId: map(s.memberId) })),
  };
}
