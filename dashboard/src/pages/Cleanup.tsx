import { useMemo, useState } from "react";
import { getArtifact, kindLabel, manifest } from "../data";
import type { Artifact, ArtifactKind, RegistryStatus } from "../types";
import { ArtifactDrawer } from "../components/Drawer";
import { StatusChip } from "../components/StatusChip";

const STATUS_BUCKETS: Array<{
  status: RegistryStatus;
  title: string;
  description: string;
}> = [
  {
    status: "deprecated",
    title: "Do not use",
    description: "Superseded artifacts that should route users to a replacement.",
  },
  {
    status: "use-with-care",
    title: "Needs confirmation",
    description: "Unbundled or uncalled artifacts that may be stale or specialist-only.",
  },
  {
    status: "internal-only",
    title: "Direct-use discouraged",
    description: "Agents that normally belong behind commands and workflows.",
  },
  {
    status: "experimental",
    title: "Experimental",
    description: "Artifacts intentionally marked as still changing.",
  },
];

function CleanupRow({
  artifact,
  onSelect,
}: {
  artifact: Artifact;
  onSelect: (artifact: Artifact) => void;
}) {
  const replacements = artifact.use_instead
    .map((id) => getArtifact(artifact.kind, id))
    .filter((a): a is Artifact => Boolean(a));

  return (
    <tr onClick={() => onSelect(artifact)}>
      <td>
        <span className={`chip kind-${artifact.kind}`} style={{ fontSize: 11 }}>
          {kindLabel[artifact.kind]}
        </span>
      </td>
      <td>
        <strong>{artifact.name}</strong>
        <div style={{ fontSize: 11, color: "var(--fg-muted)" }}>{artifact.path}</div>
      </td>
      <td>
        <StatusChip status={artifact.registry_status} size="sm" />
      </td>
      <td>
        <div className="truncate-2">
          {artifact.registry_notes || artifact.functional_summary || artifact.description}
        </div>
      </td>
      <td>
        {replacements.length === 0 && (
          <span style={{ fontSize: 11, color: "var(--fg-muted)" }}>-</span>
        )}
        {replacements.map((replacement) => (
          <button
            key={replacement.id}
            className="link-btn"
            onClick={(event) => {
              event.stopPropagation();
              onSelect(replacement);
            }}
          >
            {replacement.name}
          </button>
        ))}
      </td>
      <td>
        <span className="tag">{artifact.registry_owner}</span>
      </td>
    </tr>
  );
}

export default function CleanupPage() {
  const [selected, setSelected] = useState<Artifact | null>(null);

  const grouped = useMemo(() => {
    const out = new Map<RegistryStatus, Artifact[]>();
    for (const bucket of STATUS_BUCKETS) out.set(bucket.status, []);
    for (const artifact of manifest.artifacts) {
      if (artifact.kind === "bundle") continue;
      const bucket = out.get(artifact.registry_status);
      if (bucket) bucket.push(artifact);
    }
    for (const items of out.values()) {
      items.sort((a, b) => a.kind.localeCompare(b.kind) || a.name.localeCompare(b.name));
    }
    return out;
  }, []);

  const riskyTotal = STATUS_BUCKETS.reduce(
    (sum, bucket) => sum + (grouped.get(bucket.status)?.length ?? 0),
    0,
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Cleanup queue</h1>
        <p className="page-subtitle">
          Internal registry view for artifacts people should avoid, confirm, or call only
          through a workflow. Use this before creating another skill or agent.
        </p>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Needs attention</div>
          <div className="stat-value">{riskyTotal}</div>
          <div className="stat-meta">non-recommended artifacts</div>
        </div>
        {STATUS_BUCKETS.map((bucket) => (
          <div className="stat-card" key={bucket.status}>
            <div className="stat-label">{bucket.title}</div>
            <div className="stat-value">{grouped.get(bucket.status)?.length ?? 0}</div>
            <div className="stat-meta">{bucket.description}</div>
          </div>
        ))}
      </div>

      {STATUS_BUCKETS.map((bucket) => {
        const artifacts = grouped.get(bucket.status) ?? [];
        if (artifacts.length === 0) return null;
        return (
          <section key={bucket.status} style={{ marginBottom: 28 }}>
            <div className="row" style={{ marginBottom: 10 }}>
              <h2 style={{ margin: 0, fontSize: 18 }}>{bucket.title}</h2>
              <StatusChip status={bucket.status} />
              <span style={{ color: "var(--fg-muted)", fontSize: 13 }}>
                {bucket.description}
              </span>
            </div>
            <table className="data">
              <thead>
                <tr>
                  <th style={{ width: 80 }}>Kind</th>
                  <th style={{ width: "22%" }}>Artifact</th>
                  <th style={{ width: 110 }}>Status</th>
                  <th>Reason</th>
                  <th style={{ width: "18%" }}>Use instead</th>
                  <th style={{ width: "14%" }}>Owner</th>
                </tr>
              </thead>
              <tbody>
                {artifacts.map((artifact) => (
                  <CleanupRow
                    key={`${artifact.kind}:${artifact.id}`}
                    artifact={artifact}
                    onSelect={setSelected}
                  />
                ))}
              </tbody>
            </table>
          </section>
        );
      })}

      <ArtifactDrawer
        artifact={selected}
        onClose={() => setSelected(null)}
        onSelect={(kind: ArtifactKind, id) => {
          const next = getArtifact(kind, id);
          if (next) setSelected(next);
        }}
      />
    </div>
  );
}
