import { useMemo, useState } from "react";
import { manifest, getArtifact } from "../data";
import type { Artifact, ArtifactKind } from "../types";
import { ArtifactDrawer } from "../components/Drawer";
import { RepoChip } from "../components/RepoChip";

type Filter = "tooling-relevant" | "all" | "uncovered";

const KIND_META: Record<
  string,
  { icon: string; accent: string; blurb: string; order: number }
> = {
  "country-model": {
    icon: "◆",
    accent: "#319795",
    blurb:
      "Microsimulation engines that implement a country's tax & benefit system. Each one needs parameter/variable/test patterns and review tooling.",
    order: 0,
  },
  platform: {
    icon: "⚙",
    accent: "#285E61",
    blurb:
      "Shared engine, web apps, APIs, and the meta tooling that everything else builds on.",
    order: 1,
  },
  "data-pipeline": {
    icon: "≡",
    accent: "#0EA5E9",
    blurb:
      "Survey microdata enhancement pipelines and canonical data documentation.",
    order: 2,
  },
  library: {
    icon: "◌",
    accent: "#5b6cff",
    blurb:
      "Reusable Python packages — microsimulation utilities and data-science helpers.",
    order: 3,
  },
  "long-lived-tool": {
    icon: "▤",
    accent: "#c2410c",
    blurb:
      "Standalone calculators, chat assistants, and emulators maintained across years.",
    order: 4,
  },
  "research-platform": {
    icon: "◉",
    accent: "#9333EA",
    blurb:
      "Benchmark and validation platforms (policybench, ukds-mcp, calibration diagnostics).",
    order: 5,
  },
  "interactive-instance": {
    icon: "▢",
    accent: "#6b7280",
    blurb:
      "Individual dashboards & calculators — typically outputs of /create-dashboard and /new-tool, not separate engineering surfaces.",
    order: 6,
  },
  "research-analysis": {
    icon: "✎",
    accent: "#475569",
    blurb: "One-off analysis notebooks, year-in-reviews, internal write-ups.",
    order: 7,
  },
  analysis: {
    icon: "❉",
    accent: "#475569",
    blurb: "Specific policy analyses (budgets, reforms, manifestos).",
    order: 8,
  },
  presentation: {
    icon: "▥",
    accent: "#64748B",
    blurb: "Slide decks and event-specific repos.",
    order: 9,
  },
  "grant-proposal": {
    icon: "✸",
    accent: "#64748B",
    blurb: "Grant applications and funding proposals.",
    order: 10,
  },
  internal: {
    icon: "◂",
    accent: "#94A3B8",
    blurb: "Internal strategy, roadmaps, and team-process repos.",
    order: 11,
  },
  "archived-engine": {
    icon: "✕",
    accent: "#94A3B8",
    blurb: "Legacy engine repos preserved for history.",
    order: 12,
  },
  other: {
    icon: "·",
    accent: "#94A3B8",
    blurb: "Repos that haven't been classified yet — likely interactive instances or analyses.",
    order: 13,
  },
};

