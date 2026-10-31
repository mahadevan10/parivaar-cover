"""Picks the best-value mix of health policies for a family with OR-Tools CP-SAT.

Every candidate is one policy bought for one group of members (a single person for
individual and senior plans, any eligible group for floaters and super top-ups). The
premium for each candidate is worked out up front, so the model only chooses which
candidates to buy.
"""
import json
from itertools import combinations
from pathlib import Path

from ortools.sat.python import cp_model

import store

SHARED = Path(__file__).resolve().parent.parent / "shared"
LAKH = 100_000

# Cover we aim for per member, in lakhs. Cover above the target earns nothing,
# so spare budget is not spent on cover nobody needs.
TARGET_LAKHS_UNDER_60 = 50
TARGET_LAKHS_60_PLUS = 35

# Objective weights, all in rupees of yearly premium.
VALUE_PER_LAKH = 2000           # each lakh of cover up to the target
WAIT_PER_MONTH_BASE = 1500      # each month a member's known condition waits on a base policy
WAIT_PER_MONTH_TOPUP = 750      # the same on a super top-up
COPAY_PER_PERCENT = 500         # each percent of co-pay, per member
ROOM_RENT_CAP = 3000            # a capped room rent, per member

# The usual pick may stretch the budget a little, the way an agent's pitch does.
USUAL_PICK_BUDGET_STRETCH = 1.1

# Treatments that fall under a policy's specific illness wait, as listed in the wordings.
LISTED_ILLNESSES = {"cataract", "hernia", "knee", "joint_replacement", "gallstones", "piles", "sinus", "tonsils"}


def load_policies():
    """Policies from the policies table in SQLite, kept in step with shared/policies.json."""
    return store.policies()


def load_families():
    return {f["id"]: f for f in json.loads((SHARED / "families.json").read_text())["families"]}


def premium_for(policy, ages):
    """Premium for a group, priced on the eldest member's age band."""
    p = policy["premium"]
    eldest = max(ages)
    band = next((b for b in p["bands"] if eldest <= b["max_age"]), None)
    if band is None:
        return None
    extra = max(0, len(ages) - p["members_included"])
    return band["amount"] + extra * p["per_extra_member"]


def condition_wait(policy, conditions):
    """Months before a member's known conditions are covered. Zero if they have none."""
    if not conditions:
        return 0
    waits = policy["condition_waits_months"]
    default = policy["waiting_periods_months"]["pre_existing"]
    return max(waits.get(c, default) for c in conditions)


def is_topup(policy):
    return policy["plan_type"] == "super_topup"


def candidates(family, policies):
    members = family["members"]
    out = []
    for policy in policies:
        min_age, max_age = policy["entry_age"]["min"], policy["entry_age"]["max"]
        eligible = [m for m in members if min_age <= m["age"] <= max_age]
        if policy["plan_type"] in ("individual", "senior"):
            sizes = [1]
        elif policy["plan_type"] == "floater":
            sizes = range(2, min(policy["max_members"], len(eligible)) + 1)
        else:
            sizes = range(1, min(policy["max_members"], len(eligible)) + 1)
        for size in sizes:
            for group in combinations(eligible, size):
                premium = premium_for(policy, [m["age"] for m in group])
                if premium is None:
                    continue
                wait_weight = WAIT_PER_MONTH_TOPUP if is_topup(policy) else WAIT_PER_MONTH_BASE
                penalty = 0
                for m in group:
                    penalty += condition_wait(policy, m["conditions"]) * wait_weight
                    penalty += policy["copay_percent"] * COPAY_PER_PERCENT
                    penalty += ROOM_RENT_CAP if policy["room_rent"]["capped"] else 0
                out.append({"policy": policy, "members": [m["id"] for m in group],
                            "premium": premium, "penalty": penalty})
    return out


def office_cover(family):
    cover = {m["id"]: 0 for m in family["members"]}
    for oc in family.get("office_cover", []):
        for mid in oc["members"]:
            cover[mid] += oc["sum_insured"]
    return cover


def target_lakhs(member):
    return TARGET_LAKHS_60_PLUS if member["age"] >= 60 else TARGET_LAKHS_UNDER_60


def rules(family):
    """What the user asked of the plans beyond the budget and total cover. See shared/README.md."""
    return family.get("requirements") or {}


