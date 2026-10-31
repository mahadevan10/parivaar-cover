"""HTTP API for the frontend. Run from backend/: .venv/bin/uvicorn app:app --reload --port 8000

POST /recommend runs the solver and the claim checks. POST /chat talks to the user through
Sarvam: before a recommendation it collects the family details, after one it explains the
solver's reasons. The LLM never picks policies or quotes prices.
"""
import json
import re
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

import llm
import solver
import store

app = FastAPI(title="Parivaar Cover")
# The frontend on this machine, or on a phone or laptop on the same Wi-Fi for the demo
app.add_middleware(CORSMiddleware,
                   allow_origin_regex=r"http://(localhost|127\.0\.0\.1|10(\.\d+){3}|192\.168(\.\d+){2}"
                                      r"|172\.(1[6-9]|2\d|3[01])(\.\d+){2}):3000",
                   allow_methods=["*"], allow_headers=["*"])

POLICIES = solver.load_policies()
CLAIM_YEARS = range(1, 5)

CONDITION_NAMES = {
    "diabetes": ["diabetes", "diabetic", "sugar", "blood sugar", "type 2 diabetes", "type 1 diabetes"],
    "hypertension": ["hypertension", "bp", "high bp", "blood pressure", "high blood pressure"],
    "asthma": ["asthma", "asthmatic"],
    "heart_disease": ["heart_disease", "heart disease", "heart problem", "cardiac"],
}
CONDITION_TREATMENT = {"diabetes": "cardiac", "hypertension": "cardiac", "heart_disease": "cardiac"}


# Request shapes. They follow shared/families.json, so the solver reads them as they are.

class Member(BaseModel):
    id: str
    name: str
    age: int = Field(ge=0, le=120)
    relation: str | None = None
    conditions: list[str] = []


class OfficeCover(BaseModel):
    members: list[str]
    sum_insured: int = Field(gt=0)


class Family(BaseModel):
    id: str = "web"
    city: str | None = None
    budget: int = Field(gt=0)
    # Total cover the family wants, summed over every policy in the mix. None lets the solver choose.
    cover_target: int | None = Field(None, gt=0)
    members: list[Member] = Field(min_length=1)
    office_cover: list[OfficeCover] = []


# The family while the user is still talking. Same format with every detail optional, plus what the chat
# needs. Checked before it is stored, and turned into a Family once nothing is missing.

class DraftMember(BaseModel):
    id: str
    name: str
    age: int | None = Field(None, ge=0, le=120)
    relation: str | None = None
    conditions: list[str] = []
    heard_from: str | None = None


class FamilyDraft(BaseModel):
    id: str = "web"
    city: str | None = None
    budget: int | None = Field(None, gt=0)
    cover_target: int | None = Field(None, gt=0)
    members: list[DraftMember] = []
    office_cover: list[OfficeCover] = []
    health_checked: bool = False
    office_checked: bool = False
    cover_checked: bool = False


class Claim(BaseModel):
    id: str | None = None
    label: str | None = None
    member_id: str
    amount: int = Field(gt=0)
    related_condition: str | None = None
    treatment: str | None = None


class RecommendRequest(BaseModel):
    family: Family
    claims: list[Claim] | None = None


# /chat uses the frontend's camelCase shapes (frontend/docs/api-contract.md)

class ChatTurn(BaseModel):
    role: str
    text: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    session_id: str | None = None
    message: str
    family: dict = {}  # the UI's FamilyProfile, partial while the user is still talking
    history: list[ChatTurn] = []
    recommendation_id: str | None = None


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/recommend")
def recommend(req: RecommendRequest):
    family = req.family.model_dump()
    ids = {m["id"] for m in family["members"]}
    for claim in req.claims or []:
        if claim.member_id not in ids:
            raise HTTPException(422, f"Unknown member in claims: {claim.member_id}")

    solution = solver.solve(family, POLICIES)
    solution["id"] = "rec-" + uuid.uuid4().hex[:8]
    claim_checks = []
    if solution["status"] == "ok":
        claims = [c.model_dump() for c in req.claims] if req.claims is not None else default_claims(family)
        claim_checks = [claim_by_year(family, solution, c) for c in claims]
    rec = {"id": solution["id"], "solution": solution, "claim_checks": claim_checks}
    # The frontend builds its own id this way (toRecommendation in frontend/src/lib/solver.ts)
    alias = f"{solution['family_id']}-{solution['total_premium']}" if solution["status"] == "ok" else None
    store.save_recommendation(rec, req.family, alias)
    return rec


