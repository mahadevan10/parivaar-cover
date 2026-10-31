"use client";

import { useEffect, useState } from "react";
import { CheckIcon, SpinnerIcon } from "./icons";

const STEPS = [
  "Reading policy wordings: room rent, co-pay, waiting periods, sub-limits",
  "Testing floater, individual and top-up combinations",
  "Running claim checks for each family member",
];

// Big families can keep the solver busy for close to a minute.
const SLOW_AFTER_MS = 6000;

type Props = {
  memberCount: number;
  /** True once the solver has answered. The solver step waits for it. */
  finished: boolean;
  onFinePrintRead: () => void;
  /** Called after every step has ticked. */
  onComplete: () => void;
};

/** Shows the solver's steps while the recommendation loads. */
export function Optimising({ memberCount, finished, onFinePrintRead, onComplete }: Props) {
  const [done, setDone] = useState(0);
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (done === 1 && !finished) return; // still waiting on the solver
    const delay = [1200, 700, 500, 600][done];
    const t = setTimeout(() => {
      if (done === STEPS.length) return onComplete();
      if (done === 0) onFinePrintRead();
      setDone(done + 1);
    }, delay);
    return () => clearTimeout(t);
  }, [done, finished, onFinePrintRead, onComplete]);

  useEffect(() => {
    if (finished) return;
    const t = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(t);
  }, [finished]);

  return (
    <div className="mx-auto flex w-full max-w-lg flex-col gap-5 p-6 pt-16" aria-live="polite" aria-busy={done < STEPS.length}>
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
      {slow && !finished && (
        <p className="text-sm text-muted">Still working. A family of {memberCount} has many more combinations to test, so this can take a minute.</p>
      )}
      {done === STEPS.length && <p className="text-sm font-medium text-navy">Done. Here is your mix.</p>}
    </div>
  );
}
