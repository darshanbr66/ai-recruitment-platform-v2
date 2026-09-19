import type { UserResponse } from "../../../types/auth";

/**
 * Who the dashboard greets. An organization admin is greeted as "Admin"
 * (the role, not whatever name their account happened to be created with);
 * everyone else by their own first name. Never a hardcoded person or tenant.
 */
export function greetingName(user: Pick<UserResponse, "full_name" | "roles"> | null): string {
  if (user === null) return "there";
  if (user.roles.includes("ORG_ADMIN")) return "Admin";
  return user.full_name.trim().split(/\s+/)[0] || "there";
}
