import type { Artifact, ArtifactKind } from "../types";
import { kindLabel, manifest, getArtifact } from "../data";
import { RepoChip } from "./RepoChip";

export function ArtifactDrawer({
  artifact,
  onClose,
  onSelect,
}: {
  artifact: Artifact | null;
  onClose: () => void;
  onSelect: (kind: ArtifactKind, id: string) => void;
}) {
  if (!artifact) return null;

  const incoming = manifest.edges.filter(
    (e) => e.target_kind === artifact.kind && e.target === artifact.id,
  );
  const outgoing = manifest.edges.filter(
    (e) => e.source_kind === artifact.kind && e.source === artifact.id,
  );
  const relatedOverlaps = manifest.overlaps
    .filter(
      (o) =>
        (o.a.kind === artifact.kind && o.a.id === artifact.id) ||
        (o.b.kind === artifact.kind && o.b.id === artifact.id),
    )
    .slice(0, 8);

  const otherSide = (o: (typeof relatedOverlaps)[number]) =>
    o.a.kind === artifact.kind && o.a.id === artifact.id ? o.b : o.a;

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer">
        <div className="drawer-header">
          <div className="row">
            <span className={`chip kind-${artifact.kind}`}>
              {kindLabel[artifact.kind]}
            </span>
            <span className="chip">{artifact.category}</span>
            <span className="spacer" />
            <button className="close-btn" onClick={onClose}>
              ×
            </button>
          </div>
          <h2 style={{ margin: "12px 0 6px", fontSize: 20 }}>{artifact.name}</h2>
          <code style={{ fontSize: 11, color: "var(--fg-muted)" }}>
            {artifact.path}
          </code>
        </div>
        <div className="drawer-body">
          {artifact.functional_role && (
            <div className="drawer-section">
              <h4>Functional role</h4>
              <div style={{ marginBottom: 6 }}>
                <code
                  style={{
                    background: "var(--bg-muted)",
                    padding: "3px 8px",
                    borderRadius: 4,
                    fontSize: 12,
                  }}
                >
                  {artifact.functional_role}
                </code>
              </div>
              {artifact.functional_summary && (
                <p style={{ margin: 0, fontSize: 13 }}>
                  {artifact.functional_summary}
                </p>
              )}
              {artifact.functional_scope.length > 0 && (
                <div style={{ marginTop: 6, fontSize: 12, color: "var(--fg-muted)" }}>
                  Scope: {artifact.functional_scope.map((s) => (
                    <span key={s} className="tag" style={{ fontSize: 10 }}>{s}</span>
                  ))}
                </div>
              )}
              {artifact.functional_supersedes.length > 0 && (
                <div style={{ marginTop: 6, fontSize: 12, color: "var(--danger)" }}>
                  Supersedes: {artifact.functional_supersedes.join(", ")}
                </div>
              )}
            </div>
          )}

          <div className="drawer-section">
            <h4>Description</h4>
            <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>
              {artifact.description || (
                <em style={{ color: "var(--fg-muted)" }}>No description</em>
              )}
            </p>
          </div>

          {artifact.target_repos.length > 0 && (
            <div className="drawer-section">
              <h4>Target repos ({artifact.target_repos.length})</h4>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {artifact.target_repos.map((r) => (
                  <RepoChip key={r} repo={r} />
                ))}
              </div>
            </div>
          )}

          {artifact.triggers.length > 0 && (
            <div className="drawer-section">
              <h4>Triggers ({artifact.triggers.length})</h4>
              <div>
                {artifact.triggers.slice(0, 30).map((t) => (
                  <span key={t} className="tag">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {artifact.tools.length > 0 && (
            <div className="drawer-section">
              <h4>Tools</h4>
              <div>
                {artifact.tools.map((t) => (
                  <span key={t} className="tag">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {artifact.model && (
            <div className="drawer-section">
              <h4>Model</h4>
              <span className="tag">{artifact.model}</span>
            </div>
          )}

          {artifact.bundles.length > 0 && (
            <div className="drawer-section">
              <h4>Bundles ({artifact.bundles.length})</h4>
              <div>
                {artifact.bundles.map((b) => (
                  <span
                    key={b}
                    className="chip kind-bundle"
                    onClick={() => onSelect("bundle", b)}
                  >
                    {b}
                  </span>
                ))}
              </div>
            </div>
          )}

          {outgoing.length > 0 && (
            <div className="drawer-section">
              <h4>Calls / depends on ({outgoing.length})</h4>
              {outgoing.map((e, i) => {
                const target = getArtifact(e.target_kind, e.target);
                return (
                  <div
                    key={`${e.target_kind}-${e.target}-${i}`}
                    className="pair-card"
                    style={{ marginBottom: 6, cursor: "pointer" }}
                    onClick={() => onSelect(e.target_kind, e.target)}
                  >
                    <span className={`chip kind-${e.target_kind}`}>
                      {kindLabel[e.target_kind]}
                    </span>{" "}
                    <strong>{e.target}</strong>
                    {target && (
                      <div className="pair-meta">{target.description.slice(0, 100)}</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {incoming.length > 0 && (
            <div className="drawer-section">
              <h4>Called by ({incoming.length})</h4>
              {incoming.slice(0, 20).map((e, i) => (
                <div
                  key={`${e.source_kind}-${e.source}-${i}`}
                  className="pair-card"
                  style={{ marginBottom: 6, cursor: "pointer" }}
                  onClick={() => onSelect(e.source_kind, e.source)}
                >
                  <span className={`chip kind-${e.source_kind}`}>
                    {kindLabel[e.source_kind]}
                  </span>{" "}
                  <strong>{e.source}</strong>
                </div>
              ))}
            </div>
          )}

          {relatedOverlaps.length > 0 && (
            <div className="drawer-section">
              <h4>Likely overlaps</h4>
              {relatedOverlaps.map((o, i) => {
                const other = otherSide(o);
                return (
                  <div
                    key={i}
                    className="pair-card"
                    style={{ marginBottom: 6, cursor: "pointer" }}
                    onClick={() => onSelect(other.kind, other.id)}
                  >
                    <div className="row">
                      <span className={`chip kind-${other.kind}`}>
                        {kindLabel[other.kind]}
                      </span>
                      <strong>{other.id}</strong>
                      <span className="spacer" />
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>
                        {(o.score * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="pair-meta">
                      shared: {o.shared_terms.slice(0, 5).join(", ")}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
