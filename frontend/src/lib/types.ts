// Shapes the UI expects from the backend. Proposal lives in docs/api-contract.md
// until both developers agree to move it into shared/.

export type Stage = "talk" | "fine_print" | "optimise" | "explain";

export type Member = {
  id: string;
  name: string;
  relation?: string;
  age?: number;
  conditions: string[];
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
  /** Total cover the family wants, summed over every policy in the mix. Unset lets the solver choose. */
  coverTarget?: number;
  /** True once the user has given a cover amount or said they are not sure. */
  coverChecked?: boolean;
  /** Rules the user set for the plans. The solver keeps every one. */
  requirements?: Requirements;
};

/** What the user asked of the plans beyond the budget and total cover. Fields follow shared/README.md. */
export type Requirements = {
  /** Member id to the least cover in rupees for that person. */
  minCover?: Record<string, number>;
  /** Member id to the most months before that person's existing conditions are covered. */
  maxWaitMonths?: Record<string, number>;
  /** 0 means no co-pay. */
  maxCopayPercent?: number | null;
  uncappedRoomRent?: boolean;
  avoidInsurers?: string[];
  oneInsurer?: boolean;
  /** Policy ids to leave out. */
  avoidPolicies?: string[];
  avoidPlanTypes?: PolicyKind[];
  maxPolicies?: number | null;
};

/** A change the solver has priced. Nothing changes until the user taps "Update my mix". */
export type Proposal = {
  /** The family with the change made, rules included. */
  family: FamilyProfile;
  /** False while a detail is still needed, like a new person's age. No price yet then. */
  ready: boolean;
  changes: string[];
  premium?: number;
  premiumChange?: number;
  /** Set when a cover target is short: the budget that reaches it. */
  raiseBudgetTo?: number | null;
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
  /** Language Sarvam detected for a spoken message, e.g. "hi-IN". The reply should use it. */
  language?: string;
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
  /** Set on a change request after the mix is shown. Null when the change could not be priced. */
  proposal?: Proposal | null;
  /** True when the request was passed to an insurance expert. */
  expertRequested?: boolean;
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

/** cover_short: the budget cannot buy the cover asked for. cover_out_of_reach: no mix reaches it at any price. */
export type CoverCheck = {
  code: "cover_met" | "cover_short" | "cover_out_of_reach";
  target: number;
  totalCover: number;
  shortfall?: number;
  /** Lowest yearly premium for a mix that reaches the target. Null when none does. */
  budgetNeeded?: number | null;
  text: string;
};

export type Recommendation = {
  id: string;
  /** Null when no single floater can take the whole family, e.g. a parent past its entry age. */
  usual: PlanOption | null;
  mix: PlanOption;
  /** Null when there is no usual pick. */
  saving: number | null;
  /** Facts comparing the mix with the usual pick, in plain sentences. */
  vsUsual: { code: string; text: string }[];
  /** Catches that come from how the policies stack, most serious first, from the solver. */
  mixCatches: MixCatch[];
  /** Whether the mix reaches the cover the family asked for. Null when they gave no amount. */
  coverCheck: CoverCheck | null;
  /** Most each member can claim in a year, from the solver. */
  memberCover: Record<string, number>;
  claimScenarios: ClaimScenario[];
};

export type MixCatch = { code: string; text: string; memberIds: string[] };

/** Short summary at the top of the results. `source` is "solver" when Sarvam's text was not usable. */
export type MixSummary = { why: string; watch: string[]; source: "llm" | "solver" };

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  via?: "voice" | "text";
  /** Language Sarvam detected for a voice message, e.g. "hi-IN". */
  language?: string;
  citations?: string[];
};
