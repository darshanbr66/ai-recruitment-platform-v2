import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createEvent, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { BoundFunctions, queries } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../../lib/apiClient";
import { ToastProvider } from "../../../shared/components/ToastContext";
import type { DepartmentResponse, EmployeeResponse } from "../../../types/teamHierarchy";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { DepartmentsHierarchy } from "./DepartmentsHierarchy";
import * as teamApi from "./api";

let mockRoles: string[] = ["ORG_ADMIN"];
let mockOrganizationName: string | null = "Acme Corp";
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({
    accessToken: "test-token",
    user: { roles: mockRoles, organization_name: mockOrganizationName },
  }),
}));

// Vitest stubs out CSS imports, so read the stylesheet from disk to pin its rules.
const orgChartCss = readFileSync(
  resolve(process.cwd(), "src/features/recruiter/team/orgChart.css"),
  "utf-8",
);

const NOW = new Date().toISOString();

function makeDepartment(id: string, name: string, employee_count = 0): DepartmentResponse {
  return {
    id,
    name,
    description: null,
    deleted_at: null,
    created_at: NOW,
    updated_at: NOW,
    employee_count,
  };
}

function makeEmployee(
  id: string,
  full_name: string,
  department: DepartmentResponse | null,
  overrides: Partial<EmployeeResponse> = {},
): EmployeeResponse {
  return {
    id,
    full_name,
    email: `${id}@private.example`,
    phone: "555-0100",
    employee_code: null,
    designation: "Engineer",
    department_id: department?.id ?? null,
    manager_id: null,
    joining_date: null,
    location: null,
    employment_status: "ACTIVE",
    user_id: null,
    deleted_at: null,
    created_at: NOW,
    updated_at: NOW,
    department_name: department?.name ?? null,
    manager_name: null,
    ...overrides,
  };
}

const software = makeDepartment("dept-1", "Software Engineering", 1);
const departments: DepartmentResponse[] = [software];
const employees: EmployeeResponse[] = [
  makeEmployee("emp-1", "Sam Engineer", software, { designation: "Software Engineer" }),
];

function renderComponent() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <DepartmentsHierarchy />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The organization chart section (the management cards live outside it). */
async function findChart() {
  return within(await screen.findByRole("region", { name: "Organization chart" }));
}

describe("DepartmentsHierarchy", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockRoles = ["ORG_ADMIN"];
    mockOrganizationName = "Acme Corp";
  });

  it("labels the hierarchy with the signed-in user's own organization, not a hardcoded tenant", async () => {
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);

    renderComponent();

    expect(await screen.findByText(/Acme Corp\s*→\s*Departments/)).toBeInTheDocument();
    expect(screen.queryByText(/SIGVITAS/)).not.toBeInTheDocument();
  });

  it("falls back to a neutral label when the organization name is unavailable", async () => {
    mockOrganizationName = null;
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);

    renderComponent();

    expect(await screen.findByText(/Your organization\s*→\s*Departments/)).toBeInTheDocument();
  });

  it("shows department cards and, once expanded, its employees", async () => {
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);

    renderComponent();

    fireEvent.click(await screen.findByText("Software Engineering", { selector: "strong" }));

    expect(await screen.findByText("Sam Engineer", { selector: "td" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ New department" })).toBeInTheDocument();
  });

  it("hides manage controls for non-ORG_ADMIN roles", async () => {
    mockRoles = ["RECRUITER"];
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);

    renderComponent();

    await screen.findByText("Software Engineering", { selector: "strong" });
    expect(screen.queryByRole("button", { name: "+ New department" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Software Engineering", { selector: "strong" }));
    await screen.findByText("Sam Engineer", { selector: "td" });
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "+ Add employee" })).not.toBeInTheDocument();
  });
});

