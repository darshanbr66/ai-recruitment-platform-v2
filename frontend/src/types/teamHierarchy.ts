/** Mirrors backend/app/schemas/team_hierarchy.py. Deliberately separate
 * from types/auth.ts (User/RBAC) — most employees here have no portal
 * login at all. */

export type EmploymentStatus = "ACTIVE" | "INACTIVE";

export interface DepartmentResponse {
  id: string;
  name: string;
  description: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
  employee_count: number;
}

export interface DepartmentCreateRequest {
  name: string;
  description?: string | null;
}

export interface DepartmentUpdateRequest {
  name?: string;
  description?: string | null;
}

export interface DepartmentDeleteRequest {
  reason: string;
}

export interface EmployeeResponse {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  employee_code: string | null;
  designation: string | null;
  department_id: string | null;
  manager_id: string | null;
  joining_date: string | null;
  location: string | null;
  employment_status: EmploymentStatus;
  user_id: string | null;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
  department_name: string | null;
  manager_name: string | null;
}

export interface EmployeeCreateRequest {
  full_name: string;
  email: string;
  phone?: string | null;
  employee_code?: string | null;
  designation?: string | null;
  department_id?: string | null;
  manager_id?: string | null;
  joining_date?: string | null;
  location?: string | null;
}

export interface EmployeeUpdateRequest {
  full_name?: string;
  email?: string;
  phone?: string | null;
  employee_code?: string | null;
  designation?: string | null;
  manager_id?: string | null;
  joining_date?: string | null;
  location?: string | null;
}

export interface EmployeeMoveRequest {
  department_id: string | null;
}

export interface EmployeeDeactivateRequest {
  reason?: string | null;
}
