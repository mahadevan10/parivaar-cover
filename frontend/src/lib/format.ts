const inr = new Intl.NumberFormat("en-IN");

/** ₹1,07,000 */
export function rupees(n: number): string {
  return `₹${inr.format(Math.round(n))}`;
}

/** ₹25L, ₹1.05 crore */
export function cover(n: number): string {
  if (n >= 1_00_00_000) {
    const cr = n / 1_00_00_000;
    return `₹${Number(cr.toFixed(2))} crore`;
  }
  if (n >= 1_00_000) return `₹${Number((n / 1_00_000).toFixed(1))}L`;
  return rupees(n);
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

const LANGUAGES: Record<string, string> = {
  "hi-IN": "Hindi",
  "en-IN": "English",
  "mr-IN": "Marathi",
  "bn-IN": "Bengali",
  "ta-IN": "Tamil",
  "te-IN": "Telugu",
  "kn-IN": "Kannada",
  "ml-IN": "Malayalam",
  "gu-IN": "Gujarati",
  "pa-IN": "Punjabi",
  "od-IN": "Odia",
  "ur-IN": "Urdu",
};

export function languageName(code?: string): string | undefined {
  if (!code) return undefined;
  return LANGUAGES[code] ?? code;
}

const AVATAR_COLORS = [
  "bg-navy text-white",
  "bg-sky text-navy",
  "bg-amber text-navy",
  "bg-teal-600 text-white",
  "bg-rose-500 text-white",
  "bg-indigo-500 text-white",
];

export function avatarColor(index: number): string {
  return AVATAR_COLORS[index % AVATAR_COLORS.length];
}
