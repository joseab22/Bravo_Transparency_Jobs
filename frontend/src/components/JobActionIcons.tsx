import type { ReactNode } from "react";

import { Tooltip } from "@/components/Tooltip";

interface IconToggleButtonProps {
  pressed: boolean;
  pending: boolean;
  onClick: () => void;
  labelWhenOff: string;
  labelWhenOn: string;
  icon: ReactNode;
}

export function IconToggleButton({
  pressed,
  pending,
  onClick,
  labelWhenOff,
  labelWhenOn,
  icon,
}: IconToggleButtonProps) {
  const label = pressed ? labelWhenOn : labelWhenOff;

  return (
    <Tooltip label={label}>
      <button
        type="button"
        aria-pressed={pressed}
        aria-label={label}
        disabled={pending}
        onClick={onClick}
        className={`rounded-lg p-2 outline-none ring-accent transition focus-visible:ring-2 disabled:opacity-50 ${
          pressed
            ? "bg-accent/15 text-accent"
            : "text-ink-muted hover:bg-surface-2 hover:text-ink-secondary"
        }`}
      >
        {icon}
      </button>
    </Tooltip>
  );
}

interface IconButtonProps {
  pending: boolean;
  onClick: () => void;
  label: string;
  icon: ReactNode;
}

export function IconButton({ pending, onClick, label, icon }: IconButtonProps) {
  return (
    <Tooltip label={label}>
      <button
        type="button"
        aria-label={label}
        disabled={pending}
        onClick={onClick}
        className="rounded-lg p-2 text-ink-muted outline-none ring-accent transition hover:bg-surface-2 hover:text-ink-secondary focus-visible:ring-2 disabled:opacity-50"
      >
        {icon}
      </button>
    </Tooltip>
  );
}

export function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
      <path
        d="M12 3.5l2.6 5.4 5.9.8-4.3 4.2 1 5.9-5.2-2.8-5.2 2.8 1-5.9-4.3-4.2 5.9-.8L12 3.5z"
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function NoteIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
      <path
        d="M5 4.5h11.5L19 7v12.5a1 1 0 01-1 1H5a1 1 0 01-1-1v-14a1 1 0 011-1z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M8 10.5h8M8 14h8M8 17.5h5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
      <path
        d="M5 12.5l4.5 4.5L19 7"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-5 w-5">
      <path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
