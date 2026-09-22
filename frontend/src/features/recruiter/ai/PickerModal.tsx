import { useState, type ReactNode } from "react";
import { Alert } from "../../../shared/components/Alert";
import { EmptyState } from "../../../shared/components/EmptyState";
import { Modal } from "../../../shared/components/Modal";
import { SkeletonList } from "../../../shared/components/Skeleton";

/** A small generic "pick one from a searchable list" modal — backs both the
 * job picker ("Find candidates for a job" / "Compare candidates") and the
 * candidate picker ("Analyze a candidate") quick actions, so there's one
 * picking experience instead of two near-identical ones. */
export function PickerModal<T>({
  title,
  items,
  isLoading,
  isError,
  getKey,
  renderLabel,
  matches,
  onSelect,
  onClose,
  searchPlaceholder,
  emptyLabel,
}: {
  title: string;
  items: T[] | undefined;
  isLoading: boolean;
  isError: boolean;
  getKey: (item: T) => string;
  renderLabel: (item: T) => ReactNode;
  matches: (item: T, term: string) => boolean;
  onSelect: (item: T) => void;
  onClose: () => void;
  searchPlaceholder: string;
  emptyLabel: string;
}) {
  const [search, setSearch] = useState("");
  const term = search.trim().toLowerCase();
  const filtered = items?.filter((item) => (term ? matches(item, term) : true)) ?? [];

  return (
    <Modal title={title} onClose={onClose}>
      <input
        className="search-input"
        placeholder={searchPlaceholder}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        autoFocus
        style={{ marginBottom: "0.75rem" }}
      />

      {isLoading && <SkeletonList rows={4} />}
      {isError && <Alert>Could not load the list. Try again.</Alert>}

      {!isLoading && !isError && (
        filtered.length === 0 ? (
          <EmptyState compact title={emptyLabel} />
        ) : (
          <ul className="stack-sm" style={{ listStyle: "none", margin: 0, padding: 0, maxHeight: "20rem", overflowY: "auto" }}>
            {filtered.map((item) => (
              <li key={getKey(item)}>
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ width: "100%", justifyContent: "flex-start", textAlign: "left" }}
                  onClick={() => onSelect(item)}
                >
                  {renderLabel(item)}
                </button>
              </li>
            ))}
          </ul>
        )
      )}
    </Modal>
  );
}
