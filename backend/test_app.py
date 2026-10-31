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
        self.assertEqual(self.body["solution"]["total_premium"], 107000)
        self.assertTrue(self.body["id"].startswith("rec-"))
        self.assertEqual(self.body["solution"]["id"], self.body["id"])
        self.assertIn(self.body["id"], app.RECOMMENDATIONS)

    def test_default_claims_for_years_1_to_4(self):
        heart, cancer = self.body["claim_checks"]
        self.assertEqual((heart["id"], heart["label"], heart["amount"]), ("mohan-cardiac", "Heart procedure", 600000))
        covered = [(y["policy_year"], y["mix"]["covered"], y["usual"]["covered"]) for y in heart["by_year"]]
        self.assertEqual(covered, [(1, False, False), (2, True, False), (3, True, False), (4, True, True)])
        self.assertEqual((cancer["id"], cancer["member_id"]), ("rahul-cancer", "rahul"))

    def test_budget_too_small(self):
        body = client.post("/recommend", json={"family": dict(DEMO, budget=20000)}).json()
        self.assertEqual(body["solution"]["status"], "no_fit")
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
        self.assertFalse(body["readyToOptimise"])
        self.assertEqual(mohan["heardFrom"], "My father Mohan is 64, diabetic and has high BP. Mother Lata.")

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
        family = {"members": [{"id": "lata", "name": "Lata", "relation": "mother", "conditions": []}]}
        reply = {"reply": "Thanks.", "family": {"members": [{"name": "Lata", "age": 60, "relation": "mother"}]}}
        history = [{"role": "assistant", "text": "How old is Lata?"}]
        with mock.patch.object(app.llm, "ask_json", return_value=reply):
            body = client.post("/chat", json={"message": "60", "family": family, "history": history}).json()
        self.assertEqual(body["family"]["members"][0]["age"], 60)

    def test_office_cover_needs_the_user_to_mention_it(self):
        reply = {"reply": "Noted.", "family": {"members": [], "office_checked": True}}
        with mock.patch.object(app.llm, "ask_json", return_value=reply):
            body = client.post("/chat", json={"message": "No one else is ill"}).json()
        self.assertIn("Office cover", body["missing"])
        self.assertEqual(body["quickReplies"], [])  # "Who is in the family" comes first

    def test_ready_when_nothing_is_missing(self):
        llm_family = dict(copy.deepcopy(DEMO), health_checked=True, office_checked=True)
        family = {"members": copy.deepcopy(DEMO["members"]), "city": "Pune", "budget": 110000,
                  "healthChecked": True, "officeChecked": True}
        with mock.patch.object(app.llm, "ask_json", return_value={"reply": "Ready.", "family": llm_family}):
            body = client.post("/chat", json={"sessionId": "s1", "message": "That is all", "family": family}).json()
        self.assertTrue(body["readyToOptimise"])
        self.assertTrue(all(m["heardFrom"] is None for m in body["family"]["members"]))
        self.assertEqual([m["id"] for m in body["family"]["members"]], [m["id"] for m in DEMO["members"]])

    def test_sarvam_failure_is_a_502(self):
        with mock.patch.object(app.llm, "ask_json", side_effect=RuntimeError("down")):
            self.assertEqual(client.post("/chat", json={"message": "hi"}).status_code, 502)


class QuickReplies(unittest.TestCase):
    def test_offers_a_reply_for_yes_no_questions(self):
        family = app.clean_family({"members": [{"name": "Mohan", "age": 64, "conditions": ["diabetes"]}]}, {})
        self.assertEqual(app.quick_replies(family, ["Health conditions"]), ["No one else has one"])
        self.assertEqual(app.quick_replies(family, ["Office cover"]), ["No office cover"])


class Explain(unittest.TestCase):
    def test_answers_from_the_recommendation_and_drops_unknown_citations(self):
        rec_id = client.post("/recommend", json={"family": DEMO}).json()["id"]
        reply = {"reply": "Mohan's diabetes is covered after 1 year.",
                 "citations": ["star-red-carpet-10l", "made-up-policy"]}
        with mock.patch.object(app.llm, "ask_json", return_value=reply) as ask:
            body = client.post("/chat", json={"message": "Why Red Carpet?", "recommendationId": rec_id}).json()
        self.assertEqual(body["citations"], ["star-red-carpet-10l"])
        self.assertIn("Mohan's diabetes is covered after 1 year.", ask.call_args.args[0])

    def test_accepts_the_id_the_frontend_builds(self):
        client.post("/recommend", json={"family": dict(DEMO, id="session-1")})
        with mock.patch.object(app.llm, "ask_json", return_value={"reply": "Ok.", "citations": []}):
            res = client.post("/chat", json={"message": "Why?", "recommendationId": "session-1-107000"})
        self.assertEqual(res.status_code, 200)

    def test_unknown_recommendation_is_a_404(self):
        self.assertEqual(client.post("/chat", json={"message": "hi", "recommendationId": "rec-x"}).status_code, 404)


class Cors(unittest.TestCase):
    def preflight(self, origin):
        return client.options("/recommend", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                      "Access-Control-Request-Headers": "content-type"})

    def test_allows_the_frontend_on_this_machine_and_the_local_network(self):
        for origin in ["http://localhost:3000", "http://127.0.0.1:3000", "http://10.150.24.59:3000",
                       "http://192.168.1.20:3000"]:
            self.assertEqual(self.preflight(origin).status_code, 200, origin)

    def test_blocks_other_sites(self):
        self.assertEqual(self.preflight("https://example.com").status_code, 400)


if __name__ == "__main__":
    unittest.main()
