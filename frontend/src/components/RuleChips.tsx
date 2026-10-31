"use client";

import type { Requirements } from "@/lib/types";
import { ruleChips } from "@/lib/rules";
import { XIcon } from "./icons";

type Props = {
  requirements?: Requirements;
  nameOf: (id: string) => string;
  policyName?: (id: string) => string | undefined;
  /** Called with the rules minus the one removed. Leave out to show the chips read-only. */
  onRemove?: (next: Requirements) => void;
  disabled?: boolean;
};

/** The rules the user set, like "No co-pay", each with a button to take it out. */
export function RuleChips({ requirements, nameOf, policyName = () => undefined, onRemove, disabled }: Props) {
  const chips = ruleChips(requirements, nameOf, policyName);
  if (chips.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-sm">
      <span className="text-muted">Your rules:</span>
      {chips.map((c) => (
        <span key={c.key} className="inline-flex items-center gap-1 rounded-full bg-sky-soft py-0.5 pl-2.5 pr-1 font-medium text-navy">
          {c.label}
          {onRemove && (
            <button
              type="button"
              onClick={() => onRemove(c.without)}
              disabled={disabled}
              aria-label={`Remove the rule ${c.label}`}
              className="rounded-full p-0.5 hover:bg-white disabled:opacity-40"
            >
              <XIcon className="h-3.5 w-3.5" />
            </button>
          )}
        </span>
      ))}
    </div>
  );
}