def allowed(family, c):
    """False when a requirement rules this candidate out."""
    req, policy = rules(family), c["policy"]
    by_id = {m["id"]: m for m in family["members"]}
    if policy["id"] in (req.get("avoid_policies") or []):
        return False
    if policy["insurer"].lower() in {i.lower() for i in req.get("avoid_insurers") or []}:
        return False
    if policy["plan_type"] in (req.get("avoid_plan_types") or []):
        return False
    if req.get("max_copay_percent") is not None and policy["copay_percent"] > req["max_copay_percent"]:
        return False
    if req.get("uncapped_room_rent") and policy["room_rent"]["capped"]:
        return False
    for mid, months in (req.get("max_wait_months") or {}).items():
        if mid in c["members"] and condition_wait(policy, by_id[mid]["conditions"]) > months:
            return False
    return True


def lakhs_up(amount):
    """Rupees as whole lakhs, rounded up, so a floor of ₹1,50,001 asks for 2 lakh."""
    return -(-amount // LAKH)


def build_model(family, cands, *, budget=True, floor=None, forbid=None, member_floors=None):
    """The rules every mix must follow, plus the value of each member's cover.

    budget=False drops the budget limit. floor is the least total cover the picks must add up to,
    in rupees. forbid rules out one candidate, which shows what the solver would pick without it.
    member_floors is the least cover per member in rupees, on top of the min_cover requirement.
    Returns the model, one choice per candidate, the total cover in lakhs and the value terms.
    """
    office = office_cover(family)
    req = rules(family)
    least = dict(member_floors or {})
    for mid, amount in (req.get("min_cover") or {}).items():
        least[mid] = max(least.get(mid, 0), amount)
    model = cp_model.CpModel()
    x = [model.NewBoolVar(f"c{i}") for i in range(len(cands))]

    def covering(mid, topup):
        return [i for i, c in enumerate(cands) if mid in c["members"] and is_topup(c["policy"]) == topup]

    objective = []
    for m in family["members"]:
        mid = m["id"]
        bases, topups = covering(mid, False), covering(mid, True)
        # One base policy each, unless office cover already gives them a base.
        if office[mid] > 0:
            model.Add(sum(x[i] for i in bases) <= 1)
        else:
            model.Add(sum(x[i] for i in bases) == 1)
        model.Add(sum(x[i] for i in topups) <= 1)

        cover = office[mid] // LAKH + sum(cands[i]["policy"]["sum_insured"] // LAKH * x[i] for i in bases + topups)
        if least.get(mid):
            model.Add(cover >= lakhs_up(least[mid]))
        # Cover the user asked for counts in full, even above the usual target
        counted = model.NewIntVar(0, max(target_lakhs(m), lakhs_up(least.get(mid, 0))), f"counted_{mid}")
        model.Add(counted <= cover)
        objective.append(VALUE_PER_LAKH * counted)

    # A top-up only makes sense when the base cover reaches its deductible.
    for i, c in enumerate(cands):
        if not is_topup(c["policy"]):
            continue
        deductible = c["policy"]["deductible"]
        for mid in c["members"]:
            if office[mid] >= deductible:
                continue
            enough = [j for j in covering(mid, False)
                      if cands[j]["policy"]["sum_insured"] + office[mid] >= deductible]
            model.Add(x[i] <= sum(x[j] for j in enough))

    # Total cover is what the picks add up to, the same sum as total_cover in the output
    total_cover = sum(c["policy"]["sum_insured"] // LAKH * x[i] for i, c in enumerate(cands))
    if budget:
        model.Add(sum(c["premium"] * x[i] for i, c in enumerate(cands)) <= family["budget"])
    if floor:
        model.Add(total_cover >= lakhs_up(floor))
    if forbid is not None:
        model.Add(x[forbid] == 0)
    if req.get("max_policies"):
        model.Add(sum(x) <= req["max_policies"])
    if req.get("one_insurer"):
        chosen = {}
        for i, c in enumerate(cands):
            insurer = c["policy"]["insurer"]
            chosen.setdefault(insurer, model.NewBoolVar(f"insurer_{len(chosen)}"))
            model.Add(x[i] <= chosen[insurer])
        model.Add(sum(chosen.values()) <= 1)
    return model, x, total_cover, objective


def run(model, x):
    """Indices of the chosen candidates, or None when no mix follows the rules."""
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [i for i in range(len(x)) if solver.Value(x[i])]


def optimise(family, cands, forbid=None, floor=None):
    """The best-value mix within the budget with at least floor rupees of cover, or None."""
    model, x, _, objective = build_model(family, cands, floor=floor, forbid=forbid)
    objective += [-(c["premium"] + c["penalty"]) * x[i] for i, c in enumerate(cands)]
    model.Maximize(sum(objective))
    return run(model, x)


def max_cover(family, cands, target):
    """The most total cover the budget can buy, up to the target, in rupees. None if nothing fits."""
    model, x, total_cover, _ = build_model(family, cands)
    counted = model.NewIntVar(0, lakhs_up(target), "counted_total")
    model.Add(counted <= total_cover)
    model.Maximize(counted)
    chosen = run(model, x)
    if chosen is None:
        return None
    return sum(cands[i]["policy"]["sum_insured"] for i in chosen)


def cheapest_for(family, cands, target, member_floors=None):
    """The lowest yearly premium for a mix with at least the target cover, ignoring the budget."""
    model, x, _, _ = build_model(family, cands, budget=False, floor=target, member_floors=member_floors)
    model.Minimize(sum(c["premium"] * x[i] for i, c in enumerate(cands)))
    chosen = run(model, x)
    return None if chosen is None else sum(cands[i]["premium"] for i in chosen)


def allowed_candidates(family, policies):
    return [c for c in candidates(family, policies) if allowed(family, c)]


def budget_needed(family, member_floors=None, policies=None):
    """The lowest yearly premium for a mix that follows every rule and gives each member at least
    their floor, ignoring the budget. None when no mix of the listed plans can."""
    return cheapest_for(family, allowed_candidates(family, policies or load_policies()), None, member_floors)


def solve(family, policies=None):
    policies = policies or load_policies()
    cands = allowed_candidates(family, policies)
    target = family.get("cover_target")

    # The budget comes first. When it cannot buy the cover asked for, the mix gets as close as it can.
    floor, chosen, short = target, None, False
    if target:
        chosen = optimise(family, cands, floor=target)
        if chosen is None:
            reachable = max_cover(family, cands, target)
            if reachable is not None:
                floor, short = reachable, True
                chosen = optimise(family, cands, floor=reachable)
    else:
        chosen = optimise(family, cands)
    if chosen is None:
        # The cover target is never the reason: the budget comes first, so it was already let go
        needed = cheapest_for(family, cands, None)
        return {"status": "no_fit", "family_id": family["id"], "budget": family["budget"],
                "cover_target": target, "budget_needed": needed, "reason": "budget" if needed else "rules",
                "message": "No mix covers everyone within this budget." if needed
                           else "No mix of the plans we have meets all of your rules."}

    picks = [dict(pick_out(cands[i]), reasons=reasons_for(family, cands, chosen, i, floor)) for i in chosen]
    picks.sort(key=lambda p: (p["plan_type"] == "super_topup", -len(p["members"])))
    usual = usual_pick(family, policies)
    total = sum(p["premium"] for p in picks)
    total_cover = sum(p["sum_insured"] for p in picks)
    return {
        "status": "ok",
        "family_id": family["id"],
        "budget": family["budget"],
        "cover_target": target,
        "illustrative": True,
        "picks": picks,
        "total_premium": total,
        "total_cover": total_cover,
        "member_cover": member_cover(family, picks),
        "usual_pick": usual,
        "saving_vs_usual": usual["premium"] - total if usual else None,
        "vs_usual": vs_usual(family, picks, usual),
        "mix_catches": mix_catches(family, picks),
        "cover_check": cover_check(family, cands, target, total_cover) if target else None,
        "requirements": rules(family),
        "requirement_notes": requirement_notes(family, picks),
    }


def requirement_notes(family, picks):
    """One sentence per rule the user set, saying how the mix keeps it. Same shape as the reasons."""
    req, out = rules(family), []
    by_id = {m["id"]: m for m in family["members"]}
    cover = member_cover(family, picks)
    for mid, amount in (req.get("min_cover") or {}).items():
        if mid in by_id:
            out.append({"code": "min_cover", "member": mid, "asked": amount, "cover": cover[mid],
                        "text": f"You asked for at least {lakhs(amount)} for {by_id[mid]['name']}. "
                                f"{by_id[mid]['name']} gets {lakhs(cover[mid])}."})
    for mid, months in (req.get("max_wait_months") or {}).items():
        if mid in by_id and by_id[mid]["conditions"]:
            out.append({"code": "max_wait", "member": mid, "months": months,
                        "text": f"Every plan for {by_id[mid]['name']} covers {by_id[mid]['name']}'s "
                                f"{names(c.replace('_', ' ') for c in by_id[mid]['conditions'])} within {duration(months)}."})
    if req.get("max_copay_percent") is not None:
        cap = req["max_copay_percent"]
        out.append({"code": "max_copay", "percent": cap,
                    "text": "No plan in this mix has a co-pay." if cap == 0 else f"No plan in this mix has a co-pay above {cap}%."})
    if req.get("uncapped_room_rent"):
        out.append({"code": "uncapped_room_rent", "text": "No plan in this mix caps room rent."})
    if req.get("avoid_insurers"):
        out.append({"code": "avoid_insurers", "insurers": req["avoid_insurers"],
                    "text": f"This mix leaves out {names(req['avoid_insurers'])}, as you asked."})
    if req.get("avoid_plan_types"):
        out.append({"code": "avoid_plan_types", "plan_types": req["avoid_plan_types"],
                    "text": f"This mix has no {names(PLAN_TYPE_NAMES[t] for t in req['avoid_plan_types'])}, as you asked."})
    if req.get("avoid_policies"):
        out.append({"code": "avoid_policies", "policy_ids": req["avoid_policies"],
                    "text": f"This mix leaves out {len(req['avoid_policies'])} "
                            f"{'plan' if len(req['avoid_policies']) == 1 else 'plans'} you asked to drop."})
    if req.get("one_insurer") and picks:
        out.append({"code": "one_insurer", "insurer": picks[0]["insurer"],
                    "text": f"Every plan in this mix is from {picks[0]['insurer']}."})
    if req.get("max_policies"):
        out.append({"code": "max_policies", "most": req["max_policies"],
                    "text": f"This mix has {len(picks)} {'policy' if len(picks) == 1 else 'policies'}, "
                            f"within the {req['max_policies']} you asked for."})
    return out


PLAN_TYPE_NAMES = {"floater": "family floater", "individual": "individual plan", "senior": "senior plan",
                   "super_topup": "super top-up"}


def cover_check(family, cands, target, total_cover):
    """Whether the mix reaches the cover the family asked for and, if not, what budget would."""
    if total_cover >= target:
        return {"code": "cover_met", "target": target, "total_cover": total_cover,
                "text": f"You asked for {lakhs(target)} of cover. This mix gives {lakhs(total_cover)}."}
    needed = cheapest_for(family, cands, target)
    out = {"target": target, "total_cover": total_cover, "shortfall": target - total_cover,
           "budget": family["budget"], "budget_needed": needed}
    if needed is None:
        return dict(out, code="cover_out_of_reach",
                    text=f"You asked for {lakhs(target)} of cover. No mix of the plans we have reaches that. "
                         f"This mix gives {lakhs(total_cover)}, the most your {inr(family['budget'])} budget can buy.")
    return dict(out, code="cover_short",
                text=f"You asked for {lakhs(target)} of cover. Your {inr(family['budget'])} budget reaches "
                     f"{lakhs(total_cover)}. {lakhs(target)} of cover needs about "
                     f"{inr(needed)} a year.")


def pick_out(c):
    p = c["policy"]
    return {
        "policy_id": p["id"], "insurer": p["insurer"], "product": p["product"], "plan_type": p["plan_type"],
        "members": c["members"], "sum_insured": p["sum_insured"], "deductible": p["deductible"],
        "premium": c["premium"], "copay_percent": p["copay_percent"],
        "waiting_periods_months": p["waiting_periods_months"], "catches": policy_catches(p),
        "source": p["source"],
    }


# Catches are built from the policy's fields, so the text cannot drift from the numbers the
# solver uses. other_catches in policies.json holds only what the fields do not say.

SUB_LIMIT_NAMES = {"cardiac": "heart treatment", "fracture": "fractures"}


def policy_catches(policy):
    waits = policy["waiting_periods_months"]
    out = []
    if is_topup(policy):
        out.append(f"Pays only after the year's bills cross {lakhs(policy['deductible'])}.")
    if policy["copay_percent"]:
        out.append(f"You pay {policy['copay_percent']}% of every claim.")
    out.append(f"Illnesses you already have are covered {'only ' if waits['pre_existing'] >= 36 else ''}"
               f"{years(waits['pre_existing'])}.")
    for cond, months in policy["condition_waits_months"].items():
        out.append(f"{cond.replace('_', ' ').capitalize()} is covered {years(months)}.")
    if waits["specific_illness"]:
        out.append(f"Some listed illnesses, like cataract and hernia, are covered only {years(waits['specific_illness'])}.")
    if policy["room_rent"]["capped"]:
        out.append(policy["room_rent"]["text"])
    # Sub-limits without a known amount share one sentence, so a card does not list five of them
    unknown = [s["item"] for s in policy["sub_limits"] if "Check the policy wording" in s["text"]]
    out += [s["text"] for s in policy["sub_limits"] if s["item"] not in unknown]
    if unknown:
        label = names(SUB_LIMIT_NAMES.get(i, i.replace("_", " ")) for i in unknown)
        one = len(unknown) == 1
        out.append(f"{label[0].upper() + label[1:]} {'has a sub-limit' if one else 'have sub-limits'}. "
                   f"Check the policy wording for the {'amount' if one else 'amounts'}.")
    if policy["plan_type"] == "floater":
        out.append("One cover is shared by everyone on the policy.")
    return out + policy["other_catches"]


# Reasons are facts the solver worked out, each with a code, the numbers behind it and
# a plain sentence. The explainer turns them into its answer and must not add its own.

def names(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def duration(months):
    if months % 12:
        return f"{months} months"
    return "1 year" if months == 12 else f"{months // 12} years"


def years(months):
    return f"after {duration(months)}" if months else "with no wait"


def wait_clause(policy, condition):
    if condition in policy["condition_waits_months"]:
        return f"condition_waits_months.{condition}"
    return "waiting_periods_months.pre_existing"


def base_index(cands, chosen, mid):
    return next((i for i in chosen if mid in cands[i]["members"] and not is_topup(cands[i]["policy"])), None)


def reasons_for(family, cands, chosen, i, floor=None):
    c, policy = cands[i], cands[i]["policy"]
    by_id = {m["id"]: m for m in family["members"]}
    group = [by_id[mid] for mid in c["members"]]
    reasons = []

    if policy["plan_type"] == "floater":
        eldest = max(group, key=lambda m: m["age"])
        reasons.append({"code": "priced_on_eldest", "member": eldest["id"], "age": eldest["age"],
                        "text": f"The premium is set by the eldest member, {eldest['name']}, age {eldest['age']}."})
        for m in family["members"]:
            if m["id"] in c["members"]:
                continue
            if not policy["entry_age"]["min"] <= m["age"] <= policy["entry_age"]["max"]:
                reasons.append({"code": "left_out", "member": m["id"], "why": "entry_age",
                                "clause": "entry_age", "max_entry_age": policy["entry_age"]["max"],
                                "text": f"{m['name']} is not in it. {policy['product']} takes members up to "
                                        f"age {policy['entry_age']['max']}."})
            elif len(group) < policy["max_members"]:
                with_them = premium_for(policy, [g["age"] for g in group] + [m["age"]])
                if with_them is not None:
                    reasons.append({"code": "left_out", "member": m["id"], "why": "premium",
                                    "premium_with_member": with_them,
                                    "text": f"{m['name']} is not in it. Adding {m['name']} would raise "
                                            f"this premium from {inr(c['premium'])} to {inr(with_them)}."})

    if is_topup(policy):
        below = {}
        for m in group:
            j = base_index(cands, chosen, m["id"])
            below.setdefault(cands[j]["policy"]["product"] if j is not None else "office cover", []).append(m["name"])
        reasons.append({"code": "topup_on_base", "deductible": policy["deductible"],
                        "sum_insured": policy["sum_insured"], "premium": c["premium"],
                        "text": f"Adds {inr(policy['sum_insured'])} of cover for {inr(c['premium'])} a year. "
                                f"It pays once a claim passes {inr(policy['deductible'])}. Below that, "
                                + "; ".join(f"{product} pays for {names(who)}" for product, who in below.items()) + "."})

    for m in group:
        for cond in m["conditions"]:
            months = condition_wait(policy, [cond])
            others = sorted({condition_wait(o["policy"], [cond]) for o in cands
                             if m["id"] in o["members"] and is_topup(o["policy"]) == is_topup(policy)
                             and o["policy"]["id"] != policy["id"]})
            text = f"{m['name']}'s {cond.replace('_', ' ')} is covered {years(months)}."
            if others and min(others) > months:
                text += f" Every other plan {m['name']} can join waits longer, at least {duration(others[0])}."
            elif others and min(others) < months:
                text += f" The shortest wait on another plan {m['name']} can join is {duration(others[0])}."
            reasons.append({"code": "condition_wait", "member": m["id"], "condition": cond,
                            "months": months, "other_options_months": others,
                            "clause": wait_clause(policy, cond), "text": text})

    reasons.append(next_best(family, cands, chosen, i, floor))
    return reasons


def member_terms(family, cands, idx):
    """Per member: total cover, plus wait, co-pay and room rent on their base policy."""
    office = office_cover(family)
    terms = {}
    for m in family["members"]:
        mine = [cands[j]["policy"] for j in idx if m["id"] in cands[j]["members"]]
        base = next((p for p in mine if not is_topup(p)), None)
        terms[m["id"]] = {
            "cover": office[m["id"]] + sum(p["sum_insured"] for p in mine),
            "wait": condition_wait(base, m["conditions"]) if base else 0,
            "copay": base["copay_percent"] if base else 0,
            "room_capped": base["room_rent"]["capped"] if base else False,
        }
    return terms


def next_best(family, cands, chosen, i, floor=None):
    """What the solver picks when this candidate is ruled out, compared with the chosen mix."""
    alt = optimise(family, cands, forbid=i, floor=floor)
    if alt is None:
        return {"code": "next_best", "possible": False,
                "text": f"Without this plan, no mix gives {lakhs(floor)} of cover within the budget." if floor
                        else "Without this plan, no mix covers everyone within the budget."}
    by_id = {m["id"]: m for m in family["members"]}

    def label(j):
        p = cands[j]["policy"]
        return f"{inr(p['sum_insured'])} {p['insurer']} {p['product']} for {names(by_id[mid]['name'] for mid in cands[j]['members'])}"

    premium_change = sum(cands[j]["premium"] for j in alt) - sum(cands[j]["premium"] for j in chosen)
    now, then = member_terms(family, cands, chosen), member_terms(family, cands, alt)
    changes = [{"member": mid, "term": term, "from": now[mid][term], "to": then[mid][term]}
               for mid in now for term in now[mid] if now[mid][term] != then[mid][term]]

    # One sentence per kind of change, naming everyone it applies to.
    grouped = {}
    for ch in changes:
        if ch["term"] == "cover":
            diff = ch["to"] - ch["from"]
            key = f"get{{s}} {inr(abs(diff))} {'more' if diff > 0 else 'less'} cover."
        elif ch["term"] == "wait":
            diff = ch["to"] - ch["from"]
            key = f"wait{{s}} {duration(abs(diff))} {'longer' if diff > 0 else 'less'} for existing illness cover."
        elif ch["term"] == "copay":
            key = f"pay{{s}} {ch['to']}% of each claim, against {ch['from']}% in the mix."
        else:
            key = f"get{{s}} {'capped' if ch['to'] else 'uncapped'} room rent."
        grouped.setdefault(key, []).append(by_id[ch["member"]]["name"])
    sentences = [names(who) + " " + key.format(s="s" if len(who) == 1 else "") for key, who in grouped.items()]
    if premium_change:
        sentences.insert(0, f"It costs {inr(abs(premium_change))} {'more' if premium_change > 0 else 'less'} a year.")
    swapped_in = [label(j) for j in alt if j not in chosen]
    text = f"The next best option uses {'; '.join(swapped_in) or 'fewer plans'}. " + " ".join(sentences)
    return {"code": "next_best", "possible": True, "swapped_in": swapped_in,
            "premium_change": premium_change, "changes": changes, "text": text.strip()}


def vs_usual(family, picks, usual):
    """How the mix compares with the usual single floater."""
    if usual is None:
        return []
    out = []
    saving = usual["premium"] - sum(p["premium"] for p in picks)
    out.append({"code": "premium", "saving": saving,
                "text": f"The mix costs {inr(abs(saving))} {'less' if saving >= 0 else 'more'} a year than "
                        f"one {inr(usual['sum_insured'])} {usual['product']} floater."})
    cover = member_cover(family, picks)
    for m in family["members"]:
        mine = cover[m["id"]]
        if mine != usual["sum_insured"]:
            out.append({"code": "member_cover", "member": m["id"], "mix": mine, "usual": usual["sum_insured"],
                        "text": f"{m['name']} gets {inr(mine)} of cover, against a shared {inr(usual['sum_insured'])}."})
    policies = {p["id"]: p for p in load_policies()}
    for m in family["members"]:
        if not m["conditions"]:
            continue
        base = next((p for p in picks if m["id"] in p["members"] and p["plan_type"] != "super_topup"), None)
        if base is None:
            continue
        mix_wait = condition_wait(policies[base["policy_id"]], m["conditions"])
        usual_wait = condition_wait(policies[usual["policy_id"]], m["conditions"])
        if mix_wait != usual_wait:
            out.append({"code": "condition_wait", "member": m["id"], "mix_months": mix_wait, "usual_months": usual_wait,
                        "text": f"{m['name']}'s {', '.join(m['conditions'])} is covered from year {mix_wait // 12 + 1}, "
                                f"against year {usual_wait // 12 + 1} with the usual pick."})
    return out


def mix_catches(family, picks):
    """Catches that come from how the picks stack, most serious first. Same shape as the reasons."""
    policies = {p["id"]: p for p in load_policies()}
    office = office_cover(family)
    by_id = {m["id"]: m for m in family["members"]}
    waits, copays, office_gaps, insurers, shared = [], {}, [], {}, []

    for m in family["members"]:
        mine = [p for p in picks if m["id"] in p["members"]]
        base = next((p for p in mine if p["plan_type"] != "super_topup"), None)
        topup = next((p for p in mine if p["plan_type"] == "super_topup"), None)
        if topup is None:
            continue

        for cond in m["conditions"] if base else []:
            base_wait = condition_wait(policies[base["policy_id"]], [cond])
            topup_wait = condition_wait(policies[topup["policy_id"]], [cond])
            if topup_wait <= base_wait:
                continue
            # Same year counting as claim_check: a 12-month wait ends at the start of year 2
            start, end = base_wait // 12 + 1, topup_wait // 12
            when = f"year {start}" if start == end else f"years {start} to {end}"
            label = cond.replace("_", " ")
            waits.append({"code": "topup_waits_longer", "members": [m["id"]],
                          "policy_ids": [base["policy_id"], topup["policy_id"]], "condition": cond,
                          "base_months": base_wait, "topup_months": topup_wait,
                          "clause": wait_clause(policies[topup["policy_id"]], cond),
                          "text": f"{m['name']}'s {label} is covered by {base['product']} {years(base_wait)} and by "
                                  f"the {topup['insurer']} top-up {years(topup_wait)}. In {when}, only {base['product']} pays "
                                  f"{label} claims, up to {lakhs(base['sum_insured'])}."})

        if base and base["copay_percent"]:
            copays.setdefault(base["policy_id"], (base, []))[1].append(m["id"])

        own = base["sum_insured"] if base else 0
        if office[m["id"]] and own < topup["deductible"]:
            gap = f"between {lakhs(own)} and {lakhs(topup['deductible'])}" if own else f"up to {lakhs(topup['deductible'])}"
            office_gaps.append({"code": "topup_on_office_cover", "members": [m["id"]], "policy_ids": [topup["policy_id"]],
                                "office_cover": office[m["id"]], "deductible": topup["deductible"], "clause": "deductible",
                                "text": f"{m['name']}'s top-up counts the {lakhs(office[m['id']])} office cover toward its "
                                        f"{lakhs(topup['deductible'])} deductible. If {m['name']} leaves the job, bills "
                                        f"{gap} are not covered."})

        if base and base["insurer"] != topup["insurer"]:
            insurers.setdefault((base["insurer"], topup["policy_id"]), (base, topup, []))[2].append(m["id"])

    for base, who in copays.values():
        share = base["sum_insured"] * base["copay_percent"] // 100
        copays[base["policy_id"]] = {
            "code": "copay_under_topup", "members": who, "policy_ids": [base["policy_id"]],
            "copay_percent": base["copay_percent"], "most_paid": share, "clause": "copay_percent",
            "text": f"{base['product']} makes {names(by_id[mid]['name'] for mid in who)} pay {base['copay_percent']}% "
                    f"of each claim it covers. On a big bill, that share can reach {inr(share)}. The top-up does not pay it."}

    for key, (base, topup, who) in list(insurers.items()):
        bases = [p["policy_id"] for p in picks if p["plan_type"] != "super_topup" and set(p["members"]) & set(who)]
        insurers[key] = {
            "code": "two_insurers", "members": who, "policy_ids": list(dict.fromkeys(bases)) + [topup["policy_id"]],
            "clause": "insurer",
            "text": f"{names(by_id[mid]['name'] for mid in who)}'s base {'plan is' if len(who) == 1 else 'plans are'} "
                    f"from {base['insurer']} and the top-up "
                    f"from {topup['insurer']}. A bill above {lakhs(topup['deductible'])} means two claims, and "
                    f"{topup['insurer']} asks for {base['insurer']}'s settlement papers."}

    for topup in picks:
        if topup["plan_type"] != "super_topup" or len(topup["members"]) < 2:
            continue
        floater = next((p for p in picks if p["plan_type"] == "floater" and set(p["members"]) == set(topup["members"])), None)
        who = names(by_id[mid]["name"] for mid in topup["members"])
        what = (f"the {lakhs(floater['sum_insured'])} floater and the {lakhs(topup['sum_insured'])} top-up" if floater
                else f"the {lakhs(topup['sum_insured'])} top-up")
        others = "the other" if len(topup["members"]) == 2 else "the others"
        shared.append({"code": "shared_cover", "members": topup["members"],
                       "policy_ids": [p["policy_id"] for p in (floater, topup) if p], "clause": "sum_insured",
                       "text": f"{who} share {what}. A big claim for one of them leaves less for {others} that year."})

    return waits + list(copays.values()) + office_gaps + list(insurers.values()) + shared


def member_cover(family, picks):
    cover = office_cover(family)
    for p in picks:
        for mid in p["members"]:
            cover[mid] += p["sum_insured"]
    return cover


def usual_pick(family, policies):
    """The single floater for everyone with the most cover, the way it is usually sold."""
    ages = [m["age"] for m in family["members"]]
    limit = family["budget"] * USUAL_PICK_BUDGET_STRETCH
    best = None
    for p in policies:
        if p["plan_type"] != "floater" or len(ages) > p["max_members"] or len(ages) < 2:
            continue
        if not all(p["entry_age"]["min"] <= a <= p["entry_age"]["max"] for a in ages):
            continue
        premium = premium_for(p, ages)
        if premium is None or premium > limit:
            continue
        key = (p["sum_insured"], -premium)
        if best is None or key > best[0]:
            best = (key, p, premium)
    if best is None:
        return None
    _, p, premium = best
    return pick_out({"policy": p, "members": [m["id"] for m in family["members"]], "premium": premium})


def inr(amount):
    """Rupees with Indian digit grouping, like ₹1,80,000."""
    digits = str(int(amount))
    head, tail = digits[:-3], digits[-3:]
    while len(head) > 2:
        tail = head[-2:] + "," + tail
        head = head[:-2]
    return "₹" + (head + "," + tail if head else tail)


def lakhs(amount):
    """Cover amounts the way policies state them, like ₹10 lakh, ₹1 crore or ₹1.05 crore."""
    if amount and amount >= 100 * LAKH and amount % LAKH == 0:
        return f"₹{amount / (100 * LAKH):g} crore"
    if amount and amount % LAKH == 0:
        return f"₹{amount // LAKH} lakh"
    return inr(amount)


def claim_check(family, picks, member_id, amount, policy_year, related_condition=None, treatment=None):
    """Works out what a claim pays in a given policy year, for any set of picks."""
    policies = {p["id"]: p for p in load_policies()}
    member = next(m for m in family["members"] if m["id"] == member_id)
    conditions = [related_condition] if related_condition in member["conditions"] else []
    notes, payable, wait_left = [], 0, 0

    def waits_for(policy):
        waits = policy["waiting_periods_months"]
        listed = waits["specific_illness"] if treatment in LISTED_ILLNESSES else 0
        return max(condition_wait(policy, conditions), waits["initial"], listed)

    def first_year(wait):
        """A wait of under a year ends inside year 1, 12 months ends at the start of year 2, and so on."""
        return wait // 12 + 1

    mine = [p for p in picks if member_id in p["members"]]
    base = next((p for p in mine if p["plan_type"] != "super_topup"), None)
    topup = next((p for p in mine if p["plan_type"] == "super_topup"), None)

    if base:
        policy = policies[base["policy_id"]]
        wait = waits_for(policy)
        if policy_year >= first_year(wait):
            paid = min(amount, base["sum_insured"])
            copay = paid * base["copay_percent"] // 100
            payable += paid - copay
            if copay:
                notes.append(f"{base['product']} pays after a {base['copay_percent']}% co-pay of {inr(copay)}.")
        else:
            wait_left = max(wait_left, wait)
            notes.append(f"{base['product']} covers this only from year {first_year(wait)}.")
        for sub in policy["sub_limits"]:
            if treatment and sub["item"] == treatment:
                notes.append(sub["text"])

    if topup and amount > topup["deductible"]:
        policy = policies[topup["policy_id"]]
        wait = waits_for(policy)
        if policy_year >= first_year(wait):
            payable += min(amount - topup["deductible"], topup["sum_insured"])
        else:
            notes.append(f"{topup['product']} covers this only from year {first_year(wait)}.")

    payable = min(payable, amount)
    return {
        "member_id": member_id, "amount": amount, "policy_year": policy_year,
        "covered": payable > 0, "payable": payable, "out_of_pocket": amount - payable,
        "covered_from_year": first_year(wait_left) if wait_left else policy_year,
        "notes": notes,
    }


if __name__ == "__main__":
    family = load_families()["demo-pune"]
    result = solve(family)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    for name, picks in (("mix", result["picks"]), ("usual", [result["usual_pick"]])):
        check = claim_check(family, picks, "mohan", 600_000, 2, "diabetes", "cardiac")
        print(name, json.dumps(check, ensure_ascii=False))
