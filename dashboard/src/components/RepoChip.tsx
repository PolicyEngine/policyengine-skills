export function RepoChip({
  repo,
  onClick,
  size = "md",
}: {
  repo: string;
  onClick?: () => void;
  size?: "sm" | "md";
}) {
  return (
    <span
      onClick={onClick}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: size === "sm" ? "1px 7px" : "2px 9px",
        fontSize: size === "sm" ? 10 : 11,
        fontWeight: 500,
        fontFamily: "var(--font-mono)",
        borderRadius: 4,
        background: "var(--muted)",
        color: "var(--gray-700)",
        border: "1px solid var(--border)",
        cursor: onClick ? "pointer" : "default",
        whiteSpace: "nowrap",
      }}
    >
      {repo}
    </span>
  );
}

// Kept exported for back-compat in case any caller still imports it,
// but it now returns a neutral gray to keep the dashboard from looking
// like a color palette test.
export function repoColor(_repo: string): string {
  return "var(--gray-500)";
}
