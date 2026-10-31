"use client";

import { useEffect, useRef } from "react";
import type { Policy } from "@/lib/types";
import { cover, rupees } from "@/lib/format";
import { AlertIcon, DocIcon, XIcon } from "./icons";

const months = (m: number) => (m === 0 ? "None" : m % 12 === 0 ? `${m / 12} ${m === 12 ? "year" : "years"}` : `${m} ${m === 1 ? "month" : "months"}`);

/** The fine print for one policy, as stored in shared/policies.json. */
export function FinePrintSheet({ policy, onClose }: { policy: Policy | null; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (policy && !d.open) d.showModal();
    if (!policy && d.open) d.close();
  }, [policy]);

  const rows: [string, string][] = policy
    ? [
        ["Cover", cover(policy.sumInsured)],
        ...(policy.deductible ? [["Starts after", cover(policy.deductible)] as [string, string]] : []),
        ["Premium", `${rupees(policy.premium)} a year`],
        ["Co-pay", policy.copayPercent ? `You pay ${policy.copayPercent}% of each claim` : "None"],
        ["Wait for illnesses you already have", months(policy.waitsMonths.preExisting)],
        ["Wait for listed illnesses", months(policy.waitsMonths.specificIllness)],
        ["First wait for any illness", months(policy.waitsMonths.initial)],
      ]
    : [];

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className="m-auto w-[min(92vw,32rem)] rounded-2xl p-0 shadow-xl backdrop:bg-navy/40 backdrop:backdrop-blur-[2px]"
    >
      {policy && (
        <div className="p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-2 text-navy">
              <DocIcon className="mt-0.5 h-5 w-5" />
              <div>
                <h2 className="font-semibold">{policy.product}</h2>
                <p className="text-xs text-muted">{policy.insurer}</p>
              </div>
            </div>
            <button type="button" onClick={onClose} aria-label="Close" className="rounded-full p-1 text-muted hover:bg-canvas">
              <XIcon className="h-4 w-4" />
            </button>
          </div>

          <dl className="mt-4 divide-y divide-line rounded-xl border border-line text-sm">
            {rows.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 px-3 py-2">
                <dt className="text-muted">{k}</dt>
                <dd className="text-right font-medium text-ink">{v}</dd>
              </div>
            ))}
          </dl>

          {policy.catches.length > 0 && (
            <ul className="mt-4 space-y-1.5">
              {policy.catches.map((c) => (
                <li key={c} className="flex items-start gap-1.5 text-sm text-ink">
                  <AlertIcon className="mt-0.5 h-4 w-4 text-amber" />
                  {c}
                </li>
              ))}
            </ul>
          )}

          <p className="mt-4 text-xs text-muted">
            From the insurer&apos;s public brochure. Not yet checked against the policy wording.
            {policy.sourceUrl && (
              <>
                {" "}
                <a href={policy.sourceUrl} target="_blank" rel="noreferrer" className="font-medium text-sky hover:underline">
                  Insurer page
                </a>
              </>
            )}
          </p>
        </div>
      )}
    </dialog>
  );
}
