import { useMemo, useState } from "react";
import { manifest, getArtifact, kindLabel } from "../data";
import type {
  Artifact,
  ArtifactKind,
  FunctionalOverlap,
  FunctionalOverlapCategory,
  OverlapPair,
} from "../types";
import { ArtifactDrawer } from "../components/Drawer";

type View = "functional" | "raw";

const CATEGORY_META: Record<
  FunctionalOverlapCategory,
  { label: string; color: string; description: string; rank: number }
> = {
  superseded: {
    label: "Superseded",
    color: "var(--danger)",
    description: "One explicitly replaces the other — deprecation candidate.",
    rank: 0,
  },
  "merge-candidate": {
    label: "Merge candidate",
    color: "var(--warning)",
    description: "Same kind, same functional role, overlapping scope.",
    rank: 1,
  },
  "wiring-gap": {
    label: "Wiring gap",
    color: "var(--warning)",
    description:
      "Same functional role across kinds but not actually linked in the workflow graph — likely missing reference.",
    rank: 2,
  },
  "implementation-pair": {
    label: "Implementation pair",
    color: "var(--success)",
    description:
      "Same functional role across kinds AND linked in the workflow graph — healthy coupling.",
    rank: 3,
  },
  complementary: {
    label: "Complementary",
    color: "var(--gray-500)",
    description:
      "Same role but disjoint scope (e.g. testing patterns for country models vs frontend) — intentional siblings.",
    rank: 4,
  },
};

const CATEGORY_ORDER: FunctionalOverlapCategory[] = [
  "superseded",
  "merge-candidate",
  "wiring-gap",
  "implementation-pair",
  "complementary",
];

function FunctionalOverlapCard({
  overlap,
  onSelect,
}: {
  overlap: FunctionalOverlap;
  onSelect: (a: Artifact) => void;
}) {
  const meta = CATEGORY_META[overlap.category];
  const arts = overlap.artifacts
    .map((a) => getArtifact(a.kind, a.id))
    .filter((a): a is Artifact => a !== undefined);

  return (
    <div
      className="card"
      style={{
        borderLeftColor: meta.color,
        borderLeftWidth: 3,
        borderLeftStyle: "solid",
      }}
    >
      <div className="row" style={{ marginBottom: 8 }}>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 11,
            fontWeight: 600,
            color: meta.color,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: meta.color,
              display: "inline-block",
            }}
          />
          {meta.label}
        </span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            color: "var(--gray-500)",
          }}
        >
          {overlap.role}
        </span>
      </div>
      <div className="pair">
        {arts.map((a, idx) => (
          <div key={`${a.kind}:${a.id}`} style={{ display: "contents" }}>
            <div
              className="pair-card"
              onClick={() => onSelect(a)}
              style={{ cursor: "pointer" }}
            >
              <div className="row" style={{ marginBottom: 4 }}>
                <span className={`chip kind-${a.kind}`} style={{ fontSize: 10 }}>
                  {kindLabel[a.kind]}
                </span>
                <span style={{ fontSize: 11, color: "var(--fg-muted)" }}>
                  {a.category}
                </span>
              </div>
              <div className="pair-name">{a.name}</div>
              <div
                className="truncate-2"
                style={{ fontSize: 12, marginTop: 4 }}
              >
                {a.functional_summary ?? a.description}
              </div>
            </div>
            {idx < arts.length - 1 && <div className="pair-arrow">⇆</div>}
          </div>
        ))}
      </div>
      <div
        style={{
          marginTop: 10,
          padding: "8px 12px",
          background: "var(--muted)",
          color: "var(--gray-700)",
          borderRadius: 6,
          fontSize: 12,
          lineHeight: 1.5,
        }}
      >
        {overlap.rationale}
      </div>
    </div>
  );
}

function matchesKindPair(o: OverlapPair, filter: string) {
  if (filter === "all") return true;
  const pair = [o.a.kind, o.b.kind].sort().join("-");
  return pair === filter.split("-").sort().join("-");
}

const SAME_KIND_OPTIONS = [
  { value: "all", label: "All same-kind" },
  { value: "skill-skill", label: "Skill ↔ Skill" },
  { value: "agent-agent", label: "Agent ↔ Agent" },
  { value: "command-command", label: "Command ↔ Command" },
];

