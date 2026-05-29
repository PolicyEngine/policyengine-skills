import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  getArtifact,
  kindLabel,
  manifest,
  statusDescription,
  statusRank,
} from "../data";
import type { Artifact, ArtifactKind } from "../types";
import { ArtifactDrawer } from "../components/Drawer";
import { RepoChip } from "../components/RepoChip";
import { StatusChip } from "../components/StatusChip";

interface FinderTask {
  id: string;
  label: string;
  prompt: string;
  roles: string[];
  keywords: string[];
  repoHints?: string[];
}

const TASKS: FinderTask[] = [
  {
    id: "review-pr",
    label: "Review a PR",
    prompt: "Review country-model PRs, references, parameters, formulas, and tests.",
    roles: ["workflow:review-program", "workflow:review-pr-program", "pattern:review"],
    keywords: ["review", "pr", "reference", "validator", "program"],
    repoHints: ["policyengine-us", "policyengine-uk", "policyengine-canada"],
  },
  {
    id: "implement-program",
    label: "Implement a program",
    prompt: "Encode benefits, variables, parameters, formulas, and country-model tests.",
    roles: [
      "workflow:encode-policy",
      "workflow:backdate-program",
      "pattern:variables",
      "pattern:parameters",
      "pattern:testing:country-models",
    ],
    keywords: ["program", "benefit", "variable", "parameter", "yaml", "formula"],
    repoHints: ["policyengine-us"],
  },
  {
    id: "fix-pr",
    label: "Fix PR feedback",
    prompt: "Respond to review comments, CI failures, or targeted implementation issues.",
    roles: ["workflow:fix-pr", "orchestrate:ci-fixer"],
    keywords: ["fix", "ci", "failure", "comment", "review"],
    repoHints: ["policyengine-us"],
  },
  {
    id: "build-dashboard",
    label: "Build a dashboard",
    prompt: "Plan, scaffold, build, validate, and deploy interactive dashboards.",
    roles: [
      "workflow:create-dashboard",
      "workflow:new-tool",
      "frontend:scaffold-dashboard",
      "frontend:scaffold-tool",
      "frontend:ui-kit",
    ],
    keywords: ["dashboard", "frontend", "interactive", "tool", "ui-kit", "vercel"],
    repoHints: ["interactive-tools", "policyengine-app-v2", "policyengine-ui-kit"],
  },
  {
    id: "write-tests",
    label: "Write tests",
    prompt: "Find testing guidance for frontend, APIs, SDKs, data pipelines, or country models.",
    roles: [
      "workflow:write-tests-frontend",
      "pattern:testing:frontend",
      "pattern:testing:country-models",
      "pattern:testing:data-pipelines",
    ],
    keywords: ["test", "testing", "vitest", "yaml", "fixture"],
  },
  {
    id: "content",
    label: "Generate content",
    prompt: "Create PolicyEngine social images, post copy, and neutral written content.",
    roles: ["workflow:content-generation", "domain:writing-style", "domain:research-lookup"],
    keywords: ["content", "social", "post", "writing", "blog"],
  },
];

function scoreArtifact(artifact: Artifact, query: string, task: FinderTask | null) {
  let score = 0;
  const haystack = [
    artifact.name,
    artifact.id,
    artifact.description,
    artifact.functional_summary ?? "",
    artifact.functional_role ?? "",
    artifact.registry_owner,
    artifact.target_repos.join(" "),
    artifact.triggers.join(" "),
  ]
    .join(" ")
    .toLowerCase();

  if (task) {
    if (artifact.functional_role && task.roles.includes(artifact.functional_role)) score += 80;
    if (artifact.target_repos.some((r) => task.repoHints?.includes(r))) score += 20;
    for (const keyword of task.keywords) {
      if (haystack.includes(keyword)) score += 8;
    }
  }

  for (const term of query.toLowerCase().trim().split(/\s+/).filter(Boolean)) {
    if (haystack.includes(term)) score += 12;
  }

  if (artifact.kind === "command") score += 12;
  if (artifact.kind === "skill") score += 6;
  if (artifact.registry_status === "recommended") score += 10;
  if (artifact.registry_status === "deprecated") score -= 100;
  if (artifact.registry_status === "use-with-care") score -= 20;
  if (artifact.registry_status === "internal-only") score -= 8;

  return score;
}

