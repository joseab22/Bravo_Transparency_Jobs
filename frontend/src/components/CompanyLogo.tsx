import { useState } from "react";

interface CompanyLogoProps {
  name: string;
  logoUrl?: string | null;
  size?: number;
}

export function CompanyLogo({ name, logoUrl, size = 40 }: CompanyLogoProps) {
  const [failed, setFailed] = useState(false);
  const initial = name.trim().charAt(0).toUpperCase() || "?";

  if (!logoUrl || failed) {
    return (
      <div
        aria-hidden="true"
        style={{ width: size, height: size }}
        className="flex shrink-0 items-center justify-center rounded-lg border border-line bg-surface-2 text-sm font-semibold text-ink-secondary"
      >
        {initial}
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={logoUrl}
      alt=""
      aria-hidden="true"
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
      style={{ width: size, height: size }}
      className="shrink-0 rounded-lg border border-line-subtle bg-white object-contain p-1"
    />
  );
}
