// Language codes Sarvam's speech-to-text and text-to-speech both support.
export const SARVAM_LANGUAGES = new Set([
  "en-IN", "hi-IN", "bn-IN", "gu-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN",
]);

const SCRIPTS: [RegExp, string][] = [
  [/[ঀ-৿]/, "bn-IN"],
  [/[਀-੿]/, "pa-IN"],
  [/[઀-૿]/, "gu-IN"],
  [/[଀-୿]/, "od-IN"],
  [/[஀-௿]/, "ta-IN"],
  [/[ఀ-౿]/, "te-IN"],
  [/[ಀ-೿]/, "kn-IN"],
  [/[ഀ-ൿ]/, "ml-IN"],
];

/**
 * The voice to read a reply in, from the script the reply is written in.
 * Devanagari is Hindi unless the user spoke Marathi. Latin script is English.
 */
export function replyLanguage(text: string, userLanguage?: string): string {
  if (/[ऀ-ॿ]/.test(text)) return userLanguage === "mr-IN" ? "mr-IN" : "hi-IN";
  return SCRIPTS.find(([re]) => re.test(text))?.[1] ?? "en-IN";
}