function ArtifactResult({
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
    <div className="card" style={{ padding: 16 }}>
      <div className="row wrap" style={{ marginBottom: 8 }}>
        <span className={`chip kind-${artifact.kind}`}>{kindLabel[artifact.kind]}</span>
        <StatusChip status={artifact.registry_status} />
        <span className="tag">{artifact.registry_owner}</span>
        <span className="spacer" />
        <button className="secondary-btn" onClick={() => onSelect(artifact)}>
          Inspect
        </button>
      </div>
      <h3 style={{ margin: "0 0 4px" }}>{artifact.name}</h3>
      <p style={{ margin: "0 0 10px", color: "var(--gray-700)", fontSize: 13 }}>
        {artifact.functional_summary || artifact.description || statusDescription[artifact.registry_status]}
      </p>
      {artifact.recommended_for.length > 0 && (
        <div style={{ color: "var(--fg-muted)", fontSize: 12, marginBottom: 8 }}>
          {artifact.recommended_for[0]}
        </div>
      )}
      {replacements.length > 0 && (
        <div style={{ fontSize: 12, color: "var(--danger)", marginBottom: 8 }}>
          Use instead:{" "}
          {replacements.map((r) => (
            <button
              key={r.id}
              className="link-btn"
              onClick={() => onSelect(r)}
            >
              {r.name}
            </button>
          ))}
        </div>
      )}
      {artifact.target_repos.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {artifact.target_repos.slice(0, 8).map((repo) => (
            <RepoChip key={repo} repo={repo} size="sm" />
          ))}
        </div>
      )}
    </div>
  );
}

export default function FinderPage() {
  const [query, setQuery] = useState("");
  const [taskId, setTaskId] = useState(TASKS[0].id);
  const [selected, setSelected] = useState<Artifact | null>(null);

  const task = TASKS.find((t) => t.id === taskId) ?? null;
  const results = useMemo(() => {
    return manifest.artifacts
      .filter((a) => a.kind !== "bundle")
      .map((artifact) => ({ artifact, score: scoreArtifact(artifact, query, task) }))
      .filter((r) => r.score > 0)
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return statusRank[b.artifact.registry_status] - statusRank[a.artifact.registry_status];
      })
      .slice(0, 12)
      .map((r) => r.artifact);
  }, [query, task]);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Find what to use</h1>
        <p className="page-subtitle">
          Start from the job, not the file name. Recommended commands appear first;
          direct agent use is flagged when it is normally an implementation detail.
        </p>
      </div>

      <div className="toolbar">
        <input
          type="search"
          placeholder="Search task, repo, policy area, or artifact name"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Link className="secondary-btn" to="/cleanup">
          Review do-not-use list
        </Link>
      </div>

      <div className="finder-layout">
        <div className="finder-tasks">
          {TASKS.map((candidate) => (
            <button
              key={candidate.id}
              className={`task-card ${candidate.id === taskId ? "active" : ""}`}
              onClick={() => setTaskId(candidate.id)}
            >
              <strong>{candidate.label}</strong>
              <span>{candidate.prompt}</span>
            </button>
          ))}
        </div>

        <div>
          {task && (
            <div className="card" style={{ marginBottom: 12 }}>
              <div className="stat-label">Selected use case</div>
              <h2 style={{ margin: "4px 0", fontSize: 18 }}>{task.label}</h2>
              <p style={{ margin: 0, color: "var(--gray-600)", fontSize: 13 }}>
                {task.prompt}
              </p>
            </div>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {results.map((artifact) => (
              <ArtifactResult
                key={`${artifact.kind}:${artifact.id}`}
                artifact={artifact}
                onSelect={setSelected}
              />
            ))}
            {results.length === 0 && (
              <div className="empty">
                No matching artifacts. Try a repo name like policyengine-us or a broader task.
              </div>
            )}
          </div>
        </div>
      </div>

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