const CROSS_KIND_OPTIONS = [
  { value: "all", label: "All cross-kind" },
  { value: "skill-command", label: "Skill ↔ Command" },
  { value: "skill-agent", label: "Skill ↔ Agent" },
  { value: "agent-command", label: "Agent ↔ Command" },
];

export default function DuplicatesPage() {
  const [view, setView] = useState<View>("functional");
  const [activeCategories, setActiveCategories] = useState<Set<FunctionalOverlapCategory>>(
    new Set(["superseded", "merge-candidate", "wiring-gap", "implementation-pair"]),
  );
  const [rawSameKind, setRawSameKind] = useState(true);
  const [rawMinScore, setRawMinScore] = useState(0.3);
  const [rawKindFilter, setRawKindFilter] = useState("all");
  const [selected, setSelected] = useState<Artifact | null>(null);

  const overlapsByCategory = useMemo(() => {
    const m: Record<FunctionalOverlapCategory, FunctionalOverlap[]> = {
      superseded: [],
      "merge-candidate": [],
      "wiring-gap": [],
      "implementation-pair": [],
      complementary: [],
    };
    for (const o of manifest.functional_overlaps ?? []) {
      m[o.category].push(o);
    }
    return m;
  }, []);

  const filteredFunctional = useMemo(() => {
    const out: FunctionalOverlap[] = [];
    for (const cat of CATEGORY_ORDER) {
      if (!activeCategories.has(cat)) continue;
      out.push(...overlapsByCategory[cat]);
    }
    return out;
  }, [overlapsByCategory, activeCategories]);

  const filteredRaw = useMemo(() => {
    return manifest.overlaps.filter((o) => {
      if (o.score < rawMinScore) return false;
      if (rawSameKind && o.a.kind !== o.b.kind) return false;
      if (!rawSameKind && o.a.kind === o.b.kind) return false;
      if (!matchesKindPair(o, rawKindFilter)) return false;
      return true;
    });
  }, [rawMinScore, rawSameKind, rawKindFilter]);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Overlaps</h1>
        <p className="page-subtitle">
          Curated functional overlaps based on a hand-tagged role for every artifact.
          Two views: <strong>Functional</strong> categorizes pairs by their
          relationship; <strong>Raw text similarity</strong> shows the underlying TF-IDF
          signal for spelunking.
        </p>
      </div>

      <div className="toolbar" style={{ marginBottom: 16 }}>
        <span
          className={`chip ${view === "functional" ? "active" : ""}`}
          onClick={() => setView("functional")}
        >
          Functional ({manifest.functional_overlaps?.length ?? 0})
        </span>
        <span
          className={`chip ${view === "raw" ? "active" : ""}`}
          onClick={() => setView("raw")}
        >
          Raw text similarity ({manifest.overlaps.length})
        </span>
      </div>

      {view === "functional" && (
        <>
          <div className="stat-grid">
            {CATEGORY_ORDER.map((cat) => {
              const meta = CATEGORY_META[cat];
              const count = overlapsByCategory[cat].length;
              const active = activeCategories.has(cat);
              return (
                <div
                  key={cat}
                  className="stat-card"
                  style={{
                    borderLeftWidth: 3,
                    borderLeftStyle: "solid",
                    borderLeftColor: meta.color,
                    cursor: "pointer",
                    opacity: active ? 1 : 0.55,
                  }}
                  onClick={() => {
                    const next = new Set(activeCategories);
                    if (next.has(cat)) next.delete(cat);
                    else next.add(cat);
                    setActiveCategories(next);
                  }}
                >
                  <div className="stat-label">{meta.label}</div>
                  <div className="stat-value">{count}</div>
                  <div className="stat-meta" style={{ fontSize: 11 }}>
                    {meta.description}
                  </div>
                </div>
              );
            })}
          </div>

          {filteredFunctional.length === 0 && (
            <div className="empty">No functional overlaps in the active categories.</div>
          )}

          {filteredFunctional.map((o, i) => (
            <FunctionalOverlapCard
              key={i}
              overlap={o}
              onSelect={(a) => setSelected(a)}
            />
          ))}

          {(overlapsByCategory["merge-candidate"].length === 0 &&
            overlapsByCategory.superseded.length === 0 &&
            overlapsByCategory["wiring-gap"].length === 0) && (
            <div
              className="card"
              style={{
                marginTop: 16,
                background: "var(--success-tint)",
                borderColor: "var(--success)",
              }}
            >
              <strong style={{ color: "var(--success)" }}>✓ No deprecations, merge candidates, or wiring gaps.</strong>
              <p style={{ margin: "4px 0 0", fontSize: 13 }}>
                The remaining functional overlaps are all healthy implementation pairs or
                intentional sibling skills (different scopes).
              </p>
            </div>
          )}
        </>
      )}

      {view === "raw" && (
        <>
          <div
            className="card"
            style={{ background: "var(--bg-muted)", marginBottom: 16, fontSize: 13 }}
          >
            <strong>Heads up:</strong> Raw TF-IDF similarity catches vocabulary overlap, not
            functional overlap. Two artifacts about "reviewing PRs" can score high even when
            they review entirely different things (API vs frontend). Use the Functional view
            for actual duplicate analysis — this view is here for spelunking.
          </div>
          <div className="toolbar">
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 13, color: "var(--fg-muted)" }}>Min similarity</span>
              <input
                type="range"
                min={0.15}
                max={0.8}
                step={0.05}
                value={rawMinScore}
                onChange={(e) => setRawMinScore(parseFloat(e.target.value))}
              />
              <span style={{ fontFamily: "var(--font-mono)", minWidth: 50 }}>
                {(rawMinScore * 100).toFixed(0)}%
              </span>
            </label>
            <span
              className={`chip ${rawSameKind ? "active" : ""}`}
              onClick={() => setRawSameKind(true)}
            >
              Same kind
            </span>
            <span
              className={`chip ${!rawSameKind ? "active" : ""}`}
              onClick={() => setRawSameKind(false)}
            >
              Cross kind
            </span>
            <select
              value={rawKindFilter}
              onChange={(e) => setRawKindFilter(e.target.value)}
              style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid var(--border)" }}
            >
              {(rawSameKind ? SAME_KIND_OPTIONS : CROSS_KIND_OPTIONS).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <span className="spacer" />
            <span style={{ color: "var(--fg-muted)", fontSize: 13 }}>
              {filteredRaw.length} pairs
            </span>
          </div>

          {filteredRaw.slice(0, 50).map((o, i) => {
            const a = getArtifact(o.a.kind, o.a.id);
            const b = getArtifact(o.b.kind, o.b.id);
            if (!a || !b) return null;
            return (
              <div className="card" key={i}>
                <div className="row" style={{ marginBottom: 10 }}>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 14, fontWeight: 600 }}>
                    {(o.score * 100).toFixed(0)}%
                  </span>
                  <span className="score-bar">
                    <span
                      className="score-fill"
                      style={{ width: `${o.score * 100}%`, display: "block" }}
                    />
                  </span>
                  <span className="spacer" />
                  <span style={{ fontSize: 12, color: "var(--fg-muted)" }}>
                    shared: {o.shared_terms.slice(0, 6).map((t) => (
                      <span key={t} className="tag" style={{ fontSize: 10 }}>{t}</span>
                    ))}
                  </span>
                </div>
                <div className="pair">
                  <div className="pair-card" onClick={() => setSelected(a)} style={{ cursor: "pointer" }}>
                    <div className="row" style={{ marginBottom: 4 }}>
                      <span className={`chip kind-${a.kind}`} style={{ fontSize: 10 }}>
                        {kindLabel[a.kind]}
                      </span>
                      <span style={{ fontSize: 11, color: "var(--fg-muted)" }}>{a.category}</span>
                    </div>
                    <div className="pair-name">{a.name}</div>
                    <div className="truncate-2" style={{ fontSize: 12, marginTop: 4 }}>
                      {a.functional_summary ?? a.description}
                    </div>
                  </div>
                  <div className="pair-arrow">⇆</div>
                  <div className="pair-card" onClick={() => setSelected(b)} style={{ cursor: "pointer" }}>
                    <div className="row" style={{ marginBottom: 4 }}>
                      <span className={`chip kind-${b.kind}`} style={{ fontSize: 10 }}>
                        {kindLabel[b.kind]}
                      </span>
                      <span style={{ fontSize: 11, color: "var(--fg-muted)" }}>{b.category}</span>
                    </div>
                    <div className="pair-name">{b.name}</div>
                    <div className="truncate-2" style={{ fontSize: 12, marginTop: 4 }}>
                      {b.functional_summary ?? b.description}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
          {filteredRaw.length > 50 && (
            <div className="empty">
              Showing top 50 of {filteredRaw.length}. Raise the similarity threshold to narrow.
            </div>
          )}
        </>
      )}

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
