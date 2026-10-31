// Stand-in for the backend's /chat while it is being built. It pulls family
// details out of a message with simple patterns and asks for what is missing.
// The real extraction and replies come from the backend LLM.

import type { ChatRequest, ChatResponse, FamilyProfile, Member } from "../types";
import { cover, rupees } from "../format";
import { DEMO_FAMILY, DEMO_RECOMMENDATION } from "./demo";
import { missingList } from "../family";

type Ask = "members" | "age" | "health" | "city" | "budget" | "office" | "ready" | "explain";

const RELATIONS: [RegExp, string][] = [
  [/\b(father[- ]in[- ]law|sasur(?:ji)?)\b|ससुर/i, "father-in-law"],
  [/\b(mother[- ]in[- ]law|saas(?:u)?(?:ji)?)\b|सास/i, "mother-in-law"],
  [/\b(i am|i'm|im|myself)\b|मैं/i, "self"],
  [/\b(wife|patni)\b|पत्नी/i, "wife"],
  [/\b(husband|pati)\b|पति/i, "husband"],
  [/\b(son|beta)\b|बेटा/i, "son"],
  [/\b(daughter|beti)\b|बेटी/i, "daughter"],
  [/\b(father|dad|papa|pitaji)\b|पापा|पिताजी/i, "father"],
  [/\b(mother|mom|mum|mummy|maa|mataji)\b|माँ|मां|मम्मी/i, "mother"],
];

const CONDITIONS: [RegExp, string][] = [
  [/diabet|\bsugar\b|शुगर|मधुमेह/i, "diabetes"],
  [/\bbp\b|blood pressure|hypertension|बीपी/i, "high BP"],
  [/heart|cardiac|दिल/i, "heart condition"],
  [/thyroid/i, "thyroid"],
  [/asthma/i, "asthma"],
];

const CITIES = [
  "Pune", "Mumbai", "Delhi", "Bengaluru", "Bangalore", "Chennai", "Hyderabad",
  "Kolkata", "Ahmedabad", "Jaipur", "Lucknow", "Noida", "Gurugram", "Nagpur", "Indore",
];

const NOT_NAMES = new Set([
  "I", "I'm", "Im", "My", "Our", "We", "The", "He", "She", "His", "Her", "And", "Is", "Are",
  "No", "Yes", "None", "Budget", "About", "Around", "Office", "Company", "Hi", "Hello",
  "Also", "Both", "Use", "Find", "Father", "Mother", "Wife", "Son", "Daughter", "Husband",
  "Papa", "Mummy", "Dad", "Mom", "Lakh", "Rs", "Diabetic", "Diabetes", "Sugar", "BP",
  "Mere", "Meri", "Mera", "Hamare", "Hamari", "Hum", "Main", "Aur", "Woh", "Unki", "Unke", "Unko", "Saal",
  ...CITIES,
]);

const NO = /^\s*(no|none|nope|nahi|nahin|nobody|no one|koi nahi|नहीं|कोई नहीं)\b/i;

const SELF_NAME = "You";

function titleCase(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function parseAmount(text: string): number | undefined {
  const m = text.match(/(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|l\b|k\b|thousand|crores?|cr\b)?/i);
  if (!m) return undefined;
  const n = parseFloat(m[1].replace(/,/g, ""));
  const unit = (m[2] ?? "").toLowerCase();
  const mult = unit.startsWith("l") ? 1_00_000 : unit.startsWith("k") || unit.startsWith("t") ? 1_000 : unit.startsWith("c") ? 1_00_00_000 : 1;
  if (mult === 1 && n < 1_000) return undefined;
  return Math.round(n * mult);
}

function findAge(clause: string): number | undefined {
  const m = clause.match(/\b(\d{1,2})(?!\d|[.,]\d)(?!\s*(?:lakhs?|lacs?|l\b|k\b|thousand|%|crores?))/i);
  if (!m) return undefined;
  const n = Number(m[1]);
  return n > 0 && n < 100 ? n : undefined;
}

function findName(clause: string): string | undefined {
  for (const m of clause.matchAll(/\b([A-Z][a-z]{2,})\b/g)) {
    if (!NOT_NAMES.has(m[1])) return m[1];
  }
  return undefined;
}

function cloneFamily(f: FamilyProfile): FamilyProfile {
  return { ...f, members: f.members.map((m) => ({ ...m, conditions: [...m.conditions] })) };
}

/** Apply one message to the family profile. Returns short notes on what changed. */
export function extract(message: string, family: FamilyProfile, lastAsk: Ask): string[] {
  const notes: string[] = [];
  const heard = new Map<Member, string[]>();

  if (lastAsk === "health" && NO.test(message)) {
    family.healthChecked = true;
    notes.push("no other health conditions");
  }
  if (/\b(no|not any|don'?t have)\b.*\b(office|company|corporate|employer)\b/i.test(message) ||
      (lastAsk === "office" && NO.test(message))) {
    family.officeChecked = true;
    notes.push("no office cover");
  }

  const city = CITIES.find((c) => new RegExp(`\\b${c}\\b`, "i").test(message));
  if (city) {
    family.city = city === "Bangalore" ? "Bengaluru" : city;
    notes.push(family.city);
  }

  let last: Member | undefined;
  const clauses = message.split(/[.?!](?=\s|$)|(?<!\d),(?!\d)|[;\n]|\band\b|\baur\b|और/i).map((c) => c.trim()).filter(Boolean);

  for (const clause of clauses) {
    const amount = parseAmount(clause);
    const isOffice = /office|company|corporate|employer|work/i.test(clause);
    const isBudget = /budget|afford|spend|per year|a year|yearly|annual|saal ka/i.test(clause) ||
      (lastAsk === "budget" && !isOffice);

    if (amount && isOffice && !/\bno\b/i.test(clause)) {
      const self = family.members.find((m) => m.relation === "self");
      family.officeCover = { amount, memberIds: self ? [self.id] : [] };
      family.officeChecked = true;
      notes.push(`${cover(amount)} office cover`);
      continue;
    }
    if (amount && isBudget) {
      family.budget = amount;
      notes.push(`budget ${rupees(amount)} a year`);
      continue;
    }

    const relation = RELATIONS.find(([re]) => re.test(clause))?.[1];
    const name = findName(clause);
    const age = findAge(clause);
    const conditions = CONDITIONS.filter(([re]) => re.test(clause)).map(([, c]) => c);

    let member: Member | undefined;
    if (name) member = family.members.find((m) => m.name.toLowerCase() === name.toLowerCase());
    if (!member && relation) {
      member = family.members.find(
        (m) => m.relation === relation && (!name || m.name === SELF_NAME || m.name === titleCase(relation)),
      );
    }
    if (!member && (name || relation)) {
      member = {
        id: `m${family.members.length + 1}-${Date.now().toString(36)}`,
        name: name ?? (relation === "self" ? SELF_NAME : titleCase(relation!)),
        relation,
        conditions: [],
      };
      family.members.push(member);
    }
    if (!member && (age !== undefined || conditions.length)) {
      member = last ?? family.members.find((m) => m.age === undefined);
    }
    if (!member) continue;

    if (name && (member.name === SELF_NAME || member.name === titleCase(member.relation ?? ""))) member.name = name;
    if (relation && !member.relation) member.relation = relation;
    if (age !== undefined && !(isOffice || isBudget)) member.age = age;
    for (const c of conditions) if (!member.conditions.includes(c)) member.conditions.push(c);
    if (conditions.length && lastAsk === "health") family.healthChecked = true;

    heard.set(member, [...(heard.get(member) ?? []), clause]);
    member.heardFrom = heard.get(member)!.join(", ");
    last = member;
  }

  for (const m of heard.keys()) {
    const bits = [m.name, m.age !== undefined ? `${m.age}` : null, ...m.conditions].filter(Boolean);
    notes.push(bits.join(", "));
  }
  return notes;
}

function nextAsk(family: FamilyProfile): Ask {
  if (family.members.length === 0) return "members";
  if (family.members.some((m) => m.age === undefined)) return "age";
  if (!family.healthChecked) return "health";
  if (!family.city) return "city";
  if (!family.budget) return "budget";
  if (!family.officeChecked) return "office";
  return "ready";
}

function question(ask: Ask, family: FamilyProfile): { text: string; quickReplies: string[] } {
  switch (ask) {
    case "members":
      return {
        text: "Who should the plan cover? Tell me each person's name, age and how they're related to you.",
        quickReplies: ["Use the demo family"],
      };
    case "age": {
      const m = family.members.find((x) => x.age === undefined)!;
      return { text: `How old is ${m.name === SELF_NAME ? "you" : m.name}?`, quickReplies: [] };
    }
    case "health": {
      const any = family.members.some((m) => m.conditions.length);
      return {
        text: any
          ? "Does anyone else have a health condition, like diabetes, BP or a heart problem?"
          : "Does anyone have a health condition, like diabetes, BP or a heart problem?",
        quickReplies: any ? ["No one else"] : ["None", "Father has diabetes"],
      };
    }
    case "city":
      return { text: "Which city do you live in? Hospital costs differ by city.", quickReplies: ["Pune", "Mumbai", "Bengaluru"] };
    case "budget":
      return {
        text: "Roughly how much can you spend on premiums each year?",
        quickReplies: ["About ₹1 lakh a year", "About ₹1.5 lakh a year"],
      };
    case "office":
      return {
        text: "Does anyone get health cover from their office? If yes, how much?",
        quickReplies: ["No office cover", "₹5 lakh from my office"],
      };
    case "ready":
      return {
        text: "That's everything I need. Check the family board, fix anything I got wrong, then find your mix.",
        quickReplies: ["Find my mix"],
      };
    case "explain":
      return { text: "", quickReplies: [] };
  }
}

function explain(message: string): Pick<ChatResponse, "reply" | "citations"> {
  const r = DEMO_RECOMMENDATION;
  const q = message.toLowerCase();
  if (/one floater|single|usual|why not/.test(q)) {
    return {
      reply: `One ₹25L floater puts all five people on one shared limit. It also makes Mohan wait 3 years for diabetes cover. The mix gives the parents their own plans, so Mohan waits 1 year, and the family gets ${cover(r.mix.totalCover)} of cover.`,
      citations: ["c-floater-usual", "c-ped-usual", "c-ped-senior"],
    };
  }
  if (/top.?up|deductible/.test(q)) {
    return {
      reply: "A super top-up pays only after the year's hospital bills cross ₹10L. Your base plans cover the first ₹10L, so the top-up is cheap and still gives you room for a very large claim.",
      citations: ["c-topup-deductible"],
    };
  }
  if (/catch|downside|problem|risk/.test(q)) {
    return {
      reply: "Three catches to know. The young family's ₹10L is shared by all three. Mohan's room rent is capped at ₹10,000 a day. Lata waits 2 years for knee or cataract surgery.",
      citations: ["c-floater-shared", "c-room-senior", "c-specific-wait"],
    };
  }
  if (/diabet|wait|mohan/.test(q)) {
    return {
      reply: "Mohan's senior plan covers his diabetes after 1 year. On the usual floater he would wait 3 years. Move the year slider in the claim check to see the difference.",
      citations: ["c-ped-senior", "c-ped-usual"],
    };
  }
  if (/room/.test(q)) {
    return { reply: "Mohan's senior plan pays room rent up to ₹10,000 a day. A costlier room cuts the payout on related charges too.", citations: ["c-room-senior"] };
  }
  if (/lata|knee|cataract/.test(q)) {
    return {
      reply: "Lata has no health conditions, so a standard individual plan costs less than a senior plan. Knee and cataract surgery are covered after 2 years.",
      citations: ["c-specific-wait"],
    };
  }
  if (/cost|price|premium|cheap|save/.test(q)) {
    return {
      reply: `The mix costs ${rupees(r.mix.premium)} a year, against ${rupees(r.usual.premium)} for the usual pick. These premiums are illustrative.`,
    };
  }
  return {
    reply: "I can explain any pick, its catches, or what a claim would cost. Try asking why Mohan has his own plan.",
  };
}

export function createMockChat() {
  let lastAsk: Ask = "members";

  return async function chat(req: ChatRequest): Promise<ChatResponse> {
    await new Promise((r) => setTimeout(r, 450));

    if (req.recommendationId) {
      return {
        ...explain(req.message),
        family: req.family,
        missing: [],
        quickReplies: ["Why not one floater?", "What is a super top-up?", "What are the catches?"],
        readyToOptimise: true,
      };
    }

    let family = cloneFamily(req.family);
    let notes: string[];
    if (/demo family/i.test(req.message)) {
      family = cloneFamily(DEMO_FAMILY);
      notes = ["the Pune demo family"];
    } else {
      notes = extract(req.message, family, lastAsk);
    }

    lastAsk = nextAsk(family);
    const q = question(lastAsk, family);
    const heard = notes.length ? `Noted: ${notes.join("; ")}. ` : "";
    const fallback = notes.length ? "" : "I didn't catch any family details there. ";

    return {
      reply: `${heard}${fallback}${q.text}`,
      family,
      missing: missingList(family),
      quickReplies: q.quickReplies,
      readyToOptimise: lastAsk === "ready",
    };
  };
}
