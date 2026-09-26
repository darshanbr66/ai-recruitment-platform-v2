import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Alert } from "../../../shared/components/Alert";
import { Icon } from "../../../shared/components/Icon";
import { Spinner } from "../../../shared/components/Spinner";
import type { CalendarAttendeeOption } from "../../../types/calendar";

/** Mirrors MAX_ATTENDEES in backend/app/schemas/calendar_event.py, so the
 * form stops at the same limit the API enforces. */
const MAX_ATTENDEES = 50;

/**
 * Multi-select for event attendees. Options come from
 * `/recruiter/calendar/attendee-options`, which returns the caller's own
 * organization only — this component never filters tenants itself.
 *
 * Shape is a combobox: the collapsed field shows only the chips for who is
 * already invited plus a search input, and the directory lives in a popover
 * that opens on focus. Nothing about the directory is rendered while the
 * popover is closed, so an organization with hundreds of people costs the
 * modal no vertical space and no DOM.
 *
 * Selection is driven entirely by `selectedIds`, so an id can only ever be
 * present once; already-selected people are dropped from the popover instead
 * of being offered a second time, and are removed via their chip.
 */
export function AttendeeSelector({
  options,
  selectedIds,
  onChange,
  isPending,
  isError,
  disabled,
}: {
  options: CalendarAttendeeOption[];
  selectedIds: string[];
  onChange: (next: string[]) => void;
  isPending: boolean;
  isError: boolean;
  disabled?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const listboxId = useId();
  const hintId = useId();
  const optionDomId = (index: number) => `${listboxId}-option-${index}`;

  const byId = useMemo(
    () => new Map(options.map((option) => [option.id, option])),
    [options],
  );

  // Selected ids that the directory doesn't describe (an attendee who has
  // since been deactivated) still render, so editing an event never silently
  // drops them from the payload.
  const selected = selectedIds.map((id) => byId.get(id) ?? null);

  const needle = query.trim().toLowerCase();
  const visible = useMemo(() => {
    const available = options.filter((option) => !selectedIds.includes(option.id));
    if (!needle) return available;
    return available.filter(
      (option) =>
        option.full_name.toLowerCase().includes(needle) ||
        option.email.toLowerCase().includes(needle),
    );
  }, [options, selectedIds, needle]);

  const atLimit = selectedIds.length >= MAX_ATTENDEES;
  // Keep the highlight on a row that still exists after filtering or picking.
  const activeIdx = Math.min(activeIndex, Math.max(visible.length - 1, 0));

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    // Escape belongs to the popover while it is open. Modal closes itself on a
    // document-level Escape, so without stopping the event here the first
    // Escape would discard the whole half-filled event form. Capture phase
    // runs before Modal's bubble-phase listener.
    // Focus is left alone: the options are never focusable, so it is still in
    // the search input — and re-focusing would re-fire onFocus and reopen the
    // popover we were asked to close.
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      setOpen(false);
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown, true);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [open]);

  // The popover is absolutely positioned inside the dialog, which scrolls
  // itself; nudge it into view so opening it near the bottom of a long form
  // doesn't leave it clipped below the fold.
  useEffect(() => {
    if (!open) return;
    listRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [open]);

  // Follow the keyboard highlight when it walks past the popover's scroll edge.
  useEffect(() => {
    if (!open) return;
    listRef.current
      ?.querySelector<HTMLElement>('[data-active="true"]')
      ?.scrollIntoView?.({ block: "nearest" });
  }, [open, activeIdx]);

  function add(id: string) {
    if (selectedIds.includes(id) || atLimit) return;
    onChange([...selectedIds, id]);
    // Inviting several people in a row is the common case, so the popover
    // stays open; clearing the query puts the rest of the directory back in
    // reach without a manual delete.
    setQuery("");
    setActiveIndex(0);
    inputRef.current?.focus();
  }

  function remove(id: string) {
    onChange(selectedIds.filter((selectedId) => selectedId !== id));
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setActiveIndex(Math.min(activeIdx + 1, visible.length - 1));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setActiveIndex(Math.max(activeIdx - 1, 0));
      return;
    }
    if (event.key === "Enter" && open) {
      // Always swallowed while the popover is open: Enter here picks a person,
      // it must never fall through and submit the event form.
      event.preventDefault();
      const option = visible[activeIdx];
      if (option) add(option.id);
      return;
    }
    if (event.key === "Backspace" && query === "" && selectedIds.length > 0) {
      remove(selectedIds[selectedIds.length - 1]);
      return;
    }
    if (event.key === "Tab") setOpen(false);
  }

  return (
    <div
      className="attendee-selector"
      ref={rootRef}
      onBlur={(event) => {
        // Tabbing out of the field closes the popover; moving between the
        // input, a chip and an option inside it does not.
        if (!rootRef.current?.contains(event.relatedTarget as Node | null)) setOpen(false);
      }}
    >
      {selectedIds.length > 0 && (
        <ul className="attendee-chips" aria-label="Selected attendees">
          {selected.map((option, index) => {
            const id = selectedIds[index];
            const label = option ? option.full_name : "Former team member";
            return (
              <li key={id} className="chip">
                <span>
                  {label}
                  {option && <span className="muted"> · {option.email}</span>}
                </span>
                <button
                  type="button"
                  className="chip-remove"
                  onClick={() => remove(id)}
                  disabled={disabled}
                  aria-label={`Remove ${label}`}
                >
                  <Icon name="x" size={12} />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {isPending && <Spinner label="Loading people…" />}
      {isError && <Alert>Could not load the people in your organization.</Alert>}

      {!isPending && !isError && options.length === 0 && (
        <p className="muted attendee-empty">No one else in your organization yet.</p>
      )}

      {!isPending && !isError && options.length > 0 && (
        <>
          <div className="search-input-wrap attendee-search">
            <Icon name="search" size={16} className="search-input-icon" />
            <input
              ref={inputRef}
              type="text"
              className="search-input"
              placeholder="Search people by name or email…"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setActiveIndex(0);
                setOpen(true);
              }}
              onFocus={() => setOpen(true)}
              onClick={() => setOpen(true)}
              onKeyDown={handleInputKeyDown}
              disabled={disabled}
              aria-label="Search attendees"
              aria-describedby={hintId}
              role="combobox"
              aria-expanded={open}
              aria-controls={listboxId}
              aria-haspopup="listbox"
              aria-autocomplete="list"
              aria-activedescendant={
                open && visible[activeIdx] ? optionDomId(activeIdx) : undefined
              }
            />
            {query && (
              <button
                type="button"
                className="search-input-clear"
                aria-label="Clear attendee search"
                onClick={() => {
                  setQuery("");
                  setActiveIndex(0);
                  inputRef.current?.focus();
                }}
              >
                <Icon name="x" size={14} />
              </button>
            )}

            {open && (
              <ul className="attendee-popover" id={listboxId} role="listbox" ref={listRef}>
                {visible.length === 0 && (
                  <li className="muted attendee-empty attendee-popover-empty" role="presentation">
                    {needle
                      ? `No one matches “${query}”.`
                      : "Everyone in your organization is already invited."}
                  </li>
                )}
                {visible.map((option, index) => (
                  <li
                    key={option.id}
                    id={optionDomId(index)}
                    className="attendee-option"
                    role="option"
                    aria-selected={index === activeIdx}
                    aria-disabled={atLimit || undefined}
                    data-active={index === activeIdx ? "true" : undefined}
                    // Keep focus in the input so the popover survives the click.
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => add(option.id)}
                    onMouseEnter={() => setActiveIndex(index)}
                  >
                    <span>{option.full_name}</span>
                    <span className="muted attendee-option-email">{option.email}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <p id={hintId} className="muted attendee-hint">
            {selectedIds.length === 0
              ? "No attendees selected — the event will be yours alone."
              : `${selectedIds.length} attendee${selectedIds.length === 1 ? "" : "s"} selected${atLimit ? " (maximum reached)" : ""}.`}
          </p>
        </>
      )}
    </div>
  );
}
