/** Test-only helpers shared by the Applications and Campus Drive list tests. */
import { vi } from "vitest";
import type { PagedResult } from "../../../lib/apiClient";
import type { ApplicationResponse, JobResponse } from "../../../types/recruitment";

export function makeApplication(
  n: number,
  overrides: Partial<ApplicationResponse> = {},
): ApplicationResponse {
  return {
    id: `app-${n}`,
    organization_id: "org-1",
    candidate_id: `cand-${n}`,
    candidate_full_name: `Candidate ${n}`,
    candidate_email: `candidate${n}@example.com`,
    candidate_phone: `+91 90000 000${String(n).padStart(2, "0")}`,
    job_id: "job-1",
    job_title: "Data Analyst",
    campus_drive_id: null,
    status: "APPLIED",
    source: "PORTAL",
    applied_at: new Date(2026, 8, 1).toISOString(),
    created_at: new Date(2026, 8, 1).toISOString(),
    updated_at: new Date(2026, 8, 1).toISOString(),
    resume_id: null,
    resume_filename: null,
    deleted_at: null,
    ...overrides,
  };
}

export function makeJob(id: string, title: string): JobResponse {
  return {
    id,
    organization_id: "org-1",
    title,
    department: null,
    location: null,
    employment_type: null,
    description: `${title} role.`,
    description_visible: true,
    status: "OPEN",
    openings_count: 1,
    created_by: "user-1",
    deleted_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

export function pageOf(items: ApplicationResponse[], total = items.length): PagedResult<ApplicationResponse> {
  return { items, total };
}

/** The query the page most recently sent to the API, as URLSearchParams. */
export function lastQuery(spy: { mock: { calls: unknown[][] } }): URLSearchParams {
  const call = spy.mock.calls[spy.mock.calls.length - 1];
  return new URLSearchParams(String(call[0]));
}

/** Every `q` the page has sent, in order. */
export function sentSearches(spy: { mock: { calls: unknown[][] } }): (string | null)[] {
  return spy.mock.calls.map((call) => new URLSearchParams(String(call[0])).get("q"));
}

/** Makes `useMediaQuery` report a phone-sized (or desktop) viewport. */
export function stubViewport(isPhone: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: isPhone && query.includes("max-width"),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}
