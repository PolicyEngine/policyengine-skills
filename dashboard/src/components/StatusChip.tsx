import { statusDescription, statusLabel } from "../data";
import type { RegistryStatus } from "../types";

export function StatusChip({
  status,
  size = "md",
}: {
  status: RegistryStatus;
  size?: "sm" | "md";
}) {
  return (
    <span
      className={`status-chip status-${status}`}
      title={statusDescription[status]}
      style={{ fontSize: size === "sm" ? 10 : 11 }}
    >
      {statusLabel[status]}
    </span>
  );
}
