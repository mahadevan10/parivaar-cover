// Talks to the FastAPI backend. Set NEXT_PUBLIC_API_BASE_URL if it isn't on localhost:8000.

import type { ChatRequest, ChatResponse, FamilyProfile, MixSummary, Recommendation } from "./types";
import { claimsFor, toRecommendation, toSolverFamily, type SolverClaimSeries, type SolverOutput } from "./solver";

const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} failed with ${res.status}`);
  return res.json() as Promise<T>;
}

export function sendChat(req: ChatRequest): Promise<ChatResponse> {
  return post<ChatResponse>("/chat", req);
}

export class NoFitError extends Error {}

/** Runs the solver. The backend returns its own output format, mapped here. */
export async function getRecommendation(family: FamilyProfile, sessionId: string): Promise<Recommendation> {
  const solverFamily = toSolverFamily(family, sessionId);
  const { id, solution, claim_checks } = await post<{ id?: string; solution: SolverOutput; claim_checks?: SolverClaimSeries[] }>(
    "/recommend",
    { family: solverFamily, claims: claimsFor(solverFamily) },
  );
  if (solution.status !== "ok") throw new NoFitError("No mix fits this budget.");
  return toRecommendation(solution, claim_checks, id);
}

/** Short why-this-mix and what-to-watch, written by Sarvam from the solver's facts. */
export function getSummary(recommendationId: string): Promise<MixSummary> {
  return post<MixSummary>("/summary", { recommendationId });
}

export type Transcript = { transcript: string; languageCode?: string };

/** `language` is the session's language once known, e.g. "hi-IN". Leave it out to auto-detect. */
export async function transcribe(audio: Blob, language?: string): Promise<Transcript> {
  const form = new FormData();
  const ext = audio.type.includes("mp4") ? "m4a" : audio.type.includes("ogg") ? "ogg" : "webm";
  form.append("file", audio, `speech.${ext}`);
  if (language) form.append("language", language);
  const res = await fetch("/api/stt", { method: "POST", body: form });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error ?? `Speech service failed with ${res.status}`);
  return data as Transcript;
}
