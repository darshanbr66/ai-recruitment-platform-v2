import type { EmployeeResponse } from "../../../types/teamHierarchy";

export type DropPosition = "before" | "after";

/**
 * The id list with `movedId` taken out and re-inserted next to `targetId`.
 * Returns the original array when the move would change nothing (dropping an
 * employee on themselves, or next to where they already are), so callers can
 * skip a pointless save.
 */
export function moveEmployeeId(
  ids: string[],
  movedId: string,
  targetId: string,
  position: DropPosition,
): string[] {
  if (movedId === targetId || !ids.includes(movedId) || !ids.includes(targetId)) return ids;

  const remaining = ids.filter((id) => id !== movedId);
  const targetIndex = remaining.indexOf(targetId);
  const insertAt = position === "before" ? targetIndex : targetIndex + 1;
  const next = [...remaining.slice(0, insertAt), movedId, ...remaining.slice(insertAt)];

  return next.every((id, index) => id === ids[index]) ? ids : next;
}

/**
 * Reflects a new order for one group of employees in the full employee list
 * (which mixes every department): the listed employees keep the slots they
 * already occupy in the list but are filled in the new order, and everyone
 * else stays exactly where they were. Used to update the cache optimistically
 * while the reorder request is in flight.
 */
export function applyEmployeeOrder(
  employees: EmployeeResponse[],
  orderedIds: string[],
): EmployeeResponse[] {
  const byId = new Map(employees.map((employee) => [employee.id, employee]));
  const reordered = orderedIds.flatMap((id) => byId.get(id) ?? []);
  if (reordered.length !== orderedIds.length) return employees;

  const wanted = new Set(orderedIds);
  let next = 0;
  return employees.map((employee) => (wanted.has(employee.id) ? reordered[next++] : employee));
}
