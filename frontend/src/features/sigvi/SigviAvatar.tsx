import { useId } from "react";

/** Sigvi's mark: a signal-blue orb with a four-point spark and two graph nodes
 * — the same "talent graph" motif as the SIGVITAS logo, so the assistant reads
 * as part of the brand rather than a stock chat widget. Decorative: the
 * accessible name always comes from the surrounding text. */
export function SigviAvatar({ size = 32 }: { size?: number }) {
  const gradient = useId();
  return (
    <svg
      className="sigvi-avatar"
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id={gradient} x1="4" y1="3" x2="28" y2="29" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="var(--kind-ai)" />
          <stop offset="1" stopColor="var(--color-primary-solid)" />
        </linearGradient>
      </defs>
      <circle cx="16" cy="16" r="16" fill={`url(#${gradient})`} />
      <path
        d="M16 7.5c.6 4.6 1.9 5.9 6.5 6.5-4.6.6-5.9 1.9-6.5 6.5-.6-4.6-1.9-5.9-6.5-6.5 4.6-.6 5.9-1.9 6.5-6.5z"
        fill="#fff"
      />
      <circle cx="22.8" cy="22.4" r="1.7" fill="#fff" fillOpacity="0.85" />
      <circle cx="9.4" cy="21.6" r="1.2" fill="#fff" fillOpacity="0.6" />
      <path d="M11 20.9l4-2.6M21.6 21.3l-3.6-2" stroke="#fff" strokeOpacity="0.45" strokeWidth="0.9" strokeLinecap="round" />
    </svg>
  );
}
