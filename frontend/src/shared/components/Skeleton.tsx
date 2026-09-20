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

/** Dashboard stat tiles: label, big number, caption — same footprint as the
 * real `.stat-card`, so the numbers land in place. */
export function SkeletonStatGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="card-grid skeleton-stat-grid" aria-hidden="true">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="stat-card skeleton-stat-card">
          <Skeleton height="0.7rem" width="55%" />
          <Skeleton height="2rem" width="42%" style={{ borderRadius: 8 }} />
        </div>
      ))}
    </div>
  );
}

/** A titled card with a few lines — for the panels beside/under the stats. */
export function SkeletonCard({ lines = 4 }: { lines?: number }) {
  return (
    <div className="card stack-sm" aria-hidden="true">
      <Skeleton height="1.1rem" width="38%" />
      <SkeletonLines count={lines} />
    </div>
  );
}

/** Avatar + two lines per row: candidate lists, activity streams, timelines. */
export function SkeletonList({ rows = 4 }: { rows?: number }) {
  return (
    <div className="stack-sm skeleton-list" aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton-list-row">
          <Skeleton width="2.25rem" height="2.25rem" style={{ borderRadius: 999, flexShrink: 0 }} />
          <div className="skeleton-list-lines">
            <Skeleton height="0.85rem" width={i % 2 ? "48%" : "62%"} />
            <Skeleton height="0.7rem" width="34%" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Organization chart: a root node, a row of department nodes, a few cards. */
export function SkeletonOrgChart() {
  return (
    <div className="card skeleton-org-chart" aria-hidden="true">
      <Skeleton height="1.1rem" width="9rem" />
      <div className="skeleton-org-tree">
        <Skeleton width="10rem" height="2.6rem" style={{ borderRadius: 10 }} />
        <div className="skeleton-org-row">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton-org-branch">
              <Skeleton width="9rem" height="2.6rem" style={{ borderRadius: 10 }} />
              <Skeleton width="7.5rem" height="2.1rem" style={{ borderRadius: 8 }} />
              {i !== 1 && <Skeleton width="7.5rem" height="2.1rem" style={{ borderRadius: 8 }} />}
            </div>
          ))}
        </div>
      </div>
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
