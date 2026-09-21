/** Prev/next pager with a "Showing 26–50 of 123" summary. Pure presentation:
 * the caller owns the page number and asks the server for that page. */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  disabled = false,
  noun = "results",
}: {
  /** 1-based. */
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  /** e.g. while the next page is loading. */
  disabled?: boolean;
  noun?: string;
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);

  return (
    <nav className="pager" aria-label="Pagination">
      <p className="pager-summary" aria-live="polite">
        {total === 0 ? `No ${noun}` : `Showing ${first}–${last} of ${total} ${noun}`}
      </p>
      {pageCount > 1 && (
        <div className="pager-controls">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => onPageChange(page - 1)}
            disabled={disabled || page <= 1}
            aria-label="Previous page"
          >
            ‹ Previous
          </button>
          <span className="pager-page">
            Page {page} of {pageCount}
          </span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => onPageChange(page + 1)}
            disabled={disabled || page >= pageCount}
            aria-label="Next page"
          >
            Next ›
          </button>
        </div>
      )}
    </nav>
  );
}
