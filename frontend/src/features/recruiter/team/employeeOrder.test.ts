import { describe, expect, it } from "vitest";
import type { EmployeeResponse } from "../../../types/teamHierarchy";
import { applyEmployeeOrder, moveEmployeeId } from "./employeeOrder";

const NOW = new Date().toISOString();

function employee(id: string, department_id: string | null): EmployeeResponse {
  return {
    id,
    full_name: id,
    email: `${id}@example.com`,
    phone: null,
    employee_code: null,
    designation: null,
    department_id,
    manager_id: null,
    joining_date: null,
    location: null,
    employment_status: "ACTIVE",
    user_id: null,
    deleted_at: null,
    created_at: NOW,
    updated_at: NOW,
    department_name: null,
    manager_name: null,
  };
}

describe("moveEmployeeId", () => {
  const ids = ["a", "b", "c", "d"];

  it("moves to the top, between two others, and to the bottom", () => {
    expect(moveEmployeeId(ids, "d", "a", "before")).toEqual(["d", "a", "b", "c"]);
    expect(moveEmployeeId(ids, "d", "b", "before")).toEqual(["a", "d", "b", "c"]);
    expect(moveEmployeeId(ids, "a", "b", "after")).toEqual(["b", "a", "c", "d"]);
    expect(moveEmployeeId(ids, "a", "d", "after")).toEqual(["b", "c", "d", "a"]);
  });

  it("returns the very same array when nothing would change", () => {
    expect(moveEmployeeId(ids, "b", "b", "before")).toBe(ids);
    expect(moveEmployeeId(ids, "b", "a", "after")).toBe(ids); // already right after a
    expect(moveEmployeeId(ids, "b", "c", "before")).toBe(ids); // already right before c
  });

  it("ignores ids that aren't in the list, and never mutates its input", () => {
    expect(moveEmployeeId(ids, "x", "a", "before")).toBe(ids);
    expect(moveEmployeeId(ids, "a", "x", "before")).toBe(ids);
    moveEmployeeId(ids, "d", "a", "before");
    expect(ids).toEqual(["a", "b", "c", "d"]);
  });
});

describe("applyEmployeeOrder", () => {
  it("re-fills the group's slots in the new order and leaves everyone else in place", () => {
    const all = [
      employee("a1", "dept-a"),
      employee("b1", "dept-b"),
      employee("a2", "dept-a"),
      employee("a3", "dept-a"),
    ];

    const result = applyEmployeeOrder(all, ["a3", "a1", "a2"]);

    expect(result.map((e) => e.id)).toEqual(["a3", "b1", "a1", "a2"]);
    expect(all.map((e) => e.id)).toEqual(["a1", "b1", "a2", "a3"]); // input untouched
  });

  it("returns the list unchanged if an id is unknown", () => {
    const all = [employee("a1", null), employee("a2", null)];
    expect(applyEmployeeOrder(all, ["a2", "ghost"])).toBe(all);
  });
});
