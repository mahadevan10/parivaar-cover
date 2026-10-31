// Proxies a short voice clip to Sarvam AI speech-to-text, so the API key never
// reaches the browser. Docs: https://docs.sarvam.ai/api-reference-docs/speech-to-text/transcribe

const SARVAM_URL = "https://api.sarvam.ai/speech-to-text";
const MAX_BYTES = 5 * 1024 * 1024;

// Words Sarvam should expect, so insurance terms and demo names come back spelled right.
const KEYTERMS = [
  "super top-up", "family floater", "co-pay", "room rent", "waiting period", "deductible",
  "sum insured", "diabetes", "diabetic", "lakh", "premium",
  "Rahul", "Sneha", "Aarav", "Mohan", "Lata", "Pune",
];

export async function POST(request: Request) {
  const key = process.env.SARVAM_API_KEY;
  if (!key) {
    return Response.json({ error: "Voice is not set up. Add SARVAM_API_KEY to frontend/.env.local." }, { status: 500 });
  }

  const incoming = await request.formData();
  const file = incoming.get("file");
  if (!(file instanceof Blob) || file.size === 0) {
    return Response.json({ error: "No audio received." }, { status: 400 });
  }
  if (file.size > MAX_BYTES) {
    return Response.json({ error: "That clip is too long. Keep it under 30 seconds." }, { status: 413 });
  }

  // Browsers label recordings like "audio/webm;codecs=opus". Sarvam only accepts the bare type.
  const audio = new Blob([file], { type: file.type.split(";")[0] || "audio/webm" });

  const form = new FormData();
  form.append("file", audio, file instanceof File ? file.name : "speech.webm");
  form.append("language_code", process.env.SARVAM_STT_LANGUAGE ?? "unknown");
  form.append("keyterms", JSON.stringify(KEYTERMS));
  if (process.env.SARVAM_STT_MODEL) form.append("model", process.env.SARVAM_STT_MODEL);
  if (process.env.SARVAM_STT_MODE) form.append("mode", process.env.SARVAM_STT_MODE);

  const res = await fetch(SARVAM_URL, {
    method: "POST",
    headers: { "api-subscription-key": key },
    body: form,
  });
  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const message = data?.error?.message ?? `Sarvam returned ${res.status}`;
    console.error("[stt]", res.status, message);
    const friendly =
      res.status === 429 ? "Voice is busy right now. Please type, or try again in a moment." :
      res.status === 403 ? "The Sarvam key was rejected. Check SARVAM_API_KEY." :
      "Couldn't understand that clip. Please try again or type.";
    return Response.json({ error: friendly, detail: message }, { status: 502 });
  }

  return Response.json({
    transcript: (data?.transcript ?? "").trim(),
    languageCode: data?.language_code ?? undefined,
  });
}
