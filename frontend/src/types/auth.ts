/**
 * Mirrors backend/app/schemas/{auth,user,organization}.py. Kept in sync by
 * hand for now — see docs/architecture.md § 6.
 */

export type AssignableRole = "ORG_ADMIN" | "RECRUITER" | "HIRING_MANAGER" | "INTERVIEWER";

export const ASSIGNABLE_ROLES: AssignableRole[] = [
  "ORG_ADMIN",
  "RECRUITER",
  "HIRING_MANAGER",
  "INTERVIEWER",
];

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserResponse {
  id: string;
  organization_id: string | null;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
  roles: string[];
  /** Only populated by `GET /auth/me`; null for a SUPER_ADMIN. */
  organization_name?: string | null;
}

export interface UserCreateRequest {
  email: string;
  password: string;
  full_name: string;
  role: AssignableRole;
}

export interface UserUpdateRequest {
  is_active?: boolean;
  role?: AssignableRole;
  reason?: string | null;
}

export interface OrganizationResponse {
  id: string;
  name: string;
  slug: string;
  status: string;
  /** Published recruitment contact shown to candidates (null = none). */
  careers_contact_email: string | null;
  created_at: string;
}

export interface OrganizationCreateRequest {
  name: string;
  slug: string;
  admin_email: string;
  admin_password: string;
  admin_full_name: string;
}
