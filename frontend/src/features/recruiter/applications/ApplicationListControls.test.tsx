import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApplicationListControls, SEARCH_DEBOUNCE_MS } from "./ApplicationListControls";
import { DEFAULT_LIST_STATE, EMPTY_FILTERS, type ApplicationListState } from "./applicationFilters";

function setup(state: ApplicationListState = DEFAULT_LIST_STATE) {
  const onChange = vi.fn();
  const view = render(
    <ApplicationListControls
      state={state}
      onChange={onChange}
      fields={["status", "applied"]}
      searchLabel="Search"
      searchPlaceholder="Search…"
    />,
  );
  const rerenderWith = (next: ApplicationListState) =>
    view.rerender(
      <ApplicationListControls
        state={next}
        onChange={onChange}
        fields={["status", "applied"]}
        searchLabel="Search"
        searchPlaceholder="Search…"
      />,
    );
  return { onChange, rerenderWith, box: () => screen.getByRole("searchbox", { name: "Search" }) };
}

const advance = (ms: number) =>
  act(() => {
    vi.advanceTimersByTime(ms);
  });

describe("ApplicationListControls — search debounce", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("waits for typing to pause: nothing before the delay, exactly one change at it", () => {
    const { onChange, box } = setup();

    fireEvent.change(box(), { target: { value: "jane" } });
    advance(SEARCH_DEBOUNCE_MS - 1);
    expect(onChange).not.toHaveBeenCalled();

    advance(1);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({
      ...DEFAULT_LIST_STATE,
      filters: { ...EMPTY_FILTERS, q: "jane" },
      page: 1,
    });
  });

  it("restarts the wait on each keystroke, so a burst is one change", () => {
    const { onChange, box } = setup();

    for (const value of ["j", "ja", "jan", "jane"]) {
      fireEvent.change(box(), { target: { value } });
      advance(SEARCH_DEBOUNCE_MS - 100); // each pause is shorter than the delay
    }
    expect(onChange).not.toHaveBeenCalled();

    advance(100);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0].filters.q).toBe("jane");
  });

  it("sends immediately on Enter, and does not send again when the timer fires", () => {
    const { onChange, box } = setup();

    fireEvent.change(box(), { target: { value: "asha" } });
    fireEvent.submit(box().closest("form") as HTMLFormElement);
    expect(onChange).toHaveBeenCalledTimes(1);

    advance(SEARCH_DEBOUNCE_MS * 2);
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("resets to page 1, whatever page it was on", () => {
    const { onChange, box } = setup({ ...DEFAULT_LIST_STATE, page: 4 });

    fireEvent.change(box(), { target: { value: "x" } });
    advance(SEARCH_DEBOUNCE_MS);

    expect(onChange.mock.calls[0][0].page).toBe(1);
  });

  it("trims the text it sends and sends nothing for an unchanged search", () => {
    const { onChange, box } = setup({
      ...DEFAULT_LIST_STATE,
      filters: { ...EMPTY_FILTERS, q: "jane" },
    });

    fireEvent.change(box(), { target: { value: "  jane  " } });
    advance(SEARCH_DEBOUNCE_MS);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("shows a search that changed elsewhere (Clear all, browser back) without echoing it back", () => {
    const { onChange, box, rerenderWith } = setup({
      ...DEFAULT_LIST_STATE,
      filters: { ...EMPTY_FILTERS, q: "jane" },
    });
    expect(box()).toHaveValue("jane");

    rerenderWith({ ...DEFAULT_LIST_STATE, filters: { ...EMPTY_FILTERS, q: "" } });
    expect(box()).toHaveValue("");

    advance(SEARCH_DEBOUNCE_MS * 2);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("sends no change if unmounted before the delay", () => {
    const { onChange, box } = setup();
    fireEvent.change(box(), { target: { value: "gone" } });
    // (unmount happens in cleanup; the timer must not fire into a dead component)
    advance(SEARCH_DEBOUNCE_MS - 1);
    expect(onChange).not.toHaveBeenCalled();
  });
});
