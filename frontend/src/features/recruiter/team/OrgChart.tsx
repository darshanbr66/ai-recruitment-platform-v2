import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type DragEvent,
  type KeyboardEvent,
} from "react";
import { Spinner } from "../../../shared/components/Spinner";
import type { DepartmentResponse, EmployeeResponse } from "../../../types/teamHierarchy";
import { moveEmployeeId, type DropPosition } from "./employeeOrder";
import "./orgChart.css";

const UNASSIGNED_KEY = "__unassigned__";
// Up to this many active employees the chart opens fully expanded (the
// familiar org-chart look); beyond it, departments start collapsed so a large
// organization doesn't open as a wall of cards.
const AUTO_EXPAND_LIMIT = 40;

interface Branch {
  key: string;
  // null for the Unassigned group, which is ordered like any department.
  departmentId: string | null;
  name: string;
  employees: EmployeeResponse[];
  unassigned: boolean;
}

interface DragState {
  branchKey: string;
  employeeId: string;
}

interface DropTarget {
  employeeId: string;
  position: DropPosition;
}

function employeeCountLabel(count: number): string {
  return `${count} ${count === 1 ? "employee" : "employees"}`;
}

/**
 * Organization chart: organization -> departments -> employees.
 *
 * Everything shown is derived from the `departments` and `employees` props,
 * which come straight from the same queries as the management UI below it —
 * so adding, renaming or removing a department, and adding, moving or
 * deactivating an employee, is reflected as soon as those queries refresh.
 * Nothing (organization, department or person) is hardcoded.
 *
 * Only ACTIVE employees appear, and only name and title — no email or phone.
 *
 * Employees appear in the order the `employees` prop lists them: the API
 * returns each department's employees in their persisted order, and this
 * component never sorts. When `onReorder` is given (the parent passes it only
 * to users allowed to manage employees — the backend enforces that too), each
 * employee gets a drag handle and can be dragged within their own department
 * (or the Unassigned group); the keyboard alternative is Arrow Up/Down on the
 * handle. `onReorder` receives that group's full new order of employee ids.
 */
