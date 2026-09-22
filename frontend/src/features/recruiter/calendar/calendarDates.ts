import type { CalendarEventResponse } from "../../../types/calendar";

export type CalendarView = "month" | "week" | "day";

const DAY_MS = 24 * 60 * 60 * 1000;

export function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

export function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

export function addDays(date: Date, days: number): Date {
  return new Date(date.getTime() + days * DAY_MS);
}

/** The Sunday on or before `date` — every view's week starts on Sunday. */
export function startOfWeek(date: Date): Date {
  const start = startOfDay(date);
  return addDays(start, -start.getDay());
}

/** 42 days (6 full weeks) covering the month `date` falls in, so the grid
 * is always a stable 6-row rectangle regardless of which weekday the 1st
 * lands on. */
export function getMonthGridDays(date: Date): Date[] {
  const firstOfMonth = new Date(date.getFullYear(), date.getMonth(), 1);
  const gridStart = startOfWeek(firstOfMonth);
  return Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
}

export function getWeekDays(date: Date): Date[] {
  const start = startOfWeek(date);
  return Array.from({ length: 7 }, (_, i) => addDays(start, i));
}

/** The [start, end) range to query the API for, given a view anchored on
 * `date` — a month view fetches its full 42-day grid so events from the
 * trailing/leading days of adjacent months still render. */
export function rangeForView(date: Date, view: CalendarView): { start: Date; end: Date } {
  if (view === "day") {
    const start = startOfDay(date);
    return { start, end: addDays(start, 1) };
  }
  if (view === "week") {
    const start = startOfWeek(date);
    return { start, end: addDays(start, 7) };
  }
  const days = getMonthGridDays(date);
  return { start: days[0], end: addDays(days[days.length - 1], 1) };
}

export function eventsOnDay(events: CalendarEventResponse[], day: Date): CalendarEventResponse[] {
  const dayStart = startOfDay(day).getTime();
  const dayEnd = dayStart + DAY_MS;
  return events.filter((event) => {
    const eventStart = new Date(event.start_at).getTime();
    const eventEnd = new Date(event.end_at).getTime();
    return eventStart < dayEnd && eventEnd >= dayStart;
  });
}

export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

/** Formats a `Date` as the value a `<input type="datetime-local">` expects
 * (local wall-clock time, no timezone/offset), and the reverse. */
export function toDateTimeLocalValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function fromDateTimeLocalValue(value: string): Date {
  return new Date(value);
}
