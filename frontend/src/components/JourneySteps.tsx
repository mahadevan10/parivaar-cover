import type { Stage } from "@/lib/types";
import { CheckIcon } from "./icons";

const STEPS: { id: Stage; label: string }[] = [
  { id: "talk", label: "Talk" },
  { id: "fine_print", label: "Read the fine print" },
  { id: "optimise", label: "Optimise" },
  { id: "explain", label: "Explain" },
];

export function JourneySteps({ stage }: { stage: Stage }) {
  const current = STEPS.findIndex((s) => s.id === stage);
  return (
    <ol className="flex items-center gap-1 text-xs sm:gap-2" aria-label="Progress">
      {STEPS.map((s, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <li key={s.id} className={`items-center gap-1 sm:gap-2 ${active ? "flex" : "hidden sm:flex"}`}>
            {i > 0 && <span className={`hidden h-px w-3 sm:block sm:w-6 ${done || active ? "bg-sky" : "bg-white/25"}`} />}
            <span
              aria-current={active ? "step" : undefined}
              className={`flex items-center gap-1.5 rounded-full px-2 py-1 transition-colors ${
                active ? "bg-sky text-navy font-semibold" : done ? "text-sky" : "text-white/55"
              }`}
            >
              <span className={`flex h-4 w-4 items-center justify-center rounded-full text-[10px] ${
                active ? "bg-navy text-white" : done ? "bg-sky text-navy" : "border border-white/40"
              }`}>
                {done ? <CheckIcon className="h-3 w-3" /> : i + 1}
              </span>
              <span className={active ? "" : "hidden md:inline"}>{s.label}</span>
              {active && <span className="sr-only">, step {i + 1} of {STEPS.length}</span>}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