def default_claims(family):
    """The deck's ₹6L heart claim for each member with a known condition, and one large claim
    for the first member, so the claim check shows what the top-ups are for."""
    claims = []
    for m in family["members"]:
        if m["conditions"]:
            condition = m["conditions"][0]
            treatment = CONDITION_TREATMENT.get(condition)
            claims.append({"id": f"{m['id']}-{treatment or 'hospital'}", "member_id": m["id"], "amount": 600_000,
                           "label": "Heart procedure" if treatment else "Hospital stay",
                           "related_condition": condition, "treatment": treatment})
    first = family["members"][0]["id"]
    claims.append({"id": f"{first}-cancer", "member_id": first, "amount": 3_000_000,
                   "label": "Cancer treatment", "related_condition": None, "treatment": None})
    return claims


def claim_by_year(family, solution, claim):
    by_year = []
    for year in CLAIM_YEARS:
        args = (claim["member_id"], claim["amount"], year, claim["related_condition"], claim["treatment"])
        usual = solution["usual_pick"]
        by_year.append({
            "policy_year": year,
            "mix": solver.claim_check(family, solution["picks"], *args),
            "usual": solver.claim_check(family, [usual], *args) if usual else None,
        })
    claim = dict(claim, by_year=by_year)
    claim["id"] = claim["id"] or f"{claim['member_id']}-{claim['amount']}"
    claim["label"] = claim["label"] or "Hospital stay"
    return claim


# Chat

STYLE = ("Write plain, short sentences in sentence case. Do not use em or en dashes. "
         "Do not use hype words. Reply in the language the user writes in. "
         "Write money with the rupee sign and Indian grouping, like ₹1,10,000.")

INTAKE_PROMPT = """You help one person insure their family's health. Collect the family's details.

You never pick policies, name insurers or quote prices. A solver does that after you have the details.

Current family, as JSON:
{family}

Still missing before the solver can run: {missing}

Apply what the user just said to the family and return the whole family again. In your reply, say in
one short sentence what you noted. Do not ask for the next detail, the app does that. Only ask a
question if something the user said is unclear, such as who a condition belongs to.

Return only a JSON object:
{{"reply": "what you say to the user",
  "family": {{"city": str or null, "budget": yearly rupees as an integer or null,
             "cover_target": total cover in rupees the user wants to buy for the whole family, or null,
             "members": [{{"name": str, "age": int or null, "relation": str,
                          "conditions": [only conditions the user said this person has, in lowercase]}}],
             "office_cover": [{{"members": [member ids], "sum_insured": rupees as an integer}}],
             "health_checked": true once the user has said who has health conditions,
             "office_checked": true once the user has said whether anyone has office cover,
             "cover_checked": true once the user has said how much cover they want or that they are not sure}}}}

Only record what the user actually said. Never guess an age or a health condition. If the user has
not mentioned a condition for someone, their conditions list is empty.
Convert lakh and crore amounts to rupees: 1.1 lakh is 110000 and 1 crore is 10000000.
Office cover is cover the user already has. cover_target is the new cover they want, so keep them apart.
The user is "self". Use relations like spouse, son, daughter, father, mother.
""" + STYLE

