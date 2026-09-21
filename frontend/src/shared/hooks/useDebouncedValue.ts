import { useEffect, useState } from "react";

/** `value`, but only after it has stopped changing for `delayMs` — so a search
 * box that fires a request per keystroke fires one when the user pauses. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
