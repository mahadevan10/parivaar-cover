// Demo data for the mock backend. Everything here comes from the backend's
// files in shared/, so the demo shows real solver output.
// Regenerate claim_checks.json with: python3 frontend/scripts/gen_claim_checks.py

import families from "@shared/families.json";
import demoOutput from "@shared/examples/demo_solver_output.json";
import claimChecks from "./claim_checks.json";
import type { FamilyProfile, Recommendation } from "../types";
import {
  remapMembers,
  toRecommendation,
  type SolverClaimSeries,
  type SolverFamily,
  type SolverOutput,
} from "../solver";

const DEMO_SOLVER_FAMILY = (families.families as SolverFamily[]).find((f) => f.id === "demo-pune")!;

export const DEMO_OUTPUT = demoOutput as SolverOutput;
/** The demo family always has a usual pick. */
export const DEMO_USUAL = DEMO_OUTPUT.usual_pick!;
const DEMO_CLAIMS = claimChecks as SolverClaimSeries[];

const SAME_ROLE: Record<string, string[]> = { spouse: ["spouse", "wife", "husband"] };

/** The demo result, pointed at the user's own member ids (matched by name, then relation). */
export function demoRecommendationFor(family: FamilyProfile): Recommendation {
  const ids = new Map<string, string>();
  const used = new Set<string>();
  for (const d of DEMO_SOLVER_FAMILY.members) {
    const roles: (string | undefined)[] = SAME_ROLE[d.relation ?? ""] ?? [d.relation];
    const match =
      family.members.find((m) => !used.has(m.id) && m.name.toLowerCase() === d.name.toLowerCase()) ??
      family.members.find((m) => !used.has(m.id) && roles.includes(m.relation));
    if (match) {
      ids.set(d.id, match.id);
      used.add(match.id);
    }
  }
  const { out, series } = remapMembers(DEMO_OUTPUT, DEMO_CLAIMS, (id) => ids.get(id) ?? id);
  return toRecommendation(out, series);
}

/** Look up a demo pick by product name, for the mock explainer. */
export function demoPick(product: string) {
  return [...DEMO_OUTPUT.picks, DEMO_USUAL].find((p) => p.product === product)!;
}