EXPLAIN_PROMPT = """You explain a health insurance recommendation to the person who asked for it.

The solver chose the policies and worked out every number and reason below. Answer only from these
facts. Never change a premium, add a reason or suggest a different policy. If the facts do not answer
the question, say so. Mention catches such as co-pay, waits and sub-limits when they matter.
Policy year 1 is the first year after buying, so "next year" is year 2.

Facts, as JSON:
{facts}

Return only a JSON object:
{{"reply": "your answer", "citations": [policy ids from the facts that your answer relies on]}}
""" + STYLE

SUMMARY_PROMPT = """You write a short summary of a health insurance recommendation. It sits at the top of the results.

The solver chose the policies and worked out every fact below. Use only these facts. Never add a number,
a reason or a policy that is not in them.

Facts, as JSON:
{facts}

Return only a JSON object:
{{"why": "2 or 3 sentences on why this mix suits the family, compared with the usual single floater if there is one",
  "watch": ["one line for each entry in watch_these, in the same order"]}}

In why, use at most 60 words. Cover the yearly cost, the cover each person gets, and when existing illnesses are covered.
Each line in watch is one sentence of at most 20 words. Keep the person's name and the key number or year.
Copy every amount exactly as the facts write it.
Use names, never he, she, his or her.
""" + STYLE


@app.post("/chat")
def chat(req: ChatRequest):
    history = [{"role": t.role, "content": t.text} for t in req.history] + [{"role": "user", "content": req.message}]
    if req.recommendation_id:
        rec = store.recommendation(req.recommendation_id)
        if rec is None:
            raise HTTPException(404, "Recommendation not found. Run /recommend again.")
        out = call_llm(EXPLAIN_PROMPT.format(facts=json.dumps(explain_facts(rec), ensure_ascii=False)), history)
        solution = rec["solution"]
        known = {p["policy_id"] for p in solution.get("picks", [])}
        if solution.get("usual_pick"):
            known.add(solution["usual_pick"]["policy_id"])
        reply = tidy(out.get("reply", ""))
        remember(req.session_id, req.message, reply)
        return {"reply": reply, "family": req.family, "missing": [], "quickReplies": [],
                "readyToOptimise": True, "citations": list(dict.fromkeys(c for c in out.get("citations", []) if c in known))}

    before = from_profile(req.family)
    family = clean_family(before, before)
    out = call_llm(INTAKE_PROMPT.format(family=json.dumps(family, ensure_ascii=False),
                                        missing=", ".join(missing_details(family)) or "nothing"), history)
    new = dict(out.get("family") or {})
    # ids come from names, so the LLM cannot rename a member
    new["members"] = [{k: v for k, v in m.items() if k != "id"} for m in new.get("members") or []]
    # The check runs on English, so values said in Malayalam or Hindi are not thrown away
    english = [dict(t, content=llm.to_english(t["content"])) if t["role"] == "user" else t for t in history]
    family = grounded(clean_family(new, family), family, english)
    if req.message.strip().lower() == COVER_NOT_SURE.lower():
        family["cover_checked"], family["cover_target"] = True, None
    missing = missing_details(family)
    reply = tidy(out.get("reply", ""))
    reply = proper_case(reply, [m["name"] for m in family["members"]] + [family["city"] or ""])
    if "?" not in reply:
        reply = f"{reply} {next_question(missing[0]) if missing else 'I have everything I need to find your options.'}"
    for m in family["members"]:
        old = next((o for o in before.get("members", []) if o.get("id") == m["id"]), None)
        if old is None or any(old.get(k) != m[k] for k in ("age", "relation", "conditions")):
            m["heard_from"] = req.message
    if req.session_id:
        family["id"] = req.session_id
        store.save_family(req.session_id, FamilyDraft.model_validate(family), missing)
    remember(req.session_id, req.message, reply, english[-1]["content"])
    return {"reply": reply, "family": to_profile(family), "missing": missing,
            "quickReplies": quick_replies(family, missing), "readyToOptimise": not missing}


