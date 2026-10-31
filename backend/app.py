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
from pydantic import BaseModel, Field

import llm
import solver

app = FastAPI(title="Parivaar Cover")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])

POLICIES = solver.load_policies()
RECOMMENDATIONS = {}  # id -> /recommend response, kept in memory for follow-up chat
CLAIM_YEARS = range(1, 5)
DEFAULT_CLAIM_AMOUNT = 600_000

CONDITION_NAMES = {
    "diabetes": ["diabetes", "diabetic", "sugar", "blood sugar", "type 2 diabetes", "type 1 diabetes"],
    "hypertension": ["hypertension", "bp", "high bp", "blood pressure", "high blood pressure"],
    "asthma": ["asthma", "asthmatic"],
    "heart_disease": ["heart_disease", "heart disease", "heart problem", "cardiac"],
}
CONDITION_TREATMENT = {"diabetes": "cardiac", "hypertension": "cardiac", "heart_disease": "cardiac"}
TREATMENT_LABEL = {"cardiac": "heart procedure"}


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
    members: list[Member] = Field(min_length=1)
    office_cover: list[OfficeCover] = []


class Claim(BaseModel):
    member_id: str
    amount: int = Field(gt=0)
    related_condition: str | None = None
    treatment: str | None = None


class RecommendRequest(BaseModel):
    family: Family
    claims: list[Claim] | None = None


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    family: dict = {}  # partial while the user is still telling us about the family
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

    result = solver.solve(family, POLICIES)
    result["id"] = "rec-" + uuid.uuid4().hex[:8]
    result["claim_checks"] = []
    if result["status"] == "ok":
        claims = [c.model_dump() for c in req.claims] if req.claims is not None else default_claims(family)
        result["claim_checks"] = [claim_by_year(family, result, c) for c in claims]
    RECOMMENDATIONS[result["id"]] = result
    return result


def default_claims(family):
    """A ₹6L claim for each member with a known condition, like the deck's claim check."""
    claims = []
    for m in family["members"]:
        if m["conditions"]:
            condition = m["conditions"][0]
            claims.append({"member_id": m["id"], "amount": DEFAULT_CLAIM_AMOUNT,
                           "related_condition": condition, "treatment": CONDITION_TREATMENT.get(condition)})
    return claims


def claim_by_year(family, result, claim):
    name = next(m["name"] for m in family["members"] if m["id"] == claim["member_id"])
    what = TREATMENT_LABEL.get(claim["treatment"], "hospital stay")
    by_year = []
    for year in CLAIM_YEARS:
        args = (claim["member_id"], claim["amount"], year, claim["related_condition"], claim["treatment"])
        usual = result["usual_pick"]
        by_year.append({
            "year": year,
            "mix": solver.claim_check(family, result["picks"], *args),
            "usual": solver.claim_check(family, [usual], *args) if usual else None,
        })
    return dict(claim, label=f"{solver.inr(claim['amount'])} {what} for {name}", by_year=by_year)


# Chat

STYLE = ("Write plain, short sentences in sentence case. Do not use em or en dashes. "
         "Do not use hype words. Reply in the language the user writes in.")

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
             "members": [{{"name": str, "age": int or null, "relation": str,
                          "conditions": [only conditions the user said this person has, in lowercase]}}],
             "office_cover": [{{"members": [member ids], "sum_insured": rupees as an integer}}],
             "health_checked": true once the user has said who has health conditions,
             "office_checked": true once the user has said whether anyone has office cover}}}}

Only record what the user actually said. Never guess an age or a health condition. If the user has
not mentioned a condition for someone, their conditions list is empty.
Convert lakh amounts to rupees: 1.1 lakh is 110000.
The user is "self". Use relations like spouse, son, daughter, father, mother.
""" + STYLE

EXPLAIN_PROMPT = """You explain a health insurance recommendation to the person who asked for it.

The solver chose the policies and worked out every number and reason below. Answer only from these
facts. Never change a premium, add a reason or suggest a different policy. If the facts do not answer
the question, say so. Mention catches such as co-pay, waits and sub-limits when they matter.
All premiums are illustrative. Policy year 1 is the first year after buying, so "next year" is year 2.
Write money with the rupee sign and Indian grouping, like ₹1,80,000.

Facts, as JSON:
{facts}

