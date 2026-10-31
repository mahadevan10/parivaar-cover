"""Run from backend/: .venv/bin/python -m unittest test_app -v

Sarvam is replaced with a stub, so these tests run offline.
"""
import copy
import unittest
from unittest import mock

from fastapi.testclient import TestClient

import app
import solver

client = TestClient(app.app)
DEMO = solver.load_families()["demo-pune"]


class Recommend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = client.post("/recommend", json={"family": DEMO})
        cls.body = cls.res.json()

    def test_returns_the_deck_mix_with_an_id(self):
        self.assertEqual(self.res.status_code, 200)
        self.assertEqual(self.body["total_premium"], 107000)
        self.assertTrue(self.body["id"].startswith("rec-"))
        self.assertIn(self.body["id"], app.RECOMMENDATIONS)

    def test_default_claim_is_mohans_heart_procedure_for_years_1_to_4(self):
        [claim] = self.body["claim_checks"]
        self.assertEqual(claim["label"], "₹6,00,000 heart procedure for Mohan")
        covered = [(y["year"], y["mix"]["covered"], y["usual"]["covered"]) for y in claim["by_year"]]
        self.assertEqual(covered, [(1, False, False), (2, True, False), (3, True, False), (4, True, True)])

    def test_budget_too_small(self):
        body = client.post("/recommend", json={"family": dict(DEMO, budget=20000)}).json()
        self.assertEqual(body["status"], "no_fit")
        self.assertEqual(body["claim_checks"], [])

    def test_rejects_missing_age_and_unknown_claim_member(self):
        family = dict(DEMO, members=[{"id": "x", "name": "X"}])
        self.assertEqual(client.post("/recommend", json={"family": family}).status_code, 422)
        claims = [{"member_id": "nobody", "amount": 100000}]
        self.assertEqual(client.post("/recommend", json={"family": DEMO, "claims": claims}).status_code, 422)


class Intake(unittest.TestCase):
    def test_cleans_the_llm_family_and_works_out_what_is_missing(self):
        reply = {"reply": "Noted. Which city do you live in?", "family": {
            "members": [{"name": "Mohan", "age": "64", "relation": "father", "conditions": ["Diabetic", "high BP"]},
                        {"id": "lata", "name": "Lata", "age": None, "relation": "mother", "conditions": []}],
            "budget": "1,10,000", "health_checked": True}}
        with mock.patch.object(app.llm, "ask_json", return_value=reply):
            body = client.post("/chat", json={"message": "My father Mohan is 64, diabetic and has high BP. Mother Lata."}).json()
        mohan, lata = body["family"]["members"]
        self.assertEqual((mohan["id"], mohan["age"], mohan["conditions"]), ("mohan", 64, ["diabetes", "hypertension"]))
        self.assertIsNone(lata["age"])
        self.assertEqual(body["family"]["budget"], 110000)
        self.assertEqual(body["missing"], ["Lata's age", "Office cover", "City"])
        self.assertEqual(body["reply"], "Noted. Which city do you live in?")  # the LLM asked, so no second question
        self.assertFalse(body["ready"])

    def test_drops_ages_and_conditions_the_user_never_said(self):
        reply = {"reply": "noted.", "family": {"members": [
            {"id": "self", "name": "rahul", "age": 36, "conditions": []},
            {"name": "Sneha", "age": 33, "conditions": ["diabetes"]},
            {"name": "Mohan", "age": 64, "conditions": ["sugar"]}]}}
        with mock.patch.object(app.llm, "ask_json", return_value=reply):
            body = client.post("/chat", json={"message": "I am Rahul, 36. Wife Sneha. Father Mohan has sugar."}).json()
        self.assertEqual(body["reply"], "Noted. How old is Sneha?")
        got = [(m["id"], m["name"], m["age"], m["conditions"]) for m in body["family"]["members"]]
        self.assertEqual(got, [("rahul", "Rahul", 36, []), ("sneha", "Sneha", None, []), ("mohan", "Mohan", None, ["diabetes"])])

    def test_short_answer_counts_for_the_member_asked_about(self):
        family = {"members": [{"id": "lata", "name": "Lata", "age": None, "relation": "mother", "conditions": []}]}
        reply = {"reply": "Thanks.", "family": {"members": [{"name": "Lata", "age": 60, "relation": "mother"}]}}
        history = [{"role": "assistant", "content": "How old is Lata?"}]
        with mock.patch.object(app.llm, "ask_json", return_value=reply):
            body = client.post("/chat", json={"message": "60", "family": family, "history": history}).json()
        self.assertEqual(body["family"]["members"][0]["age"], 60)

    def test_office_cover_needs_the_user_to_mention_it(self):
        reply = {"reply": "Noted.", "family": {"members": [], "office_checked": True}}
        with mock.patch.object(app.llm, "ask_json", return_value=reply):
            body = client.post("/chat", json={"message": "No one else is ill"}).json()
        self.assertIn("Office cover", body["missing"])

    def test_ready_when_nothing_is_missing(self):
        family = dict(copy.deepcopy(DEMO), health_checked=True, office_checked=True)
        with mock.patch.object(app.llm, "ask_json", return_value={"reply": "Ready.", "family": copy.deepcopy(family)}):
            body = client.post("/chat", json={"message": "That is all", "family": family}).json()
        self.assertTrue(body["ready"])
        self.assertEqual([m["id"] for m in body["family"]["members"]], [m["id"] for m in DEMO["members"]])

    def test_sarvam_failure_is_a_502(self):
        with mock.patch.object(app.llm, "ask_json", side_effect=RuntimeError("down")):
            self.assertEqual(client.post("/chat", json={"message": "hi"}).status_code, 502)


class Explain(unittest.TestCase):
    def test_answers_from_the_recommendation_and_drops_unknown_citations(self):
        rec_id = client.post("/recommend", json={"family": DEMO}).json()["id"]
        reply = {"reply": "Mohan's diabetes is covered after 1 year.",
                 "citations": ["star-red-carpet-10l", "made-up-policy"]}
        with mock.patch.object(app.llm, "ask_json", return_value=reply) as ask:
            body = client.post("/chat", json={"message": "Why Red Carpet?", "recommendation_id": rec_id}).json()
        self.assertEqual(body["citations"], ["star-red-carpet-10l"])
        self.assertIn("Mohan's diabetes is covered after 1 year.", ask.call_args.args[0])

    def test_unknown_recommendation_is_a_404(self):
        self.assertEqual(client.post("/chat", json={"message": "hi", "recommendation_id": "rec-x"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
