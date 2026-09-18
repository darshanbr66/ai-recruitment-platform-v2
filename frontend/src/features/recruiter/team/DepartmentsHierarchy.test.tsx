import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../../shared/components/ToastContext";
import type { DepartmentResponse, EmployeeResponse } from "../../../types/teamHierarchy";
import { DepartmentsHierarchy } from "./DepartmentsHierarchy";
import * as teamApi from "./api";

let mockRoles: string[] = ["ORG_ADMIN"];
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: "test-token", user: { roles: mockRoles } }),
}));

const departments: DepartmentResponse[] = [
  {
    id: "dept-1",
    name: "Software Engineering",
    description: "Builds the product.",
    deleted_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    employee_count: 1,
  },
];

const employees: EmployeeResponse[] = [
  {
    id: "emp-1",
    full_name: "Sam Engineer",
    email: "sam@sigvitas.dev",
    phone: null,
    employee_code: null,
    designation: "Software Engineer",
    department_id: "dept-1",
    manager_id: null,
    joining_date: null,
    location: null,
    employment_status: "ACTIVE",
    user_id: null,
    deleted_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    department_name: "Software Engineering",
    manager_name: null,
  },
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

describe("DepartmentsHierarchy", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockRoles = ["ORG_ADMIN"];
  });

  it("shows department cards and, once expanded, its employees", async () => {
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);

    renderComponent();

    const heading = await screen.findByText("Software Engineering");
    fireEvent.click(heading);

    expect(await screen.findByText("Sam Engineer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ New department" })).toBeInTheDocument();
  });

  it("hides manage controls for non-ORG_ADMIN roles", async () => {
    mockRoles = ["RECRUITER"];
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue(departments);
    vi.spyOn(teamApi, "listEmployees").mockResolvedValue(employees);

    renderComponent();

    await screen.findByText("Software Engineering");
    expect(screen.queryByRole("button", { name: "+ New department" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Software Engineering"));
    await screen.findByText("Sam Engineer");
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "+ Add employee" })).not.toBeInTheDocument();
  });
});
