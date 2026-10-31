// Short labels for the rules a user set, shown as chips with a remove button.

import type { PolicyKind, Requirements } from "./types";
import { cover } from "./format";

export type RuleChip = {
  key: string;
  label: string;
  /** The rules with this one taken out. */
  without: Requirements;
};

const KIND_PLURAL: Record<PolicyKind, string> = {
  floater: "family floaters",
  individual: "individual plans",
  senior: "senior plans",
  super_topup: "super top-ups",
};

const span = (months: number) =>
  months % 12 === 0 ? `${months / 12} ${months === 12 ? "year" : "years"}` : `${months} months`;

const drop = <T,>(record: Record<string, T> | undefined, key: string) =>
  Object.fromEntries(Object.entries(record ?? {}).filter(([k]) => k !== key));

/** One chip per rule. Names and policy names come from the caller, so a chip reads "Mohan: at least ₹25L". */
export function ruleChips(r: Requirements | undefined, nameOf: (id: string) => string, policyName: (id: string) => string | undefined): RuleChip[] {
  if (!r) return [];
  const out: RuleChip[] = [];
  for (const [id, amount] of Object.entries(r.minCover ?? {})) {
    out.push({ key: `min-${id}`, label: `${nameOf(id)}: at least ${cover(amount)}`, without: { ...r, minCover: drop(r.minCover, id) } });
  }
  for (const [id, months] of Object.entries(r.maxWaitMonths ?? {})) {
    out.push({ key: `wait-${id}`, label: `${nameOf(id)}: covered within ${span(months)}`, without: { ...r, maxWaitMonths: drop(r.maxWaitMonths, id) } });
  }
  if (r.maxCopayPercent != null) {
    out.push({ key: "copay", label: r.maxCopayPercent === 0 ? "No co-pay" : `Co-pay up to ${r.maxCopayPercent}%`, without: { ...r, maxCopayPercent: null } });
  }
  if (r.uncappedRoomRent) out.push({ key: "room", label: "No room rent cap", without: { ...r, uncappedRoomRent: false } });
  if (r.oneInsurer) out.push({ key: "one-insurer", label: "One insurer", without: { ...r, oneInsurer: false } });
  for (const insurer of r.avoidInsurers ?? []) {
    out.push({ key: `insurer-${insurer}`, label: `Not ${insurer}`, without: { ...r, avoidInsurers: r.avoidInsurers!.filter((i) => i !== insurer) } });
  }
  for (const id of r.avoidPolicies ?? []) {
    out.push({ key: `policy-${id}`, label: `Not ${policyName(id) ?? "a plan you dropped"}`, without: { ...r, avoidPolicies: r.avoidPolicies!.filter((p) => p !== id) } });
  }
  for (const kind of r.avoidPlanTypes ?? []) {
    out.push({ key: `kind-${kind}`, label: `No ${KIND_PLURAL[kind]}`, without: { ...r, avoidPlanTypes: r.avoidPlanTypes!.filter((k) => k !== kind) } });
  }
  if (r.maxPolicies) out.push({ key: "max-policies", label: `At most ${r.maxPolicies} policies`, without: { ...r, maxPolicies: null } });
  return out;
}
