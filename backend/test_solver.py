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

    def test_mix_catches(self):
        found = {(c["code"], tuple(c["members"])) for c in self.result["mix_catches"]}
        self.assertEqual(found, {
            ("topup_waits_longer", ("mohan",)),
            ("copay_under_topup", ("mohan",)),
            ("two_insurers", ("mohan",)),
            ("two_insurers", ("lata",)),
            ("shared_cover", ("rahul", "sneha", "aarav")),
            ("shared_cover", ("mohan", "lata")),
        })
        self.assertEqual(self.result["mix_catches"][0]["code"], "topup_waits_longer")
        wait = self.result["mix_catches"][0]
        self.assertEqual((wait["base_months"], wait["topup_months"]), (12, 24))
        self.assertIn("In year 2, only Senior Citizens Red Carpet pays", wait["text"])

    def test_topup_wait_matches_the_claim_check(self):
        # A diabetes claim above the deductible in year 2: only Red Carpet pays, after its 30% co-pay
        check = solver.claim_check(self.family, self.result["picks"], "mohan", 1500000, 2, "diabetes")
        self.assertEqual(check["payable"], 700000)
        copay = next(c for c in self.result["mix_catches"] if c["code"] == "copay_under_topup")
        self.assertEqual(copay["most_paid"], 300000)
        self.assertEqual(check["out_of_pocket"] - 500000, copay["most_paid"])

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


class CoverTarget(unittest.TestCase):
    def solve(self, **changes):
        return solver.solve(dict(FAMILIES["demo-pune"], **changes), POLICIES)

    def test_one_crore_keeps_the_deck_mix(self):
        result = self.solve(cover_target=10000000)
        self.assertEqual(result["total_premium"], 107000)
        self.assertEqual(result["cover_check"]["code"], "cover_met")
        self.assertEqual(result["cover_check"]["text"], "You asked for ₹1 crore of cover. This mix gives ₹1.05 crore.")

    def test_a_higher_target_buys_more_cover_within_the_budget(self):
        result = self.solve(cover_target=30000000)
        self.assertGreaterEqual(result["total_cover"], 30000000)
        self.assertLessEqual(result["total_premium"], 110000)
        self.assertEqual(result["cover_check"]["code"], "cover_met")

    def test_budget_comes_first_and_says_what_the_cover_needs(self):
        result = self.solve(cover_target=10000000, budget=42000)
        check = result["cover_check"]
        self.assertEqual(result["status"], "ok")
        self.assertLessEqual(result["total_premium"], 42000)
        self.assertLess(result["total_cover"], 10000000)
        self.assertEqual(check["code"], "cover_short")
        self.assertEqual(check["shortfall"], 10000000 - result["total_cover"])
        self.assertGreater(check["budget_needed"], 42000)
        self.assertIn("₹42,000 budget reaches", check["text"])
        # The suggested budget really buys the cover
        again = self.solve(cover_target=10000000, budget=check["budget_needed"])
        self.assertEqual(again["cover_check"]["code"], "cover_met")

    def test_short_mix_has_the_most_cover_the_budget_allows(self):
        short = self.solve(cover_target=10000000, budget=42000)
        for target in (short["total_cover"] + solver.LAKH, 10000000 - solver.LAKH):
            self.assertLess(self.solve(cover_target=target, budget=42000)["total_cover"], target)

    def test_a_target_no_mix_reaches(self):
        check = self.solve(cover_target=1_000_000_000)["cover_check"]
        self.assertEqual(check["code"], "cover_out_of_reach")
        self.assertIsNone(check["budget_needed"])

    def test_no_target_means_no_cover_check(self):
        result = self.solve(cover_target=None)
        self.assertIsNone(result["cover_check"])
        self.assertEqual(result["total_premium"], 107000)


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
        result = self.check_valid("office-cover-lucknow")
        gaps = {c["members"][0]: c for c in result["mix_catches"] if c["code"] == "topup_on_office_cover"}
        self.assertEqual(set(gaps), {"imran", "ayesha", "zoya"})
        self.assertIn("bills between ₹5 lakh and ₹10 lakh are not covered", gaps["imran"]["text"])
        self.assertIn("bills up to ₹5 lakh are not covered", gaps["ayesha"]["text"])

    def test_budget_too_small(self):
        family = dict(FAMILIES["demo-pune"], budget=20000)
        self.assertEqual(solver.solve(family, POLICIES)["status"], "no_fit")


class Catches(unittest.TestCase):
    def test_built_from_the_fields(self):
        red_carpet = next(p for p in POLICIES if p["id"] == "star-red-carpet-10l")
        self.assertEqual(solver.policy_catches(red_carpet), [
            "You pay 30% of every claim.",
            "Illnesses you already have are covered after 1 year.",
            "Some listed illnesses, like cataract and hernia, are covered only after 2 years.",
            "Room rent up to 1% of the cover, at most ₹4,000 a day.",
            "Heart treatment, cataract, stroke, cancer and fractures have sub-limits. Check the policy wording for the amounts.",
        ])
        topup = next(p for p in POLICIES if p["id"] == "cigna-super-top-up-25l-10l")
        self.assertEqual(solver.policy_catches(topup)[0], "Pays only after the year's bills cross ₹10 lakh.")

    def test_other_catches_do_not_repeat_the_fields(self):
        for p in POLICIES:
            built = solver.policy_catches(dict(p, other_catches=[]))
            self.assertFalse(set(p["other_catches"]) & set(built), p["id"])


class Formatting(unittest.TestCase):
    def test_inr(self):
        self.assertEqual(solver.inr(180000), "₹1,80,000")
        self.assertEqual(solver.inr(10500000), "₹1,05,00,000")
        self.assertEqual(solver.inr(950), "₹950")

    def test_lakhs(self):
        self.assertEqual(solver.lakhs(1000000), "₹10 lakh")
        self.assertEqual(solver.lakhs(10000000), "₹1 crore")
        self.assertEqual(solver.lakhs(10500000), "₹1.05 crore")
        self.assertEqual(solver.lakhs(250000), "₹2,50,000")


if __name__ == "__main__":
    unittest.main()
