import { act, render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../lib/apiClient";
import type { TokenResponse, UserResponse } from "../../types/auth";
import * as authApi from "./api";
import { AuthProvider, useAuth } from "./AuthContext";

const user: UserResponse = {
  id: "user-1",
  organization_id: "org-1",
  email: "admin@acme.dev",
  full_name: "Acme Admin",
  is_active: true,
  created_at: new Date().toISOString(),
  roles: ["ORG_ADMIN"],
  organization_name: "Acme Corp",
};

function tokens(accessToken: string, expiresIn = 900): TokenResponse {
  return { access_token: accessToken, token_type: "bearer", expires_in: expiresIn };
}

function StatusProbe() {
  const { status, accessToken, user: currentUser } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="token">{accessToken ?? "none"}</span>
      <span data-testid="org">{currentUser?.organization_name ?? "none"}</span>
    </div>
  );
}

function renderProvider(strict = false) {
  const tree = (
    <AuthProvider>
      <StatusProbe />
    </AuthProvider>
  );
  return render(strict ? <StrictMode>{tree}</StrictMode> : tree);
}

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("AuthProvider session persistence", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(authApi, "fetchCurrentUser").mockResolvedValue(user);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("restores the session on load with a single refresh call, even under StrictMode", async () => {
    // StrictMode mounts the effect twice; two refreshes would rotate the
    // cookie twice and the second would trip token-reuse detection.
    const refresh = vi.spyOn(authApi, "refreshSession").mockResolvedValue(tokens("token-1"));

    renderProvider(true);
    await flush();

    expect(refresh).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");
    expect(screen.getByTestId("token")).toHaveTextContent("token-1");
    expect(screen.getByTestId("org")).toHaveTextContent("Acme Corp");
  });

  it("treats a 401 from refresh as signed out, without retrying", async () => {
    const refresh = vi
      .spyOn(authApi, "refreshSession")
      .mockRejectedValue(new ApiError("Refresh token is invalid or expired.", 401, "unauthorized"));

    renderProvider();
    await flush(60_000);

    expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated");
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("stays signed in through a transient failure (e.g. API cold start) and retries", async () => {
    const refresh = vi
      .spyOn(authApi, "refreshSession")
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockRejectedValueOnce(new ApiError("Service Unavailable", 503, "http_error"))
      .mockResolvedValue(tokens("token-after-retry"));

    renderProvider();
    await flush();
    // Not signed out while the API is unreachable — still restoring.
    expect(screen.getByTestId("status")).toHaveTextContent("loading");

    await flush(2_000);
    expect(screen.getByTestId("status")).toHaveTextContent("loading");
    await flush(4_000);

    expect(refresh).toHaveBeenCalledTimes(3);
    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");
    expect(screen.getByTestId("token")).toHaveTextContent("token-after-retry");
  });

  it("renews the access token before it expires", async () => {
    const refresh = vi
      .spyOn(authApi, "refreshSession")
      .mockResolvedValueOnce(tokens("token-1", 120))
      .mockResolvedValueOnce(tokens("token-2", 120));

    renderProvider();
    await flush();
    expect(screen.getByTestId("token")).toHaveTextContent("token-1");

    // 120s lifetime, renewed 60s early.
    await flush(59_000);
    expect(refresh).toHaveBeenCalledTimes(1);
    await flush(1_500);

    expect(refresh).toHaveBeenCalledTimes(2);
    expect(screen.getByTestId("token")).toHaveTextContent("token-2");
    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");
  });

  it("signs out when a scheduled renewal finds the session revoked", async () => {
    vi.spyOn(authApi, "refreshSession")
      .mockResolvedValueOnce(tokens("token-1", 120))
      .mockRejectedValueOnce(new ApiError("Refresh token is invalid or expired.", 401, "unauthorized"));

    renderProvider();
    await flush();
    await flush(61_000);

    expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated");
    expect(screen.getByTestId("token")).toHaveTextContent("none");
  });
});