def remember(session_id, message, reply, english=None):
    """Stores both sides of a chat turn. Turns without a session id are not stored."""
    if session_id:
        store.add_message(session_id, "user", message, english)
        store.add_message(session_id, "assistant", reply)


def from_profile(p):
    """The UI's camelCase FamilyProfile in the shared snake_case format."""
    office = p.get("officeCover")
    return {
        "city": p.get("city"), "budget": p.get("budget"),
        "members": [{"id": m.get("id"), "name": m.get("name"), "age": m.get("age"), "relation": m.get("relation"),
                     "conditions": m.get("conditions") or [], "heard_from": m.get("heardFrom")}
                    for m in p.get("members") or []],
        "office_cover": [{"members": office.get("memberIds") or [], "sum_insured": office.get("amount")}] if office else [],
        "health_checked": p.get("healthChecked", False), "office_checked": p.get("officeChecked", False),
        "cover_target": p.get("coverTarget"), "cover_checked": p.get("coverChecked", False),
    }


def to_profile(f):
    office = f["office_cover"][0] if f["office_cover"] else None
    profile = {
        "members": [{"id": m["id"], "name": m["name"], "relation": m["relation"], "age": m["age"],
                     "conditions": m["conditions"], "heardFrom": m.get("heard_from")} for m in f["members"]],
        "city": f["city"], "budget": f["budget"],
        "healthChecked": f["health_checked"], "officeChecked": f["office_checked"],
        "coverTarget": f["cover_target"], "coverChecked": f["cover_checked"],
    }
    if office:
        profile["officeCover"] = {"amount": office["sum_insured"], "memberIds": office["members"]}
    return profile


def quick_replies(family, missing):
    if not missing:
        return []
    if missing[0] == "Health conditions":
        anyone = any(m["conditions"] for m in family["members"])
        return ["No one else has one" if anyone else "No one has a condition"]
    if missing[0] == "Office cover":
        return ["No office cover"]
    if missing[0] == "Cover you want":
        return [COVER_NOT_SURE]
    return []


COVER_NOT_SURE = "Not sure"


NEXT_QUESTION = {
    "Who is in the family": "Who would you like to insure? Tell me each person's name and age.",
    "Health conditions": "Does anyone have a health condition, like diabetes or high blood pressure?",
    "Office cover": "Does anyone get health cover from their office? If yes, how much?",
    "City": "Which city do you live in?",
    "Yearly budget": "How much can you spend on premiums each year?",
    "Cover you want": "How much total cover would you like for the family? For example, ₹1 crore.",
}


def next_question(label):
    if label.endswith("'s age"):
        return "How old is " + label.removesuffix("'s age") + "?"
    return NEXT_QUESTION[label]


def tidy(text):
    """Capital letter at the start of every sentence."""
    return re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), str(text).strip())


def call_llm(system, history):
    try:
        return llm.ask_json(system, history)
    except Exception as e:  # Sarvam down, bad key or unreadable JSON
        raise HTTPException(502, f"The assistant could not answer: {e}") from e


def explain_facts(rec):
    """The parts of a recommendation the explainer may use."""
    claim_checks, rec = rec["claim_checks"], rec["solution"]
    if rec["status"] != "ok":
        return {"status": rec["status"], "budget": rec["budget"], "message": rec["message"]}
    keep = ("policy_id", "insurer", "product", "plan_type", "members", "sum_insured", "deductible",
            "premium", "copay_percent", "catches", "reasons")
    usual = rec["usual_pick"]
    return {
        "budget": rec["budget"], "total_premium": rec["total_premium"], "total_cover": rec["total_cover"],
        "cover_target": rec.get("cover_target"), "cover_check": rec.get("cover_check"),
        "member_cover": rec["member_cover"],
        "picks": [{k: p[k] for k in keep} for p in rec["picks"]],
        "usual_pick": {k: usual[k] for k in keep if k in usual} if usual else None,
        "vs_usual": [r["text"] for r in rec["vs_usual"]],
        "mix_catches": [c["text"] for c in rec.get("mix_catches", [])],
        "claim_checks": [{"label": c["label"], "member_id": c["member_id"], "amount": c["amount"], "by_year": [
            {"policy_year": y["policy_year"], "mix": y["mix"], "usual": y["usual"]} for y in c["by_year"]]}
            for c in claim_checks],
    }


