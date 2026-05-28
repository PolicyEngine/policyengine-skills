import { Link } from "react-router-dom";
import { manifest } from "../data";
import { RepoChip } from "../components/RepoChip";

function pct(a: number, b: number) {
  if (b === 0) return "0%";
  return `${Math.round((a / b) * 100)}%`;
}

export default function OverviewPage() {
  const skills = manifest.artifacts.filter((a) => a.kind === "skill");
  const agents = manifest.artifacts.filter((a) => a.kind === "agent");
  const commands = manifest.artifacts.filter((a) => a.kind === "command");
  const bundles = manifest.artifacts.filter((a) => a.kind === "bundle");

  const highOverlap = manifest.overlaps.filter((o) => o.score >= 0.4).length;
  const totalGaps = Object.values(manifest.gaps).reduce(
    (sum, arr) => sum + arr.length,
    0,
  );
  const skillsInBundles = skills.filter((s) => s.bundles.length > 0).length;
  const agentsInBundles = agents.filter((s) => s.bundles.length > 0).length;
  const avgBundlesPerSkill =
    skills.reduce((s, a) => s + a.bundles.length, 0) / Math.max(skills.length, 1);

  const repoCounts = new Map<string, { skill: number; agent: number; command: number }>();
  for (const a of manifest.artifacts) {
    if (a.kind === "bundle") continue;
    for (const r of a.target_repos) {
      const cur = repoCounts.get(r) ?? { skill: 0, agent: 0, command: 0 };
      cur[a.kind as "skill" | "agent" | "command"] += 1;
      repoCounts.set(r, cur);
    }
  }
  const reposByCount = Array.from(repoCounts.entries()).sort(
    ([, a], [, b]) => b.skill + b.agent + b.command - (a.skill + a.agent + a.command),
  );

  const topReferencedSkills = [...skills]
    .map((s) => ({
      ...s,
      incoming: manifest.edges.filter(
        (e) => e.target_kind === "skill" && e.target === s.id,
      ).length,
    }))
    .sort((a, b) => b.incoming - a.incoming)
    .slice(0, 5);

  const topReferencedAgents = [...agents]
    .map((a) => ({
      ...a,
      incoming: manifest.edges.filter(
        (e) => e.target_kind === "agent" && e.target === a.id,
      ).length,
    }))
    .sort((a, b) => b.incoming - a.incoming)
    .slice(0, 5);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Ecosystem overview</h1>
        <p className="page-subtitle">
          A map of every skill, agent, command, and bundle in the policyengine-skills repo —
          surfacing duplication, gaps, and how things compose.
        </p>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Skills</div>
          <div className="stat-value">{skills.length}</div>
          <div className="stat-meta">{skillsInBundles} in a bundle</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Agents</div>
          <div className="stat-value">{agents.length}</div>
          <div className="stat-meta">{agentsInBundles} in a bundle</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Commands</div>
          <div className="stat-value">{commands.length}</div>
          <div className="stat-meta">orchestrate flows</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Bundles</div>
          <div className="stat-value">{bundles.length}</div>
          <div className="stat-meta">avg {avgBundlesPerSkill.toFixed(1)}/skill</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Likely duplicates</div>
          <div className="stat-value">{highOverlap}</div>
          <div className="stat-meta">≥40% similarity</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Coverage gaps</div>
          <div className="stat-value">{totalGaps}</div>
          <div className="stat-meta">across {Object.keys(manifest.gaps).length} categories</div>
        </div>
        <div
          className="stat-card"
          style={{
            borderLeftWidth: 3,
            borderLeftStyle: "solid",
            borderLeftColor: "var(--warning)",
          }}
        >
          <div className="stat-label">Uncovered repos</div>
          <div className="stat-value">
            {manifest.repo_coverage?.filter((r) => r.tooling_relevant && r.total === 0)
              .length ?? 0}
          </div>
          <div className="stat-meta">
            tooling-relevant; of {manifest.known_repos?.length ?? 0} org repos
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Most-referenced skills</h3>
          <p style={{ color: "var(--fg-muted)", fontSize: 13, margin: "0 0 12px" }}>
            Skills that other commands and agents lean on the most. These are the load-bearing
            knowledge files in the ecosystem.
          </p>
          {topReferencedSkills.map((s) => (
            <div
              key={s.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "6px 0",
                borderBottom: "1px solid var(--border)",
              }}
            >
              <div>
                <span className="kind-dot kind-skill" />
                <strong>{s.id}</strong>
                <div style={{ fontSize: 12, color: "var(--fg-muted)", marginLeft: 14 }}>
                  {s.category}
                </div>
              </div>
              <div style={{ fontFamily: "var(--font-mono)" }}>{s.incoming}</div>
            </div>
          ))}
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>Most-referenced agents</h3>
          <p style={{ color: "var(--fg-muted)", fontSize: 13, margin: "0 0 12px" }}>
            Agents invoked by the most commands and other agents.
          </p>
          {topReferencedAgents.map((s) => (
            <div
              key={s.id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                padding: "6px 0",
                borderBottom: "1px solid var(--border)",
              }}
            >
              <div>
                <span className="kind-dot kind-agent" />
                <strong>{s.id}</strong>
                <div style={{ fontSize: 12, color: "var(--fg-muted)", marginLeft: 14 }}>
                  {s.category}
                </div>
              </div>
              <div style={{ fontFamily: "var(--font-mono)" }}>{s.incoming}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Coverage by target repo</h3>
        <p style={{ color: "var(--fg-muted)", fontSize: 13, margin: "0 0 12px" }}>
          Where the artifacts in this repo actually get used. Inferred from artifact names,
          descriptions, and body text. Each artifact can target multiple repos.
        </p>
        <table className="data">
          <thead>
            <tr>
              <th>Repo</th>
              <th style={{ textAlign: "right" }}>Skills</th>
              <th style={{ textAlign: "right" }}>Agents</th>
              <th style={{ textAlign: "right" }}>Commands</th>
              <th style={{ textAlign: "right" }}>Total</th>
            </tr>
          </thead>
          <tbody>
            {reposByCount.map(([repo, counts]) => (
              <tr key={repo}>
                <td>
                  <Link to={`/catalog?repo=${repo}`}>
                    <RepoChip repo={repo} />
                  </Link>
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                  {counts.skill}
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                  {counts.agent}
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                  {counts.command}
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                  {counts.skill + counts.agent + counts.command}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Bundle composition</h3>
        <p style={{ color: "var(--fg-muted)", fontSize: 13, margin: "0 0 12px" }}>
          What each bundle ships. Hint: the "complete" bundle is a superset; look at the smaller
          ones to understand intent.
        </p>
        <table className="data">
          <thead>
            <tr>
              <th>Bundle</th>
              <th style={{ textAlign: "right" }}>Skills</th>
              <th style={{ textAlign: "right" }}>Agents</th>
              <th style={{ textAlign: "right" }}>Commands</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {manifest.bundles_raw.map((b) => (
              <tr key={b.name}>
                <td>
                  <strong>{b.name}</strong>
                  <div style={{ fontSize: 11, color: "var(--fg-muted)" }}>{b.category}</div>
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                  {b.skills?.length ?? 0}
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                  {b.agents?.length ?? 0}
                </td>
                <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                  {b.commands?.length ?? 0}
                </td>
                <td>
                  <div className="truncate-2">{b.description}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 24, fontSize: 12, color: "var(--fg-muted)" }}>
        <Link to="/catalog">Browse the catalog →</Link> &nbsp; · &nbsp;{" "}
        <Link to="/duplicates">Inspect duplicates →</Link> &nbsp; · &nbsp;{" "}
        <Link to="/workflows">Workflow graph →</Link> &nbsp; · &nbsp;{" "}
        <Link to="/gaps">Coverage gaps →</Link>
      </div>
    </div>
  );
}
