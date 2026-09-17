import type { CSSProperties } from "react";

/** Shimmering placeholder blocks for page/list loading (QA: prefer skeleton
 * loaders over bare "Loading…" text for page/list loading). Kept to a
 * single shimmer animation, reused everywhere, so loading states stay
 * visually consistent instead of every page inventing its own. */
export function Skeleton({
  width = "100%",
  height = "1rem",
  style,
}: {
  width?: string | number;
  height?: string | number;
  style?: CSSProperties;
}) {
  return <span className="skeleton" style={{ width, height, ...style }} />;
}

/** A skeleton shaped like a `data-table` — used in place of the list body
 * while its query is pending, matching the real table's row height so the
 * page doesn't jump once data arrives. */
export function SkeletonTable({
  columns,
  rows = 5,
}: {
  columns: number;
  rows?: number;
}) {
  return (
    <div className="table-scroll">
      <table className="data-table skeleton-table" aria-hidden="true">
        <tbody>
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <tr key={rowIndex}>
              {Array.from({ length: columns }).map((_, colIndex) => (
                <td key={colIndex}>
                  <Skeleton height="0.9rem" width={colIndex === 0 ? "1.5rem" : "80%"} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A handful of skeleton lines for a card/detail-style pending state. */
export function SkeletonLines({ count = 4 }: { count?: number }) {
  return (
    <div className="stack-sm" aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} height="0.9rem" width={i === count - 1 ? "60%" : "100%"} />
      ))}
    </div>
  );
}
