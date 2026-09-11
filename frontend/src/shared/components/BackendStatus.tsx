import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../lib/apiClient";
import type { ReadinessResponse } from "../../types/system";

/**
 * Proves the frontend/backend/database wiring works end-to-end. Not a
 * product feature — a foundation check, useful while later phases build
 * real screens on top of this scaffold.
 */
export function BackendStatus() {
  const { data, isPending, isError } = useQuery({
    queryKey: ["readyz"],
    queryFn: () => apiClient.get<ReadinessResponse>("/readyz"),
  });

  if (isPending) {
    return <p role="status">Checking backend connection…</p>;
  }

  if (isError || data.status !== "ok") {
    return (
      <p role="status" style={{ color: "crimson" }}>
        Backend unreachable or not ready.
      </p>
    );
  }

  return (
    <p role="status" style={{ color: "seagreen" }}>
      Backend connected — database {data.database}.
    </p>
  );
}
