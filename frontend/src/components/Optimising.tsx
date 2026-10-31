"use client";

import { useEffect, useState } from "react";
import { CheckIcon, SpinnerIcon } from "./icons";

const STEPS = [
  "Reading policy wordings: room rent, co-pay, waiting periods, sub-limits",
  "Testing floater, individual and top-up combinations",
  "Running claim checks for each family member",
];

/** Shows the solver's steps while the recommendation loads. */
export function Optimising({ memberCount }: { memberCount: number }) {
  const [done, setDone] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setDone((d) => Math.min(d + 1, STEPS.length)), 800);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="mx-auto flex w-full max-w-lg flex-col gap-5 p-6 pt-16" aria-live="polite">
      <div>
        <h2 className="text-lg font-semibold text-navy">Finding the best mix for {memberCount} people</h2>
        <p className="text-sm text-muted">The solver picks the policies. I only explain them.</p>
      </div>
      <ol className="space-y-3">
        {STEPS.map((s, i) => (
          <li key={s} className={`flex items-start gap-3 rounded-xl border bg-white p-3 text-sm transition ${i <= done ? "border-line opacity-100" : "border-transparent opacity-40"}`}>
            <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${i < done ? "bg-sky text-navy" : "bg-navy-soft text-navy"}`}>
              {i < done ? <CheckIcon className="h-4 w-4" /> : i === done ? <SpinnerIcon className="h-4 w-4" /> : i + 1}
            </span>
            <span className="pt-0.5 text-ink">{s}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