describe("Organization chart", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockRoles = ["ORG_ADMIN"];
    mockOrganizationName = "Acme Corp";
  });

  it("is built from the organization, departments and employees in the data", async () => {
    const design = makeDepartment("dept-2", "Design", 1);
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue([software, design]);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue([
      ...employees,
      makeEmployee("emp-2", "Dee Designer", design, { designation: "Product Designer" }),
    ]);

    renderComponent();
    const chart = await findChart();

    expect(chart.getByLabelText("Organization: Acme Corp")).toBeInTheDocument();
    expect(chart.getByRole("button", { name: "Software Engineering, 1 employee" })).toBeInTheDocument();
    expect(chart.getByRole("button", { name: "Design, 1 employee" })).toBeInTheDocument();
    expect(chart.getByText("Sam Engineer")).toBeInTheDocument();
    expect(chart.getByText("Software Engineer")).toBeInTheDocument(); // title
    expect(chart.getByText("Dee Designer")).toBeInTheDocument();
  });

  it("shows only the signed-in organization: Acme never shows SIGVITAS and vice versa", async () => {
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);

    mockOrganizationName = "Acme Corp";
    const acme = renderComponent();
    const acmeChart = await findChart();
    expect(acmeChart.getByLabelText("Organization: Acme Corp")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/sigvitas/i);
    acme.unmount();

    mockOrganizationName = "SIGVITAS";
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue([makeDepartment("dept-9", "Patent Engineering")]);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue([]);
    renderComponent();
    const sigvitasChart = await findChart();
    expect(sigvitasChart.getByLabelText("Organization: SIGVITAS")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/acme/i);
    expect(sigvitasChart.getByText("Patent Engineering")).toBeInTheDocument();
  });

  it("counts and lists only active employees, and shows only name and title", async () => {
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue([
      ...employees,
      makeEmployee("emp-3", "Ida Inactive", software, { employment_status: "INACTIVE" }),
    ]);

    renderComponent();
    const chart = await findChart();

    expect(chart.getByRole("button", { name: "Software Engineering, 1 employee" })).toBeInTheDocument();
    expect(chart.queryByText("Ida Inactive")).not.toBeInTheDocument();
    // No contact details in the visual hierarchy.
    expect(chart.queryByText(/@private\.example/)).not.toBeInTheDocument();
    expect(chart.queryByText(/555-0100/)).not.toBeInTheDocument();
  });

  it("collapses and expands a department, and all at once", async () => {
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);

    renderComponent();
    const chart = await findChart();
    const node = chart.getByRole("button", { name: "Software Engineering, 1 employee" });

    expect(node).toHaveAttribute("aria-expanded", "true"); // small orgs open expanded
    expect(chart.getByText("Sam Engineer")).toBeInTheDocument();

    fireEvent.click(node);
    expect(node).toHaveAttribute("aria-expanded", "false");
    expect(chart.queryByText("Sam Engineer")).not.toBeInTheDocument();

    fireEvent.click(node);
    expect(chart.getByText("Sam Engineer")).toBeInTheDocument();

    fireEvent.click(chart.getByRole("button", { name: "Collapse all" }));
    expect(chart.queryByText("Sam Engineer")).not.toBeInTheDocument();
    fireEvent.click(chart.getByRole("button", { name: "Expand all" }));
    expect(chart.getByText("Sam Engineer")).toBeInTheDocument();
  });

  it("starts collapsed for a large organization", async () => {
    const many = Array.from({ length: 41 }, (_, i) => makeEmployee(`e-${i}`, `Person ${i}`, software));
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue(many);

    renderComponent();
    const chart = await findChart();

    expect(chart.getByRole("button", { name: "Software Engineering, 41 employees" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(chart.queryByText("Person 0")).not.toBeInTheDocument();
  });

  it("shows a department with no employees, and unassigned employees separately", async () => {
    const empty = makeDepartment("dept-2", "Data Analyst");
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue([software, empty]);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue([
      ...employees,
      makeEmployee("emp-9", "Una Unassigned", null),
    ]);

    renderComponent();
    const chart = await findChart();

    expect(chart.getByLabelText("Data Analyst, 0 employees")).toBeInTheDocument();
    expect(chart.getByRole("button", { name: "Unassigned, 1 employee" })).toBeInTheDocument();
    expect(chart.getByText("Una Unassigned")).toBeInTheDocument();
  });

  it("adding a department updates the hierarchy", async () => {
    const patent = makeDepartment("dept-2", "Patent Engineering");
    const list = vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);
    vi.spyOn(teamApi, "createDepartment").mockResolvedValue(patent);

    renderComponent();
    const chart = await findChart();
    expect(chart.queryByText("Patent Engineering")).not.toBeInTheDocument();

    list.mockResolvedValue([software, patent]); // what the server returns after the create
    fireEvent.click(screen.getByRole("button", { name: "+ New department" }));
    fireEvent.change(await screen.findByLabelText("Name"), { target: { value: "Patent Engineering" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await chart.findByLabelText("Patent Engineering, 0 employees")).toBeInTheDocument();
  });

  it("renaming a department updates the hierarchy", async () => {
    const renamed = { ...software, name: "Platform Engineering" };
    const list = vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);
    vi.spyOn(teamApi, "updateDepartment").mockResolvedValue(renamed);

    renderComponent();
    const chart = await findChart();
    fireEvent.click(await screen.findByText("Software Engineering", { selector: "strong" }));

    list.mockResolvedValue([renamed]);
    fireEvent.click(screen.getByRole("button", { name: "Edit department" }));
    const nameInput = await screen.findByLabelText("Name");
    fireEvent.change(nameInput, { target: { value: "Platform Engineering" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await chart.findByRole("button", { name: "Platform Engineering, 1 employee" }),
    ).toBeInTheDocument();
    expect(chart.queryByText("Software Engineering")).not.toBeInTheDocument();
  });

  it("adding an employee puts them under the right department", async () => {
    const newHire = makeEmployee("emp-7", "Nia Newhire", software, { designation: "QA Engineer" });
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    const listEmployees = vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);
    vi.spyOn(teamApi, "createEmployee").mockResolvedValue(newHire);

    renderComponent();
    const chart = await findChart();
    fireEvent.click(await screen.findByText("Software Engineering", { selector: "strong" }));

    listEmployees.mockResolvedValue([...employees, newHire]);
    fireEvent.click(await screen.findByRole("button", { name: "+ Add employee" }));
    fireEvent.change(await screen.findByLabelText("Full name"), { target: { value: "Nia Newhire" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "nia@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await chart.findByText("Nia Newhire")).toBeInTheDocument();
    expect(chart.getByRole("button", { name: "Software Engineering, 2 employees" })).toBeInTheDocument();
    expect(chart.getByText("QA Engineer")).toBeInTheDocument();
  });

  it("moving an employee moves them in the hierarchy", async () => {
    const design = makeDepartment("dept-2", "Design");
    const moved = { ...employees[0], department_id: design.id, department_name: design.name };
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue([software, design]);
    const listEmployees = vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);
    vi.spyOn(teamApi, "moveEmployee").mockResolvedValue(moved);

    renderComponent();
    const chart = await findChart();
    expect(chart.getByRole("button", { name: "Software Engineering, 1 employee" })).toBeInTheDocument();
    fireEvent.click(await screen.findByText("Software Engineering", { selector: "strong" }));

    listEmployees.mockResolvedValue([moved]);
    fireEvent.click(await screen.findByRole("button", { name: "Move" }));
    const moveDialog = await screen.findByRole("dialog");
    fireEvent.change(within(moveDialog).getByLabelText("Department"), { target: { value: design.id } });

    expect(await chart.findByRole("button", { name: "Design, 1 employee" })).toBeInTheDocument();
    expect(chart.getByLabelText("Software Engineering, 0 employees")).toBeInTheDocument();
  });

  it("deactivating an employee removes them from the hierarchy", async () => {
    const deactivated = { ...employees[0], employment_status: "INACTIVE" as const };
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    const listEmployees = vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);
    vi.spyOn(teamApi, "deactivateEmployee").mockResolvedValue(deactivated);

    renderComponent();
    const chart = await findChart();
    expect(chart.getByText("Sam Engineer")).toBeInTheDocument();
    fireEvent.click(await screen.findByText("Software Engineering", { selector: "strong" }));

    listEmployees.mockResolvedValue([deactivated]);
    fireEvent.click(await screen.findByRole("button", { name: "Deactivate" }));

    await waitFor(() => expect(chart.queryByText("Sam Engineer")).not.toBeInTheDocument());
    expect(chart.getByLabelText("Software Engineering, 0 employees")).toBeInTheDocument();
  });

  it("uses a compact vertical layout on narrow screens instead of a wide diagram", () => {
    // jsdom can't lay anything out, so this pins the responsive rules in the
    // stylesheet itself: a <= 720px block that stacks the departments.
    const narrow = orgChartCss.slice(orgChartCss.indexOf("@media (max-width: 720px)"));
    expect(narrow).toContain("@media (max-width: 720px)");
    expect(narrow).toMatch(/\.org-level\s*\{[^}]*flex-direction:\s*column/);
    expect(narrow).toMatch(/\.org-chart\s*\{[^}]*width:\s*auto/);
    // and the desktop chart scrolls sideways rather than overflowing the page
    expect(orgChartCss).toMatch(/\.org-chart-scroll\s*\{[^}]*overflow-x:\s*auto/);
  });
});

describe("Organization chart ordering", () => {
  type Scope = BoundFunctions<typeof queries>;

  // Deliberately not alphabetical: the chart must show the persisted order.
  const team = () => [
    makeEmployee("emp-rajesh", "Rajesh", software),
    makeEmployee("emp-yashaswini", "Yashaswini", software),
    makeEmployee("emp-rajkumar", "Rajkumar", software),
    makeEmployee("emp-darshan", "Darshan", software),
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    mockRoles = ["ORG_ADMIN"];
    mockOrganizationName = "Acme Corp";
  });

  async function findEmployeeList(label = "Software Engineering") {
    const chart = await findChart();
    return within(chart.getByRole("list", { name: `Employees in ${label}` }));
  }

  function namesIn(list: Scope): string[] {
    return list
      .getAllByRole("listitem")
      .map((item) => item.querySelector(".org-node-title")?.textContent ?? "");
  }

  function cardFor(list: Scope, name: string): HTMLElement {
    return list.getByText(name, { selector: ".org-node-title" }).closest("li") as HTMLElement;
  }

  // jsdom draws nothing, so every box is 0-high at y=0: a negative clientY is
  // the upper half of a card ("before"), a positive one the lower half.
  const TOP_HALF = -1;
  const BOTTOM_HALF = 1;

  /** jsdom's drag events don't carry clientY, so pin it on the event. Returns
   * false when the handler called preventDefault (i.e. the drop is allowed). */
  function dragEventAt(type: "dragOver" | "drop", target: HTMLElement, clientY: number): boolean {
    const event = createEvent[type](target);
    Object.defineProperty(event, "clientY", { value: clientY });
    return fireEvent(target, event);
  }

  function setup(employees = team()) {
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    const listEmployees = vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);
    const reorder = vi.spyOn(teamApi, "reorderEmployees");
    renderComponent();
    return { listEmployees, reorder };
  }

  it("shows employees in the order the API returns them, not A-Z, and never shows a number", async () => {
    setup();
    const list = await findEmployeeList();

    expect(namesIn(list)).toEqual(["Rajesh", "Yashaswini", "Rajkumar", "Darshan"]);
    const shownText = list.getAllByRole("listitem").map((item) => item.textContent).join(" ");
    expect(shownText).not.toMatch(/\d/);
  });

  it("lets an admin drag an employee to the top, saves the order and keeps it", async () => {
    const { reorder, listEmployees } = setup();
    reorder.mockResolvedValue([]);
    const list = await findEmployeeList();

    fireEvent.dragStart(cardFor(list, "Darshan"));
    dragEventAt("dragOver", cardFor(list, "Rajesh"), TOP_HALF);
    expect(cardFor(list, "Rajesh")).toHaveClass("org-employee-drop-before"); // the preview

    // what the server holds once the request lands
    const [rajesh, yashaswini, rajkumar, darshan] = team();
    listEmployees.mockResolvedValue([darshan, rajesh, yashaswini, rajkumar]);
    dragEventAt("drop", cardFor(list, "Rajesh"), TOP_HALF);

    // (the request goes out once the optimistic update has been applied)
    await waitFor(() =>
      expect(reorder).toHaveBeenCalledWith(
        ["emp-darshan", "emp-rajesh", "emp-yashaswini", "emp-rajkumar"],
        "test-token",
      ),
    );
    await waitFor(() =>
      expect(namesIn(list)).toEqual(["Darshan", "Rajesh", "Yashaswini", "Rajkumar"]),
    );
  });

  it("supports dropping between two employees and at the bottom", async () => {
    const { reorder } = setup();
    reorder.mockResolvedValue([]);
    const list = await findEmployeeList();

    // Darshan between Rajesh and Yashaswini: onto Yashaswini's upper half
    fireEvent.dragStart(cardFor(list, "Darshan"));
    dragEventAt("drop", cardFor(list, "Yashaswini"), TOP_HALF);
    await waitFor(() =>
      expect(reorder).toHaveBeenLastCalledWith(
        ["emp-rajesh", "emp-darshan", "emp-yashaswini", "emp-rajkumar"],
        "test-token",
      ),
    );
    await waitFor(() => expect(screen.queryByText("Saving order…")).not.toBeInTheDocument());

    // Rajesh to the bottom: onto the lower half of the last card
    const last = namesIn(list).at(-1) as string;
    fireEvent.dragStart(cardFor(list, "Rajesh"));
    dragEventAt("drop", cardFor(list, last), BOTTOM_HALF);
    await waitFor(() => expect(reorder).toHaveBeenCalledTimes(2));
    expect(reorder.mock.lastCall?.[0].at(-1)).toBe("emp-rajesh");
  });

  it("does nothing when an employee is dropped where they already are", async () => {
    const { reorder } = setup();
    const list = await findEmployeeList();

    fireEvent.dragStart(cardFor(list, "Rajesh"));
    dragEventAt("drop", cardFor(list, "Rajesh"), TOP_HALF); // onto themselves
    fireEvent.dragStart(cardFor(list, "Rajesh"));
    dragEventAt("drop", cardFor(list, "Yashaswini"), TOP_HALF); // right where they already sit

    expect(reorder).not.toHaveBeenCalled();
  });

  it("shows a saving state, then restores the previous order and reports the error when saving fails", async () => {
    const { reorder } = setup();
    let fail: (error: Error) => void = () => undefined;
    reorder.mockImplementation(
      () =>
        new Promise((_resolve, reject) => {
          fail = reject;
        }),
    );
    const list = await findEmployeeList();

    fireEvent.dragStart(cardFor(list, "Darshan"));
    dragEventAt("drop", cardFor(list, "Rajesh"), TOP_HALF);

    // optimistic: the new order shows straight away, with a saving indicator
    await waitFor(() => expect(namesIn(list)[0]).toBe("Darshan"));
    expect(screen.getByText("Saving order…")).toBeInTheDocument();

    fail(new ApiError("This department's employees have changed.", 409, "conflict"));

    await waitFor(() =>
      expect(namesIn(list)).toEqual(["Rajesh", "Yashaswini", "Rajkumar", "Darshan"]),
    );
    expect(await screen.findByText("This department's employees have changed.")).toBeInTheDocument();
    expect(screen.queryByText("Saving order…")).not.toBeInTheDocument();
  });

  it("falls back to a generic message when the server can't be reached", async () => {
    const { reorder } = setup();
    reorder.mockRejectedValue(new TypeError("Failed to fetch"));
    const list = await findEmployeeList();

    fireEvent.dragStart(cardFor(list, "Darshan"));
    dragEventAt("drop", cardFor(list, "Rajesh"), TOP_HALF);

    expect(await screen.findByText(/Could not save the new order/)).toBeInTheDocument();
    await waitFor(() => expect(namesIn(list)[0]).toBe("Rajesh"));
  });

  it("only allows dropping within the same department", async () => {
    const design = makeDepartment("dept-2", "Design", 1);
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue([software, design]);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue([
      ...team(),
      makeEmployee("emp-dee", "Dee Designer", design),
    ]);
    const reorder = vi.spyOn(teamApi, "reorderEmployees").mockResolvedValue([]);
    renderComponent();
    const engineering = await findEmployeeList();
    const designers = await findEmployeeList("Design");

    fireEvent.dragStart(cardFor(engineering, "Darshan"));
    const acrossDepartments = dragEventAt("dragOver", cardFor(designers, "Dee Designer"), TOP_HALF);
    dragEventAt("drop", cardFor(designers, "Dee Designer"), TOP_HALF);
    expect(acrossDepartments).toBe(true); // not cancelled => the browser refuses the drop
    expect(reorder).not.toHaveBeenCalled();

    const withinDepartment = dragEventAt("dragOver", cardFor(engineering, "Rajesh"), TOP_HALF);
    expect(withinDepartment).toBe(false); // cancelled => the drop is allowed
  });

  it("saves only active employees and leaves inactive ones out of the list it sends", async () => {
    const { reorder } = setup([
      makeEmployee("emp-rajesh", "Rajesh", software),
      makeEmployee("emp-ida", "Ida Inactive", software, { employment_status: "INACTIVE" }),
      makeEmployee("emp-darshan", "Darshan", software),
    ]);
    reorder.mockResolvedValue([]);
    const list = await findEmployeeList();
    expect(namesIn(list)).toEqual(["Rajesh", "Darshan"]);

    fireEvent.dragStart(cardFor(list, "Darshan"));
    dragEventAt("drop", cardFor(list, "Rajesh"), TOP_HALF);

    await waitFor(() =>
      expect(reorder).toHaveBeenCalledWith(["emp-darshan", "emp-rajesh"], "test-token"),
    );
  });

  it("orders the Unassigned group as well", async () => {
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue([
      ...employees,
      makeEmployee("emp-una", "Una", null),
      makeEmployee("emp-uri", "Uri", null),
    ]);
    const reorder = vi.spyOn(teamApi, "reorderEmployees").mockResolvedValue([]);
    renderComponent();
    const unassigned = await findEmployeeList("Unassigned");

    fireEvent.dragStart(cardFor(unassigned, "Uri"));
    dragEventAt("drop", cardFor(unassigned, "Una"), TOP_HALF);

    await waitFor(() =>
      expect(reorder).toHaveBeenCalledWith(["emp-uri", "emp-una"], "test-token"),
    );
  });

  it("moves an employee with the keyboard: arrow keys on the drag handle", async () => {
    const { reorder } = setup();
    reorder.mockResolvedValue([]);
    const list = await findEmployeeList();

    fireEvent.keyDown(list.getByRole("button", { name: "Reorder Darshan" }), { key: "ArrowUp" });
    await waitFor(() =>
      expect(reorder).toHaveBeenLastCalledWith(
        ["emp-rajesh", "emp-yashaswini", "emp-darshan", "emp-rajkumar"],
        "test-token",
      ),
    );
    await waitFor(() => expect(screen.queryByText("Saving order…")).not.toBeInTheDocument());

    // already first / last: nothing to do
    reorder.mockClear();
    fireEvent.keyDown(list.getByRole("button", { name: "Reorder Rajesh" }), { key: "ArrowUp" });
    const last = namesIn(list).at(-1) as string;
    fireEvent.keyDown(list.getByRole("button", { name: `Reorder ${last}` }), { key: "ArrowDown" });
    expect(reorder).not.toHaveBeenCalled();
  });

  it("gives admins a drag handle on every employee", async () => {
    setup();
    const list = await findEmployeeList();

    for (const name of ["Rajesh", "Yashaswini", "Rajkumar", "Darshan"]) {
      expect(list.getByRole("button", { name: `Reorder ${name}` })).toBeInTheDocument();
      expect(cardFor(list, name)).toHaveAttribute("draggable", "true");
    }
  });

  it.each(["RECRUITER", "HIRING_MANAGER"])(
    "shows %s the persisted order without any reorder controls",
    async (role) => {
      mockRoles = [role];
      const { reorder } = setup();
      const list = await findEmployeeList();

      expect(namesIn(list)).toEqual(["Rajesh", "Yashaswini", "Rajkumar", "Darshan"]);
      expect(screen.queryByRole("button", { name: /^Reorder / })).not.toBeInTheDocument();
      expect(document.querySelector("[data-reorder-handle]")).toBeNull();
      expect(screen.queryByText("Drag employees to reorder them")).not.toBeInTheDocument();
      for (const card of list.getAllByRole("listitem")) {
        expect(card).not.toHaveAttribute("draggable");
      }

      // and a drag attempt does nothing
      fireEvent.dragStart(cardFor(list, "Darshan"));
      dragEventAt("drop", cardFor(list, "Rajesh"), TOP_HALF);
      expect(reorder).not.toHaveBeenCalled();
    },
  );
});
