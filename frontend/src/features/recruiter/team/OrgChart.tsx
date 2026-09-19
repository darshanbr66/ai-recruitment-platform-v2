import { useMemo, useState } from "react";
import type { DepartmentResponse, EmployeeResponse } from "../../../types/teamHierarchy";
import "./orgChart.css";

const UNASSIGNED_KEY = "__unassigned__";
// Up to this many active employees the chart opens fully expanded (the
// familiar org-chart look); beyond it, departments start collapsed so a large
// organization doesn't open as a wall of cards.
const AUTO_EXPAND_LIMIT = 40;

interface Branch {
  key: string;
  name: string;
  employees: EmployeeResponse[];
  unassigned: boolean;
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
 */
export function OrgChart({
  organizationName,
  departments,
  employees,
}: {
  organizationName: string;
  departments: DepartmentResponse[];
  employees: EmployeeResponse[];
}) {
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
      name: department.name,
      employees: activeByDepartment.get(department.id) ?? [],
      unassigned: false,
    }));
    const unassigned = activeByDepartment.get(null) ?? [];
    if (unassigned.length > 0) {
      result.push({ key: UNASSIGNED_KEY, name: "Unassigned", employees: unassigned, unassigned: true });
    }
    return result;
  }, [departments, employees]);

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

      <div className="org-chart-scroll">
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
                      {branch.employees.map((employee) => (
                        <li key={employee.id} className="org-employee">
                          <span className="org-node-title">{employee.full_name}</span>
                          {employee.designation && (
                            <span className="org-employee-role">{employee.designation}</span>
                          )}
                        </li>
                      ))}
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