# Summary at the top of the results

class SummaryRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    recommendation_id: str


@app.post("/summary")
def summary(req: SummaryRequest):
    """A short why-this-mix and what-to-watch, written by Sarvam from the solver's facts.

    If Sarvam fails or its text has a number the facts do not, the solver's own sentences are
    returned instead (source "solver"). Only Sarvam's text is stored, so a later call can retry.
    """
    rec = store.recommendation(req.recommendation_id)
    if rec is None:
        raise HTTPException(404, "Recommendation not found. Run /recommend again.")
    if rec.get("summary"):
        return rec["summary"]
    if rec["solution"]["status"] != "ok":
        raise HTTPException(422, "No mix to summarise.")
    facts = summary_facts(rec["solution"], store.recommendation_family(rec["id"]))
    try:
        out = llm.ask_json(SUMMARY_PROMPT.format(facts=json.dumps(facts, ensure_ascii=False)),
                           [{"role": "user", "content": "Write the summary."}])
        checked = checked_summary(out, facts)
    except Exception:  # Sarvam down, bad key or unreadable JSON
        checked = None
    if checked is None:
        return fallback_summary(rec["solution"])
    store.save_summary(rec["id"], checked)
    return checked


def summary_facts(solution, family):
    name = {m["id"]: m["name"] for m in family["members"]}
    return {
        # Amounts go in written out, so the model copies them instead of formatting its own
        "yearly_premium": solver.inr(solution["total_premium"]),
        "saving_vs_usual": solver.inr(solution["saving_vs_usual"]) if solution["saving_vs_usual"] else None,
        "members": [{"name": m["name"], "age": m["age"], "conditions": m["conditions"],
                     "most_claimable_a_year": solver.inr(solution["member_cover"][m["id"]])} for m in family["members"]],
        "vs_usual": [r["text"] for r in solution["vs_usual"]],
        "picks": [{"policy": f"{p['insurer']} {p['product']}", "members": [name[mid] for mid in p["members"]],
                   "premium": solver.inr(p["premium"]),
                   "reasons": [r["text"] for r in p.get("reasons", []) if r["code"] != "next_best"]}
                  for p in solution["picks"]],
        "watch_these": [c["text"] for c in solution.get("mix_catches", [])[:3]],
        # cover_check is left out: the results show its sentence as written, above the summary
    }


def fallback_summary(solution):
    why = [r["text"] for r in solution["vs_usual"][:2]] or [r["text"] for r in solution["picks"][0].get("reasons", [])[:1]]
    return {"why": " ".join(why), "watch": [c["text"] for c in solution.get("mix_catches", [])[:3]], "source": "solver"}


RUPEES = re.compile(r"(?:₹|\brs\.?)\s*(\d[\d,]*(?:\.\d+)?)\s*(lakh|crore)?|(\d+(?:\.\d+)?)\s*(lakh|crore)", re.IGNORECASE)
PERCENT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", re.IGNORECASE)
UNIT = {"": 1, "lakh": 100_000, "crore": 10_000_000}
OPENERS = {"a", "an", "the", "this", "that", "these", "each", "both", "neither", "together", "overall", "your",
           "with", "in", "on", "for", "if", "until", "from", "only", "all", "and", "but", "so", "while", "after"}


def rupees_in(text):
    """Every rupee amount in the text, so ₹10 lakh and ₹10,00,000 both read as 1000000."""
    out = set()
    for m in RUPEES.finditer(text):
        number, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        out.add(round(float(number.replace(",", "")) * UNIT[(unit or "").lower()]))
    return out


