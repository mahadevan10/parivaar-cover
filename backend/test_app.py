"""Run from backend/: .venv/bin/python -m unittest test_app -v

Sarvam is replaced with a stub, so these tests run offline. Storage goes to a temporary SQLite file.
"""
import copy
import json
import os
import tempfile
import unittest
from contextlib import closing
from unittest import mock

from fastapi.testclient import TestClient

os.environ["PARIVAAR_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import app
import solver
import store

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
        self.assertEqual(store.recommendation(self.body["id"]), self.body)

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
        self.assertEqual(body["missing"], ["Lata's age", "Office cover", "City", "Cover you want"])
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

    def test_keeps_ages_said_in_malayalam(self):
        # The Malayalam turn from the demo, and what Sarvam's translation returns for it
        said = "എന്റെ ഭാര്യക്ക് ഇരുപത്തിമൂന്ന് വയസ്സ്. എന്റെ മക്കൾക്ക് മോന് അഞ്ച് വയസ്സും മോൾക്ക് മൂന്ന് വയസ്സും."
        english = "My wife is twenty-three years old. My children are five and three."
        family = {"members": [{"id": "self", "name": "Self", "relation": "self", "age": 24, "conditions": []},
                              {"id": "spouse", "name": "Spouse", "relation": "spouse", "conditions": []},
                              {"id": "son", "name": "Son", "relation": "son", "conditions": []},
                              {"id": "daughter", "name": "Daughter", "relation": "daughter", "conditions": []}]}
        reply = {"reply": "Noted.", "family": {"members": [
            {"name": "Self", "age": 24, "relation": "self"}, {"name": "Spouse", "age": 23, "relation": "spouse"},
            {"name": "Son", "age": 5, "relation": "son"}, {"name": "Daughter", "age": 3, "relation": "daughter"}]}}
        with mock.patch.object(app.llm, "ask_json", return_value=reply), \
                mock.patch.object(app.llm, "to_english", side_effect=lambda t: english if t == said else t):
            body = client.post("/chat", json={"message": said, "family": family}).json()
        self.assertEqual([m["age"] for m in body["family"]["members"]], [24, 23, 5, 3])

    def test_number_words_become_digits(self):
        self.assertEqual(app.with_digits("father is sixty-four, mother sixty and son five"),
                         "father is 64, mother 60 and son 5")

    def test_office_cover_needs_the_user_to_mention_it(self):
        reply = {"reply": "Noted.", "family": {"members": [], "office_checked": True}}
        with mock.patch.object(app.llm, "ask_json", return_value=reply):
            body = client.post("/chat", json={"message": "No one else is ill"}).json()
        self.assertIn("Office cover", body["missing"])
        self.assertEqual(body["quickReplies"], [])  # "Who is in the family" comes first

    def test_ready_when_nothing_is_missing(self):
        llm_family = dict(copy.deepcopy(DEMO), health_checked=True, office_checked=True)
        family = {"members": copy.deepcopy(DEMO["members"]), "city": "Pune", "budget": 110000,
                  "healthChecked": True, "officeChecked": True, "coverTarget": 10000000, "coverChecked": True}
        with mock.patch.object(app.llm, "ask_json", return_value={"reply": "Ready.", "family": llm_family}):
            body = client.post("/chat", json={"sessionId": "s1", "message": "That is all", "family": family}).json()
        self.assertTrue(body["readyToOptimise"])
        self.assertTrue(all(m["heardFrom"] is None for m in body["family"]["members"]))
        self.assertEqual([m["id"] for m in body["family"]["members"]], [m["id"] for m in DEMO["members"]])

    def test_sarvam_failure_is_a_502(self):
        with mock.patch.object(app.llm, "ask_json", side_effect=RuntimeError("down")):
            self.assertEqual(client.post("/chat", json={"message": "hi"}).status_code, 502)


class CoverTarget(unittest.TestCase):
    def ask(self, message, llm_family, family=None):
        with mock.patch.object(app.llm, "ask_json", return_value={"reply": "Noted.", "family": llm_family}):
            return client.post("/chat", json={"message": message, "family": family or {}}).json()

    def ready_family(self, **extra):
        return dict({"members": copy.deepcopy(DEMO["members"]), "city": "Pune", "budget": 110000,
                     "healthChecked": True, "officeChecked": True}, **extra)

    def test_asks_for_cover_after_the_budget(self):
        llm_family = dict(copy.deepcopy(DEMO), health_checked=True, office_checked=True)
        llm_family.pop("cover_target", None)
        body = self.ask("The budget is 1.1 lakh", llm_family, self.ready_family())
        self.assertEqual(body["missing"], ["Cover you want"])
        self.assertEqual(body["quickReplies"], ["Not sure"])
        self.assertIn("How much total cover would you like for the family?", body["reply"])
        self.assertFalse(body["readyToOptimise"])

    def test_stores_the_cover_amount(self):
        llm_family = dict(copy.deepcopy(DEMO), health_checked=True, office_checked=True, cover_target="1,00,00,000")
        body = self.ask("1 crore", llm_family, self.ready_family())
        self.assertEqual((body["family"]["coverTarget"], body["family"]["coverChecked"]), (10000000, True))
        self.assertTrue(body["readyToOptimise"])

    def test_keeps_the_cover_amount_when_the_llm_leaves_it_out(self):
        llm_family = dict(copy.deepcopy(DEMO), health_checked=True, office_checked=True)
        llm_family.pop("cover_target", None)
        body = self.ask("Thanks", llm_family, self.ready_family(coverTarget=5000000, coverChecked=True))
        self.assertEqual(body["family"]["coverTarget"], 5000000)

    def test_not_sure_lets_the_solver_choose(self):
        llm_family = dict(copy.deepcopy(DEMO), health_checked=True, office_checked=True)
        llm_family.pop("cover_target", None)
        body = self.ask("Not sure", llm_family, self.ready_family())
        self.assertEqual((body["family"]["coverTarget"], body["family"]["coverChecked"]), (None, True))
        self.assertTrue(body["readyToOptimise"])

    def test_recommend_says_when_the_budget_keeps_cover_short(self):
        body = client.post("/recommend", json={"family": dict(DEMO, budget=42000, cover_target=10000000)}).json()
        check = body["solution"]["cover_check"]
        self.assertEqual(check["code"], "cover_short")
        self.assertLessEqual(body["solution"]["total_premium"], 42000)
        self.assertGreater(check["budget_needed"], 42000)
        # The results show this sentence as written, so the summary is not asked to restate it
        self.assertNotIn(check["text"], json.dumps(app.summary_facts(body["solution"], DEMO), ensure_ascii=False))

    def test_recommend_without_a_target_has_no_cover_check(self):
        family = {k: v for k, v in DEMO.items() if k != "cover_target"}
        self.assertIsNone(client.post("/recommend", json={"family": family}).json()["solution"]["cover_check"])


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


def profile(family=DEMO, **extra):
    """The demo family the way the UI sends it."""
    return dict(app.to_profile(app.clean_family(dict(family, health_checked=True, office_checked=True,
                                                     cover_checked=True), {})), **extra)


class Changes(unittest.TestCase):
    """Change requests after the mix is shown. The first Sarvam call is the explainer, the second the editor."""

    @classmethod
    def setUpClass(cls):
        cls.rec = client.post("/recommend", json={"family": dict(DEMO, id="s-edit")}).json()

    def change(self, message, edit, family=None, history=None, **extra):
        replies = [{"reply": "", "citations": [], "change": True}, edit]
        with mock.patch.object(app.llm, "ask_json", side_effect=replies):
            return client.post("/chat", json=dict({"sessionId": "s-edit", "message": message,
                                                   "family": family or profile(),
                                                   "history": history or [], "recommendationId": self.rec["id"]},
                                                  **extra)).json()

    def edited(self, **changes):
        family = copy.deepcopy(DEMO)
        for m in family["members"]:
            m.update(changes.pop(m["id"], {}))
        return dict(family, **changes)

    def test_a_question_is_answered_as_before(self):
        with mock.patch.object(app.llm, "ask_json", return_value={"reply": "Because it is cheaper.", "citations": []}):
            body = client.post("/chat", json={"message": "Why not one floater?", "recommendationId": self.rec["id"]}).json()
        self.assertEqual(body["reply"], "Because it is cheaper.")
        self.assertNotIn("proposal", body)

    def test_an_age_change_is_quoted_from_the_solver(self):
        body = self.change("My father Mohan is 66 now", {"family": self.edited(mohan={"age": 66})})
        expected = solver.solve(app.Family.model_validate(self.edited(mohan={"age": 66})).model_dump(), app.POLICIES)
        proposal = body["proposal"]
        self.assertTrue(proposal["ready"])
        self.assertEqual(proposal["premium"], expected["total_premium"])
        self.assertEqual(proposal["premiumChange"], expected["total_premium"] - 107000)
        self.assertEqual(next(m for m in proposal["family"]["members"] if m["id"] == "mohan")["age"], 66)
        self.assertTrue(body["reply"].startswith("Mohan's age is now 66."))
        self.assertIn("Premiums are illustrative.", body["reply"])
        self.assertEqual(body["quickReplies"], ["Update my mix", "Keep this mix"])
        # The board keeps the family the mix ran on until the user updates
        self.assertEqual(body["family"]["members"][3]["age"], 64)

    def test_more_cover_over_budget_raises_the_budget(self):
        body = self.change("I need at least 1.5 crore for pitaji",
                           {"family": self.edited(), "requirements": {"min_cover": {"mohan": 15000000}}})
        proposal = body["proposal"]
        self.assertEqual(proposal["family"]["requirements"]["minCover"], {"mohan": 15000000})
        self.assertGreater(proposal["family"]["budget"], 110000)
        self.assertIn("Mohan needs at least ₹1.5 crore of cover.", body["reply"])
        self.assertIn(f"Updating sets your budget to {solver.inr(proposal['family']['budget'])}.", body["reply"])
        self.assertIn("Mohan's cover goes from ₹35 lakh to ₹1.5 crore.", body["reply"])

    def test_more_cover_without_an_amount_asks_for_one(self):
        body = self.change("I need more cover for my father",
                           {"family": self.edited(), "requirements": {"min_cover": {"mohan": 7000000}}})
        self.assertIn("How much cover would you like for Mohan? Mohan has ₹35 lakh now.", body["reply"])
        self.assertEqual(body["quickReplies"], ["₹50 lakh", "₹1 crore"])
        self.assertFalse(body["proposal"]["ready"])

    def test_the_amount_given_next_is_quoted(self):
        first = self.change("I need more coverage for my father", {"family": self.edited(), "more_cover_for": ["mohan"]})
        # The LLM may still list Mohan, but the amount is now known, so the change is priced
        body = self.change("₹50 lakh", {"family": self.edited(), "requirements": {"min_cover": {"mohan": 5000000}},
                                       "more_cover_for": ["mohan"]},
                           family=first["proposal"]["family"],
                           history=[{"role": "assistant", "text": first["reply"]}])
        self.assertTrue(body["proposal"]["ready"])
        self.assertGreaterEqual(body["proposal"]["family"]["requirements"]["minCover"]["mohan"], 5000000)
        self.assertTrue(body["reply"].startswith("Mohan needs at least ₹50 lakh of cover. Your mix becomes"))

    def test_a_rule_for_someone_the_user_never_named_is_dropped(self):
        body = self.change("No co-pay please", {"family": self.edited(),
                                                "requirements": {"max_copay_percent": 0, "min_cover": {"lata": 5000000}}})
        self.assertEqual(body["proposal"]["family"]["requirements"]["minCover"], {})
        self.assertEqual(body["proposal"]["family"]["requirements"]["maxCopayPercent"], 0)
        self.assertTrue(body["reply"].startswith("No plans with a co-pay."))

    def test_a_change_the_editor_cannot_express_goes_to_an_expert(self):
        body = self.change("Add dental cover for everyone", {"family": self.edited()})
        self.assertTrue(body["expertRequested"])
        self.assertEqual(store.expert_requests("s-edit")[-1]["reason"], "no field for this request")

    def test_nothing_heard_changes_nothing(self):
        body = self.change("Hmm okay", {"family": self.edited(budget=50000), "requirements": {"one_insurer": True}})
        self.assertIsNone(body["proposal"])
        self.assertIn("I could not tell what to change.", body["reply"])

    def test_something_no_rule_can_express_goes_to_an_expert(self):
        body = self.change("I need maternity cover for Sneha",
                           {"family": self.edited(), "unsupported": "maternity cover", "more_cover_for": ["sneha"]})
        self.assertTrue(body["expertRequested"])
        self.assertIsNone(body["proposal"])
        self.assertIn("An expert will contact you directly and suggest a floater", body["reply"])
        self.assertEqual(store.expert_requests("s-edit")[-1]["reason"], "maternity cover")

    def test_rules_no_mix_can_meet_go_to_an_expert(self):
        body = self.change("Mohan needs 5 crore of cover",
                           {"family": self.edited(), "requirements": {"min_cover": {"mohan": 50000000}}})
        self.assertTrue(body["expertRequested"])
        self.assertEqual(store.expert_requests("s-edit")[-1]["reason"], "no_plan_meets_rules")

    def test_a_cover_target_the_budget_cannot_reach_offers_a_higher_budget(self):
        body = self.change("We want 3 crore of cover in total", {"family": self.edited(cover_target=30000000, budget=110000)},
                           family=profile(dict(DEMO, budget=60000)))
        label = next(q for q in body["quickReplies"] if q.startswith("Raise budget to"))
        self.assertEqual(label, f"Raise budget to {solver.inr(body['proposal']['raiseBudgetTo'])}")
        self.assertIn("You asked for ₹3 crore of cover.", body["reply"])

    def test_a_new_person_without_an_age_is_asked_about(self):
        family = self.edited()
        family["members"].append({"name": "Riya", "relation": "sister", "conditions": []})
        body = self.change("Add my sister Riya", {"family": family})
        self.assertIn("Riya is added. How old is Riya?", body["reply"])
        self.assertFalse(body["proposal"]["ready"])
        # The next turn sends the draft back, and the quote covers both changes
        family["members"][-1]["age"] = 28
        draft = body["proposal"]["family"]
        body = self.change("She is 28", {"family": family}, family=draft,
                           history=[{"role": "assistant", "text": "How old is Riya?"}])
        self.assertTrue(body["proposal"]["ready"])
        self.assertIn("Riya, 28, is added.", body["reply"])
        self.assertIn("Riya gets", body["reply"])

    def test_the_quote_keeps_the_numbers_in_another_language(self):
        def translate(text, language):
            return text.replace("₹", "रु ") if "drop" not in language else text.replace("66", "")
        with mock.patch.object(app.llm, "from_english", side_effect=translate):
            hindi = self.change("मेरे पिता मोहन अब 66 के हैं", {"family": self.edited(mohan={"age": 66})}, language="hi-IN")
            broken = self.change("Mohan is 66 now", {"family": self.edited(mohan={"age": 66})}, language="hi-IN-drop")
        self.assertIn("रु ", hindi["reply"])
        self.assertTrue(broken["reply"].startswith("Mohan's age is now 66."))

    def test_removing_a_rule_on_the_results_screen_is_quoted(self):
        family = dict(DEMO, id="s-quote", requirements={"max_copay_percent": 0})
        rec = client.post("/recommend", json={"family": family}).json()
        body = client.post("/quote", json={"sessionId": "s-quote", "family": profile(DEMO),
                                            "recommendationId": rec["id"]}).json()
        self.assertTrue(body["reply"].startswith("Plans with a co-pay are allowed again."))
        self.assertEqual(body["proposal"]["premium"], 107000)


class Rules(unittest.TestCase):
    def test_intake_keeps_a_rule_the_user_said(self):
        reply = {"reply": "Noted.", "family": {"members": [{"name": "Mohan", "age": 64, "relation": "father"}]},
                 "requirements": {"min_cover": {"Mohan": "25,00,000"}}}
        with mock.patch.object(app.llm, "ask_json", return_value=reply):
            body = client.post("/chat", json={"message": "My father Mohan is 64. He needs 25 lakh of cover",
                                              "family": {}}).json()
        self.assertEqual(body["family"]["requirements"]["minCover"], {"mohan": 2500000})

    def test_intake_keeps_rules_the_llm_leaves_out(self):
        family = profile(DEMO)
        family["requirements"]["maxCopayPercent"] = 0
        with mock.patch.object(app.llm, "ask_json", return_value={"reply": "Noted.", "family": app.from_profile(family)}):
            body = client.post("/chat", json={"message": "Thanks", "family": family}).json()
        self.assertEqual(body["family"]["requirements"]["maxCopayPercent"], 0)

    def test_unsupported_in_intake_asks_an_expert(self):
        reply = {"reply": "Noted.", "family": {}, "unsupported": "OPD cover"}
        with mock.patch.object(app.llm, "ask_json", return_value=reply):
            body = client.post("/chat", json={"sessionId": "s-intake", "message": "I want OPD cover", "family": {}}).json()
        self.assertTrue(body["expertRequested"])
        self.assertIn("insurance expert", body["reply"])

    def test_recommend_rejects_rules_for_unknown_members(self):
        family = dict(DEMO, requirements={"min_cover": {"nobody": 100000}})
        self.assertEqual(client.post("/recommend", json={"family": family}).status_code, 422)

    def test_amounts_and_months(self):
        self.assertEqual(app.amounts_in("budget is 60k, 1.5 crore and ₹50,00,000"), {60000, 15000000, 5000000})
        self.assertEqual(app.months_in("within a year or 18 months"), {12, 18})


class Summary(unittest.TestCase):
    def setUp(self):
        self.rec_id = client.post("/recommend", json={"family": DEMO}).json()["id"]

    def summarise(self, reply=None, error=None):
        with mock.patch.object(app.llm, "ask_json", return_value=reply, side_effect=error) as ask:
            body = client.post("/summary", json={"recommendationId": self.rec_id}).json()
        return body, ask

    def test_returns_sarvam_text_from_the_solver_facts(self):
        reply = {"why": "The mix costs ₹11,000 less a year and gives Mohan cover from year 2.",
                 "watch": ["Mohan pays 30% of each claim on Red Carpet — up to ₹3,00,000."]}
        body, ask = self.summarise(reply)
        self.assertEqual(body["source"], "llm")
        self.assertEqual(body["watch"], ["Mohan pays 30% of each claim on Red Carpet, up to ₹3,00,000."])
        self.assertIn("In year 2, only Senior Citizens Red Carpet pays", ask.call_args.args[0])

    def test_is_stored_so_sarvam_is_asked_once(self):
        self.summarise({"why": "The mix gives everyone more cover.", "watch": []})
        body, ask = self.summarise({"why": "Something else.", "watch": []})
        ask.assert_not_called()
        self.assertEqual(body["why"], "The mix gives everyone more cover.")

    def test_an_amount_not_in_the_facts_falls_back_to_the_solver(self):
        body, _ = self.summarise({"why": "The mix saves ₹25,000 a year.", "watch": []})
        self.assertEqual(body["source"], "solver")
        self.assertIn("₹11,000 less a year", body["why"])
        self.assertEqual(len(body["watch"]), 3)

    def test_a_name_not_in_the_family_falls_back_to_the_solver(self):
        body, _ = self.summarise({"why": "Rachel, Sneha and Aarav share the floater.", "watch": []})
        self.assertEqual(body["source"], "solver")

    def test_names_come_back_in_their_own_case(self):
        body, _ = self.summarise({"why": "Sneha and Mohan are covered.", "watch": ["manipalcigna asks for star health's papers."]})
        self.assertEqual(body["watch"], ["ManipalCigna asks for Star Health's papers."])

    def test_lakh_amounts_from_the_facts_are_allowed(self):
        body, _ = self.summarise({"why": "Mohan and Lata share a 25 lakh top-up.", "watch": []})
        self.assertEqual(body["source"], "llm")

    def test_sarvam_failure_falls_back_to_the_solver(self):
        body, _ = self.summarise(error=RuntimeError("Sarvam is down"))
        self.assertEqual(body["source"], "solver")
        body, ask = self.summarise({"why": "The mix gives everyone more cover.", "watch": []})
        self.assertEqual(body["source"], "llm")

    def test_unknown_recommendation_is_a_404(self):
        self.assertEqual(client.post("/summary", json={"recommendationId": "rec-x"}).status_code, 404)


class Storage(unittest.TestCase):
    def test_stores_the_turn_and_the_family_for_the_session(self):
        reply = {"reply": "Noted.", "family": {"members": [
            {"name": "Mohan", "age": 64, "relation": "father", "conditions": ["sugar"]}], "health_checked": True}}
        with mock.patch.object(app.llm, "ask_json", return_value=reply):
            client.post("/chat", json={"sessionId": "store-1", "message": "Father Mohan is 64 and has sugar"})
        turns = [(m["role"], m["text"]) for m in store.messages("store-1")]
        self.assertEqual(turns, [("user", "Father Mohan is 64 and has sugar"),
                                 ("assistant", "Noted. " + app.next_question("Office cover"))])
        saved = store.family("store-1")
        mohan = saved["family"]["members"][0]
        self.assertEqual((saved["family"]["id"], mohan["age"], mohan["conditions"]), ("store-1", 64, ["diabetes"]))
        self.assertEqual((saved["missing"], saved["ready"]), (["Office cover", "City", "Yearly budget", "Cover you want"], False))

    def test_keeps_only_the_latest_family(self):
        for age in (60, 61):
            reply = {"reply": "Noted.", "family": {"members": [{"name": "Lata", "age": age, "relation": "mother"}]}}
            with mock.patch.object(app.llm, "ask_json", return_value=reply):
                client.post("/chat", json={"sessionId": "store-2", "message": f"Mother Lata is {age}"})
        self.assertEqual(store.family("store-2")["family"]["members"][0]["age"], 61)
        self.assertEqual(len(store.messages("store-2")), 4)

    def test_turns_without_a_session_are_not_stored(self):
        with mock.patch.object(app.llm, "ask_json", return_value={"reply": "Hi.", "family": {}}):
            client.post("/chat", json={"message": "hello"})
        self.assertEqual(store.messages(None), [])

    def test_an_age_out_of_range_is_dropped_before_storing(self):
        reply = {"reply": "Noted.", "family": {"members": [{"name": "Lata", "age": 600, "relation": "mother"}]}}
        with mock.patch.object(app.llm, "ask_json", return_value=reply):
            res = client.post("/chat", json={"sessionId": "store-3", "message": "Mother Lata is 600"})
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(store.family("store-3")["family"]["members"][0]["age"])

    def test_recommendation_keeps_the_family_the_solver_ran_on(self):
        rec = client.post("/recommend", json={"family": dict(DEMO, id="store-4")}).json()
        with store.connect() as conn:
            row = conn.execute("SELECT session_id, family FROM recommendations WHERE id = ?", (rec["id"],)).fetchone()
        self.assertEqual(row["session_id"], "store-4")
        self.assertEqual(app.Family.model_validate_json(row["family"]).members[3].conditions, ["diabetes"])


class PolicyStore(unittest.TestCase):
    def test_policies_match_the_json_file_in_order(self):
        on_disk = json.loads(store.POLICIES_JSON.read_text())["policies"]
        self.assertEqual(store.policies(), on_disk)

    def test_columns_can_be_queried(self):
        with closing(store.connect()) as conn:
            store.sync_policies(conn)
            row = conn.execute("SELECT plan_type, sum_insured, diabetes_wait_months, policy FROM policies "
                               "WHERE id = 'star-comprehensive-25l-floater'").fetchone()
        self.assertEqual((row["plan_type"], row["sum_insured"], row["diabetes_wait_months"]), ("floater", 2500000, 36))

    def test_rebuilds_when_the_file_changes(self):
        data = json.loads(store.POLICIES_JSON.read_text())
        data["policies"] = data["policies"][:2]
        data["policies"][0]["copay_percent"] = 20
        path = os.path.join(tempfile.mkdtemp(), "policies.json")
        with open(path, "w") as f:
            json.dump(data, f)
        with closing(store.connect()) as conn:
            store.sync_policies(conn, path)
            rows = conn.execute("SELECT copay_percent FROM policies ORDER BY position").fetchall()
            self.assertEqual([r["copay_percent"] for r in rows], [20, data["policies"][1]["copay_percent"]])
            store.sync_policies(conn)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0], len(store.policies()))


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
