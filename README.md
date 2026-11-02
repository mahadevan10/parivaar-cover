# Parivaar Cover

Parivaar Cover finds the best-value mix of health policies for a whole family, from kids to grandparents.

Team Prometheus, Paytm AI Hackathon 2026, track "AI-Powered Financial Journeys: make Insurance, Lending and Fintech simpler, faster and more human". The stage 1 pitch deck got us shortlisted. This repo is the stage 2 prototype, built on site in Bangalore.

## The problem: insuring three generations is guesswork

Take Rahul's family in Pune: Rahul (36), his wife Sneha (33), their son Aarav (6), and Rahul's parents Mohan (64, diabetic) and Lata (60). Rahul wants to insure all five, and he has to decide:

1. One family floater for all five, or separate plans for his parents?
2. Is a super top-up worth adding, and at what deductible?
3. Which of hundreds of plans, from dozens of insurers?
4. What will co-pay, room rent caps and waiting periods cost him when someone falls ill?

Agents usually sell one big floater. Comparison sites rank one policy at a time. Nobody works out the right combination for the whole family.

The stakes are high:

- About 40% of health spending in India is paid out of pocket (National Health Accounts 2021-22).
- 44% of policyholders say their claim was rejected or only partly paid (LocalCircles survey, 2023-25).
- Medical inflation was about 12% in 2024, roughly three times general inflation (Milliman).

## Our solution

Parivaar Cover lets one person insure a three-generation family by recommending a combination of policies: family floaters, individual and senior plans, and super top-ups, across insurers. The journey has four steps.

1. Talk. The user chats or speaks, in English, Hindi or another Indian language. They share each member's age, health conditions, city and budget, plus any office cover. A family board on screen fills in as they talk, and they check it before anything is priced.
2. Read the fine print. Every policy is stored as comparable data: room rent rules, co-pay, waiting periods for pre-existing and named conditions, sub-limits, entry ages and premium bands.
3. Optimise. A solver tests floater, individual, senior and top-up combinations for the family and picks the most useful cover per rupee within the budget. It weighs cover, waiting periods on each member's known conditions, co-pay and room rent caps, and keeps any rules the user sets (no co-pay, one insurer, a minimum cover for a parent, and so on).
4. Explain. Each pick comes with a plain-language reason and its catches, tied to the policy field it comes from. A claim check shows what a real treatment would cost the family in each policy year.

One rule holds everywhere: **prices and picks come from the solver.** The language model only talks to the user and explains the solver's output. It never chooses a policy or states a premium the solver did not produce, and the backend checks every amount and percent it writes against the solver's facts.

## What it does for Rahul's family

| | The usual pick | Parivaar Cover's mix |
|---|---|---|
| Policies | One ₹25L family floater for all five | Five policies built for this family |
| Yearly premium | ₹1,18,000 | ₹1,07,000 |
| Total cover | ₹25L, shared by five people | ₹1.05 crore |
| Mohan's diabetes wait | 3 years | 1 year |

The mix:

| Who | Policy | Premium |
|---|---|---|
| Rahul, Sneha, Aarav | ₹10L family floater | ₹21,000 |
| Rahul, Sneha, Aarav | ₹50L super top-up, ₹10L deductible | ₹4,500 |
| Mohan | ₹10L senior plan, 1-year diabetes wait | ₹41,000 |
| Lata | ₹10L individual plan | ₹24,500 |
| Mohan, Lata | ₹25L super top-up, ₹10L deductible | ₹16,000 |

Rahul gets four times the cover for ₹11,000 less a year.

Claim check: Mohan needs a ₹6L heart procedure in year 2. The mix covers it, with Mohan paying a 30% co-pay (₹1,80,000) on his senior plan. The usual floater pays nothing for it until year 4.

Premiums are illustrative and rounded for a Pune family. Real quotes depend on the insurer and medical tests.

## What the prototype does

- Chat and voice intake. Speech is transcribed with Sarvam AI (`saaras:v4`, auto language detect) and shown for review before it is sent. Talk mode reads replies aloud and listens again, so the user can hold a voice conversation.
- A live family board with avatars, each member's details and short notes on what matters for them, such as a condition and its waiting period.
- A CP-SAT solver (Google OR-Tools) over 34 health policies from Star Health, ManipalCigna and Reliance General.
- A results screen comparing the mix with the usual pick: cover per person, the claim check with a year slider, each policy's catches, catches that come from how the policies stack, and a short summary of why this mix and what to watch.
- Changes after the mix is shown. The user can ask in the chat ("what if Lata has no co-pay?", "keep it under ₹1 lakh") or edit on the results screen, and the solver prices the change.

Policy features follow public brochures and aggregator pages. They have not yet been checked against the policy wordings.

## How it works

```
 Browser (Next.js)                 Backend (FastAPI)                   Data
 ─────────────────                 ─────────────────                   ────
 Chat, voice, family board  ──▶   /chat     intake and explanations    shared/policies.json
 Results screen             ──▶   /recommend  CP-SAT solver + claims     │
                            ──▶   /quote    price a change               ▼
                            ──▶   /summary  why this mix, what to watch  SQLite (backend/parivaar.db)
 /api/stt, /api/tts (Sarvam)       Sarvam LLM explains solver facts     policies, chats, families,
                                                                         recommendations
```

| Layer | What we used |
|---|---|
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind 4, in `frontend/` |
| Backend and solver | Python 3, FastAPI, Google OR-Tools CP-SAT, in `backend/` |
| Language model | Sarvam `sarvam-105b-conversations`, for intake and explanations only |
| Voice | Sarvam speech to text and text to speech |
| Data | SQLite. Policies are edited in `shared/policies.json` and loaded into the database when the file changes |

The full data format, solver output and reason codes are in [`shared/README.md`](shared/README.md).

## Run it locally

You need Python 3, Node.js and a Sarvam AI API key.

Backend, on port 8000:

```bash
cp .env.example .env            # add SARVAM_API_KEY
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app:app --reload --port 8000
```

Frontend, on port 3000:

```bash
cd frontend
cp .env.example .env.local      # add SARVAM_API_KEY
npm install
npm run dev
```

Open http://localhost:3000 and describe Rahul's family, or your own.

Tests (Sarvam is stubbed):

```bash
cd backend
.venv/bin/python -m unittest test_solver test_app
```

## Repo layout

| Path | What it holds |
|---|---|
| `frontend/` | The app: chat, voice, family board, results |
| `backend/` | API, solver, language model calls, SQLite store |
| `shared/` | Policy data, demo families and the API contract |
| `stage1_ppt/` | Stage 1 pitch deck |

## What's next

Policy data checked against the real wordings, a pilot with a small group of Paytm users, one Paytm checkout for every policy in the mix with EMI for large premiums, and a yearly check-up that re-runs the solver at renewal.
