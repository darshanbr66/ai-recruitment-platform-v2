/** Small inline spinner for a button mid-async-action. Paired with
 * `disabled` on the button itself (which also prevents duplicate
 * submissions) — this only adds the visual cue. */
export function Spinner({ label }: { label?: string }) {
  return (
    <span className="btn-spinner-group">
      <span className="spinner" aria-hidden="true" />
      {label}
    </span>
  );
}
