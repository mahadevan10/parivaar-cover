// Reads an assistant reply aloud with Sarvam AI text-to-speech (Bulbul), so the
// API key never reaches the browser. Docs: https://docs.sarvam.ai/api-reference-docs/text-to-speech/convert
import { replyLanguage, SARVAM_LANGUAGES } from "@/lib/sarvam";

const SARVAM_URL = "https://api.sarvam.ai/text-to-speech";
const MAX_CHARS = 1400;

/** Trims long replies at a sentence end so the voice never stops mid-word. */
function speakable(text: string): string {
  const flat = text.replace(/\s+/g, " ").trim();
  if (flat.length <= MAX_CHARS) return flat;
  const cut = flat.slice(0, MAX_CHARS);
  const end = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("। "), cut.lastIndexOf("? "));
  return end > 0 ? cut.slice(0, end + 1) : cut;
}

export async function POST(request: Request) {
  const key = process.env.SARVAM_API_KEY;
  if (!key) {
    return Response.json({ error: "Voice is not set up. Add SARVAM_API_KEY to frontend/.env.local." }, { status: 500 });
  }

  const body = await request.json().catch(() => null);
  const text = typeof body?.text === "string" ? speakable(body.text) : "";
  if (!text) return Response.json({ error: "Nothing to read." }, { status: 400 });

  const payload: Record<string, string> = {
    text,
    // `voice` is set when the browser reads a reply in pieces and has already picked one.
    target_language_code: SARVAM_LANGUAGES.has(body?.voice)
      ? body.voice
      : replyLanguage(text, typeof body?.language === "string" ? body.language : undefined),
  };
  if (process.env.SARVAM_TTS_MODEL) payload.model = process.env.SARVAM_TTS_MODEL;
  if (process.env.SARVAM_TTS_SPEAKER) payload.speaker = process.env.SARVAM_TTS_SPEAKER;

  const res = await fetch(SARVAM_URL, {
    method: "POST",
    headers: { "api-subscription-key": key, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => null);
  const audio: string | undefined = data?.audios?.[0];

  if (!res.ok || !audio) {
    console.error("[tts]", res.status, data?.error?.message ?? "no audio");
    return Response.json({ error: "Couldn't read that reply aloud." }, { status: 502 });
  }

  return new Response(Buffer.from(audio, "base64"), {
    headers: { "Content-Type": "audio/wav", "Cache-Control": "no-store" },
  });
}
