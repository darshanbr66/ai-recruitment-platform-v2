import type { ReactNode } from "react";

export function Alert({
  variant = "error",
  children,
}: {
  variant?: "error" | "success";
  children: ReactNode;
}) {
  return (
    <p className={`alert alert-${variant}`} role={variant === "error" ? "alert" : "status"}>
      {children}
    </p>
  );
}
