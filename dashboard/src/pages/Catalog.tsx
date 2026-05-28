import { useMemo, useState } from "react";
import { manifest, kindLabel, getArtifact } from "../data";
import type { Artifact, ArtifactKind } from "../types";
import { ArtifactDrawer } from "../components/Drawer";
import { RepoChip } from "../components/RepoChip";

const ALL_KINDS: ArtifactKind[] = ["skill", "agent", "command", "bundle"];

export default function CatalogPage() {
  const [query, setQuery] = useState("");
  const [activeKinds, setActiveKinds] = useState<Set<ArtifactKind>>(
    new Set(ALL_KINDS),
  );
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [activeBundle, setActiveBundle] = useState<string | null>(null);
  const [activeRepo, setActiveRepo] = useState<string | null>(null);
  const [selected, setSelected] = useState<Artifact | null>(null);

  const categories = useMemo(() => {
    const s = new Set<string>();
    manifest.artifacts.forEach((a) => {
      if (activeKinds.has(a.kind)) s.add(a.category);
    });
    return Array.from(s).sort();
  }, [activeKinds]);

  const bundles = useMemo(
    () => manifest.bundles_raw.map((b) => b.name).sort(),
    [],
  );

  const repos = useMemo(() => {
    const counts = new Map<string, number>();
    for (const a of manifest.artifacts) {
      for (const r of a.target_repos) counts.set(r, (counts.get(r) ?? 0) + 1);
    }
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, []);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    return manifest.artifacts.filter((a) => {
      if (!activeKinds.has(a.kind)) return false;
      if (activeCategory && a.category !== activeCategory) return false;
      if (activeBundle && !a.bundles.includes(activeBundle)) return false;
      if (activeRepo && !a.target_repos.includes(activeRepo)) return false;
      if (!q) return true;
      const hay =
        `${a.name} ${a.id} ${a.description} ${a.triggers.join(" ")} ${a.category}`.toLowerCase();
      return hay.includes(q);
    });
  }, [query, activeKinds, activeCategory, activeBundle, activeRepo]);

  const toggleKind = (k: ArtifactKind) => {
    const next = new Set(activeKinds);
    if (next.has(k)) next.delete(k);
    else next.add(k);
    if (next.size === 0) next.add(k);
    setActiveKinds(next);
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Catalog</h1>
        <p className="page-subtitle">
          Search, filter, and inspect every artifact. Click a row for details, dependencies,
          and likely overlaps.
        </p>
      </div>

      <div className="toolbar">
        <input
          type="search"
          placeholder="Search names, descriptions, triggers…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {ALL_KINDS.map((k) => (
          <span
            key={k}
            className={`chip ${activeKinds.has(k) ? `kind-${k}` : ""}`}
            onClick={() => toggleKind(k)}
            style={{ opacity: activeKinds.has(k) ? 1 : 0.4 }}
          >
            <span className={`kind-dot kind-${k}`} />
            {kindLabel[k]}s ({manifest.counts[k]})
          </span>
        ))}
      </div>

      <div className="toolbar">
        <select
          value={activeCategory ?? ""}
          onChange={(e) => setActiveCategory(e.target.value || null)}
          style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid var(--border)" }}
        >
          <option value="">All categories ({categories.length})</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          value={activeBundle ?? ""}
          onChange={(e) => setActiveBundle(e.target.value || null)}
          style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid var(--border)" }}
        >
          <option value="">All bundles</option>
          {bundles.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
        <select
          value={activeRepo ?? ""}
          onChange={(e) => setActiveRepo(e.target.value || null)}
          style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid var(--border)" }}
        >
          <option value="">All target repos</option>
          {repos.map(([r, n]) => (
            <option key={r} value={r}>
              {r} ({n})
            </option>
          ))}
        </select>
        <span style={{ color: "var(--fg-muted)", fontSize: 13 }}>
          Showing {filtered.length} of {manifest.artifacts.length}
        </span>
      </div>

      <table className="data">
        <thead>
          <tr>
            <th style={{ width: 80 }}>Kind</th>
            <th style={{ width: "18%" }}>Name</th>
            <th style={{ width: "28%" }}>Description</th>
            <th style={{ width: "10%" }}>Category</th>
            <th style={{ width: "22%" }}>Target repos</th>
            <th style={{ width: "14%" }}>Bundles</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((a) => (
            <tr key={`${a.kind}:${a.id}`} onClick={() => setSelected(a)}>
              <td>
                <span className={`chip kind-${a.kind}`} style={{ fontSize: 11 }}>
                  {kindLabel[a.kind]}
                </span>
              </td>
              <td>
                <strong>{a.name}</strong>
                {a.triggers.length > 0 && (
                  <div style={{ fontSize: 11, color: "var(--fg-muted)" }}>
                    {a.triggers.length} trigger phrases
                  </div>
                )}
              </td>
              <td>
                <div className="truncate-2">{a.description}</div>
              </td>
              <td>
                <span className="tag">{a.category}</span>
              </td>
              <td>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                  {a.target_repos.length === 0 && (
                    <span style={{ fontSize: 11, color: "var(--fg-muted)" }}>—</span>
                  )}
                  {a.target_repos.map((r) => (
                    <RepoChip
                      key={r}
                      repo={r}
                      size="sm"
                      onClick={() => {
                        setActiveRepo(r);
                      }}
                    />
                  ))}
                </div>
              </td>
              <td>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
                  {a.bundles.length === 0 && (
                    <span style={{ fontSize: 11, color: "var(--fg-muted)" }}>—</span>
                  )}
                  {a.bundles.map((b) => (
                    <span key={b} className="tag" style={{ fontSize: 10 }}>
                      {b}
                    </span>
                  ))}
                </div>
              </td>
            </tr>
          ))}
          {filtered.length === 0 && (
            <tr>
              <td colSpan={6}>
                <div className="empty">No artifacts match these filters.</div>
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <ArtifactDrawer
        artifact={selected}
        onClose={() => setSelected(null)}
        onSelect={(kind, id) => {
          const next = getArtifact(kind, id);
          if (next) setSelected(next);
        }}
      />
    </div>
  );
}
