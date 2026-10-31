// Shapes the UI expects from the backend. Proposal lives in docs/api-contract.md
// until both developers agree to move it into shared/.

export type Stage = "talk" | "fine_print" | "optimise" | "explain";

export type Member = {
  id: string;
  name: string;
  relation?: string;
  age?: number;
  conditions: string[];
  /** Least cover the user asked for this member, in rupees. The solver must meet it. */
  minCover?: number;
  /** The words this member's details were heard from, shown so the user can check them. */
  heardFrom?: string;
};

export type OfficeCover = {
  amount: number;
  memberIds: string[];
};

export type FamilyProfile = {
  members: Member[];
  city?: string;
  /** Yearly premium budget in rupees. */
  budget?: number;
  officeCover?: OfficeCover;
  /** True once the user has answered the health question for everyone. */
  healthChecked: boolean;
  /** True once the user has said whether anyone has office cover. */
  officeChecked: boolean;
};

export type ChatTurn = {
  role: "user" | "assistant";
  text: string;
};

export type ChatRequest = {
  sessionId: string;
  message: string;
  family: FamilyProfile;
  history: ChatTurn[];
  /** Set after a recommendation exists, so follow-up questions are answered from it. */
  recommendationId?: string;
};

export type ChatResponse = {
  reply: string;
  family: FamilyProfile;
  /** Short labels for what is still needed, e.g. "Lata's age". */
  missing: string[];
  quickReplies: string[];
  readyToOptimise: boolean;
  /** Policy ids the reply relies on. The UI shows them as tappable fine-print chips. */
  citations?: string[];
  /** A quoted change to the mix, e.g. more cover for one member. Re-run the solver on this family if the user agrees. */
  proposal?: { family: FamilyProfile; premium: number };
};

export type PolicyKind = "floater" | "individual" | "senior" | "super_topup";

export type Policy = {
  id: string;
  product: string;
  insurer: string;
  kind: PolicyKind;
  memberIds: string[];
  sumInsured: number;
  /** 0 except for super top-ups. */
  deductible: number;
  premium: number;
  copayPercent: number;
  waitsMonths: { initial: number; specificIllness: number; preExisting: number };
  catches: string[];
  /** Why the solver made this pick, in plain sentences. */
  reasons: string[];
  /** What the solver would pick without this one, and what changes. */
  nextBest?: string;
  sourceUrl?: string;
};

export type PlanOption = {
  label: string;
  premium: number;
  totalCover: number;
  policies: Policy[];
};

export type ClaimOutcome = {
  covered: boolean;
  payable: number;
  outOfPocket: number;
  coveredFromYear: number;
  notes: string[];
};

export type ClaimScenario = {
  id: string;
  memberId: string;
  label: string;
  amount: number;
  /** Solver result for each policy year, year 1 first. */
  byYear: { year: number; usual: ClaimOutcome; mix: ClaimOutcome }[];
};

export type Recommendation = {
  id: string;
  /** Premiums are illustrative in the prototype. The UI labels them wherever shown. */
  illustrative: boolean;
  /** Null when no single floater can take the whole family, e.g. a parent past its entry age. */
  usual: PlanOption | null;
  mix: PlanOption;
  /** Null when there is no usual pick. */
  saving: number | null;
  /** Facts comparing the mix with the usual pick, in plain sentences. */
  vsUsual: { code: string; text: string }[];
  /** Most each member can claim in a year, from the solver. */
  memberCover: Record<string, number>;
  claimScenarios: ClaimScenario[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  via?: "voice" | "text";
  /** Language Sarvam detected for a voice message, e.g. "hi-IN". */
  language?: string;
  citations?: string[];
};
