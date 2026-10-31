"""Run from backend/: .venv/bin/python -m unittest test_solver -v"""
import unittest

import solver

FAMILIES = solver.load_families()
POLICIES = solver.load_policies()


class DemoFamily(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.family = FAMILIES["demo-pune"]
        cls.result = solver.solve(cls.family, POLICIES)

    def test_picks_the_deck_mix(self):
        picks = {(p["policy_id"], tuple(p["members"]), p["premium"]) for p in self.result["picks"]}
        self.assertEqual(picks, {
            ("star-young-star-gold-10l-floater", ("rahul", "sneha", "aarav"), 21000),
            ("star-super-surplus-gold-50l-10l", ("rahul", "sneha", "aarav"), 4500),
            ("star-red-carpet-10l", ("mohan",), 41000),
            ("reliance-health-infinity-10l", ("lata",), 24500),
            ("cigna-super-top-up-25l-10l", ("mohan", "lata"), 16000),
        })
        self.assertEqual(self.result["total_premium"], 107000)
        self.assertEqual(self.result["total_cover"], 105 * solver.LAKH)

    def test_usual_pick_is_the_25l_floater(self):
        usual = self.result["usual_pick"]
        self.assertEqual(usual["sum_insured"], 25 * solver.LAKH)
        self.assertEqual(usual["premium"], 118000)
        self.assertEqual(usual["waiting_periods_months"]["pre_existing"], 36)
        self.assertEqual(self.result["saving_vs_usual"], 11000)

    def test_every_pick_has_reasons_ending_in_next_best(self):
        for p in self.result["picks"]:
            self.assertTrue(all(r["text"] for r in p["reasons"]), p["policy_id"])
            self.assertEqual(p["reasons"][-1]["code"], "next_best", p["policy_id"])

    def test_senior_plan_reasons_cite_the_short_diabetes_wait(self):
        reasons = next(p for p in self.result["picks"] if p["policy_id"] == "star-red-carpet-10l")["reasons"]
        wait = next(r for r in reasons if r["code"] == "condition_wait")
        self.assertEqual((wait["member"], wait["months"]), ("mohan", 12))
        self.assertEqual(wait["clause"], "waiting_periods_months.pre_existing")
        changes = reasons[-1]["changes"]
        self.assertIn({"member": "mohan", "term": "wait", "from": 12, "to": 24}, changes)

    def test_vs_usual_reasons(self):
        codes = {(r["code"], r.get("member")) for r in self.result["vs_usual"]}
        self.assertIn(("premium", None), codes)
        self.assertIn(("condition_wait", "mohan"), codes)
        wait = next(r for r in self.result["vs_usual"] if r["code"] == "condition_wait")
        self.assertEqual((wait["mix_months"], wait["usual_months"]), (12, 36))

    def test_mohan_heart_claim_in_year_2(self):
        mix = solver.claim_check(self.family, self.result["picks"], "mohan", 600000, 2, "diabetes", "cardiac")
        usual = solver.claim_check(self.family, [self.result["usual_pick"]], "mohan", 600000, 2, "diabetes", "cardiac")
        self.assertTrue(mix["covered"])
        self.assertEqual(mix["payable"], 420000)  # 30% co-pay on Red Carpet
        self.assertFalse(usual["covered"])
        self.assertEqual(usual["covered_from_year"], 4)

    def test_hospital_stay_in_year_1(self):
        for picks in (self.result["picks"], [self.result["usual_pick"]]):
            check = solver.claim_check(self.family, picks, "rahul", 300000, 1)
            self.assertTrue(check["covered"])
            self.assertEqual(check["payable"], 300000)
            self.assertEqual(check["covered_from_year"], 1)

    def test_listed_illness_waits_2_years(self):
        for year, covered in ((1, False), (2, False), (3, True)):
            check = solver.claim_check(self.family, self.result["picks"], "lata", 300000, year, None, "knee")
            self.assertEqual(check["covered"], covered, year)
            self.assertEqual(check["covered_from_year"], 3 if not covered else year)


class OtherFamilies(unittest.TestCase):
    def check_valid(self, family_id):
        family = FAMILIES[family_id]
        result = solver.solve(family, POLICIES)
        self.assertEqual(result["status"], "ok")
        self.assertLessEqual(result["total_premium"], family["budget"])
        office = solver.office_cover(family)
        for m in family["members"]:
            mine = [p for p in result["picks"] if m["id"] in p["members"]]
            bases = [p for p in mine if p["plan_type"] != "super_topup"]
            self.assertLessEqual(len(bases), 1, m["id"])
            if not office[m["id"]]:
                self.assertEqual(len(bases), 1, m["id"])
            for p in mine:
                policy = next(x for x in POLICIES if x["id"] == p["policy_id"])
                self.assertTrue(policy["entry_age"]["min"] <= m["age"] <= policy["entry_age"]["max"], m["id"])
        return result

    def test_young_couple(self):
        self.check_valid("young-couple-bengaluru")

    def test_single_parent_with_senior(self):
        result = self.check_valid("single-parent-chennai")
        ramesh = [p for p in result["picks"] if "ramesh" in p["members"]]
        self.assertTrue(all(p["plan_type"] in ("senior", "super_topup") for p in ramesh))

    def test_office_cover(self):
        self.check_valid("office-cover-lucknow")

    def test_budget_too_small(self):
        family = dict(FAMILIES["demo-pune"], budget=20000)
        self.assertEqual(solver.solve(family, POLICIES)["status"], "no_fit")


class Formatting(unittest.TestCase):
    def test_inr(self):
        self.assertEqual(solver.inr(180000), "₹1,80,000")
        self.assertEqual(solver.inr(10500000), "₹1,05,00,000")
        self.assertEqual(solver.inr(950), "₹950")



class MinCover(unittest.TestCase):
    def with_min_cover(self, amount, budget=None):
        family = FAMILIES["demo-pune"]
        members = [dict(m, min_cover=amount) if m["id"] == "mohan" else m for m in family["members"]]
        return dict(family, members=members, budget=budget or family["budget"])

    def test_gives_the_member_at_least_the_cover_asked_for(self):
        result = solver.solve(self.with_min_cover(50 * solver.LAKH, budget=200000), POLICIES)
        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(result["member_cover"]["mohan"], 50 * solver.LAKH)

    def test_no_fit_says_the_budget_needed(self):
        family = self.with_min_cover(100 * solver.LAKH, budget=80000)
        result = solver.solve(family, POLICIES)
        self.assertEqual(result["status"], "no_fit")
        again = solver.solve(dict(family, budget=result["budget_needed"]), POLICIES)
        self.assertEqual(again["status"], "ok")
        self.assertEqual(solver.solve(dict(family, budget=result["budget_needed"] - 1), POLICIES)["status"], "no_fit")

    def test_no_budget_needed_when_no_plan_goes_that_high(self):
        result = solver.solve(self.with_min_cover(500 * solver.LAKH), POLICIES)
        self.assertEqual(result["status"], "no_fit")
        self.assertIsNone(result["budget_needed"])


if __name__ == "__main__":
    unittest.main()
