import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { manifest, getArtifact, kindLabel } from "../data";
import type { Artifact, ArtifactKind } from "../types";
import { ArtifactDrawer } from "../components/Drawer";
import { RepoChip } from "../components/RepoChip";

// Commands with a Guide tab entry. Add ids here as guides are written.
const COMMANDS_WITH_GUIDES = new Set(["analyze-policy"]);

// ---------------------------------------------------------------------------
// Topic areas — what work this ecosystem actually does. Each area lists the
// functional roles of the commands that belong to it. Commands map 1:1 to a
// topic area; some areas also include "knowledge" skills used for manual work
// without a dedicated command.
// ---------------------------------------------------------------------------

interface TopicArea {
  id: string;
  title: string;
  blurb: string;
  icon: string;
  accent: string;
  commandRoles: string[];
  // skill roles to surface as "reference knowledge" the user might invoke manually
  knowledgeRoles?: string[];
}

const TOPIC_AREAS: TopicArea[] = [
  {
    id: "implement",
    title: "Implement programs & reforms",
    blurb:
      "Build government benefit programs, contributed policy reforms, and backdated historical parameter values in the country models.",
    icon: "⚙",
    accent: "#319795",
    commandRoles: [
      "workflow:encode-policy",
      "workflow:encode-reform",
      "workflow:backdate-program",
    ],
    knowledgeRoles: [
      "pattern:variables",
      "pattern:parameters",
      "pattern:reforms",
      "pattern:vectorization",
    ],
  },
  {
    id: "review",
    title: "Review & fix PRs",
    blurb:
      "Multi-validator PR reviews (code patterns, references, regulations, tests) and the fix loop that responds to review findings or CI failures.",
    icon: "✓",
    accent: "#026AA2",
    commandRoles: [
      "workflow:review-program",
      "workflow:review-pr-program",
      "workflow:fix-pr",
    ],
    knowledgeRoles: ["pattern:review", "review:standards"],
  },
  {
    id: "audit",
    title: "Audit quality",
    blurb:
      "Read-only audits of specific surfaces — state tax PDFs vs. parameter values, multi-zone Next.js config, SEO health.",
    icon: "⚖",
    accent: "#c2410c",
    commandRoles: [
      "workflow:audit-state-tax",
      "workflow:audit-multizone",
      "workflow:audit-seo",
    ],
    knowledgeRoles: ["seo"],
  },
  {
    id: "build-frontend",
    title: "Build interactive tools & dashboards",
    blurb:
      "Scaffold new standalone calculators, multi-page dashboards, and ui-kit components — including planning, building, validating, and deploying them.",
    icon: "▦",
    accent: "#5b6cff",
    commandRoles: [
      "workflow:new-tool",
      "workflow:create-dashboard",
      "workflow:create-new-component",
      "workflow:deploy-dashboard",
      "workflow:dashboard-overview",
    ],
    knowledgeRoles: [
      "frontend:scaffold-tool",
      "frontend:scaffold-dashboard",
      "frontend:ui-kit",
      "frontend:styling:tailwind",
      "frontend:deployment:vercel",
      "frontend:deployment:modal",
    ],
  },
  {
    id: "content",
    title: "Generate content & marketing",
    blurb:
      "Turn blog posts and announcements into branded social images and platform-optimized post copy, localized for UK and US audiences.",
    icon: "✎",
    accent: "#285E61",
    commandRoles: ["workflow:content-generation"],
    knowledgeRoles: ["workflow:content-generation", "domain:writing-style"],
  },
  {
    id: "pr-mechanics",
    title: "PR mechanics & test authoring",
    blurb:
      "The mechanical pieces that wrap around every PR — opening a draft, polling CI, marking ready, and authoring frontend/SDK tests.",
    icon: "↗",
    accent: "#6b7280",
    commandRoles: ["workflow:create-pr", "workflow:write-tests-frontend"],
    knowledgeRoles: ["pattern:testing:frontend"],
  },
  {
    id: "utilities",
    title: "Utilities",
    blurb: "Small helpers that don't belong to a larger workflow.",
    icon: "•",
    accent: "#475569",
    commandRoles: ["workflow:fetch-pdf", "config:claude-settings"],
  },
];

// ---------------------------------------------------------------------------
// Workflow strip — renders a command and the chain of agents/skills it calls.
// ---------------------------------------------------------------------------

function classifyCommand(cmd: Artifact): "manual" | "knowledge-only" | "agentic" {
  const agentCount = cmd.references.agent?.length ?? 0;
  const skillCount = cmd.references.skill?.length ?? 0;
  if (agentCount >= 1) return "agentic";
  if (skillCount >= 1) return "knowledge-only";
  return "manual";
}