def numbers_in(value):
    if isinstance(value, bool):
        return set()
    if isinstance(value, int):
        return {value}
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return set().union(*(numbers_in(v) for v in value)) if value else set()
    return set()


def checked_summary(out, facts):
    """Sarvam's summary, tidied, or None when it is the wrong shape or has a number the facts do not."""
    why, watch = out.get("why"), out.get("watch")
    if not isinstance(why, str) or not why.strip() or not isinstance(watch, list):
        return None
    no_dash = lambda t: re.sub(r"\s*[—–]\s*|\s+-\s+", ", ", str(t))
    fix = lambda t: proper_case(tidy(no_dash(t)), [m["name"] for m in facts["members"]] + POLICY_NAMES)
    why, watch = fix(why), list(dict.fromkeys(fix(w) for w in watch if str(w).strip()))[:3]
    if len(why) > 450 or any(len(w) > 220 for w in watch):
        return None
    facts_text = json.dumps(facts, ensure_ascii=False)
    allowed = rupees_in(facts_text) | numbers_in(facts)
    percents = {float(p) for p in PERCENT.findall(facts_text)}
    text = " ".join([why] + watch)
    if not rupees_in(text) <= allowed or not {float(p) for p in PERCENT.findall(text)} <= percents:
        return None
    # A capitalised word the facts do not have is likely a made-up name, like Rachel for Rahul
    known = set(re.findall(r"[a-z]+", (facts_text + SUMMARY_PROMPT).lower())) | OPENERS
    if any(w.lower() not in known for w in re.findall(r"\b[A-Z][A-Za-z]*", text)):
        return None
    return {"why": why, "watch": watch, "source": "llm"}


POLICY_NAMES = sorted({p["insurer"] for p in POLICIES} | {p["product"] for p in POLICIES})


def proper_case(text, words):
    """Puts names back in their own case. Sarvam sometimes writes "sneha" or "manipalcigna"."""
    for word in sorted(filter(None, words), key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(word)}\b", word, text, flags=re.IGNORECASE)
    return text


def condition_name(text):
    text = str(text).strip().lower()
    for name, words in CONDITION_NAMES.items():
        if text in words:
            return name
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def as_int(value):
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None


def clean_family(raw, previous):
    """Puts an LLM or frontend family into the shared format. Keeps ids stable across turns."""
    old_ids = {m.get("name", "").strip().lower(): m["id"]
               for m in previous.get("members", []) if m.get("id")}
    members, seen = [], set()
    for m in raw.get("members") or []:
        name = str(m.get("name") or "").strip()
        name = name.title() if name.islower() else name
        if not name:
            continue
        mid = m.get("id") or old_ids.get(name.lower()) or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        while mid in seen:
            mid += "-2"
        seen.add(mid)
        conditions = []
        for c in m.get("conditions") or []:
            if condition_name(c) and condition_name(c) not in conditions:
                conditions.append(condition_name(c))
        old = next((o for o in previous.get("members", []) if o.get("id") == mid), {})
        age = as_int(m.get("age"))
        members.append({"id": mid, "name": name, "age": age if age is not None and 0 <= age <= 120 else None,
                        "relation": m.get("relation"), "conditions": conditions,
                        "heard_from": m.get("heard_from") or old.get("heard_from")})
    office = []
    for oc in raw.get("office_cover") or []:
        amount, who = as_int(oc.get("sum_insured")), [mid for mid in oc.get("members") or [] if mid in seen]
        if amount and who:
            office.append({"members": who, "sum_insured": amount})
    return {
        "id": raw.get("id") or previous.get("id") or "web",
        # The LLM sometimes leaves out fields it was not asked about, so keep what we had
        "city": raw.get("city") or previous.get("city") or None,
        "budget": next((b for b in (as_int(raw.get("budget")), as_int(previous.get("budget"))) if b and b > 0), None),
        "members": members,
        "office_cover": office,
        "health_checked": bool(raw.get("health_checked") or previous.get("health_checked")),
        "office_checked": bool(raw.get("office_checked") or previous.get("office_checked") or office),
        "cover_target": next((c for c in (as_int(raw.get("cover_target")), as_int(previous.get("cover_target")))
                              if c and c > 0), None),
        "cover_checked": bool(raw.get("cover_checked") or previous.get("cover_checked")
                              or as_int(raw.get("cover_target"))),
    }


