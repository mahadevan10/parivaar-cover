// Talks to the backend when NEXT_PUBLIC_API_BASE_URL is set, otherwise uses
// the mock so the UI can be built and demoed on its own.

import type { ChatRequest, ChatResponse, FamilyProfile, Recommendation } from "./types";
import { toRecommendation, toSolverFamily, type SolverClaimSeries, type SolverOutput } from "./solver";
import { createMockChat } from "./mock/chat";
import { demoRecommendationFor } from "./mock/demo";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");

export const usingMock = !BASE;

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} failed with ${res.status}`);
  return res.json() as Promise<T>;
}

const mockChat = createMockChat();

export function sendChat(req: ChatRequest): Promise<ChatResponse> {
  return BASE ? post<ChatResponse>("/chat", req) : mockChat(req);
}

export class NoFitError extends Error {}

/** Runs the solver. The backend returns its own output format, mapped here. */
export async function getRecommendation(family: FamilyProfile, sessionId: string): Promise<Recommendation> {
  if (!BASE) {
    await new Promise((r) => setTimeout(r, 300));
    return demoRecommendationFor(family);
  }
  const { id, solution, claim_checks } = await post<{ id?: string; solution: SolverOutput; claim_checks?: SolverClaimSeries[] }>(
    "/recommend",
    { family: toSolverFamily(family, sessionId) },
  );
  if (solution.status !== "ok") throw new NoFitError("No mix fits this budget.");
  return toRecommendation(solution, claim_checks, id);
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