function workflowTypeMeta(type: ReturnType<typeof classifyCommand>) {
  if (type === "agentic")
    return { label: "Multi-agent", dot: "var(--kind-agent)" };
  if (type === "knowledge-only")
    return { label: "Knowledge-driven", dot: "var(--kind-skill)" };
  return { label: "Manual", dot: "var(--gray-400)" };
}

function WorkflowStrip({
  command,
  onSelect,
}: {
  command: Artifact;
  onSelect: (a: Artifact) => void;
}) {
  const type = classifyCommand(command);
  const typeMeta = workflowTypeMeta(type);
  const agentRefs = command.references.agent ?? [];
  const skillRefs = command.references.skill ?? [];

  return (
    <div
      className="card"
      style={{ padding: 18, borderColor: "var(--border)" }}
    >
      <div className="row" style={{ marginBottom: 10, gap: 10 }}>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 14,
            fontWeight: 600,
            color: "var(--gray-900)",
          }}
        >
          /{command.id}
        </span>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 11,
            fontWeight: 500,
            color: "var(--gray-600)",
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: typeMeta.dot,
              display: "inline-block",
            }}
          />
          {typeMeta.label}
        </span>
        {command.target_repos.slice(0, 2).map((r) => (
          <RepoChip key={r} repo={r} size="sm" />
        ))}
        <span className="spacer" />
        {COMMANDS_WITH_GUIDES.has(command.id) && (
          <Link
            to="/guides"
            style={{
              fontSize: 11,
              fontWeight: 600,
              color: "var(--accent-700, #285E61)",
              textDecoration: "none",
              padding: "3px 8px",
              border: "1px solid var(--accent-700, #285E61)",
              borderRadius: 4,
              fontFamily: "var(--font-mono)",
            }}
          >
            Open guide →
          </Link>
        )}
        <span
          style={{ fontSize: 11, color: "var(--fg-muted)", fontFamily: "var(--font-mono)" }}
        >
          {agentRefs.length} agents · {skillRefs.length} skills
        </span>
      </div>

      <p
        style={{
          margin: "0 0 14px",
          fontSize: 13,
          color: "var(--gray-700)",
          lineHeight: 1.5,
        }}
      >
        {command.functional_summary ?? command.description}
      </p>

      {agentRefs.length > 0 && (
        <div style={{ marginBottom: skillRefs.length > 0 ? 12 : 0 }}>
          <div
            style={{
              fontSize: 10,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--gray-500)",
              marginBottom: 6,
            }}
          >
            Agent chain
          </div>
          <div className="flow-chain">
            <span
              className="flow-node flow-node-command"
              onClick={() => onSelect(command)}
              style={{ cursor: "pointer" }}
            >
              /{command.id}
            </span>
            {agentRefs.map((agentId, i) => {
              const agent = getArtifact("agent", agentId);
              if (!agent) return null;
              return (
                <span key={agentId} style={{ display: "contents" }}>
                  <span className="flow-arrow">→</span>
                  <span
                    className="flow-node flow-node-agent"
                    onClick={() => onSelect(agent)}
                    style={{ cursor: "pointer" }}
                    title={agent.functional_summary ?? ""}
                  >
                    {agent.name}
                  </span>
                </span>
              );
            })}
          </div>
        </div>
      )}

      {skillRefs.length > 0 && (
        <div>
          <div
            style={{
              fontSize: 10,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
              color: "var(--gray-500)",
              marginBottom: 6,
            }}
          >
            Reference skills loaded
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {skillRefs.map((skillId) => {
              const skill = getArtifact("skill", skillId);
              if (!skill) return null;
              return (
                <span
                  key={skillId}
                  className="chip kind-skill"
                  onClick={() => onSelect(skill)}
                  title={skill.functional_summary ?? ""}
                  style={{ fontSize: 11 }}
                >
                  {skill.name}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {agentRefs.length === 0 && skillRefs.length === 0 && (
        <div
          style={{
            fontSize: 12,
            color: "var(--gray-500)",
            fontStyle: "italic",
          }}
        >
          Standalone command — no orchestration, runs inline.
        </div>
      )}
    </div>
  );
}

function KpiCell({ label, value }: { label: string; value: number }) {
  return (
    <div className="kpi-cell">
      <div className="kpi-value">{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}

function KnowledgeSkills({
  roles,
  onSelect,
}: {
  roles: string[];
  onSelect: (a: Artifact) => void;
}) {
  const skills = manifest.artifacts.filter(
    (a) =>
      a.kind === "skill" &&
      a.functional_role &&
      roles.includes(a.functional_role),
  );
  if (skills.length === 0) return null;
  return (
    <div
      style={{
        marginTop: 16,
        paddingTop: 16,
        borderTop: "1px dashed var(--border)",
      }}
    >
      <div
        style={{
          fontSize: 10,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--gray-500)",
          marginBottom: 8,
        }}
      >
        Reference skills you can also load manually
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {skills.map((s) => (
          <span
            key={s.id}
            className="chip kind-skill"
            onClick={() => onSelect(s)}
            title={s.functional_summary ?? ""}
            style={{ fontSize: 11 }}
          >
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function WorkflowsPage() {
  const [activeTopicId, setActiveTopicId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Artifact | null>(null);

  const topicWorkflows = useMemo(() => {
    const map = new Map<string, Artifact[]>();
    for (const t of TOPIC_AREAS) map.set(t.id, []);
    const unassigned: Artifact[] = [];

    const commands = manifest.artifacts.filter((a) => a.kind === "command");
    for (const cmd of commands) {
      const topic = TOPIC_AREAS.find((t) =>
        cmd.functional_role
          ? t.commandRoles.includes(cmd.functional_role)
          : false,
      );
      if (topic) {
        map.get(topic.id)!.push(cmd);
      } else {
        unassigned.push(cmd);
      }
    }
    return { byTopic: map, unassigned };
  }, []);

  const totalCommands = manifest.artifacts.filter((a) => a.kind === "command").length;

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Workflows</h1>
        <p className="page-subtitle">
          What the ecosystem can do, organized by topic. Each card shows the
          command, its agent chain, and the reference skills it pulls in. Click
          <strong> Open guide</strong> on any command that has a writeup.
        </p>
      </div>

      <div className="kpi-strip">
        <KpiCell label="Skills" value={manifest.counts.skill} />
        <KpiCell label="Agents" value={manifest.counts.agent} />
        <KpiCell label="Commands" value={manifest.counts.command} />
        <KpiCell label="Bundles" value={manifest.counts.bundle} />
        <div className="kpi-meta">
          Last refreshed{" "}
          {new Date(manifest.generated_at).toLocaleDateString()}
        </div>
      </div>

      <div className="toolbar" style={{ marginBottom: 20 }}>
        <span
          className={`chip ${activeTopicId === null ? "active" : ""}`}
          onClick={() => setActiveTopicId(null)}
        >
          All ({totalCommands} workflows)
        </span>
        {TOPIC_AREAS.map((t) => {
          const count = topicWorkflows.byTopic.get(t.id)?.length ?? 0;
          if (count === 0) return null;
          return (
            <span
              key={t.id}
              className={`chip ${activeTopicId === t.id ? "active" : ""}`}
              onClick={() => setActiveTopicId(t.id)}
            >
              {t.icon} {t.title} · {count}
            </span>
          );
        })}
      </div>

      {TOPIC_AREAS.filter((t) => activeTopicId === null || t.id === activeTopicId).map((topic) => {
        const cmds = topicWorkflows.byTopic.get(topic.id) ?? [];
        if (cmds.length === 0) return null;
        return (
          <section
            key={topic.id}
            style={{
              marginBottom: 36,
              paddingTop: 4,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 14,
                marginBottom: 14,
                paddingBottom: 10,
                borderBottom: "1px solid var(--border)",
              }}
            >
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 8,
                  background: "var(--muted)",
                  color: "var(--gray-600)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 17,
                  fontWeight: 500,
                  flexShrink: 0,
                  border: "1px solid var(--border)",
                }}
              >
                {topic.icon}
              </div>
              <div style={{ flex: 1 }}>
                <h2
                  style={{
                    margin: 0,
                    fontSize: 19,
                    fontWeight: 600,
                    color: "var(--gray-900)",
                    letterSpacing: "-0.015em",
                  }}
                >
                  {topic.title}
                </h2>
                <p
                  style={{
                    margin: "3px 0 0",
                    color: "var(--gray-600)",
                    fontSize: 13.5,
                    maxWidth: 720,
                    lineHeight: 1.5,
                  }}
                >
                  {topic.blurb}
                </p>
              </div>
              <span
                style={{
                  fontSize: 12,
                  color: "var(--gray-500)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                {cmds.length} workflow{cmds.length === 1 ? "" : "s"}
              </span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {cmds.map((cmd) => (
                <WorkflowStrip
                  key={cmd.id}
                  command={cmd}
                  onSelect={(a) => setSelected(a)}
                />
              ))}
            </div>

            {topic.knowledgeRoles && (
              <KnowledgeSkills
                roles={topic.knowledgeRoles}
                onSelect={(a) => setSelected(a)}
              />
            )}
          </section>
        );
      })}

      {activeTopicId === null && topicWorkflows.unassigned.length > 0 && (
        <section style={{ marginBottom: 36 }}>
          <h2
            style={{
              fontSize: 17,
              fontWeight: 600,
              color: "var(--gray-700)",
              borderBottom: "2px solid var(--border)",
              paddingBottom: 8,
              marginBottom: 12,
            }}
          >
            Unassigned commands
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {topicWorkflows.unassigned.map((cmd) => (
              <WorkflowStrip
                key={cmd.id}
                command={cmd}
                onSelect={(a) => setSelected(a)}
              />
            ))}
          </div>
        </section>
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