export function OrgChart({
  organizationName,
  departments,
  employees,
  onReorder,
  isSavingOrder = false,
}: {
  organizationName: string;
  departments: DepartmentResponse[];
  employees: EmployeeResponse[];
  onReorder?: (departmentId: string | null, orderedEmployeeIds: string[]) => void;
  isSavingOrder?: boolean;
}) {
  const reorderable = onReorder !== undefined;
  const [dragging, setDragging] = useState<DragState | null>(null);
  const [dropTarget, setDropTarget] = useState<DropTarget | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const handleToFocus = useRef<string | null>(null);

  const branches = useMemo<Branch[]>(() => {
    const activeByDepartment = new Map<string | null, EmployeeResponse[]>();
    for (const employee of employees) {
      if (employee.employment_status !== "ACTIVE" || employee.deleted_at) continue;
      const list = activeByDepartment.get(employee.department_id) ?? [];
      list.push(employee);
      activeByDepartment.set(employee.department_id, list);
    }

    const result: Branch[] = departments.map((department) => ({
      key: department.id,
      departmentId: department.id,
      name: department.name,
      employees: activeByDepartment.get(department.id) ?? [],
      unassigned: false,
    }));
    const unassigned = activeByDepartment.get(null) ?? [];
    if (unassigned.length > 0) {
      result.push({
        key: UNASSIGNED_KEY,
        departmentId: null,
        name: "Unassigned",
        employees: unassigned,
        unassigned: true,
      });
    }
    return result;
  }, [departments, employees]);

  // Reordering moves the card in the DOM, which can drop keyboard focus from
  // the handle that was just used — put it back.
  useEffect(() => {
    const employeeId = handleToFocus.current;
    if (employeeId === null) return;
    handleToFocus.current = null;
    chartRef.current
      ?.querySelector<HTMLElement>(`[data-reorder-handle="${employeeId}"]`)
      ?.focus();
  });

  function clearDrag() {
    setDragging(null);
    setDropTarget(null);
  }

  function dropPositionFor(event: DragEvent<HTMLElement>): DropPosition {
    const box = event.currentTarget.getBoundingClientRect();
    return event.clientY < box.top + box.height / 2 ? "before" : "after";
  }

  function handleDragStart(event: DragEvent<HTMLElement>, branch: Branch, employee: EmployeeResponse) {
    setDragging({ branchKey: branch.key, employeeId: employee.id });
    // Firefox only starts a drag when some data is set.
    event.dataTransfer?.setData("text/plain", employee.id);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
  }

  function handleDragOver(event: DragEvent<HTMLElement>, branch: Branch, employee: EmployeeResponse) {
    // Employees can only be placed within their own department: over any
    // other list the drop is simply not allowed.
    if (dragging === null || dragging.branchKey !== branch.key) return;
    event.preventDefault();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "move";

    if (dragging.employeeId === employee.id) {
      if (dropTarget !== null) setDropTarget(null);
      return;
    }
    const position = dropPositionFor(event);
    if (dropTarget?.employeeId !== employee.id || dropTarget.position !== position) {
      setDropTarget({ employeeId: employee.id, position });
    }
  }

  function handleDrop(event: DragEvent<HTMLElement>, branch: Branch, employee: EmployeeResponse) {
    if (dragging === null || dragging.branchKey !== branch.key || onReorder === undefined) return;
    event.preventDefault();

    const currentIds = branch.employees.map((member) => member.id);
    const nextIds = moveEmployeeId(currentIds, dragging.employeeId, employee.id, dropPositionFor(event));
    clearDrag();
    if (nextIds !== currentIds) onReorder(branch.departmentId, nextIds);
  }

  function handleHandleKeyDown(event: KeyboardEvent<HTMLElement>, branch: Branch, index: number) {
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    event.preventDefault();
    const neighbour = branch.employees[index + (event.key === "ArrowUp" ? -1 : 1)];
    if (isSavingOrder || neighbour === undefined || onReorder === undefined) return;

    const employee = branch.employees[index];
    const nextIds = moveEmployeeId(
      branch.employees.map((member) => member.id),
      employee.id,
      neighbour.id,
      event.key === "ArrowUp" ? "before" : "after",
    );
    handleToFocus.current = employee.id;
    onReorder(branch.departmentId, nextIds);
  }

  const totalActive = branches.reduce((sum, branch) => sum + branch.employees.length, 0);
  const openByDefault = totalActive <= AUTO_EXPAND_LIMIT;
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const isOpen = (key: string) => overrides[key] ?? openByDefault;

  function toggle(key: string) {
    setOverrides((current) => ({ ...current, [key]: !(current[key] ?? openByDefault) }));
  }

  function setAll(open: boolean) {
    setOverrides(Object.fromEntries(branches.map((branch) => [branch.key, open])));
  }

  if (branches.length === 0) return null;

  const allOpen = branches.every((branch) => branch.employees.length === 0 || isOpen(branch.key));

  return (
    <section className="card" aria-labelledby="org-chart-title">
      <div className="org-chart-header">
        <h2 id="org-chart-title">Organization chart</h2>
        {reorderable && totalActive > 1 && (
          <span className="org-reorder-hint muted">
            {isSavingOrder ? <Spinner label="Saving order…" /> : "Drag employees to reorder them"}
          </span>
        )}
        {totalActive > 0 && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setAll(!allOpen)}
          >
            {allOpen ? "Collapse all" : "Expand all"}
          </button>
        )}
      </div>

      <div className="org-chart-scroll" ref={chartRef}>
        <div className="org-chart">
          <div className="org-node org-node-root" aria-label={`Organization: ${organizationName}`}>
            {organizationName}
          </div>

          <ul className="org-level" aria-label={`Departments of ${organizationName}`}>
            {branches.map((branch) => {
              const count = branch.employees.length;
              const open = count > 0 && isOpen(branch.key);
              const listId = `org-employees-${branch.key}`;
              const nodeClass = `org-node org-node-dept${branch.unassigned ? " org-node-unassigned" : ""}`;
              const content = (
                <>
                  <span className="org-node-title">{branch.name}</span>
                  <span className="org-node-meta">{employeeCountLabel(count)}</span>
                </>
              );

              return (
                <li key={branch.key} className="org-branch">
                  {count > 0 ? (
                    <button
                      type="button"
                      className={nodeClass}
                      aria-expanded={open}
                      aria-controls={listId}
                      aria-label={`${branch.name}, ${employeeCountLabel(count)}`}
                      onClick={() => toggle(branch.key)}
                    >
                      {content}
                    </button>
                  ) : (
                    <div className={nodeClass} aria-label={`${branch.name}, ${employeeCountLabel(count)}`}>
                      {content}
                    </div>
                  )}

                  {open && (
                    <ul
                      id={listId}
                      className="org-employees"
                      aria-label={`Employees in ${branch.name}`}
                    >
                      {branch.employees.map((employee, index) => {
                        const isDragged = dragging?.employeeId === employee.id;
                        const dropClass =
                          dropTarget?.employeeId === employee.id
                            ? ` org-employee-drop-${dropTarget.position}`
                            : "";
                        return (
                          <li
                            key={employee.id}
                            className={`org-employee${reorderable ? " org-employee-reorderable" : ""}${
                              isDragged ? " org-employee-dragging" : ""
                            }${dropClass}`}
                            draggable={reorderable ? !isSavingOrder : undefined}
                            onDragStart={
                              reorderable ? (event) => handleDragStart(event, branch, employee) : undefined
                            }
                            onDragOver={
                              reorderable ? (event) => handleDragOver(event, branch, employee) : undefined
                            }
                            onDrop={reorderable ? (event) => handleDrop(event, branch, employee) : undefined}
                            onDragEnd={reorderable ? clearDrag : undefined}
                          >
                            {reorderable && (
                              <span
                                role="button"
                                tabIndex={0}
                                className="org-drag-handle"
                                data-reorder-handle={employee.id}
                                aria-label={`Reorder ${employee.full_name}`}
                                aria-disabled={isSavingOrder}
                                title="Drag to reorder, or press the up/down arrow keys"
                                onKeyDown={(event) => handleHandleKeyDown(event, branch, index)}
                              >
                                <span aria-hidden="true">⋮⋮</span>
                              </span>
                            )}
                            <span className="org-node-title">{employee.full_name}</span>
                            {employee.designation && (
                              <span className="org-employee-role">{employee.designation}</span>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </section>
  );
}
