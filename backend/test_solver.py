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

    def test_mohan_heart_claim_in_year_2(self):
        mix = solver.claim_check(self.family, self.result["picks"], "mohan", 600000, 2, "diabetes", "cardiac")
        usual = solver.claim_check(self.family, [self.result["usual_pick"]], "mohan", 600000, 2, "diabetes", "cardiac")
        self.assertTrue(mix["covered"])
        self.assertEqual(mix["payable"], 420000)  # 30% co-pay on Red Carpet
        self.assertFalse(usual["covered"])
        self.assertEqual(usual["covered_from_year"], 4)


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


if __name__ == "__main__":
    unittest.main()
