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


def load_policies():
    return json.loads((SHARED / "policies.json").read_text())["policies"]


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


def optimise(family, cands, forbid=None):
    """Indices of the best candidates to buy, or None when nothing fits the budget.

    forbid rules out one candidate, which shows what the solver would pick without it.
    """
    office = office_cover(family)
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
        counted = model.NewIntVar(0, target_lakhs(m), f"counted_{mid}")
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

    model.Add(sum(c["premium"] * x[i] for i, c in enumerate(cands)) <= family["budget"])
    if forbid is not None:
        model.Add(x[forbid] == 0)
    objective += [-(c["premium"] + c["penalty"]) * x[i] for i, c in enumerate(cands)]
    model.Maximize(sum(objective))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [i for i in range(len(cands)) if solver.Value(x[i])]


def solve(family, policies=None):
    policies = policies or load_policies()
    cands = candidates(family, policies)
    chosen = optimise(family, cands)
    if chosen is None:
        return {"status": "no_fit", "family_id": family["id"], "budget": family["budget"],
                "message": "No mix covers everyone within this budget."}

    picks = [dict(pick_out(cands[i]), reasons=reasons_for(family, cands, chosen, i)) for i in chosen]
    picks.sort(key=lambda p: (p["plan_type"] == "super_topup", -len(p["members"])))
    usual = usual_pick(family, policies)
    total = sum(p["premium"] for p in picks)
    return {
        "status": "ok",
        "family_id": family["id"],
        "budget": family["budget"],
        "illustrative": True,
        "picks": picks,
        "total_premium": total,
        "total_cover": sum(p["sum_insured"] for p in picks),
        "member_cover": member_cover(family, picks),
        "usual_pick": usual,
        "saving_vs_usual": usual["premium"] - total if usual else None,
        "vs_usual": vs_usual(family, picks, usual),
    }


def pick_out(c):
    p = c["policy"]
    return {
        "policy_id": p["id"], "insurer": p["insurer"], "product": p["product"], "plan_type": p["plan_type"],
        "members": c["members"], "sum_insured": p["sum_insured"], "deductible": p["deductible"],
        "premium": c["premium"], "copay_percent": p["copay_percent"],
        "waiting_periods_months": p["waiting_periods_months"], "catches": p["catches"],
        "source": p["source"],
    }


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


def reasons_for(family, cands, chosen, i):
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

    reasons.append(next_best(family, cands, chosen, i))
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


def next_best(family, cands, chosen, i):
    """What the solver picks when this candidate is ruled out, compared with the chosen mix."""
    alt = optimise(family, cands, forbid=i)
    if alt is None:
        return {"code": "next_best", "possible": False,
                "text": "Without this plan, no mix covers everyone within the budget."}
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


def claim_check(family, picks, member_id, amount, policy_year, related_condition=None, treatment=None):
    """Works out what a claim pays in a given policy year, for any set of picks."""
    policies = {p["id"]: p for p in load_policies()}
    member = next(m for m in family["members"] if m["id"] == member_id)
    conditions = [related_condition] if related_condition in member["conditions"] else []
    months_in_force = (policy_year - 1) * 12
    notes, payable, wait_left = [], 0, 0

    def waits_for(policy):
        return max(condition_wait(policy, conditions), policy["waiting_periods_months"]["initial"])

    mine = [p for p in picks if member_id in p["members"]]
    base = next((p for p in mine if p["plan_type"] != "super_topup"), None)
    topup = next((p for p in mine if p["plan_type"] == "super_topup"), None)

    if base:
        policy = policies[base["policy_id"]]
        wait = waits_for(policy)
        if months_in_force >= wait:
            paid = min(amount, base["sum_insured"])
            copay = paid * base["copay_percent"] // 100
            payable += paid - copay
            if copay:
                notes.append(f"{base['product']} pays after a {base['copay_percent']}% co-pay of {inr(copay)}.")
        else:
            wait_left = max(wait_left, wait)
            notes.append(f"{base['product']} covers this only from year {wait // 12 + 1}.")
        for sub in policy["sub_limits"]:
            if treatment and sub["item"] == treatment:
                notes.append(sub["text"])

    if topup and amount > topup["deductible"]:
        policy = policies[topup["policy_id"]]
        wait = waits_for(policy)
        if months_in_force >= wait:
            payable += min(amount - topup["deductible"], topup["sum_insured"])
        else:
            notes.append(f"{topup['product']} covers this only from year {wait // 12 + 1}.")

    payable = min(payable, amount)
    return {
        "member_id": member_id, "amount": amount, "policy_year": policy_year,
        "covered": payable > 0, "payable": payable, "out_of_pocket": amount - payable,
        "covered_from_year": wait_left // 12 + 1 if wait_left else policy_year,
        "notes": notes,
    }


if __name__ == "__main__":
    family = load_families()["demo-pune"]
    result = solve(family)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    for name, picks in (("mix", result["picks"]), ("usual", [result["usual_pick"]])):
        check = claim_check(family, picks, "mohan", 600_000, 2, "diabetes", "cardiac")
        print(name, json.dumps(check, ensure_ascii=False))
