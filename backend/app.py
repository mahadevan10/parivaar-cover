"""HTTP API for the frontend. Run from backend/: .venv/bin/uvicorn app:app --reload --port 8000

POST /recommend runs the solver and the claim checks. POST /chat talks to the user through
Sarvam: before a recommendation it collects the family details, after one it explains the
solver's reasons or quotes a change the user asks for. POST /quote quotes a change made on the
results screen. The LLM never picks policies or quotes prices.
"""
import json
import re
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

import llm
import solver
import store

app = FastAPI(title="Parivaar Cover")
# The frontend on this machine, or on a phone or laptop on the same Wi-Fi for the demo.
# Ports 3000 to 3009, so a second checkout can run next to the first.
app.add_middleware(CORSMiddleware,
                   allow_origin_regex=r"http://(localhost|127\.0\.0\.1|10(\.\d+){3}|192\.168(\.\d+){2}"
                                      r"|172\.(1[6-9]|2\d|3[01])(\.\d+){2}):300\d",
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


class Requirements(BaseModel):
    """What the user asked of the plans beyond the budget and total cover (shared/README.md).
    The UI sends the same fields in camelCase."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    min_cover: dict[str, int] = {}
    max_wait_months: dict[str, int] = {}
    max_copay_percent: int | None = Field(None, ge=0, le=100)
    uncapped_room_rent: bool = False
    avoid_insurers: list[str] = []
    one_insurer: bool = False
    avoid_policies: list[str] = []
    avoid_plan_types: list[Literal["floater", "individual", "senior", "super_topup"]] = []
    max_policies: int | None = Field(None, ge=1)


class Family(BaseModel):
    id: str = "web"
    city: str | None = None
    budget: int = Field(gt=0)
    # Total cover the family wants, summed over every policy in the mix. None lets the solver choose.
    cover_target: int | None = Field(None, gt=0)
    members: list[Member] = Field(min_length=1)
    office_cover: list[OfficeCover] = []
    requirements: Requirements = Requirements()


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
    requirements: Requirements = Requirements()
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
    language: str | None = None  # set for spoken messages, e.g. hi-IN


class QuoteRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    session_id: str | None = None
    family: dict  # the UI's FamilyProfile with the change made
    recommendation_id: str
    language: str | None = None


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
    rules = family["requirements"]
    for mid in list(rules["min_cover"]) + list(rules["max_wait_months"]):
        if mid not in ids:
            raise HTTPException(422, f"Unknown member in requirements: {mid}")

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
    if solution["status"] == "no_fit" and solution["reason"] == "rules":
        # The family id is the session id (toSolverFamily in frontend/src/lib/solver.ts)
        store.save_expert_request(family["id"], family, None, "no_plan_meets_rules")
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

# The rules a user can set, shared by the intake and edit prompts. Doubled braces, as they go through format.
REQUIREMENT_FIELDS = """{{"min_cover": {{member id: least cover in rupees for that one person}},
                   "max_wait_months": {{member id: most months before that person's existing conditions are covered}},
                   "max_copay_percent": most co-pay percent allowed, 0 for no co-pay, or null,
                   "uncapped_room_rent": true if the user wants no room rent cap,
                   "avoid_insurers": [insurer names to leave out],
                   "one_insurer": true if every plan must come from one insurer,
                   "avoid_policies": [policy ids to leave out],
                   "avoid_plan_types": [plan types to leave out: floater, individual, senior, super_topup],
                   "max_policies": most policies in the mix, or null}}"""
UNSUPPORTED_FIELD = ('"a few words naming what the user wants that none of these fields can express, '
                     'like maternity cover, OPD or a named hospital, or null"')
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
             "cover_checked": true once the user has said how much cover they want or that they are not sure}},
  "requirements": """ + REQUIREMENT_FIELDS + """,
  "unsupported": """ + UNSUPPORTED_FIELD + """}}

Only record what the user actually said. Never guess an age or a health condition. If the user has
not mentioned a condition for someone, their conditions list is empty.
Convert lakh and crore amounts to rupees: 1.1 lakh is 110000 and 1 crore is 10000000.
Office cover is cover the user already has. cover_target is the new cover they want, so keep them apart.
Requirements are optional. Leave them as they are unless the user asks for one.
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
{{"change": true if the user asks to change anything behind the mix, else false,
  "reply": "your answer", "citations": [policy ids from the facts that your answer relies on]}}

A change is the user saying what they want, or what is different now: anything about the family, the
budget, the cover or the plans. These are all changes: "my father is 66 now", "budget is 60k",
"at least 50 lakh for papa", "I need more cover for my father", "no co-pay plans please",
"only Star Health", "add my sister", "drop the top-up", "fewer policies", "I need maternity cover".
A question about the mix, like "why not one floater?" or "what is a co-pay?", is not a change.
When change is true, reply can be empty.
""" + STYLE


EDIT_PROMPT = """You help one person change the details behind their family's health insurance mix.

You never pick policies, name prices or say what the mix will cost. A solver does that after you.

Current family and rules, as JSON:
{family}

Insurers, plan types and the plans in the current mix, as JSON:
{options}

Apply what the user just asked to change. Return the whole family and every rule again, keeping
everything the user did not ask to change.

Return only a JSON object:
{{"family": {{"city": str, "budget": yearly rupees as an integer,
             "cover_target": total cover in rupees for the whole family, or null to let the solver choose,
             "members": [{{"name": str, "age": int or null, "relation": str, "conditions": [lowercase]}}],
             "office_cover": [{{"members": [member ids], "sum_insured": rupees as an integer}}]}},
  "requirements": """ + REQUIREMENT_FIELDS + """,
  "more_cover_for": [member ids the user wants a bigger sum insured for, without saying how much],
  "unsupported": """ + UNSUPPORTED_FIELD + """}}

Only record what the user actually said. Never guess an age, a condition or an amount.
cover_target is the total for the whole family. min_cover is for one person.
A kind of cover, like maternity, OPD or dental, is unsupported. It is not more cover.
If the user wants only one insurer, put every other insurer in avoid_insurers.
Convert amounts to rupees: 60k is 60000, 1.1 lakh is 110000 and 1 crore is 10000000.
Convert years to months: 1 year is 12.
"""


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
        if out.get("change") is True:
            return change_turn(req, rec, history)
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
    edited = grounded(clean_family(new, family), family, english)
    edited["requirements"], _ = grounded_requirements(proposed_requirements(out, family, edited),
                                                      family["requirements"], said_last(english, edited), edited)
    family = edited
    expert = bool(out.get("unsupported")) and str(out.get("unsupported")).lower() != "null"
    if expert:
        store.save_expert_request(req.session_id, family, req.message, str(out["unsupported"]))
    if req.message.strip().lower() == COVER_NOT_SURE.lower():
        family["cover_checked"], family["cover_target"] = True, None
    missing = missing_details(family)
    reply = tidy(out.get("reply", ""))
    reply = proper_case(reply, [m["name"] for m in family["members"]] + [family["city"] or ""])
    if expert:
        reply = f"{reply} {EXPERT_LINE}".strip()
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
            "quickReplies": quick_replies(family, missing), "readyToOptimise": not missing,
            "expertRequested": expert}


# Changes after a mix is shown. The LLM says what the user wants changed, code checks it against
# what they said, and the solver prices it. Nothing changes until the user taps "Update my mix".

UPDATE_MIX, KEEP_MIX = "Update my mix", "Keep this mix"
EXPERT_LINE = ("Your requirement needs help from an insurance expert. An expert will contact you directly "
               "and suggest a floater that fits your family.")
EXPERT_REPLY = EXPERT_LINE + " Your current mix stays as it is."


def change_turn(req, rec, history):
    """A chat turn that asks to change something behind the mix: the change, checked and quoted."""
    shown = rec_family(rec, req.family)
    # A change still being put together (a new person without an age) comes back as the request's family
    draft = clean_family(from_profile(req.family), from_profile(req.family))
    out = call_llm(EDIT_PROMPT.format(family=json.dumps(draft, ensure_ascii=False),
                                      options=json.dumps(edit_options(rec), ensure_ascii=False)), history)
    new = dict(out.get("family") or {})
    new["members"] = [{k: v for k, v in m.items() if k != "id"} for m in new.get("members") or []]
    english = [dict(t, content=llm.to_english(t["content"])) if t["role"] == "user" else t for t in history]
    raw = clean_family(new, draft)
    raw["requirements"] = proposed_requirements(out, draft, raw)
    # The user asked for a change the editor could not put in any field, like dental cover: an expert's job
    nothing = not describe_changes(draft, raw) and not out.get("more_cover_for")
    edited = grounded_edit(grounded(clean_family(new, draft), draft, english), draft, said_last(english, draft))
    said = said_last(english, edited)
    edited["requirements"], ask = grounded_requirements(proposed_requirements(out, draft, edited),
                                                        draft["requirements"], said, edited)
    unsupported = out.get("unsupported") if out.get("unsupported") not in (None, "", "null") else None
    if nothing and not unsupported:
        unsupported = "no field for this request"
    # "Maternity cover for Sneha" is a kind of cover the plans may not have, not a bigger amount
    more = out.get("more_cover_for") if isinstance(out.get("more_cover_for"), list) and not unsupported else []
    # Someone who now has an amount is not asked again, even if the LLM still lists them
    ask += [m["id"] for m in edited["members"] if m["id"] in more and m["id"] not in ask
            and m["id"] not in edited["requirements"]["min_cover"] and any(mentions(p, m) for p in said)]
    reply, proposal, quick, expert = quote_change(req.session_id, shown, edited, rec["solution"], unsupported,
                                                  ask, req.message)
    reply = localised(reply, req.language)
    remember(req.session_id, req.message, reply, english[-1]["content"])
    return {"reply": reply, "family": req.family, "missing": [], "quickReplies": quick, "readyToOptimise": True,
            "citations": [], "proposal": proposal, "expertRequested": expert}


@app.post("/quote")
def quote(req: QuoteRequest):
    """Quotes a change made on the results screen, like removing a rule, the same way as a chat change."""
    rec = store.recommendation(req.recommendation_id)
    if rec is None:
        raise HTTPException(404, "Recommendation not found. Run /recommend again.")
    profile = from_profile(req.family)
    edited = clean_family(profile, profile)
    reply, proposal, quick, expert = quote_change(req.session_id, rec_family(rec, req.family), edited,
                                                  rec["solution"], None, [], None)
    reply = localised(reply, req.language)
    if req.session_id:
        store.add_message(req.session_id, "assistant", reply)
    return {"reply": reply, "family": req.family, "missing": [], "quickReplies": quick, "readyToOptimise": True,
            "citations": [], "proposal": proposal, "expertRequested": expert}


def rec_family(rec, profile):
    """The family a recommendation ran on, in the shape clean_family returns."""
    stored = store.recommendation_family(rec["id"])
    shown = from_profile(profile)
    base = clean_family(stored, shown) if stored else clean_family(shown, shown)
    # Checks the solver never needed are kept from the board, so the diff does not report them
    for key in ("health_checked", "office_checked", "cover_checked"):
        base[key] = bool(shown.get(key) or base.get(key))
    return base


def edit_options(rec):
    picks = rec["solution"].get("picks", [])
    return {"insurers": INSURERS, "plan_types": list(PLAN_TYPES),
            "plans_in_mix": [{"policy_id": p["policy_id"], "insurer": p["insurer"], "product": p["product"],
                              "plan_type": p["plan_type"], "members": p["members"]} for p in picks]}


def quote_change(session_id, old, new, old_solution, unsupported, ask, message):
    """The reply, proposal, quick replies and whether an expert was asked for. Code writes every sentence."""
    by_id = {m["id"]: m for m in new["members"]}
    changes = describe_changes(old, new)
    missing = [m for m in missing_details(new) if m.endswith("'s age") or m == "Who is in the family"]

    def expert(reason):
        store.save_expert_request(session_id, new, message, reason)
        return EXPERT_REPLY, None, [], True

    if not changes and not ask:
        if unsupported:
            return expert(unsupported)
        return ("I could not tell what to change. Tell me what is different, like a new budget, or how much "
                "cover one person needs, like ₹50 lakh for your father.", None, [], False)

    draft = {"family": to_profile(new), "ready": False, "changes": changes}
    if missing or ask:
        if missing:
            question = next_question(missing[0])
            quick = []
        else:
            m, now = by_id[ask[0]], old_solution["member_cover"].get(ask[0], 0)
            question = f"How much cover would you like for {m['name']}? {m['name']} has {solver.lakhs(now)} now."
            quick = [solver.lakhs(a) for a in COVER_STEPS if a > now][:2]
        return " ".join(changes + [question]), draft, quick, False

    family = Family.model_validate(new).model_dump()
    solution = solver.solve(family, POLICIES)
    lines, raised = list(changes), None
    if solution["status"] != "ok" and solution["reason"] == "budget":
        # Keep everyone else's cover where it is, or the cheapest mix would cut it to pay for the change
        floors = {mid: cover for mid, cover in old_solution["member_cover"].items()
                  if mid in by_id and mid not in family["requirements"]["min_cover"]}
        raised = solver.budget_needed(family, floors, POLICIES) or solution["budget_needed"]
        family["budget"] = raised
        solution = solver.solve(family, POLICIES)
    if solution["status"] != "ok" or (solution.get("cover_check") or {}).get("code") == "cover_out_of_reach":
        return expert(unsupported or "no_plan_meets_rules")

    premium, before = solution["total_premium"], old_solution["total_premium"]
    diff = premium - before
    count = len(solution["picks"])
    lines.append(f"Your mix becomes {count} {'policy' if count == 1 else 'policies'} at {solver.inr(premium)} a year, "
                 + (f"{solver.inr(abs(diff))} {'more' if diff > 0 else 'less'} than now." if diff else "the same as now."))
    for mid, cover in solution["member_cover"].items():
        was = old_solution["member_cover"].get(mid)
        if was is None:
            lines.append(f"{by_id[mid]['name']} gets {solver.lakhs(cover)} of cover.")
        elif was != cover:
            lines.append(f"{by_id[mid]['name']}'s cover goes from {solver.lakhs(was)} to {solver.lakhs(cover)}.")
    if raised:
        lines.append(f"That is {solver.inr(raised - old['budget'])} over your {solver.inr(old['budget'])} budget. "
                     f"Updating sets your budget to {solver.inr(raised)}.")
    quick = [UPDATE_MIX, KEEP_MIX]
    check = solution.get("cover_check") or {}
    raise_to = None
    if check.get("code") == "cover_short":
        lines.append(check["text"])
        raise_to = check["budget_needed"]
        quick.insert(1, raise_budget_label(raise_to))
    if unsupported:
        store.save_expert_request(session_id, new, message, unsupported)
        lines.append(f"For the rest, {EXPERT_LINE[0].lower()}{EXPERT_LINE[1:]}")
    proposal = dict(draft, family=to_profile(dict(new, budget=family["budget"])), ready=True, premium=premium,
                    premiumChange=diff, raiseBudgetTo=raise_to)
    return " ".join(lines), proposal, quick, bool(unsupported)


COVER_STEPS = [1_000_000, 2_500_000, 5_000_000, 10_000_000]


def raise_budget_label(amount):
    return f"Raise budget to {solver.inr(amount)}"


def describe_changes(old, new):
    """One plain sentence per change between two families, rules included."""
    out = []
    old_by_id = {m["id"]: m for m in old["members"]}
    new_by_id = {m["id"]: m for m in new["members"]}
    for m in new["members"]:
        was = old_by_id.get(m["id"])
        if was is None:
            out.append(f"{m['name']}{', ' + str(m['age']) + ',' if m['age'] is not None else ''} is added.")
            continue
        if m["age"] != was["age"] and m["age"] is not None:
            out.append(f"{m['name']}'s age is now {m['age']}.")
        if set(m["conditions"]) != set(was["conditions"]):
            out.append(f"{m['name']} now has {solver.names(c.replace('_', ' ') for c in m['conditions'])}."
                       if m["conditions"] else f"{m['name']} has no health conditions now.")
    out += [f"{m['name']} is removed." for m in old["members"] if m["id"] not in new_by_id]
    if new["city"] != old["city"] and new["city"]:
        out.append(f"Your city is now {new['city']}.")
    if new["budget"] != old["budget"] and new["budget"]:
        out.append(f"Your budget is now {solver.inr(new['budget'])} a year.")
    if new["cover_target"] != old["cover_target"]:
        out.append(f"You want {solver.lakhs(new['cover_target'])} of total cover." if new["cover_target"]
                   else "The total cover is left to the solver.")
    if new["office_cover"] != old["office_cover"]:
        out.append(" ".join(f"Office cover is now {solver.lakhs(oc['sum_insured'])} for "
                            f"{solver.names(new_by_id[mid]['name'] for mid in oc['members'])}." for oc in new["office_cover"])
                   or "No office cover now.")

    a, b = old["requirements"], new["requirements"]
    name = lambda mid: (new_by_id.get(mid) or old_by_id.get(mid) or {"name": mid})["name"]
    for mid in dict.fromkeys(list(a["min_cover"]) + list(b["min_cover"])):
        if a["min_cover"].get(mid) != b["min_cover"].get(mid):
            out.append(f"{name(mid)} needs at least {solver.lakhs(b['min_cover'][mid])} of cover."
                       if mid in b["min_cover"] else f"{name(mid)} has no set cover now.")
    for mid in dict.fromkeys(list(a["max_wait_months"]) + list(b["max_wait_months"])):
        if a["max_wait_months"].get(mid) != b["max_wait_months"].get(mid):
            out.append(f"{name(mid)}'s existing illnesses must be covered within {solver.duration(b['max_wait_months'][mid])}."
                       if mid in b["max_wait_months"] else f"{name(mid)} has no wait limit now.")
    if a["max_copay_percent"] != b["max_copay_percent"]:
        cap = b["max_copay_percent"]
        out.append("Plans with a co-pay are allowed again." if cap is None else
                   "No plans with a co-pay." if cap == 0 else f"Co-pay of at most {cap}%.")
    if a["uncapped_room_rent"] != b["uncapped_room_rent"]:
        out.append("No plans that cap room rent." if b["uncapped_room_rent"] else "Plans that cap room rent are allowed again.")
    only = [i for i in INSURERS if i not in b["avoid_insurers"]]
    if len(only) == 1 and a["avoid_insurers"] != b["avoid_insurers"]:
        out.append(f"Only {only[0]} plans.")
    else:
        for insurer in b["avoid_insurers"]:
            if insurer not in a["avoid_insurers"]:
                out.append(f"Leave out {insurer}.")
        for insurer in a["avoid_insurers"]:
            if insurer not in b["avoid_insurers"]:
                out.append(f"{insurer} is allowed again.")
    if a["one_insurer"] != b["one_insurer"] and not (len(only) == 1 and b["one_insurer"]):
        out.append("Every plan from one insurer." if b["one_insurer"] else "Plans can come from more than one insurer.")
    for pid in b["avoid_policies"]:
        if pid not in a["avoid_policies"]:
            out.append(f"Leave out {PRODUCT_NAMES[pid]}.")
    for pid in a["avoid_policies"]:
        if pid not in b["avoid_policies"]:
            out.append(f"{PRODUCT_NAMES[pid]} is allowed again.")
    for t in b["avoid_plan_types"]:
        if t not in a["avoid_plan_types"]:
            out.append(f"No {solver.PLAN_TYPE_NAMES[t]}s.")
    for t in a["avoid_plan_types"]:
        if t not in b["avoid_plan_types"]:
            out.append(f"{solver.PLAN_TYPE_NAMES[t].capitalize()}s are allowed again.")
    if a["max_policies"] != b["max_policies"]:
        out.append(f"At most {b['max_policies']} policies." if b["max_policies"] else "No limit on the number of policies.")
    return out


def localised(text, language):
    """The code-written text in the user's language. Kept only if every number survives the translation."""
    if not language or language.startswith("en"):
        return text
    translated = llm.from_english(text, language)
    digits = lambda t: sorted(re.findall(r"\d+", t.replace(",", "")))
    return translated if digits(translated) == digits(text) else text


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
        "requirements": {key: value for key, value in ((k, (p.get("requirements") or {}).get(to_camel(k)))
                                                         for k in Requirements.model_fields) if value is not None},
    }


def to_profile(f):
    office = f["office_cover"][0] if f["office_cover"] else None
    profile = {
        "members": [{"id": m["id"], "name": m["name"], "relation": m["relation"], "age": m["age"],
                     "conditions": m["conditions"], "heardFrom": m.get("heard_from")} for m in f["members"]],
        "city": f["city"], "budget": f["budget"],
        "healthChecked": f["health_checked"], "officeChecked": f["office_checked"],
        "coverTarget": f["cover_target"], "coverChecked": f["cover_checked"],
        "requirements": {to_camel(k): v for k, v in f["requirements"].items()},
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
        "requirements": rec.get("requirements"),
        "requirement_notes": [n["text"] for n in rec.get("requirement_notes", [])],
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
        "requirements": clean_requirements(raw["requirements"] if raw.get("requirements") is not None
                                           else previous.get("requirements"), members),
    }


PLAN_TYPES = ("floater", "individual", "senior", "super_topup")
INSURERS = sorted({p["insurer"] for p in POLICIES})
PRODUCT_NAMES = {p["id"]: f"{p['insurer']} {p['product']}" for p in POLICIES}


def clean_requirements(raw, members):
    """Rules from the LLM or the UI in the shared format. Anything unknown or out of range is dropped.
    Per-member rules may name a member by id or by name."""
    raw = raw if isinstance(raw, dict) else {}
    ids = {m["id"]: m["id"] for m in members} | {m["name"].lower(): m["id"] for m in members}

    def per_member(key):
        out = {}
        for who, value in (raw.get(key) if isinstance(raw.get(key), dict) else {}).items():
            mid, value = ids.get(str(who).lower(), ids.get(str(who))), as_int(value)
            if mid and value is not None and value >= 0:
                out[mid] = value
        return out

    def listed(key):
        value = raw.get(key)
        return [str(v) for v in value] if isinstance(value, list) else []

    insurers = {i.lower(): i for i in INSURERS}
    copay, most = as_int(str(raw.get("max_copay_percent")).rstrip("% ")), as_int(raw.get("max_policies"))
    return {
        "min_cover": {mid: v for mid, v in per_member("min_cover").items() if v > 0},
        "max_wait_months": per_member("max_wait_months"),
        "max_copay_percent": copay if copay is not None and 0 <= copay <= 100 else None,
        "uncapped_room_rent": raw.get("uncapped_room_rent") is True,
        "avoid_insurers": list(dict.fromkeys(insurers[i.lower()] for i in listed("avoid_insurers") if i.lower() in insurers)),
        "one_insurer": raw.get("one_insurer") is True,
        "avoid_policies": list(dict.fromkeys(i for i in listed("avoid_policies") if i in PRODUCT_NAMES)),
        "avoid_plan_types": list(dict.fromkeys(t for t in listed("avoid_plan_types") if t in PLAN_TYPES)),
        "max_policies": most if most and most > 0 else None,
    }


RELATION_WORDS = {
    "self": ["i", "me", "i'm", "myself"],
    "spouse": ["wife", "husband", "spouse"],
    "father": ["father", "dad", "papa", "appa", "pitaji", "pita", "papaji", "baba", "abba", "achan"],
    "mother": ["mother", "mom", "mum", "mummy", "amma", "maa", "mataji", "mata", "ammi"],
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
    # A user turn counts as talking about office cover if it says so, or answers the assistant's office question.
    office_said = any(
        t["role"] == "user" and any(has_word((asked + " " + t["content"]).lower(), w) for w in OFFICE_WORDS)
        for asked, t in zip([""] + [p["content"] if p["role"] != "user" else "" for p in history], history))
    if family["office_checked"] and not previous.get("office_checked") and not office_said:
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


# What the user said about rules and edits. A change only counts if the last thing the user said,
# read with the question it answers, is about it.

AMOUNT = re.compile(r"(\d+(?:\.\d+)?)\s*(k|thousand|l|lakhs?|lacs?|cr|crores?)?\b")
AMOUNT_UNIT = {"k": 1000, "thousand": 1000, "l": 100_000, "lakh": 100_000, "lakhs": 100_000, "lac": 100_000,
               "lacs": 100_000, "cr": 10_000_000, "crore": 10_000_000, "crores": 10_000_000}
MONTHS = re.compile(r"(\d+(?:\.\d+)?)\s*(years?|yrs?|months?)\b")

COPAY_WORDS = ["co-pay", "copay", "co pay", "copayment", "co-payment"]
PLAN_TYPE_WORDS = ["floater", "top-up", "topup", "top up", "top-ups", "topups", "senior", "individual"]
PLAN_WORDS = ["policy", "policies", "plan", "plans"]
INSURER_WORDS = ["insurer", "insurers", "company", "companies"] + sorted(
    {w for i in INSURERS for w in [i.lower()] + i.lower().split() if w not in ("general", "health")})
# Words that must appear for a change to each family-wide rule to count
RULE_WORDS = {
    "max_copay_percent": COPAY_WORDS,
    "uncapped_room_rent": ["room", "room rent"],
    "avoid_insurers": INSURER_WORDS,
    "one_insurer": INSURER_WORDS,
    "avoid_policies": INSURER_WORDS + PLAN_TYPE_WORDS + sorted({p["product"].lower() for p in POLICIES}),
    "avoid_plan_types": PLAN_TYPE_WORDS,
    "max_policies": PLAN_WORDS,
}


def proposed_requirements(out, previous, family):
    """The rules the LLM returned, with any it left out kept as they were."""
    raw = out.get("requirements")
    if not isinstance(raw, dict):
        return previous["requirements"]
    return clean_requirements(dict(previous["requirements"], **raw), family["members"])


def said_last(english, family):
    """The user's last message, read with the question it answers when it names nobody."""
    said = with_digits(english[-1]["content"].lower())
    if any(mentions(said, m) for m in family["members"]) or len(english) < 2:
        return [said]
    return [with_digits(english[-2]["content"].lower()) + " " + said]


def amounts_in(text):
    """Every amount in the text in rupees: "60k", "1.5 lakh", "₹50,00,000" and "2 crore" all count."""
    out = set()
    for m in AMOUNT.finditer(text.replace(",", "")):
        out.add(round(float(m.group(1)) * AMOUNT_UNIT.get(m.group(2) or "", 1)))
    return out


def months_in(text):
    out = {round(float(n) * (12 if unit.startswith("y") else 1)) for n, unit in MONTHS.findall(text)}
    return out | ({12} if re.search(r"\b(a|one) year\b", text) else set())


def grounded_requirements(new, old, said, family):
    """Keeps a change to a rule only if the user's last words were about it.

    Returns the rules, and the members the user wants more cover for without saying how much.
    """
    out, ask = dict(new), []
    heard = lambda words: any(has_word(p, w) for p in said for w in words)
    for key, words in RULE_WORDS.items():
        if new[key] != old[key] and not heard(words):
            out[key] = old[key]

    by_id = {m["id"]: m for m in family["members"]}
    for key, said_values, words in (("min_cover", amounts_in, ["cover"]),
                                    ("max_wait_months", months_in, ["wait", "waiting", "covered"])):
        kept = {mid: v for mid, v in old[key].items() if mid in by_id}
        for mid in dict.fromkeys(list(new[key]) + list(kept)):
            if new[key].get(mid) == kept.get(mid):
                continue
            about = [p for p in said if mentions(p, by_id[mid])]
            if not about:
                continue
            value = new[key].get(mid)
            if value is None:
                if any(has_word(p, w) for p in about for w in words):
                    kept.pop(mid, None)
            elif any(value in said_values(p) for p in about):
                kept[mid] = value
            elif key == "min_cover":
                ask.append(mid)
        out[key] = kept
    return out, ask


def grounded_edit(family, previous, said):
    """Undoes edits to the city, budget, cover, office cover and who is in the family that the
    user's last words were not about. Ages and conditions are checked by grounded()."""
    heard_amount = lambda amount: any(amount in amounts_in(p) for p in said)
    if family["budget"] != previous["budget"] and not heard_amount(family["budget"]):
        family["budget"] = previous["budget"]
    if family["cover_target"] != previous["cover_target"] and family["cover_target"] and not heard_amount(family["cover_target"]):
        family["cover_target"] = previous["cover_target"]
    if family["city"] != previous["city"] and not any(has_word(p, (family["city"] or "").lower()) for p in said):
        family["city"] = previous["city"]
    if family["office_cover"] != previous["office_cover"] and not any(has_word(p, w) for p in said for w in OFFICE_WORDS):
        family["office_cover"] = previous["office_cover"]

    kept = [m for m in family["members"] if any(o["id"] == m["id"] for o in previous["members"])
            or any(has_word(p, m["name"].lower()) for p in said)]
    ids = {m["id"] for m in kept}
    # Someone left out without being named is put back where they were
    for i, old in enumerate(previous["members"]):
        if old["id"] not in ids and not any(mentions(p, old) for p in said):
            kept.insert(min(i, len(kept)), old)
    family["members"] = kept
    return family
