import type { FamilyProfile } from "./types";

/** What the optimiser still needs before it can run. */
export function missingList(family: FamilyProfile): string[] {
  const out: string[] = [];
  if (family.members.length === 0) out.push("Who to cover");
  for (const m of family.members) if (m.age === undefined) out.push(`${m.name}'s age`);
  if (!family.healthChecked) out.push("Health conditions");
  if (!family.city) out.push("City");
  if (!family.budget) out.push("Yearly budget");
  if (!family.coverChecked) out.push("Cover you want");
  if (!family.officeChecked) out.push("Office cover");
  return out;
}

/** The board's verify button. Tapping it starts the search. */
export const VERIFIED = "I have verified all my information";
