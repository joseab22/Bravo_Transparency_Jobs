import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import type { ReactNode } from "react";

interface FilterPanelProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function FilterPanel({ open, onClose, children }: FilterPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const appRoot = document.getElementById("__next");

    if (open) {
      appRoot?.setAttribute("inert", "");
      panelRef.current?.focus();
    } else {
      appRoot?.removeAttribute("inert");
    }

    return () => {
      appRoot?.removeAttribute("inert");
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-40">
      <div
        className="absolute inset-0 bg-slate-950/70"
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="All filters"
        tabIndex={-1}
        className="absolute right-0 top-0 flex h-full w-full max-w-md flex-col overflow-y-auto border-l border-slate-800 bg-slate-950 p-6 shadow-2xl outline-none sm:w-[26rem]"
      >
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-slate-100">All filters</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close filters panel"
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 outline-none ring-cyan-300 transition hover:border-cyan-300 hover:text-cyan-200 focus-visible:ring-2"
          >
            Close
          </button>
        </div>

        <div className="mt-6 flex flex-1 flex-col gap-4">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