RELATION_WORDS = {
    "self": ["i", "me", "i'm", "myself"],
    "spouse": ["wife", "husband", "spouse"],
    "father": ["father", "dad", "papa", "appa"],
    "mother": ["mother", "mom", "mum", "mummy", "amma", "maa"],
    "son": ["son", "children", "child", "kids"], "daughter": ["daughter", "children", "child", "kids"],
}
# Translated messages often spell numbers out: "my wife is twenty-three"
UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
NUMBER_WORDS = re.compile(rf"\b(?:({'|'.join(TENS)})(?:[\s-]+({'|'.join(UNITS[1:10])}))?|({'|'.join(UNITS)}))\b")


def with_digits(text):
    """Writes number words as digits, so "sixty-four" can be matched against an age of 64."""
    def number(m):
        if m.group(3):
            return str(UNITS.index(m.group(3)))
        return str(20 + 10 * TENS.index(m.group(1)) + (UNITS.index(m.group(2)) if m.group(2) else 0))
    return NUMBER_WORDS.sub(number, text)


OFFICE_WORDS = ["office", "company", "employer", "corporate", "work", "job", "group"]


def has_word(text, word):
    return re.search(rf"\b{re.escape(str(word))}\b", text) is not None


def mentions(text, member):
    relation = (member.get("relation") or "").lower()
    words = [member["name"].lower()] + RELATION_WORDS.get(relation, []) + ([relation] if relation and relation != "self" else [])
    return any(has_word(text, w) for w in words)


def passages(history, members):
    """Pieces of what the user said. A sentence naming nobody is read with the question it answers."""
    out, asked = [], ""
    for turn in history:
        text = with_digits(turn["content"].lower())
        if turn["role"] != "user":
            asked = text
        elif any(mentions(text, m) for m in members):
            out += [s for s in re.split(r"[.!?\n]+", text) if s.strip()]
        else:
            out.append(asked + " " + text)
    return out


def grounded(family, previous, history):
    """Drops ages and conditions the user never said about that member, so the LLM cannot invent them."""
    before = {m["id"]: m for m in previous.get("members", [])}
    said = passages(history, family["members"])

    def heard(member, words):
        return any(mentions(p, member) and any(has_word(p, w) for w in words) for p in said)

    for m in family["members"]:
        old = before.get(m["id"], {})
        if m["age"] is not None and m["age"] != old.get("age") and not heard(m, [m["age"]]):
            m["age"] = old.get("age")
        m["conditions"] = [c for c in m["conditions"] if c in old.get("conditions", [])
                           or heard(m, CONDITION_NAMES.get(c, [c.replace("_", " ")]))]
    if family["office_checked"] and not previous.get("office_checked") and not any(
            has_word(t["content"].lower(), w) for t in history if t["role"] == "user" for w in OFFICE_WORDS):
        family["office_checked"], family["office_cover"] = False, []
    return family


def missing_details(family):
    """What the solver still needs, as short labels. Worked out in code, never by the LLM."""
    missing = []
    if not family["members"]:
        missing.append("Who is in the family")
    missing += [f"{m['name']}'s age" for m in family["members"] if m["age"] is None]
    if family["members"] and not family["health_checked"]:
        missing.append("Health conditions")
    if not family["office_checked"]:
        missing.append("Office cover")
    if not family["city"]:
        missing.append("City")
    if not family["budget"]:
        missing.append("Yearly budget")
    if not family["cover_checked"]:
        missing.append("Cover you want")
    return missing
