import { confidenceBand, type ConfidenceBand } from "@/lib/jobFormatting";

interface ConfidenceGaugeProps {
  confidence: number | null | undefined;
  size?: number;
  className?: string;
}

// Status colors, one hue per band -- validated for >=3:1 contrast against
// the app's card surface in both themes (globals.css's --surface). Resolved
// through the same CSS custom properties every other themed color in the
// app uses (see tailwind.config.js), rather than fixed hex, so this
// component adapts automatically when .dark toggles rather than needing
// its own light/dark branch. Never shown without an adjacent text label
// (the number itself, plus confidenceLabel() text wherever this renders)
// per the "status color never carries meaning alone" rule -- this
// component is decorative reinforcement, not the sole signal.
const BAND_COLOR: Record<ConfidenceBand, string> = {
  high: "rgb(var(--positive))",
  medium: "rgb(var(--warning))",
  low: "rgb(var(--negative))",
  unknown: "rgb(var(--ink-muted))",
};

const STROKE_RATIO = 0.14; // stroke width as a fraction of size -- stays thin at any size

// A single ratio (score/100) against a fixed limit is a meter, not a chart:
// same-hue track (dim) + same-hue fill (vivid), proportional arc, rounded
// ends. Renders the score as text in the center so removing the ring
// entirely (e.g. a screen reader, forced-colors) still leaves the number.
export function ConfidenceGauge({ confidence, size = 56, className = "" }: ConfidenceGaugeProps) {
  const band = confidenceBand(confidence);
  const color = BAND_COLOR[band];
  const stroke = Math.max(3, size * STROKE_RATIO);
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const fraction = confidence == null ? 0 : Math.max(0, Math.min(confidence, 100)) / 100;
  const offset = circumference * (1 - fraction);
  const center = size / 2;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={`shrink-0 ${className}`}
      aria-hidden="true"
    >
      <circle cx={center} cy={center} r={radius} fill="none" stroke={color} strokeOpacity={0.18} strokeWidth={stroke} />
      {confidence != null && (
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${center} ${center})`}
        />
      )}
      <text
        x="50%"
        y="50%"
        textAnchor="middle"
        dominantBaseline="central"
        fill={color}
        style={{ fontSize: size * 0.32, fontWeight: 700, fontFamily: "inherit" }}
      >
        {confidence == null ? "—" : Math.round(confidence)}
      </text>
    </svg>
  );
}