Return only a JSON object:
{{"reply": "your answer", "citations": [policy ids from the facts that your answer relies on]}}
""" + STYLE


@app.post("/chat")
def chat(req: ChatRequest):
    history = [t.model_dump() for t in req.history] + [{"role": "user", "content": req.message}]
    if req.recommendation_id:
        rec = RECOMMENDATIONS.get(req.recommendation_id)
        if rec is None:
            raise HTTPException(404, "Recommendation not found. Run /recommend again.")
        out = call_llm(EXPLAIN_PROMPT.format(facts=json.dumps(explain_facts(rec), ensure_ascii=False)), history)
        known = {p["policy_id"] for p in rec.get("picks", [])}
        if rec.get("usual_pick"):
            known.add(rec["usual_pick"]["policy_id"])
        return {"reply": tidy(out.get("reply", "")), "family": req.family,
                "citations": [c for c in out.get("citations", []) if c in known]}

    family = clean_family(req.family, req.family)
    out = call_llm(INTAKE_PROMPT.format(family=json.dumps(family, ensure_ascii=False),
                                        missing=", ".join(missing_details(family)) or "nothing"), history)
    new = dict(out.get("family") or {})
    # ids come from names, so the LLM cannot rename a member
    new["members"] = [{k: v for k, v in m.items() if k != "id"} for m in new.get("members") or []]
    family = grounded(clean_family(new, family), family, history)
    missing = missing_details(family)
    reply = tidy(out.get("reply", ""))
    for proper in [m["name"] for m in family["members"]] + [family["city"] or ""]:
        if proper:
            reply = re.sub(rf"\b{re.escape(proper)}\b", proper, reply, flags=re.IGNORECASE)
    if "?" not in reply:
        reply = f"{reply} {next_question(missing[0]) if missing else 'I have everything I need to find your options.'}"
    return {"reply": reply, "family": family, "missing": missing, "ready": not missing}


NEXT_QUESTION = {
    "Who is in the family": "Who would you like to insure? Tell me each person's name and age.",
    "Health conditions": "Does anyone have a health condition, like diabetes or high blood pressure?",
    "Office cover": "Does anyone get health cover from their office? If yes, how much?",
    "City": "Which city do you live in?",
    "Yearly budget": "How much can you spend on premiums each year?",
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
    if rec["status"] != "ok":
        return {"status": rec["status"], "budget": rec["budget"], "message": rec["message"]}
    keep = ("policy_id", "insurer", "product", "plan_type", "members", "sum_insured", "deductible",
            "premium", "copay_percent", "catches", "reasons")
    usual = rec["usual_pick"]
    return {
        "budget": rec["budget"], "total_premium": rec["total_premium"], "total_cover": rec["total_cover"],
        "member_cover": rec["member_cover"],
        "picks": [{k: p[k] for k in keep} for p in rec["picks"]],
        "usual_pick": {k: usual[k] for k in keep if k in usual} if usual else None,
        "vs_usual": [r["text"] for r in rec["vs_usual"]],
        "claim_checks": [{"label": c["label"], "by_year": [
            {"year": y["year"], "mix": y["mix"], "usual": y["usual"]} for y in c["by_year"]]}
            for c in rec["claim_checks"]],
    }


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
        members.append({"id": mid, "name": name, "age": as_int(m.get("age")),
                        "relation": m.get("relation"), "conditions": conditions})
    office = []
    for oc in raw.get("office_cover") or []:
        amount, who = as_int(oc.get("sum_insured")), [mid for mid in oc.get("members") or [] if mid in seen]
        if amount and who:
            office.append({"members": who, "sum_insured": amount})
    return {
        "id": raw.get("id") or previous.get("id") or "web",
        # The LLM sometimes leaves out fields it was not asked about, so keep what we had
        "city": raw.get("city") or previous.get("city") or None,
        "budget": as_int(raw.get("budget")) or as_int(previous.get("budget")),
        "members": members,
        "office_cover": office,
        "health_checked": bool(raw.get("health_checked") or previous.get("health_checked")),
        "office_checked": bool(raw.get("office_checked") or previous.get("office_checked") or office),
    }


RELATION_WORDS = {
    "self": ["i", "me", "i'm", "myself"],
    "spouse": ["wife", "husband", "spouse"],
    "father": ["father", "dad", "papa", "appa"],
    "mother": ["mother", "mom", "mum", "mummy", "amma", "maa"],
    "son": ["son"], "daughter": ["daughter"],
}


OFFICE_WORDS = ["office", "company", "employer", "corporate", "work", "job", "group"]


def has_word(text, word):
    return re.search(rf"\b{re.escape(str(word))}\b", text) is not None


def mentions(text, member):
    words = [member["name"].lower()] + RELATION_WORDS.get(member.get("relation") or "", [])
    return any(has_word(text, w) for w in words)


def passages(history, members):
    """Pieces of what the user said. A sentence naming nobody is read with the question it answers."""
    out, asked = [], ""
    for turn in history:
        text = turn["content"].lower()
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
    return missing
