# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. Two developers share this repo, each running their own Claude, so read the team workflow section before touching anything.

## What this is

Team Prometheus's entry for the Paytm AI hackathon, track "AI-Powered Financial Journeys: make Insurance, Lending and Fintech simpler, faster and more human." The pitch deck (stage 1) got us shortlisted. We're now at stage 2: a working prototype, built on site in Bangalore in about 6 hours (2026-10-31).

The scope is **health insurance only**. The product, **Parivaar Cover**, helps one person insure a three-generation family by recommending the best-value *combination* of policies (family floater, individual or senior plans, super top-ups, across insurers) instead of a single policy.

The user journey from the deck:
1. **Talk.** The user shares each family member's age, health conditions, city and budget, plus any office cover.
2. **Read the fine print.** Policy wordings are stored as comparable data: room rent, co-pay, waiting periods, sub-limits.
3. **Optimise.** A solver tests floater, individual and top-up combinations and picks the most cover per rupee within budget.
4. **Explain.** Each pick comes with a plain-language reason and its catches.

**Core rule: prices and picks come from the solver. The LLM only talks to the user and explains the solver's output, citing the policy clause.** The LLM never chooses policies or makes up premiums.

## Demo case

Use this family everywhere (seed data, tests, UI placeholders, demo script), so the demo matches the deck:

- Rahul (36), Sneha (33), Aarav (6), Mohan (64, diabetic), Lata (60), in Pune.
- **Usual pick:** one ₹25L family floater for all five at ₹1,18,000 a year. Total cover ₹25L. Diabetes waiting period of 3 years.
- **Parivaar Cover's mix:** five policies at ₹1,07,000 a year, ₹1.05 crore of total cover:
  - Rahul, Sneha, Aarav: ₹10L family floater, ₹21,000
  - Rahul, Sneha, Aarav: ₹50L super top-up, ₹10L deductible, ₹4,500
  - Mohan: ₹10L senior plan, 1-year diabetes wait, ₹41,000
  - Lata: ₹10L individual plan, ₹24,500
  - Mohan, Lata: ₹25L super top-up, ₹10L deductible, ₹16,000
- **Claim check:** a ₹6L heart procedure for Mohan in year 2 is covered by the mix. With the usual pick, it isn't covered until year 4.

## Tech stack

The deck (`stage1_ppt/slide_content.md`, slide 5) planned this stack. For a 6-hour build, use the smallest subset that runs the demo, and record what we actually picked here.

| Layer | Planned in the deck | Hackathon build |
|---|---|---|
| Frontend | React web, React Native mini-app | Next.js 16 (App Router), TypeScript, Tailwind 4 in `frontend/`. Always calls the FastAPI backend (`NEXT_PUBLIC_API_BASE_URL`, default `http://localhost:8000`). No mock. |
| Backend / solver | Python + FastAPI, Google OR-Tools | Python 3, FastAPI and OR-Tools CP-SAT in `backend/`. The solver reads policies from SQLite; families are JSON in `shared/`. |
| AI | Claude Sonnet 5.5; Bhashini / Sarvam for Indian languages | Voice input: Sarvam AI speech-to-text (`saaras:v4`, auto language detect) via `frontend/src/app/api/stt`. LLM: Sarvam `sarvam-105b-conversations` in `backend/llm.py`, for intake and explanations only. |
| Policy data | PostgreSQL + pgvector, PDF parsing | SQLite (`backend/store.py`, file `backend/parivaar.db`). Policies are edited in `shared/policies.json` and loaded into the `policies` table whenever the file changes. Chat turns, each session's family and every recommendation are stored there too. |

## Repo layout and ownership

| Path | What it holds | Owner |
|---|---|---|
| `backend/` | API, optimizer, LLM calls | TBD |
| `frontend/` | User-facing app: chat, voice, family board, results | Chat and voice UI developer |
| `shared/` | API contract and the policy data both sides use | Both, change only after agreeing |
| `stage1_ppt/` | Stage 1 pitch deck (finished, see `stage1_ppt/CLAUDE.md`) | Don't edit |

**Only edit files in folders your developer owns.** If a change is needed in the other person's folder or in `shared/`, stop and tell your developer instead of making it.

## Running locally

**Frontend** (port 3000):

```bash
cd frontend
cp .env.example .env.local   # set SARVAM_API_KEY; the backend must be running on port 8000
npm install
npm run dev
```

Context for the frontend lives in `frontend/CONTEXT.md`. Run `/update-context` to refresh it.

**Backend** (port 8000):

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app:app --reload --port 8000   # needs SARVAM_API_KEY in the repo-root .env
.venv/bin/python -m unittest test_solver test_app   # tests, Sarvam is stubbed
```

Stored data: `sqlite3 backend/parivaar.db` (tables `policies`, `chat_messages`, `families`, `recommendations`). Set `PARIVAAR_DB` to use another file.

Endpoints: `POST /recommend` (solver result, reasons and claim checks for years 1 to 4), `POST /chat` (intake, or explanations once `recommendation_id` is set), `POST /summary` (short why-this-mix and what-to-watch for a recommendation, written by Sarvam from the solver's facts), `GET /health`. Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` in the frontend to use it.

Secrets go in `.env`, which is gitignored. Commit a `.env.example` listing every variable without values, and share the real keys outside git.

## Team workflow (git)

- Never commit directly to `main`, and never force-push. `main` must always run the demo.
- One short-lived branch per task, prefixed with the area: `be/optimizer`, `fe/results-screen`.
- Before starting a task, run `git pull --rebase origin main`.
- Commit small. Every 30 to 60 minutes, push the branch, open a PR with `gh pr create`, and squash-merge it yourself with `gh pr merge --squash --delete-branch` once it runs. Don't wait for reviews.
- Only the owner of a folder adds dependencies there. If a lockfile conflicts, regenerate it instead of merging by hand.
- Never commit `.env`, `node_modules/`, virtualenvs or build output.
- Stop adding features 45 minutes before the deadline and spend that time on demo polish.

## Product copy rules

All user-facing text in the app, including LLM explanations, follows the deck's writing style:
- plain, short sentences in sentence case
- no em or en dashes, no "not X but Y" contrasts, no hype words
- if the **humanizer** skill is available, use it for any copy

Visual style: Paytm navy `#002E6E` and sky `#00BAF2`, with an amber accent. Show family members as avatars with initials in circles.
