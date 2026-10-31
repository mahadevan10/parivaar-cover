# Parivaar Cover: slide text (final, humanized)

The build script (build/build_deck.js) holds the same text. Edit both if you change wording.

## 1. Title
Paytm Hackathon 2026 · AI-Powered Financial Journeys
Parivaar Cover
Finds the best-value mix of health policies for your whole family, from kids to grandparents.
Team Prometheus

## 2. Problem statement: Insuring three generations is guesswork
Rahul's family, Pune: Rahul 36, Sneha 33, Aarav 6, Mohan 64 (diabetic), Lata 60

What Rahul has to decide
1. One floater for all five, or separate plans for his parents?
2. Is a super top-up worth adding, and at what deductible?
3. Which of hundreds of plans, from dozens of insurers?
4. What do co-pay, room-rent caps and waiting periods cost him?

Agents push one big floater and comparison sites rank one policy at a time, so no one works out the mix for the whole family.

- ~40% of health spending in India is paid out of pocket (National Health Accounts 2021-22)
- 44% of claims rejected or only partly paid, as reported by policyholders (LocalCircles survey, 2023-25)
- ~12% medical inflation in 2024, about three times general inflation (Milliman)

## 3. Proposed solution: From family details to the right policy mix
1. Talk. Chat or speak in English, Hindi or a regional language. Share each member's age, health, city and budget, plus any office cover.
2. Read the fine print. AI has already turned every policy wording into comparable data: room rent, co-pay, waiting periods, sub-limits, network hospitals.
3. Optimise. A solver tests thousands of floater, individual and top-up combinations and picks the most cover per rupee within budget.
4. Explain and buy. Each pick comes with a plain-language reason and its catches. Buy every policy in one Paytm checkout, with EMI if needed.
About 10 minutes from first question to recommendation, inside the Paytm app.

## 4. Proposed solution, Rahul's family: Rahul gets 4x the cover for ₹11,000 less
The usual pick: one ₹25L floater for all five, ₹1,18,000 a year. Five people share one ₹25L pool. Priced on Mohan's age and diabetes. Diabetes waiting period of 3 years. Total cover ₹25L.
Parivaar Cover's mix: five policies built for this family, ₹1,07,000 a year.
- Rahul, Sneha, Aarav: ₹10L family floater, ₹21,000
- Rahul, Sneha, Aarav: ₹50L super top-up, ₹10L deductible, ₹4,500
- Mohan: ₹10L senior plan, 1-year diabetes wait, ₹41,000
- Lata: ₹10L individual plan, ₹24,500
- Mohan, Lata: ₹25L super top-up, ₹10L deductible, ₹16,000
Total cover ₹1.05 crore.
Claim check: a ₹6L heart procedure for Mohan in year 2 is covered by the mix. With the usual pick it waits until year 4.
Illustrative premiums for a Pune family, rounded. Real quotes depend on the insurer and medical tests.

## 5. Technology: How it's built
- Channels (where families use it): Paytm mini-app (React Native), web (React), voice
- AI layer (talks, reads policies, explains): Claude Sonnet 5.5, Bhashini / Sarvam AI for Indian languages
- Decision engine (builds the mix): Python + FastAPI, Google OR-Tools solver, claim simulator
- Policy data (every plan as structured data): PostgreSQL + pgvector, PDF parsing pipeline, human review
- Integrations (quote, pay, issue): Paytm Insurance Broking, Paytm KYC & payments, lending partners for EMI
- Trust and compliance: DPDP Act consent, encrypted health data, audit log for every recommendation
Prices and picks come from the solver. The LLM explains them and cites the policy clause.

## 6. USP: How it compares (Agent / Comparison site / Parivaar Cover)
- Recommends a mix of policies for the whole family: Sometimes / No / Yes
- Compares plans across insurers: Partly / Yes / Yes
- Explains the fine print before you pay: Partly / Partly / Yes
- Shows your out-of-pocket cost for real treatments: No / No / Yes
- Talks in your language, by voice: Yes / No / Yes
Runs inside Paytm, so KYC, payments and renewal reminders are already in place.

## 7. Impact and benefits: Who benefits
~10 min from first question to recommendation (target) · 4x the cover for ₹11,000 less in Rahul's case · 3 to 5 policies per family instead of one
- Families: decide in one sitting; parents get proper cover (no age cap on new policies since 2024); see waiting periods and caps before paying
- Paytm: bigger ticket per household; renewals and yearly check-ups bring families back; uses Paytm's KYC, payments and lending
- Insurers: customers matched to the right product; fewer claim disputes and mis-selling complaints; lower cost to acquire customers

## 8. Business model: Free for families, paid by insurer brokerage
1. Brokerage: insurers pay brokerage on each policy via Paytm Insurance Broking (IRDAI licensed to 2029). A family buys 3 to 5.
2. Renewals: health cover renews every year. A yearly check-up re-runs the optimizer and keeps the family on Paytm.
3. Premium EMI: lending partners split large premiums into monthly payments. Paytm earns a share.
4. B2B API: employers and other distributors license the optimizer.
Year 1 illustration: 50,000 families × ₹70,000 average yearly premium = ₹350 Cr premium. ₹42 Cr revenue at an assumed 12% brokerage, before renewals.
Main costs: AI usage per session, keeping policy data current, insurer integrations.

## 9. Close
Thank you. Parivaar Cover · Team Prometheus
What's next: Round 2, working prototype on real policy data · Pilot, live with a small group of Paytm users · Scale, yearly check-ups and the employer API

## Sources
- National Health Accounts 2021-22 (Union Health Ministry): out-of-pocket share 39.4%
- LocalCircles survey of claims filed 2023-25: 15% rejected, 29% partly approved (self-reported)
- Milliman, Measuring medical inflation in India: 12% medical trend in 2024
- IRDAI, March 2024: age cap of 65 removed for new health policies; pre-existing disease wait capped at 36 months
- Paytm Insurance Broking: IRDAI direct broker licence renewed 17 Feb 2026 to 16 Feb 2029
