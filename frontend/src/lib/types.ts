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
  /** Clause ids the reply relies on. The UI shows them as tappable chips. */
  citations?: string[];
};

export type PolicyKind = "floater" | "individual" | "senior" | "super_top_up";

export type Clause = {
  id: string;
  title: string;
  text: string;
  source: string;
};

export type Policy = {
  id: string;
  planName: string;
  insurer: string;
  kind: PolicyKind;
  memberIds: string[];
  sumInsured: number;
  deductible?: number;
  premium: number;
  why: string;
  catches: string[];
  clauseIds: string[];
};

export type PlanOption = {
  label: string;
  premium: number;
  totalCover: number;
  policies: Policy[];
  highlights: string[];
};

export type ClaimOutcome = {
  covered: boolean;
  paidBy: { policyId: string; amount: number }[];
  outOfPocket: number;
  reason: string;
  clauseId?: string;
};

export type ClaimScenario = {
  id: string;
  memberId: string;
  label: string;
  amount: number;
  /** Outcome for each policy year, year 1 first. */
  byYear: { year: number; usual: ClaimOutcome; mix: ClaimOutcome }[];
};

export type Recommendation = {
  id: string;
  /** Premiums are illustrative in the prototype. The UI labels them wherever shown. */
  illustrative: boolean;
  usual: PlanOption;
  mix: PlanOption;
  clauses: Record<string, Clause>;
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
