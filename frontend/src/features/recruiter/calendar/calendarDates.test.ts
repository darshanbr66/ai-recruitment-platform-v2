import { describe, expect, it } from "vitest";
import {
  addDays,
  eventsOnDay,
  getMonthGridDays,
  getWeekDays,
  isSameDay,
  rangeForView,
  startOfWeek,
} from "./calendarDates";

describe("calendarDates", () => {
  it("builds a 42-day month grid starting on a Sunday", () => {
    const days = getMonthGridDays(new Date(2026, 8, 22)); // September 2026
    expect(days).toHaveLength(42);
    expect(days[0].getDay()).toBe(0);
    // The grid must fully contain every day of the anchor month.
    const inMonth = days.filter((d) => d.getMonth() === 8);
    expect(inMonth).toHaveLength(30);
  });

  it("builds a 7-day week starting on Sunday", () => {
    const days = getWeekDays(new Date(2026, 8, 24)); // a Thursday
    expect(days).toHaveLength(7);
    expect(days[0].getDay()).toBe(0);
    expect(isSameDay(days[6], addDays(days[0], 6))).toBe(true);
  });

  it("computes a [start, end) range matching the selected view", () => {
    const anchor = new Date(2026, 8, 24, 10, 30);
    const day = rangeForView(anchor, "day");
    expect(day.end.getTime() - day.start.getTime()).toBe(24 * 60 * 60 * 1000);

    const week = rangeForView(anchor, "week");
    expect(week.end.getTime() - week.start.getTime()).toBe(7 * 24 * 60 * 60 * 1000);
    expect(week.start.getTime()).toBe(startOfWeek(anchor).getTime());
  });

  it("filters events that overlap a given day", () => {
    const day = new Date(2026, 8, 22);
    const events = [
      { start_at: new Date(2026, 8, 22, 9).toISOString(), end_at: new Date(2026, 8, 22, 10).toISOString() },
      { start_at: new Date(2026, 8, 21, 9).toISOString(), end_at: new Date(2026, 8, 21, 10).toISOString() },
      // spans midnight into the target day
      { start_at: new Date(2026, 8, 21, 23).toISOString(), end_at: new Date(2026, 8, 22, 1).toISOString() },
    ] as never[];

    const result = eventsOnDay(events, day);
    expect(result).toHaveLength(2);
  });
});