function RepoCard({
  repo,
  onSelectArtifact,
}: {
  repo: (typeof manifest.repo_coverage)[number];
  onSelectArtifact: (a: Artifact) => void;
}) {
  const uncovered = repo.total === 0;

  return (
    <div className="card" style={{ padding: 14 }}>
      <div className="row" style={{ marginBottom: 6 }}>
        <a
          href={`https://github.com/PolicyEngine/${repo.name}`}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
        >
          <RepoChip repo={repo.name} />
        </a>
        <span className="spacer" />
        {!uncovered && (
          <span
            style={{
              fontSize: 11,
              color: "var(--gray-500)",
              fontFamily: "var(--font-mono)",
            }}
          >
            {repo.skills.length}s · {repo.agents.length}a · {repo.commands.length}c
          </span>
        )}
      </div>
      {repo.description && (
        <div
          style={{
            fontSize: 12,
            color: "var(--gray-600)",
            lineHeight: 1.4,
            marginBottom: !uncovered ? 8 : 0,
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {repo.description}
        </div>
      )}

      {!uncovered && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
          {repo.commands.map((id) => {
            const a = getArtifact("command", id);
            if (!a) return null;
            return (
              <span
                key={`c-${id}`}
                className="chip kind-command"
                onClick={() => onSelectArtifact(a)}
                style={{ fontSize: 10 }}
              >
                /{id}
              </span>
            );
          })}
          {repo.agents.map((id) => {
            const a = getArtifact("agent", id);
            if (!a) return null;
            return (
              <span
                key={`a-${id}`}
                className="chip kind-agent"
                onClick={() => onSelectArtifact(a)}
                style={{ fontSize: 10 }}
              >
                {id}
              </span>
            );
          })}
          {repo.skills.map((id) => {
            const a = getArtifact("skill", id);
            if (!a) return null;
            return (
              <span
                key={`s-${id}`}
                className="chip kind-skill"
                onClick={() => onSelectArtifact(a)}
                style={{ fontSize: 10 }}
              >
                {id}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function ReposPage() {
  const [selected, setSelected] = useState<Artifact | null>(null);
  const [filter, setFilter] = useState<Filter>("tooling-relevant");

  const filteredRepos = useMemo(() => {
    return manifest.repo_coverage.filter((r) => {
      if (filter === "tooling-relevant") return r.tooling_relevant;
      if (filter === "uncovered") return r.total === 0 && r.tooling_relevant;
      return true;
    });
  }, [filter]);

  const coverageByKind = useMemo(() => {
    const m: Record<string, typeof manifest.repo_coverage> = {};
    for (const r of filteredRepos) {
      (m[r.kind] ||= []).push(r);
    }
    for (const k of Object.keys(m)) {
      m[k].sort((a, b) => {
        // Uncovered first, then by name.
        if ((a.total === 0) !== (b.total === 0)) {
          return a.total === 0 ? -1 : 1;
        }
        return a.name.localeCompare(b.name);
      });
    }
    return m;
  }, [filteredRepos]);

  const stats = useMemo(() => {
    const total = manifest.repo_coverage.length;
    const toolingRelevant = manifest.repo_coverage.filter(
      (r) => r.tooling_relevant,
    );
    const uncoveredRelevant = toolingRelevant.filter((r) => r.total === 0);
    return {
      total,
      toolingRelevantCount: toolingRelevant.length,
      uncoveredRelevant: uncoveredRelevant.length,
      coveredRelevant: toolingRelevant.length - uncoveredRelevant.length,
    };
  }, []);

  const sortedKinds = Object.keys(coverageByKind).sort(
    (a, b) =>
      (KIND_META[a]?.order ?? 99) - (KIND_META[b]?.order ?? 99),
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Repos</h1>
        <p className="page-subtitle">
          Every PolicyEngine GitHub org repo, classified by what kind of engineering
          surface it is. Tooling-relevant kinds (country models, platform, libraries,
          long-lived tools, data pipelines, research platforms) are the ones expected
          to have skills/agents/commands supporting them. Interactive dashboards and
          one-off analyses are outputs of the existing workflows, not separate
          surfaces.
        </p>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Org repos (active)</div>
          <div className="stat-value">{stats.total}</div>
          <div className="stat-meta">fetched from GitHub</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Tooling-relevant</div>
          <div className="stat-value">{stats.toolingRelevantCount}</div>
          <div className="stat-meta">should have skills/agents/commands</div>
        </div>
        <div
          className="stat-card"
          style={{
            borderLeftWidth: 3,
            borderLeftStyle: "solid",
            borderLeftColor: "var(--success)",
          }}
        >
          <div className="stat-label">Covered</div>
          <div className="stat-value">{stats.coveredRelevant}</div>
          <div className="stat-meta">
            {Math.round(
              (stats.coveredRelevant / Math.max(1, stats.toolingRelevantCount)) * 100,
            )}
            % of relevant repos
          </div>
        </div>
        <div
          className="stat-card"
          style={{
            borderLeftWidth: 3,
            borderLeftStyle: "solid",
            borderLeftColor: "var(--warning)",
          }}
        >
          <div className="stat-label">Uncovered & relevant</div>
          <div className="stat-value">{stats.uncoveredRelevant}</div>
          <div className="stat-meta">real ecosystem gaps</div>
        </div>
      </div>

      <div className="toolbar" style={{ marginBottom: 20 }}>
        <span
          className={`chip ${filter === "tooling-relevant" ? "active" : ""}`}
          onClick={() => setFilter("tooling-relevant")}
        >
          Tooling-relevant ({stats.toolingRelevantCount})
        </span>
        <span
          className={`chip ${filter === "uncovered" ? "active" : ""}`}
          onClick={() => setFilter("uncovered")}
        >
          Uncovered gaps · {stats.uncoveredRelevant}
        </span>
        <span
          className={`chip ${filter === "all" ? "active" : ""}`}
          onClick={() => setFilter("all")}
        >
          All {stats.total} repos
        </span>
      </div>

      {sortedKinds.map((kind) => {
        const meta = KIND_META[kind] ?? KIND_META.other;
        const repos = coverageByKind[kind];
        if (!repos || repos.length === 0) return null;
        const kindUncovered = repos.filter((r) => r.total === 0).length;
        return (
          <section key={kind} style={{ marginBottom: 32 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 14,
                marginBottom: 14,
                paddingBottom: 10,
                borderBottom: "1px solid var(--border)",
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  background: "var(--muted)",
                  color: "var(--gray-600)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 16,
                  fontWeight: 500,
                  flexShrink: 0,
                  border: "1px solid var(--border)",
                }}
              >
                {meta.icon}
              </div>
              <div style={{ flex: 1 }}>
                <h2
                  style={{
                    margin: 0,
                    fontSize: 17,
                    fontWeight: 600,
                    color: "var(--gray-900)",
                  }}
                >
                  {manifest.repo_kind_labels[kind] ?? kind}{" "}
                  <span
                    style={{
                      color: "var(--gray-500)",
                      fontWeight: 500,
                      fontSize: 14,
                    }}
                  >
                    ({repos.length} {repos.length === 1 ? "repo" : "repos"}
                    {kindUncovered > 0 && (
                      <>
                        {" · "}
                        <span style={{ color: "var(--warning)" }}>
                          {kindUncovered} uncovered
                        </span>
                      </>
                    )}
                    )
                  </span>
                </h2>
                <p
                  style={{
                    margin: "2px 0 0",
                    fontSize: 12.5,
                    color: "var(--gray-600)",
                    lineHeight: 1.45,
                  }}
                >
                  {meta.blurb}
                </p>
              </div>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
                gap: 10,
              }}
            >
              {repos.map((r) => (
                <RepoCard
                  key={r.name}
                  repo={r}
                  onSelectArtifact={(a) => setSelected(a)}
                />
              ))}
            </div>
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
