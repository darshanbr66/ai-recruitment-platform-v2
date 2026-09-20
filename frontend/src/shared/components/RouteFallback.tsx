import { Skeleton, SkeletonCard } from "./Skeleton";

/** Shown while a lazily-loaded page's code arrives: a page-shaped skeleton
 * (title + two cards) rather than a spinner, so the frame stays put and the
 * page "fills in". */
export function RouteFallback() {
  return (
    <div className="stack-lg" role="status" aria-label="Loading page">
      <div aria-hidden="true">
        <Skeleton height="1.9rem" width="14rem" style={{ borderRadius: 8 }} />
      </div>
      <SkeletonCard lines={3} />
      <SkeletonCard lines={5} />
    </div>
  );
}
