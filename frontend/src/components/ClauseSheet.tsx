"use client";

import { useEffect, useRef } from "react";
import type { Clause } from "@/lib/types";
import { DocIcon, XIcon } from "./icons";

export function ClauseSheet({ clause, onClose }: { clause: Clause | null; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (clause && !d.open) d.showModal();
    if (!clause && d.open) d.close();
  }, [clause]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className="m-auto w-[min(92vw,30rem)] rounded-2xl p-0 shadow-xl backdrop:bg-navy/40 backdrop:backdrop-blur-[2px]"
    >
      {clause && (
        <div className="p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2 text-navy">
              <DocIcon />
              <h2 className="font-semibold">{clause.title}</h2>
            </div>
            <button type="button" onClick={onClose} aria-label="Close" className="rounded-full p-1 text-muted hover:bg-canvas">
              <XIcon className="h-4 w-4" />
            </button>
          </div>
          <blockquote className="mt-4 border-l-4 border-sky bg-sky-soft/50 py-2 pl-3 pr-2 text-[15px] leading-6 text-ink">
            {clause.text}
          </blockquote>
          <p className="mt-3 text-xs text-muted">Source: {clause.source}</p>
        </div>
      )}
    </dialog>
  );
}
