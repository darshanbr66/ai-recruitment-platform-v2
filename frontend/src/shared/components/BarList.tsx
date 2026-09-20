import type { CSSProperties } from "react";

/**
 * Horizontal bars for a breakdown. The bar widths are each row's share of
 * `total`; bars grow in from zero (staggered) the first time they render.
 * `tone` optionally colours a row (e.g. by pipeline stage); without it every
 * bar uses the brand colour, exactly as before.
 */
export function BarList({
  rows,
  total,
  tone,
  showShare = false,
}: {
  rows: { id: string; label: string; count: number }[];
  total: number;
  /** A CSS colour for a row, looked up by `row.id`. */
  tone?: (id: string) => string;
  /** Show each row's percentage next to its count. */
  showShare?: boolean;
}) {
  return (
    <div className="stack-lg" style={{ gap: "0.75rem" }}>
      {rows.map((row, index) => {
        const share = total === 0 ? 0 : Math.round((row.count / total) * 100);
        const style = {
          width: `${share}%`,
          ...(tone ? { "--bar-tone": tone(row.id) } : {}),
          "--bar-delay": `${Math.min(index, 8) * 60}ms`,
        } as CSSProperties;
        return (
          <div key={row.id}>
            <div className="bar-row-head">
              <span>{row.label}</span>
              <span className="muted bar-row-count">
                {row.count}
                {showShare && <span className="bar-row-share"> · {share}%</span>}
              </span>
            </div>
            <div className="bar-track">
              <div className="bar-fill" style={style} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
